"""
Ferramenta de Consulta de Informações do MySQL
Fornece funcionalidades de consulta de informações do sistema, como banco de dados, variáveis e status
"""

import json
import logging
import re
import os
from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

from .metadata_base_tool import MetadataToolBase, ParameterValidationError, QueryExecutionError
from src.security.sql_analyzer import EnvironmentType
from src.db.mysql_operations import get_db_connection, execute_query

logger = logging.getLogger("mysql_server")

# Classe de exceção personalizada
class SecurityError(QueryExecutionError):
    """Erro de restrição de segurança"""
    pass

# Obtém lista de padrões de campos sensíveis das variáveis de ambiente
def get_sensitive_patterns():
    """Obtém lista de padrões de campos sensíveis das variáveis de ambiente"""
    padrões_padrão = [
        r'password', r'auth', r'credential', r'key', r'secret', r'private', 
        r'host', r'path', r'directory', r'ssl', r'iptables', r'filter'
    ]
    
    padrões_ambiente = os.getenv('SENSITIVE_INFO_FIELDS', '')
    if padrões_ambiente:
        # Combina padrões personalizados com padrões padrão
        padrões = [padrão.strip() for padrão in padrões_ambiente.split(',') if padrão.strip()]
        return list(set(padrões + padrões_padrão))
    
    return padrões_padrão

# Lista de padrões de variáveis e status sensíveis
PATTERN_VARIAVEIS_SENSIVEIS = get_sensitive_patterns()

# Prefixos de variáveis sensíveis, cujos valores serão ocultados no ambiente de produção
PREFIXOS_VARIAVEIS_SENSIVEIS = [
    "password", "auth", "secret", "key", "certificate", "ssl", "tls", "cipher", 
    "authentication", "secure", "credential", "token"
]

def check_environment_permission(env_type: EnvironmentType, query_type: str) -> bool:
    """
    Verifica se o ambiente atual permite a execução de um tipo específico de consulta
    
    Args:
        env_type: 环境类型（开发/生产）
        query_type: 查询类型
        
    Returns:
        bool: 是否允许执行
    """
    # 开发环境不限制查询
    if env_type == EnvironmentType.DEVELOPMENT:
        return True
        
    # 生产环境限制敏感信息查询
    sensitive_queries = ['variables', 'status', 'processlist']
    
    if query_type in sensitive_queries:
        # 检查是否在环境变量中明确允许
        allow_sensitive = os.getenv('ALLOW_SENSITIVE_INFO', 'false').lower() == 'true'
        if not allow_sensitive:
            logger.warning(f"生产环境中禁止执行敏感查询: {query_type}")
            return False
            
    return True

def filter_sensitive_info(results: List[Dict[str, Any]], filter_patterns: List[str] = None) -> List[Dict[str, Any]]:
    """
    过滤结果中的敏感信息
    
    Args:
        results: 查询结果
        filter_patterns: 敏感信息的正则表达式模式列表
        
    Returns:
        过滤后的结果列表
    """
    if not filter_patterns:
        filter_patterns = SENSITIVE_VARIABLE_PATTERNS
        
    filtered_results = []
    for item in results:
        # 复制一份，避免修改原始数据
        filtered_item = item.copy()
        
        # 检查常见的变量名字段
        for field in ['Variable_name', 'variable_name', 'name']:
            if field in filtered_item:
                var_name = filtered_item[field].lower()
                # 检查是否匹配敏感模式
                is_sensitive = any(re.search(pattern, var_name, re.IGNORECASE) for pattern in filter_patterns)
                
                if is_sensitive:
                    # 敏感信息，隐藏具体的值
                    for value_field in ['Value', 'value', 'variable_value']:
                        if value_field in filtered_item:
                            filtered_item[value_field] = '*** HIDDEN ***'
                            
        filtered_results.append(filtered_item)
        
    return filtered_results

