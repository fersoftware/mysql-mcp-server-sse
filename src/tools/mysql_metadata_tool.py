"""
Ferramenta de consulta de metadados do MySQL
Fornece funcionalidades de consulta de estrutura de tabelas e outras informações de metadados
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

from .metadata_base_tool import MetadataToolBase, ParameterValidationError, QueryExecutionError
from src.db.mysql_operations import get_db_connection, execute_query

logger = logging.getLogger("mysql_server")

# Função de validação de padrão
def validate_pattern(pattern: str) -> bool:
    """
    Valida se o padrão de string é seguro (prevenindo injeção SQL)
    
    Args:
        pattern: Padrão de string a ser validado
        
    Returns:
        Retorna True se o padrão for seguro, caso contrário lança ValueError
    
    Raises:
        ValueError: Quando o padrão contém caracteres não seguros
    """
    # Apenas permite letras, números, sublinhados e caracteres curinga (% e _)
    if not re.match(r'^[a-zA-Z0-9_%]+$', pattern):
        raise ValueError("Padrão só pode conter letras, números, sublinhados e caracteres curinga (%_)")
    return True

def validate_table_name(name: str) -> bool:
    """
    Valida se o nome da tabela é seguro e válido
    
    Args:
        name: Nome da tabela a ser validado
        
    Returns:
        Retorna True se o nome da tabela for seguro, caso contrário lança ValueError
    
    Raises:
        ValueError: Quando o nome da tabela contém caracteres não seguros
    """
    # Apenas permite letras, números e sublinhados
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        raise ValueError(f"Nome de tabela inválido: {name}, nome da tabela só pode conter letras, números e sublinhados")
    return True

def validate_database_name(name: str) -> bool:
    """
    Valida se o nome do banco de dados é seguro e válido
    
    Args:
        name: Nome do banco de dados a ser validado
        
    Returns:
        Retorna True se o nome do banco for seguro, caso contrário lança ValueError
    
    Raises:
        ValueError: Quando o nome do banco contém caracteres não seguros
    """
    # Apenas permite letras, números e sublinhados
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        raise ValueError(f"Nome de banco de dados inválido: {name}, nome do banco só pode conter letras, números e sublinhados")
    return True

def register_metadata_tools(mcp: FastMCP):
    """
    Registra ferramentas de consulta de metadados do MySQL no servidor MCP
    
    Args:
        mcp: Instância do servidor FastMCP
    """
    logger.debug("Registrando ferramentas de consulta de metadados do MySQL...")
    
    @mcp.tool()
    @MetadataToolBase.handle_query_error
    async def mysql_show_tables(database: Optional[str] = None, pattern: Optional[str] = None,
                               limit: int = 100, exclude_views: bool = False) -> str:
        """
        Obtém lista de tabelas do banco de dados, com suporte a filtro e limitação de resultados
        
        Args:
            database: Nome do banco de dados (opcional, usa o banco atual por padrão)
            pattern: Padrão de correspondência para nomes de tabelas (opcional, ex: '%user%')
            limit: Número máximo de resultados a retornar (padrão 100, 0 indica sem limite)
            exclude_views: Excluir views da lista (padrão False)
            
        Returns:
            Lista de tabelas em formato JSON
        """
        # 参数验证
        if database:
            MetadataToolBase.validate_parameter(
                "database", database, 
                lambda x: re.match(r'^[a-zA-Z0-9_]+$', x),
                "数据库名称只能包含字母、数字和下划线"
            )
            
        if pattern:
            MetadataToolBase.validate_parameter(
                "pattern", pattern,
                lambda x: re.match(r'^[a-zA-Z0-9_%]+$', x),
                "模式只能包含字母、数字、下划线和通配符(%_)"
            )
            
        MetadataToolBase.validate_parameter(
            "limit", limit,
            lambda x: isinstance(x, int) and x >= 0,
            "返回结果的最大数量必须是非负整数"
        )
        
        # 基础查询
        base_query = "SHOW FULL TABLES" if exclude_views else "SHOW TABLES"
        if database:
            base_query += f" FROM `{database}`"
        if pattern:
            base_query += f" LIKE '{pattern}'"
            
        logger.debug(f"执行查询: {base_query}")
        
        # 执行查询
        with get_db_connection() as connection:
            results = await execute_query(connection, base_query)
            
            # 如果需要排除视图，且使用的是SHOW FULL TABLES
            if exclude_views and "FULL" in base_query:
                filtered_results = []
                
                # 查找表名和表类型字段
                fields = list(results[0].keys()) if results else []
                table_field = fields[0] if fields else None
                table_type_field = fields[1] if len(fields) > 1 else None
                
                if table_field and table_type_field:
                    # 基表类型通常是"BASE TABLE"
                    for item in results:
                        if item[table_type_field] == 'BASE TABLE':
                            filtered_results.append(item)
                else:
                    filtered_results = results
            else:
                filtered_results = results
                
            # 限制返回数量
            if limit > 0 and len(filtered_results) > limit:
                limited_results = filtered_results[:limit]
                is_limited = True
            else:
                limited_results = filtered_results
                is_limited = False
                
            # 构造元数据
            metadata_info = {
                "metadata_info": {
                    "operation_type": "Consulta de lista de tabelas",
                    "result_count": len(limited_results),
                    "total_count": len(results),
                    "filtered": {
                        "database": database,
                        "pattern": pattern,
                        "exclude_views": exclude_views and "FULL" in base_query,
                        "limited": is_limited
                    }
                },
                "results": limited_results
            }
            
            return json.dumps(metadata_info, default=str)
    
    @mcp.tool()
    @MetadataToolBase.handle_query_error
    async def mysql_show_columns(table: str, database: Optional[str] = None) -> str:
        """
        Obtém informações das colunas de uma tabela
        
        Args:
            table: Nome da tabela
            database: Nome do banco de dados (opcional, usa o banco atual por padrão)
            
        Returns:
            Informações das colunas da tabela em formato JSON
        """
        # Validação de parâmetros
        MetadataToolBase.validate_parameter(
            "table", table,
            lambda x: re.match(r'^[a-zA-Z0-9_]+$', x),
            "Nome da tabela só pode conter letras, números e sublinhados"
        )
        
        if database:
            MetadataToolBase.validate_parameter(
                "database", database, 
                lambda x: re.match(r'^[a-zA-Z0-9_]+$', x),
                "Nome do banco só pode conter letras, números e sublinhados"
            )
            
        query = f"SHOW COLUMNS FROM `{table}`" if not database else f"SHOW COLUMNS FROM `{database}`.`{table}`"
        logger.debug(f"Executando consulta: {query}")
        
        return await MetadataToolBase.execute_metadata_query(query, operation_type="Consulta de informações das colunas")

    @mcp.tool()
    @MetadataToolBase.handle_query_error
    async def mysql_describe_table(table: str, database: Optional[str] = None) -> str:
        """
        Descreve a estrutura de uma tabela
        
        Args:
            table: Nome da tabela
            database: Nome do banco de dados (opcional, usa o banco atual por padrão)
            
        Returns:
            Descrição da estrutura da tabela em formato JSON
        """
        # Validação de parâmetros
        MetadataToolBase.validate_parameter(
            "table", table,
            lambda x: re.match(r'^[a-zA-Z0-9_]+$', x),
            "Nome da tabela só pode conter letras, números e sublinhados"
        )
        
        if database:
            MetadataToolBase.validate_parameter(
                "database", database, 
                lambda x: re.match(r'^[a-zA-Z0-9_]+$', x),
                "Nome do banco só pode conter letras, números e sublinhados"
            )
            
        # A instrução DESCRIBE tem funcionalidade similar ao SHOW COLUMNS, mas com formato de resultado diferente
        query = f"DESCRIBE `{table}`" if not database else f"DESCRIBE `{database}`.`{table}`"
        logger.debug(f"Executando consulta: {query}")
        
        return await MetadataToolBase.execute_metadata_query(query, operation_type="Descrição da estrutura da tabela")

    @mcp.tool()
    @MetadataToolBase.handle_query_error
    async def mysql_show_create_table(table: str, database: Optional[str] = None) -> str:
        """
        Obtém o comando CREATE TABLE para uma tabela
        
        Args:
            table: Nome da tabela
            database: Nome do banco de dados (opcional, usa o banco atual por padrão)
            
        Returns:
            Comando CREATE TABLE em formato JSON
        """
        # Validação de parâmetros
        MetadataToolBase.validate_parameter(
            "table", table,
            lambda x: re.match(r'^[a-zA-Z0-9_]+$', x),
            "Nome da tabela só pode conter letras, números e sublinhados"
        )
        
        if database:
            MetadataToolBase.validate_parameter(
                "database", database, 
                lambda x: re.match(r'^[a-zA-Z0-9_]+$', x),
                "Nome do banco só pode conter letras, números e sublinhados"
            )
            
        table_ref = f"`{table}`" if not database else f"`{database}`.`{table}`"
        query = f"SHOW CREATE TABLE {table_ref}"
        logger.debug(f"Executando consulta: {query}")
        
        return await MetadataToolBase.execute_metadata_query(query, operation_type="Consulta de comando CREATE TABLE")