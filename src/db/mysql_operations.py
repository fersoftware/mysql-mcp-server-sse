import os
import logging
import mysql.connector
from mysql.connector import Error
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from ..security.sql_analyzer import SQLOperationType
from ..security.query_limiter import QueryLimiter
from ..security.interceptor import SQLInterceptor, SecurityException

logger = logging.getLogger("mysql_server")

# Inicializa componentes de segurança
sql_analyzer = SQLOperationType()
query_limiter = QueryLimiter()
sql_interceptor = SQLInterceptor(sql_analyzer)

def get_db_config() -> dict:
    """
    Obtém a configuração do banco de dados a partir das variáveis de ambiente
    
    Returns:
        dict: Dicionário com a configuração do banco de dados
    """
    return {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', ''),
        'database': os.getenv('MYSQL_DATABASE', ''),
        'port': int(os.getenv('MYSQL_PORT', '3306')),
        'connection_timeout': 5,
        'auth_plugin': 'mysql_native_password',
        'ssl_disabled': True  # Desabilita SSL temporariamente
    }

class MySQLConnectionManager:
    """
    Gerenciador de conexão MySQL que mantém o contexto entre consultas
    """
    def __init__(self):
        self.connection = None
        self.cursor = None
        self.db_config = get_db_config()
        
    def connect(self):
        """Estabelece conexão com o banco de dados"""
        if not self.connection or not self.connection.is_connected():
            self.connection = mysql.connector.connect(**self.db_config)
            self.cursor = self.connection.cursor(dictionary=True)
            logger.debug("Nova conexão estabelecida")
        return self.connection, self.cursor
        
    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Executa uma consulta SQL mantendo o contexto da conexão
        
        Args:
            query: Instrução SQL da consulta
            params: Dicionário de parâmetros da consulta (opcional)
            
        Returns:
            lista: Lista de resultados da consulta
        """
        try:
            connection, cursor = self.connect()
            
            # Verifica se a consulta é permitida
            risk_level = sql_interceptor.analyzer.analyze_risk(query)
            
            # Executa a consulta
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
                
            # Obtém a operação a partir da consulta
            operation = query.strip().split()[0].upper() if query.strip() else 'UNKNOWN'
            
            # Obtém os resultados
            results = cursor.fetchall()
            
            # Adiciona número de linhas afetadas para operações de modificação
            if query.strip().upper().startswith(('UPDATE', 'DELETE', 'INSERT')):
                results = [{'affected_rows': cursor.rowcount}] + results
                logger.info(f"Operação {operation} afetou {cursor.rowcount} linhas")
            
            # Simplificação do código para remoção dos operadores em chinês
            if operation in sql_analyzer.metadata_operations:
                # Sem resultados, retorna lista vazia com informação de metadados
                if not results:
                    logger.debug(f"Consulta de metadados {operation} não retornou resultados")
                    return [{'metadata_operation': operation, 'result_count': 0}]
                    
                # Otimiza o formato dos resultados
                metadata_results = []
                for row in results:
                    # Trata consultas específicas de metadados
                    if operation == 'SHOW' and 'Table' in row:
                        row['table_name'] = row['Table']
                    elif operation in {'DESC', 'DESCRIBE'} and 'Field' in row:
                        row['column_name'] = row['Field']
                        row['data_type'] = row['Type']
                    
                    metadata_results.append(row)
                    
                logger.debug(f"Consulta de metadados {operation} retornou {len(metadata_results)} resultados")
                return metadata_results
            
            logger.debug(f"Consulta retornou {len(results)} resultados")
            return results
                
        except SecurityException as security_err:
            logger.error(f"Falha na verificação de segurança: {str(security_err)}")
            raise
        except mysql.connector.Error as query_err:
            # Em caso de erro, faz rollback para operações de modificação
            try:
                operation = query.strip().split()[0].upper() if query.strip() else 'UNKNOWN'
                if operation in {'UPDATE', 'DELETE', 'INSERT'}:
                    self.connection.rollback()
                    logger.debug("Transação revertida")
            except:
                pass
            logger.error(f"Falha na execução da consulta: {str(query_err)}")
            raise ValueError(f"Falha na execução da consulta: {str(query_err)}")
        finally:
            # Garante que o cursor seja fechado corretamente
            if self.cursor:
                self.cursor.close()
                self.cursor = self.connection.cursor(dictionary=True)
                logger.debug("Cursor do banco de dados recriado")

# Instância global do gerenciador de conexão
connection_manager = MySQLConnectionManager()

# Mantendo compatibilidade com código existente
@contextmanager
def get_db_connection():
    """
    Cria um gerenciador de contexto para conexão com o banco de dados (compatibilidade)
    
    Yields:
        tuple: (connection, cursor) - Tupla com conexão e cursor
    """
    connection = None
    cursor = None
    try:
        db_config = get_db_config()
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(dictionary=True)
        yield (connection, cursor)
    except Error as e:
        logger.error(f"Falha na conexão com o banco de dados: {str(e)}")
        raise
    finally:
        try:
            if cursor and isinstance(cursor, mysql.connector.cursor.MySQLCursor):
                cursor.close()
                logger.debug("Cursor do banco de dados fechado")
        except Exception as e:
            logger.error(f"Erro ao fechar cursor: {str(e)}")
        try:
            if connection and connection.is_connected():
                connection.close()
                logger.debug("Conexão com o banco de dados fechada")
        except Exception as e:
            logger.error(f"Erro ao fechar conexão: {str(e)}")

async def execute_query(connection, cursor, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Executa uma consulta SQL usando conexão e cursor fornecidos (compatibilidade)
    
    Args:
        connection: Objeto de conexão com o banco de dados
        cursor: Cursor da conexão
        query: Instrução SQL da consulta
        params: Dicionário de parâmetros da consulta (opcional)
        
    Returns:
        lista: Lista de resultados da consulta
    """
    try:
        # Verifica se a consulta é permitida
        risk_level = sql_interceptor.analyzer.analyze_risk(query)
        
        # Executa a consulta
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        # Obtém a operação a partir da consulta
        operation = query.strip().split()[0].upper() if query.strip() else 'UNKNOWN'
        
        # Obtém os resultados
        results = cursor.fetchall()
        
        # Adiciona número de linhas afetadas para operações de modificação
        if query.strip().upper().startswith(('UPDATE', 'DELETE', 'INSERT')):
            results = [{'affected_rows': cursor.rowcount}] + results
            logger.info(f"Operação {operation} afetou {cursor.rowcount} linhas")
        
        # Simplificação do código para remoção dos operadores em chinês
        if operation in sql_analyzer.metadata_operations:
            # Sem resultados, retorna lista vazia com informação de metadados
            if not results:
                logger.debug(f"Consulta de metadados {operation} não retornou resultados")
                return [{'metadata_operation': operation, 'result_count': 0}]
                
            # Otimiza o formato dos resultados
            metadata_results = []
            for row in results:
                # Trata consultas específicas de metadados
                if operation == 'SHOW' and 'Table' in row:
                    row['table_name'] = row['Table']
                elif operation in {'DESC', 'DESCRIBE'} and 'Field' in row:
                    row['column_name'] = row['Field']
                    row['data_type'] = row['Type']
                
                metadata_results.append(row)
                
            logger.debug(f"Consulta de metadados {operation} retornou {len(metadata_results)} resultados")
            return metadata_results
        
        logger.debug(f"Consulta retornou {len(results)} resultados")
        return results
            
    except SecurityException as security_err:
        logger.error(f"Falha na verificação de segurança: {str(security_err)}")
        raise
    except mysql.connector.Error as query_err:
        # Em caso de erro, faz rollback para operações de modificação
        try:
            operation = query.strip().split()[0].upper() if query.strip() else 'UNKNOWN'
            if operation in {'UPDATE', 'DELETE', 'INSERT'}:
                connection.rollback()
                logger.debug("Transação revertida")
        except:
            pass
        logger.error(f"Falha na execução da consulta: {str(query_err)}")
        raise ValueError(f"Falha na execução da consulta: {str(query_err)}")
    finally:
        # Garante que o cursor seja fechado corretamente
        if cursor:
            cursor.close()
            logger.debug("Cursor do banco de dados fechado")

