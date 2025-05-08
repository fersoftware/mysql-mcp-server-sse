"""
Ferramenta avançada de consulta de estrutura do MySQL
Fornece funcionalidades de consulta avançada como índices, constraints e status das tabelas
"""

import json
import logging
import re
import os
from typing import Any, Dict, List, Optional, Union
from mcp.server.fastmcp import FastMCP

from .metadata_base_tool import MetadataToolBase, ParameterValidationError, QueryExecutionError
from src.db.mysql_operations import get_db_connection, execute_query

logger = logging.getLogger("mysql_server")

# Função de validação de parâmetros
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
        raise ValueError(f"Nome de tabela inválido: {name}, o nome da tabela só pode conter letras, números e sublinhados")
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
        raise ValueError(f"Nome de banco de dados inválido: {name}, o nome do banco só pode conter letras, números e sublinhados")
    return True

def validate_column_name(name: str) -> bool:
    """
    Valida se o nome da coluna é seguro e válido
    
    Args:
        name: Nome da coluna a ser validado
        
    Returns:
        Retorna True se o nome da coluna for seguro, caso contrário lança ValueError
    
    Raises:
        ValueError: Quando o nome da coluna contém caracteres não seguros
    """
    # Apenas permite letras, números e sublinhados
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        raise ValueError(f"Nome de coluna inválido: {name}, o nome da coluna só pode conter letras, números e sublinhados")
    return True

async def execute_schema_query(
    query: str, 
    params: Optional[Dict[str, Any]] = None, 
    operation_type: str = "Consulta de metadados"
) -> str:
    """
    Executa consulta de estrutura de tabela
    
    Args:
        query: Consulta SQL
        params: Parâmetros da consulta (opcional)
        operation_type: Tipo de operação
        
    Returns:
        Resultado da consulta em formato JSON
    """
    with get_db_connection() as connection:
        results = await execute_query(connection, query, params)
        return MetadataToolBase.format_results(results, operation_type)

