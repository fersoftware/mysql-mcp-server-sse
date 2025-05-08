import re
import os
from enum import IntEnum, Enum
import logging
from typing import Set, List

logger = logging.getLogger(__name__)

class SQLRiskLevel(IntEnum):
    """Níveis de risco de operações SQL"""
    BAIXO = 1      # Consultas SELECT
    MÉDIO = 2      # Inserções e atualizações com cláusula WHERE
    ALTO = 3       # Alterações estruturais (CREATE/ALTER) e operações sem WHERE
    CRÍTICO = 4    # Operações perigosas (DROP/TRUNCATE)

class TipoAmbiente(Enum):
    """
    Tipos de ambiente disponíveis
    """
    DESENVOLVIMENTO = "desenvolvimento"
    PRODUCAO = "producao"

    @classmethod
    def from_string(cls, value: str) -> 'TipoAmbiente':
        """
        Converte uma string em um tipo de ambiente
        
        Args:
            value: Nome do ambiente
            
        Returns:
            TipoAmbiente: Tipo de ambiente correspondente
        """
        try:
            return cls(value.lower())
        except ValueError:
            return cls.DESENVOLVIMENTO  # Padrão é ambiente de desenvolvimento

class SQLOperationType:
    """Analisador de tipos de operações SQL"""
    
    def __init__(self):
        # Configura o tipo de ambiente
        env_type_str = os.getenv('TIPO_AMBIENTE', 'desenvolvimento').lower()
        self.env_type = TipoAmbiente.from_string(env_type_str)
        
        # Define as operações DDL (Linguagem de Definição de Dados)
        self.ddl_operations = {
            'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'RENAME'  # Operações estruturais
        }
        
        # Define as operações DML (Linguagem de Manipulação de Dados)
        self.dml_operations = {
            'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'MERGE'  # Operações de dados
        }
        
        # Define as operações de metadados
        self.metadata_operations = {
            'SHOW', 'DESC', 'DESCRIBE', 'EXPLAIN', 'HELP', 
            'ANALYZE', 'CHECK', 'CHECKSUM', 'OPTIMIZE'  # Operações de consulta de metadados
        }
        
        # Configuração de níveis de risco
        self.allowed_risk_levels = self._parsear_niveis_risco()
        self.blocked_patterns = self._parsear_padroes_bloqueados('PADROES_BLOQUEADOS')
        
        # Tratamento especial para ambiente de produção: se não houver configuração explícita de níveis de risco, permite apenas operações de risco BAIXO
        if self.env_type == TipoAmbiente.PRODUCAO and not os.getenv('NIVEIS_RISCO_PERMITIDOS'):
            self.allowed_risk_levels = {SQLRiskLevel.BAIXO}
        
        logger.info(f"Analisador de SQL inicializado - Ambiente: {self.env_type.value}")
        logger.info(f"Níveis de risco permitidos: {[level.name for level in self.allowed_risk_levels]}")

    def _parsear_niveis_risco(self) -> Set[SQLRiskLevel]:
        """
        Parseia os níveis de risco permitidos das variáveis de ambiente
        
        Returns:
            Set[SQLRiskLevel]: Conjunto de níveis de risco permitidos
        """
        allowed_levels_str = os.getenv('NIVEIS_RISCO_PERMITIDOS', 'BAIXO,MÉDIO')
        allowed_levels = set()
        
        logger.info(f"Níveis de risco lidos das variáveis de ambiente: '{allowed_levels_str}'")
        
        for level_str in allowed_levels_str.upper().split(','):  
            level_str = level_str.strip()
            try:
                allowed_levels.add(SQLRiskLevel[level_str])
            except KeyError:
                logger.warning(f"Nível de risco inválido: {level_str}")
                
        return allowed_levels

    def _parsear_padroes_bloqueados(self, env_var: str) -> List[str]:
        """
        Parseia os padrões de operação bloqueados das variáveis de ambiente
        
        Args:
            env_var: Nome da variável de ambiente contendo os padrões
            
        Returns:
            List[str]: Lista de padrões bloqueados
        """
        patterns = os.getenv(env_var, '').split(',')
        return [p.strip() for p in patterns if p.strip()]

    def analisar_risco(self, sql_query: str) -> dict:
        """
        Analisa o nível de risco e o escopo de impacto da consulta SQL
        
        Args:
            sql_query: Consulta SQL
            
        Returns:
            dict: Dicionário com os resultados da análise de risco
        """
        sql_query = sql_query.strip()
        
        # Trata SQL vazio
        if not sql_query:
            return {
                'operation': '',
                'operation_type': 'DESCONHECIDO',
                'is_dangerous': True,
                'affected_tables': [],
                'estimated_impact': {
                    'operation': '',
                    'estimated_rows': 0,
                    'needs_where': False,
                    'has_where': False
                },
                'risk_level': SQLRiskLevel.ALTO,
                'is_allowed': False
            }
            
        operation = sql_query.split()[0].upper()
        
        # Análise básica de risco
        risk_analysis = {
            'operation': operation,
            'operation_type': 'DDL' if operation in self.ddl_operations else 'DML',
            'is_dangerous': self._verificar_padroes_perigosos(sql_query),
            'affected_tables': self._detectar_tabelas(sql_query),
            'estimated_impact': self._estimar_impacto(sql_query)
        }
        
        # Calcula o nível de risco
        risk_level = self._calcular_nivel_risco(sql_query, operation, risk_analysis['is_dangerous'])
        risk_analysis['risk_level'] = risk_level
        risk_analysis['is_allowed'] = risk_level in self.allowed_risk_levels
        
        return risk_analysis

    def _calcular_nivel_risco(self, sql_query: str, operation: str, is_dangerous: bool) -> SQLRiskLevel:
        """
        Calcula o nível de risco de uma operação SQL
        
        Regras de cálculo:
        1. Operação perigosa (corresponde a padrão bloqueado) => CRÍTICO
        2. Operações DDL:
           - CREATE/ALTER => ALTO
           - DROP/TRUNCATE => CRÍTICO
        3. Operações DML:
           - SELECT => BAIXO
           - INSERT => MÉDIO
           - UPDATE/DELETE com WHERE => MÉDIO
           - UPDATE sem WHERE => ALTO
           - DELETE sem WHERE => CRÍTICO
        4. Operações de metadados:
           - SHOW/DESC/DESCRIBE etc => BAIXO
        """
        # Operação perigosa
        if is_dangerous:
            return SQLRiskLevel.CRÍTICO
            
        # Operações de metadados
        if operation in self.metadata_operations:
            return SQLRiskLevel.BAIXO  # Consultas de metadados são consideradas de baixo risco
            
        # Operações não SELECT em produção
        if self.env_type == TipoAmbiente.PRODUCAO and operation != 'SELECT':
            return SQLRiskLevel.CRÍTICO
            
        # Operações DDL
        if operation in self.ddl_operations:
            if operation in {'DROP', 'TRUNCATE'}:
                return SQLRiskLevel.CRÍTICO
            return SQLRiskLevel.ALTO
            
        # Operações DML
        if operation == 'SELECT':
            return SQLRiskLevel.BAIXO
        elif operation == 'INSERT':
            return SQLRiskLevel.MÉDIO
        elif operation == 'UPDATE':
            return SQLRiskLevel.ALTO if 'WHERE' not in sql_query.upper() else SQLRiskLevel.MÉDIO
        elif operation == 'DELETE':
            # Operação DELETE sem WHERE é considerada de risco CRÍTICO
            return SQLRiskLevel.CRÍTICO if 'WHERE' not in sql_query.upper() else SQLRiskLevel.MÉDIO
            
        return SQLRiskLevel.ALTO

    def _verificar_padroes_perigosos(self, sql_query: str) -> bool:
        """
        Verifica se a consulta SQL corresponde a padrões de operação perigosos
        
        Args:
            sql_query: Consulta SQL a ser analisada
            
        Returns:
            bool: True se a consulta for considerada perigosa, False caso contrário
        """
        sql_upper = sql_query.upper()
        
        # Verificações de segurança adicionais em ambiente de produção
        if self.env_type == TipoAmbiente.PRODUCAO:
            # Em produção, todas as operações não SELECT são proibidas
            operacao = sql_upper.split()[0]
            if operacao != 'SELECT':
                logger.warning(f"Operação {operacao} não permitida em produção")
                return True
        
        for pattern in self.blocked_patterns:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                logger.warning(f"SQL contém padrão bloqueado: {pattern}")
                return True
                
        return False

    def _detectar_tabelas(self, sql_query: str) -> List[str]:
        """
        Detecta as tabelas envolvidas em uma consulta SQL
        
        Args:
            sql_query: Consulta SQL a ser analisada
            
        Returns:
            List[str]: Lista de nomes das tabelas encontradas
        """
        palavras = sql_query.split()
        tabelas = []
        
        for i, palavra in enumerate(palavras):
            # Verifica palavras-chave que indicam tabelas
            if palavra in {'FROM', 'JOIN', 'UPDATE', 'INTO', 'TABLE'}:
                if i + 1 < len(palavras):
                    tabela = palavras[i + 1].strip('`;')
                    # Ignora palavras-chave comuns
                    if tabela not in {'SELECT', 'WHERE', 'SET'}:
                        tabelas.append(tabela)
        
        return list(set(tabelas))

    def _estimar_impacto(self, sql_query: str) -> dict:
        """
        Estima o impacto potencial de uma consulta SQL
        
        Args:
            sql_query: Consulta SQL a ser analisada
            
        Returns:
            dict: Dicionário com as estimativas de impacto da consulta
        """
        operacao = sql_query.split()[0].upper()
        
        impacto = {
            'operation': operacao,
            'estimated_rows': 0,
            'needs_where': operacao in {'UPDATE', 'DELETE'},  # Operações que precisam de WHERE
            'has_where': 'WHERE' in sql_query.upper()  # Verifica se há cláusula WHERE
        }
        
        # Ajusta as estimativas com base no tipo de ambiente
        if self.env_type == TipoAmbiente.PRODUCAO:
            if operacao == 'SELECT':
                impacto['estimated_rows'] = 100
            else:
                impacto['estimated_rows'] = float('inf')  # Operações não SELECT em produção são consideradas com impacto infinito
                logger.warning(f"Operação {operacao} sem WHERE pode afetar muitas linhas")
        else:
            if operacao == 'SELECT':
                impacto['estimated_rows'] = 100
            elif operacao in {'UPDATE', 'DELETE'}:
                impacto['estimated_rows'] = 1000 if impacto['has_where'] else float('inf')
                if impacto['estimated_rows'] == float('inf'):
                    logger.warning(f"Operação {operacao} sem WHERE pode afetar muitas linhas")
        
        return impacto