async def execute_query(connection, cursor, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Executa uma consulta SQL
    
    Args:
        connection: Objeto de conexão com o banco de dados
        cursor: Cursor da conexão
        query: Instrução SQL da consulta
        params: Dicionário de parâmetros da consulta (opcional)
        
    Returns:
        lista: Lista de resultados da consulta
    
    Raises:
        SecurityException: Quando a operação é negada pelo mecanismo de segurança
        ValueError: Quando a execução da consulta falha
    """
    try:
        # Verifica se a consulta é permitida
        risk_level = sql_interceptor.analyzer.analyze_risk(query)
        
        # Executa a consulta
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
            
        # Obtém a operação a partir da consulta
        operation = query.strip().split()[0].upper() if query.strip() else 'UNKNOWN'
        
        # Obtém os resultados
        results = cursor.fetchall()
        
        # Adiciona número de linhas afetadas para operações de modificação
        if query.strip().upper().startswith(('UPDATE', 'DELETE', 'INSERT')):
            results = [{'affected_rows': cursor.rowcount}] + results
            logger.info(f"Operação {operation} afetou {cursor.rowcount} linhas")
        
        # Simplificação do código para remoção dos operadores em chinês
        if operation in sql_analyzer.metadata_operations:
            # Sem resultados, retorna lista vazia com informação de metadados
            if not results:
                logger.debug(f"Consulta de metadados {operation} não retornou resultados")
                return [{'metadata_operation': operation, 'result_count': 0}]
                
            # Otimiza o formato dos resultados
            metadata_results = []
            for row in results:
                # Trata consultas específicas de metadados
                if operation == 'SHOW' and 'Table' in row:
                    row['table_name'] = row['Table']
                elif operation in {'DESC', 'DESCRIBE'} and 'Field' in row:
                    row['column_name'] = row['Field']
                    row['data_type'] = row['Type']
                
                metadata_results.append(row)
                
            logger.debug(f"Consulta de metadados {operation} retornou {len(metadata_results)} resultados")
            return metadata_results
        
        logger.debug(f"Consulta retornou {len(results)} resultados")
        return results
            
    except SecurityException as security_err:
        logger.error(f"Falha na verificação de segurança: {str(security_err)}")
        raise
    except mysql.connector.Error as query_err:
        # Em caso de erro, faz rollback para operações de modificação
        try:
            operation = query.strip().split()[0].upper() if query.strip() else 'UNKNOWN'
            if operation in {'UPDATE', 'DELETE', 'INSERT'}:
                connection.rollback()
                logger.debug("Transação revertida")
        except:
            pass
        logger.error(f"Falha na execução da consulta: {str(query_err)}")
        raise ValueError(f"Falha na execução da consulta: {str(query_err)}")
    finally:
        # Garante que o cursor seja fechado corretamente
        if cursor:
            cursor.close()
            logger.debug("Cursor do banco de dados fechado")