def register_schema_tools(mcp: FastMCP):
    """
    Registra ferramentas avançadas de consulta de estrutura do MySQL no servidor MCP
    
    Args:
        mcp: Instância do servidor FastMCP
    """
    logger.debug("Registrando ferramentas avançadas de consulta de estrutura do MySQL...")
    
    @mcp.tool()
    @MetadataToolBase.handle_query_error
    async def mysql_show_indexes(table: str, database: Optional[str] = None) -> str:
        """
        Obtém informações sobre os índices de uma tabela
        
        Args:
            table: Nome da tabela
            database: Nome do banco de dados (opcional, usa o banco atual por padrão)
            
        Returns:
            Informações dos índices da tabela em formato JSON
        """
        # Validação dos parâmetros
        validate_table_name(table)
        
        if database:
            validate_database_name(database)
        
        # Constrói a consulta
        table_ref = f"`{table}`" if not database else f"`{database}`.`{table}`"
        query = f"SHOW INDEX FROM {table_ref}"
        logger.debug(f"Executando consulta: {query}")
        
        # Executa a consulta
        return await execute_schema_query(query, operation_type="Consulta de índices")
    
    @mcp.tool()
    @MetadataToolBase.handle_query_error
    async def mysql_show_table_status(database: Optional[str] = None, like_pattern: Optional[str] = None) -> str:
        """
        Obtém informações de status das tabelas
        
        Args:
            database: Nome do banco de dados (opcional, usa o banco atual por padrão)
            like_pattern: Padrão de correspondência para nomes de tabelas (opcional, ex: '%user%')
            
        Returns:
            Informações de status das tabelas em formato JSON
        """
        # Validação dos parâmetros
        if database:
            validate_database_name(database)
            
        if like_pattern:
            validate_column_name(like_pattern)
        
        # Constrói a consulta
        if database:
            query = f"SHOW TABLE STATUS FROM `{database}`"
        else:
            query = "SHOW TABLE STATUS"
            
        if like_pattern:
            query += f" LIKE '{like_pattern}'"
            
        logger.debug(f"Executando consulta: {query}")
        
        # Executa a consulta
        return await execute_schema_query(query, operation_type="Consulta de status de tabelas")
    
    @mcp.tool()
    @MetadataToolBase.handle_query_error
    async def mysql_show_foreign_keys(table: str, database: Optional[str] = None) -> str:
        """
        Obtém informações sobre as constraints de foreign key de uma tabela
        
        Args:
            table: Nome da tabela
            database: Nome do banco de dados (opcional, usa o banco atual por padrão)
            
        Returns:
            Informações das constraints de foreign key em formato JSON
        """
        # Validação dos parâmetros
        validate_table_name(table)
        
        if database:
            validate_database_name(database)
        
        # Determina o nome do banco de dados
        db_name = database
        if not db_name:
            # Obtém o banco de dados atual
            with get_db_connection() as connection:
                current_db_results = await execute_query(connection, "SELECT DATABASE() as db")
                if current_db_results and 'db' in current_db_results[0]:
                    db_name = current_db_results[0]['db']
        
        if not db_name:
            raise ValueError("Não foi possível determinar o nome do banco de dados, por favor especifique o parâmetro database")
        
        # Consulta foreign keys usando INFORMATION_SCHEMA
        query = """
        SELECT 
            CONSTRAINT_NAME, 
            TABLE_NAME,
            COLUMN_NAME,
            REFERENCED_TABLE_NAME,
            REFERENCED_COLUMN_NAME,
            UPDATE_RULE,
            DELETE_RULE
        FROM 
            INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
        JOIN 
            INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
        ON 
            kcu.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
        WHERE 
            kcu.TABLE_SCHEMA = %s 
            AND kcu.TABLE_NAME = %s
            AND kcu.REFERENCED_TABLE_NAME IS NOT NULL
        """
        params = {'TABLE_SCHEMA': db_name, 'TABLE_NAME': table}
        
        logger.debug(f"Executando consulta: Obtendo chaves estrangeiras da tabela {db_name}.{table}")
        
        # Executa a consulta
        return await execute_schema_query(query, params, operation_type="Consulta de chaves estrangeiras")
    
    @mcp.tool()
    @MetadataToolBase.handle_query_error
    async def mysql_paginate_results(query: str, page: int = 1, page_size: int = 50) -> str:
        """
        Executa consulta com paginação para lidar com grandes conjuntos de resultados
        
        Args:
            query: Consulta SQL
            page: Número da página (começa em 1)
            page_size: Número de registros por página (padrão 50)
            
        Returns:
            Resultados paginados em formato JSON
        """
        # Validação dos parâmetros
        MetadataToolBase.validate_parameter(
            "page", page,
            lambda x: isinstance(x, int) and x > 0,
            "O número da página deve ser um inteiro positivo"
        )
        
        MetadataToolBase.validate_parameter(
            "page_size", page_size,
            lambda x: isinstance(x, int) and 1 <= x <= 1000,
            "O número de registros por página deve estar entre 1 e 1000"
        )
        
        # Verifica a sintaxe da consulta
        if not query.strip().upper().startswith('SELECT'):
            raise ValueError("Paginação suportada apenas para consultas SELECT")
            
        # Calcula LIMIT e OFFSET
        offset = (page - 1) * page_size
        
        # Adiciona cláusula LIMIT ao final da consulta
        paginated_query = query.strip()
        if 'LIMIT' in paginated_query.upper():
            raise ValueError("A consulta já contém cláusula LIMIT, remova-a e tente novamente")
            
        paginated_query += f" LIMIT {page_size} OFFSET {offset}"
        
        logger.debug(f"Executando consulta paginada: página={page}, registros por página={page_size}")
        
        # Obtém o número total de registros (para calcular número total de páginas)
        count_query = f"SELECT COUNT(*) as total FROM ({query}) as temp_count_table"
        
        with get_db_connection() as connection:
            # Executa a consulta paginada
            results = await execute_query(connection, paginated_query)
            
            # Obtém o número total de registros
            count_results = await execute_query(connection, count_query)
            total_records = count_results[0]['total'] if count_results else 0
            
            # Calcula número total de páginas
            total_pages = (total_records + page_size - 1) // page_size
            
            # Constrói metadados de paginação
            pagination_info = {
                "metadata_info": {
                    "operation_type": "Consulta paginada",
                    "result_count": len(results),
                    "pagination": {
                        "page": page,
                        "page_size": page_size,
                        "total_records": total_records,
                        "total_pages": total_pages
                    }
                },
                "results": results
            }
            
            return json.dumps(pagination_info, default=str) 