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

def get_db_config():
    """
    Obtém configuração do banco de dados das variáveis de ambiente
    
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
        'auth_plugin': 'mysql_native_password'  # Especifica o plugin de autenticação
    }

@contextmanager
def get_db_connection():
    """
    Cria um gerenciador de contexto para conexão com o banco de dados
    
    Yields:
        mysql.connector.connection.MySQLConnection: Objeto de conexão com o banco de dados
    """
    connection = None
    try:
        db_config = get_db_config()
        if not db_config['database']:
            raise ValueError("Nome do banco de dados não definido, verifique a variável de ambiente MYSQL_DATABASE")
        
        connection = mysql.connector.connect(**db_config)
        yield connection
    except mysql.connector.Error as err:
        error_msg = str(err)
        logger.error(f"Falha na conexão com o banco de dados: {error_msg}")
        
        if "Access denied" in error_msg:
            raise ValueError("Acesso negado, verifique o nome de usuário e senha")
        elif "Unknown database" in error_msg:
            db_config = get_db_config()
            raise ValueError(f"Banco de dados '{db_config['database']}' não existe")
        elif "Can't connect" in error_msg or "Connection refused" in error_msg:
            raise ConnectionError("Não foi possível conectar ao servidor MySQL, verifique se o serviço está em execução")
        elif "Authentication plugin" in error_msg:
            raise ValueError(f"Problema com o plugin de autenticação: {error_msg}, tente alterar o método de autenticação para mysql_native_password")
        else:
            raise ConnectionError(f"Falha na conexão com o banco de dados: {error_msg}")
    finally:
        if connection and connection.is_connected():
            connection.close()
            logger.debug("Conexão com o banco de dados fechada")

async def execute_query(connection, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Executa uma consulta SQL
    
    Args:
        connection: Objeto de conexão com o banco de dados
        query: Instrução SQL da consulta
        params: Dicionário de parâmetros da consulta (opcional)
        
    Returns:
        lista: Lista de resultados da consulta
    
    Raises:
        SecurityException: Quando a operação é negada pelo mecanismo de segurança
        ValueError: Quando a execução da consulta falha
    """
    cursor = None
    operation = None  # 初始化操作类型变量
    try:
        # 安全检查
        if not await sql_interceptor.check_operation(query):
            raise SecurityException("操作被安全机制拒绝")
            
        cursor = connection.cursor(dictionary=True)
        
        # 执行查询
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        # 获取操作类型
        operation = query.strip().split()[0].upper()
        
        # 对于修改操作，提交事务并返回影响的行数
        if operation in {'UPDATE', 'DELETE', 'INSERT'}:
            affected_rows = cursor.rowcount
            # 提交事务，确保更改被保存
            connection.commit()
            logger.debug(f"修改操作 {operation} 影响了 {affected_rows} 行数据")
            return [{'affected_rows': affected_rows}]
        
        # 处理元数据查询操作
        if operation in sql_analyzer.metadata_operations:
            # 获取结果集
            results = cursor.fetchall()
            
            # 没有结果时返回空列表但添加元信息
            if not results:
                logger.debug(f"元数据查询 {operation} 没有返回结果")
                return [{'metadata_operation': operation, 'result_count': 0}]
                
            # 优化结果格式 - 为元数据结果添加额外信息
            metadata_results = []
            for row in results:
                # 对某些特定元数据查询进行特殊处理
                if operation == 'SHOW' and 'Table' in row:
                    # SHOW TABLES 结果增强
                    row['table_name'] = row['Table']
                elif operation in {'DESC', 'DESCRIBE'} and 'Field' in row:
                    # DESC/DESCRIBE 表结构结果增强
                    row['column_name'] = row['Field']
                    row['data_type'] = row['Type']
                
                metadata_results.append(row)
                
            logger.debug(f"元数据查询 {operation} 返回 {len(metadata_results)} 条结果")
            return metadata_results
        
        # 对于查询操作，返回结果集
        results = cursor.fetchall()
        logger.debug(f"查询返回 {len(results)} 条结果")
        return results
            
    except SecurityException as security_err:
        logger.error(f"安全检查失败: {str(security_err)}")
        raise
    except mysql.connector.Error as query_err:
        # 如果发生错误，进行回滚
        if operation and operation in {'UPDATE', 'DELETE', 'INSERT'}:  # 确保operation已定义
            try:
                connection.rollback()
                logger.debug("事务已回滚")
            except:
                pass
        logger.error(f"查询执行失败: {str(query_err)}")
        raise ValueError(f"查询执行失败: {str(query_err)}")
    finally:
        # 确保游标正确关闭
        if cursor:
            cursor.close()
            logger.debug("数据库游标已关闭")