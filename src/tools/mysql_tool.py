import json
import logging
from typing import Any, Dict, Optional
from mcp.server.fastmcp import FastMCP
from src.db.mysql_operations import connection_manager
import mysql.connector

logger = logging.getLogger("mysql_server")

# Tenta importar o conector MySQL
try:
    mysql.connector
    mysql_available = True
except ImportError:
    mysql_available = False

def register_mysql_tool(mcp: FastMCP):
    """
    Registra ferramenta de consulta MySQL no servidor MCP
    
    Args:
        mcp: Instância do servidor FastMCP
    """
    logger.debug("Registrando ferramenta de consulta MySQL...")
    
    @mcp.tool()
    async def mysql_query(query: str, params: Optional[Dict[str, Any]] = None) -> str:
        """
        Executa consulta MySQL e retorna os resultados
        
        Args:
            query: Consulta SQL
            params: Parâmetros da consulta (opcional)
            
        Returns:
            Resultados da consulta em formato JSON
        """
        logger.debug(f"Executando consulta MySQL: {query}, parâmetros: {params}")
        
        try:
            try:
                results = connection_manager.execute_query(query, params)
                return json.dumps(results, default=str)
            except Exception as e:
                logger.error(f"Erro ao executar consulta: {str(e)}")
                return json.dumps({"error": str(e)})
                
        except Exception as e:
            logger.error(f"Erro ao executar consulta: {str(e)}")
            return json.dumps({"error": str(e)})