def register_info_tools(mcp: FastMCP):
    """
    注册MySQL数据库信息查询工具到MCP服务器
    
    Args:
        mcp: FastMCP服务器实例
    """
    logger.debug("注册MySQL数据库信息查询工具...")
    
    @mcp.tool()
    @MetadataToolBase.handle_query_error
    async def mysql_show_databases(pattern: Optional[str] = None, limit: int = 100, exclude_system: bool = True) -> str:
        """
        获取所有数据库列表，支持筛选和限制结果数量
        
        Args:
            pattern: 数据库名称匹配模式 (可选, 例如 '%test%')
            limit: 返回结果的最大数量 (默认100，设为0表示无限制)
            exclude_system: 是否排除系统数据库 (默认为True)
            
        Returns:
            数据库列表的JSON字符串
        """
        # 参数验证
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
        
        # 构建基础查询
        query = "SHOW DATABASES"
        
        # 执行查询
        with get_db_connection() as connection:
            # 先获取所有数据库
            results = await execute_query(connection, query)
            
            # 通常结果中每个数据库名会在"Database"字段
            db_field = next((k for k in results[0].keys() if k.lower() == 'database'), None) if results else None
            
            if not db_field:
                logger.warning("查询结果未找到数据库名称字段")
                return MetadataToolBase.format_results(results, operation_type="数据库列表查询")
            
            # 对结果进行过滤
            filtered_results = []
            system_dbs = ['information_schema', 'mysql', 'performance_schema', 'sys']
            
            for item in results:
                db_name = item[db_field]
                
                # 排除系统数据库
                if exclude_system and db_name.lower() in system_dbs:
                    continue
                    
                # 根据模式过滤
                if pattern:
                    pattern_regex = pattern.replace('%', '.*').replace('_', '.')
                    if not re.search(pattern_regex, db_name, re.IGNORECASE):
                        continue
                        
                filtered_results.append(item)
            
            # 限制返回数量
            if limit > 0 and len(filtered_results) > limit:
                filtered_results = filtered_results[:limit]
                logger.debug(f"结果数量已限制为前{limit}个")
            
            # 返回结果
            metadata_info = {
                "metadata_info": {
                    "operation_type": "数据库列表查询",
                    "result_count": len(filtered_results),
                    "total_count": len(results),
                    "filtered": {
                        "pattern": pattern,
                        "exclude_system": exclude_system,
                        "limited": len(filtered_results) < len(results)
                    }
                },
                "results": filtered_results
            }
            
            return json.dumps(metadata_info, default=str)
    
    @mcp.tool()
    @MetadataToolBase.handle_query_error
    async def mysql_show_variables(pattern: Optional[str] = None, global_scope: bool = False) -> str:
        """
        获取MySQL系统变量
        
        Args:
            pattern: 变量名称匹配模式 (可选, 例如 '%buffer%')
            global_scope: 是否查询全局变量 (默认为会话变量)
            
        Returns:
            系统变量的JSON字符串
        """
        # 获取当前环境类型
        from src.security.sql_analyzer import sql_analyzer
        env_type = sql_analyzer.env_type
        
        # 检查环境权限
        if not check_environment_permission(env_type, 'variables'):
            raise SecurityError("当前环境不允许查询系统变量")
            
        # 参数验证
        if pattern:
            MetadataToolBase.validate_parameter(
                "pattern", pattern,
                lambda x: re.match(r'^[a-zA-Z0-9_%]+$', x),
                "变量模式只能包含字母、数字、下划线和通配符(%_)"
            )
            
        # 构建查询
        scope = "GLOBAL" if global_scope else "SESSION"
        query = f"SHOW {scope} VARIABLES"
        if pattern:
            query += f" LIKE '{pattern}'"
            
        logger.debug(f"执行查询: {query}")
        
        with get_db_connection() as connection:
            results = await execute_query(connection, query)
            
            # 生产环境中过滤敏感信息
            if env_type == EnvironmentType.PRODUCTION:
                results = filter_sensitive_info(results)
                
            return MetadataToolBase.format_results(results, operation_type="系统变量查询")
    
    @mcp.tool()
    @MetadataToolBase.handle_query_error
    async def mysql_show_status(pattern: Optional[str] = None, global_scope: bool = False) -> str:
        """
        获取MySQL服务器状态
        
        Args:
            pattern: 状态名称匹配模式 (可选, 例如 '%conn%')
            global_scope: 是否查询全局状态 (默认为会话状态)
            
        Returns:
            服务器状态的JSON字符串
        """
        # 获取当前环境类型
        from src.security.sql_analyzer import sql_analyzer
        env_type = sql_analyzer.env_type
        
        # 检查环境权限
        if not check_environment_permission(env_type, 'status'):
            raise SecurityError("当前环境不允许查询系统状态")
            
        # 参数验证
        if pattern:
            MetadataToolBase.validate_parameter(
                "pattern", pattern,
                lambda x: re.match(r'^[a-zA-Z0-9_%]+$', x),
                "状态模式只能包含字母、数字、下划线和通配符(%_)"
            )
            
        # 构建查询
        scope = "GLOBAL" if global_scope else "SESSION"
        query = f"SHOW {scope} STATUS"
        if pattern:
            query += f" LIKE '{pattern}'"
            
        logger.debug(f"执行查询: {query}")
        
        with get_db_connection() as connection:
            results = await execute_query(connection, query)
            
            # 生产环境中过滤敏感信息
            if env_type == EnvironmentType.PRODUCTION:
                results = filter_sensitive_info(results)
                
            return MetadataToolBase.format_results(results, operation_type="服务器状态查询")

# 工具函数: 用于参数验证
def validate_pattern(pattern: str) -> bool:
    """
    验证模式字符串是否安全 (防止SQL注入)
    
    Args:
        pattern: 要验证的模式字符串
        
    Returns:
        如果模式安全返回True，否则抛出ValueError
    
    Raises:
        ValueError: 当模式包含不安全字符时
    """
    # 仅允许字母、数字、下划线和通配符(% 和 _)
    if not re.match(r'^[a-zA-Z0-9_%]+$', pattern):
        raise ValueError("模式只能包含字母、数字、下划线和通配符(%_)")
    return True

def validate_engine_name(name: str) -> bool:
    """
    验证存储引擎名称是否合法安全
    
    Args:
        name: 要验证的引擎名称
        
    Returns:
        如果引擎名称安全返回True，否则抛出ValueError
    
    Raises:
        ValueError: 当引擎名称包含不安全字符时
    """
    # 仅允许字母、数字和下划线
    if not re.match(r'^[a-zA-Z0-9_]+$', name):
        raise ValueError(f"无效的引擎名称: {name}, 引擎名称只能包含字母、数字和下划线")
    return True 