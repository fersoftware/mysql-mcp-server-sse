"""
MySQL元数据工具基类
提供元数据查询工具的共享功能
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union, TypeVar, Generic, Callable
import functools

from src.db.mysql_operations import get_db_connection, execute_query

logger = logging.getLogger("mysql_server")

# Classe de exceção personalizada
class ParameterValidationError(Exception):
    """Parameter validation error"""
    pass

class QueryExecutionError(Exception):
    """Query execution error"""
    pass

class MetadataToolBase:
    """
    Classe base para ferramentas de consulta de metadados do MySQL
    Fornece funcionalidades comuns de tratamento de erros e formatação de resultados
    """
    
    @staticmethod
    def validar_parametro(nome_do_parametro: str, valor_do_parametro: Any, validador: callable, mensagem_de_erro: str) -> None:
        """
        Valida se um parâmetro é válido
        
        Args:
            nome_do_parametro: Nome do parâmetro
            valor_do_parametro: Valor do parâmetro
            validador: Função de validação
            mensagem_de_erro: Mensagem de erro
            
        Raises:
            ErroDeValidacaoDeParametro: Falha na validação do parâmetro
        """
        if not validador(valor_do_parametro):
            logger.warning(f"Falha na validação do parâmetro: {nome_do_parametro}={valor_do_parametro}")
            raise ErroDeValidacaoDeParametro(mensagem_de_erro)
    
    @staticmethod
    def formatar_resultados(resultados: List[Dict[str, Any]], tipo_de_operacao: str) -> str:
        """
        Formata os resultados da consulta
        
        Args:
            resultados: Lista de resultados da consulta
            tipo_de_operacao: Tipo de operação
            
        Returns:
            String JSON formatada
        """
        return json.dumps({
            "informacao_de_metadados": {
                "tipo_de_operacao": tipo_de_operacao,
                "contagem_de_resultados": len(resultados)
            },
            "resultados": resultados
        }, default=str)
    
    @classmethod
    def tratar_erro_de_consulta(cls, func):
        """
        Decorador: Trata erros de consulta
        
        Args:
            func: Função decorada
            
        Returns:
            Função decorada
        """
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ErroDeValidacaoDeParametro as e:
                logger.error(f"Erro de validação de parâmetro: {str(e)}")
                return cls.formatar_resultados([
                    {"erro": f"Falha na validação do parâmetro: {str(e)}"}
                ], "validação de parâmetro")
            except ErroDeExecucaoDeConsulta as e:
                logger.error(f"Erro na execução da consulta: {str(e)}")
                return cls.formatar_resultados([
                    {"erro": f"Falha na execução da consulta: {str(e)}"}
                ], "execução da consulta")
            except Exception as e:
                logger.error(f"Erro desconhecido: {str(e)}")
                return cls.formatar_resultados([
                    {"erro": f"Erro desconhecido: {str(e)}"}
                ], "erro desconhecido")
        return wrapper

    @classmethod
    def handle_query_error(cls, func):
        """
        Decorador: Trata erros de consulta
        
        Args:
            func: Função decorada
            
        Returns:
            Função decorada
        """
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ParameterValidationError as e:
                logger.error(f"Erro de validação de parâmetro: {str(e)}")
                return cls.formatar_resultados([
                    {"error": f"Parameter validation error: {str(e)}"}
                ], "parameter validation")
            except QueryExecutionError as e:
                logger.error(f"Erro na execução da consulta: {str(e)}")
                return cls.formatar_resultados([
                    {"error": f"Query execution error: {str(e)}"}
                ], "query execution")
            except Exception as e:
                logger.error(f"Erro desconhecido: {str(e)}")
                return cls.formatar_resultados([
                    {"error": f"Unknown error: {str(e)}"}
                ], "unknown error")
        return wrapper

    @classmethod
    async def executar_consulta_de_metadados(cls, consulta: str, params: Optional[Dict[str, Any]] = None, tipo_de_operacao: str = "consulta de metadados") -> str:
        """
        Executa uma consulta de metadados e retorna os resultados formatados
        
        Args:
            consulta: Instrução SQL da consulta
            params: Dicionário de parâmetros da consulta (opcional)
            tipo_de_operacao: Tipo de operação
            
        Returns:
            String JSON com os resultados da consulta
        """
        try:
            with get_db_connection() as connection:
                resultados = await execute_query(connection, consulta, params)
                return cls.formatar_resultados(resultados, tipo_de_operacao)
        except Exception as e:
            logger.error(f"Erro na execução da consulta de metadados: {str(e)}")
            raise QueryExecutionError(str(e))