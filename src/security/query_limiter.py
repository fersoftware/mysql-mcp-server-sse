import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

class QueryLimiter:
    """Verificador de segurança de consultas"""
    
    def __init__(self):
        # Analisa o estado de habilitação (padrão habilitado)
        enable_check = os.getenv('ENABLE_QUERY_CHECK', 'true')
        self.enable_check = str(enable_check).lower() not in {'false', '0', 'no', 'off'}

    def check_query(self, sql_query: str) -> Tuple[bool, str]:
        """
        Verifica se a consulta SQL é segura
        
        Args:
            sql_query: Consulta SQL
            
        Returns:
            Tuple[bool, str]: (Se é permitido executar, mensagem de erro)
        """
        if not self.enable_check:
            return True, ""
            
        sql_query = sql_query.strip().upper()
        operation_type = self._get_operation_type(sql_query)
        
        # Verifica se é uma operação de atualização/exclusão sem cláusula WHERE
        if operation_type in {'UPDATE', 'DELETE'} and 'WHERE' not in sql_query:
            error_msg = f"Operação {operation_type} deve conter cláusula WHERE"
            logger.warning(f"Consulta restrita: {error_msg}")
            return False, error_msg
            
        return True, ""

    def _get_operation_type(self, sql_query: str) -> str:
        """Obtém o tipo de operação SQL"""
        if not sql_query:
            return ""
        words = sql_query.split()
        if not words:
            return ""
        return words[0].upper()

    def _parse_int_env(self, env_name: str, default: int) -> int:
        """Analisa variável de ambiente do tipo inteiro"""
        try:
            return int(os.getenv(env_name, str(default)))
        except (ValueError, TypeError):
            return default

    def update_limits(self, new_limits: dict):
        """
        Atualiza os limites de operação
        
        Args:
            new_limits: Dicionário com novos valores de limite
        """
        for operation, limit in new_limits.items():
            if operation in self.max_limits:
                try:
                    self.max_limits[operation] = int(limit)
                    logger.info(f"Atualizando limite da operação {operation} para: {limit}")
                except (ValueError, TypeError):
                    logger.warning(f"Valor de limite inválido: {operation}={limit}")