import logging
import os
from typing import List, Dict

from .sql_analyzer import SQLOperationType, SQLRiskLevel

logger = logging.getLogger(__name__)

class SecurityException(Exception):
    """Exceção relacionada à segurança"""
    pass

class SQLInterceptor:
    """Interceptador de operações SQL"""
    
    def __init__(self, analyzer: SQLOperationType):
        self.analyzer = analyzer
        # Define o limite máximo de comprimento da SQL (padrão 1000 caracteres)
        self.max_sql_length = 1000

    async def check_operation(self, sql_query: str) -> bool:
        """
        Verifica se a operação SQL é permitida
        
        Args:
            sql_query: Consulta SQL
            
        Returns:
            bool: Se é permitido executar
            
        Raises:
            SecurityException: Quando a operação é rejeitada
        """
        try:
            # Verifica se a SQL está vazia
            if not sql_query or not sql_query.strip():
                raise SecurityException("SQL não pode estar vazia")
                
            # Verifica o comprimento da SQL
            if len(sql_query) > self.max_sql_length:
                raise SecurityException(f"Comprimento da SQL ({len(sql_query)}) excede o limite ({self.max_sql_length})")
                
            # Verifica se a SQL é válida
            sql_parts = sql_query.strip().split()
            if not sql_parts:
                raise SecurityException("Formato da SQL inválido")
                
            operation = sql_parts[0].upper()
            # Atualiza a lista de operações suportadas, incluindo operações de metadados
            supported_operations = {
                'SELECT', 'INSERT', 'UPDATE', 'DELETE', 
                'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'MERGE',
                'SHOW', 'DESC', 'DESCRIBE', 'EXPLAIN', 'HELP', 
                'ANALYZE', 'CHECK', 'CHECKSUM', 'OPTIMIZE'
            }
                
            if operation not in supported_operations:
                raise SecurityException(f"Operação SQL não suportada: {operation}")
            
            # Analisa o risco da SQL
            risk_analysis = self.analyzer.analyze_risk(sql_query)
            
            # Verifica se é uma operação perigosa
            if risk_analysis['is_dangerous']:
                raise SecurityException(
                    f"Operação perigosa detectada: {risk_analysis['operation']}"
                )
            
            # Verifica se a operação é permitida
            if not risk_analysis['is_allowed']:
                raise SecurityException(
                    f"Nível de risco da operação atual ({risk_analysis['risk_level'].name}) não é permitido,"
                    f"níveis de risco permitidos: {[level.name for level in self.analyzer.allowed_risk_levels]}"
                )
            
            # Determina o tipo de operação (DDL, DML ou Metadados)
            operation_category = "Operação de metadados" if operation in self.analyzer.metadata_operations else (
                "Operação DDL" if operation in self.analyzer.ddl_operations else "Operação DML"
            )
            
            # Registra log detalhado
            logger.info(
                f"SQL{operation_category} verificado com sucesso - "
                f"Operação: {risk_analysis['operation']}, "
                f"Nível de risco: {risk_analysis['risk_level'].name}, "
                f"Tabelas afetadas: {', '.join(risk_analysis['affected_tables'])}"
            )

            return True

        except SecurityException as e:
            logger.error(str(e))
            raise
        except Exception as e:
            error_msg = f"Falha na verificação de segurança: {str(e)}"
            logger.error(error_msg)
            raise SecurityException(error_msg)