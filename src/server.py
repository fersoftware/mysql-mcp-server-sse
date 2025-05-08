from mcp.server.fastmcp import FastMCP
import os
import logging
from dotenv import load_dotenv

# Carrega as variáveis de ambiente - movido para o início para garantir que as variáveis sejam carregadas antes de qualquer importação de módulo
load_dotenv()

# Importa os módulos personalizados - garante que sejam importados após o load_dotenv
from src.tools.mysql_tool import register_mysql_tool
from src.tools.mysql_metadata_tool import register_metadata_tools
from src.tools.mysql_info_tool import register_info_tools
from src.tools.mysql_schema_tool import register_schema_tools

# Configuração de logs
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mysql_server")

# Registra o carregamento das variáveis de ambiente
logger.debug("Variáveis de ambiente carregadas")
logger.debug(f"Níveis de risco permitidos atuais: {os.getenv('ALLOWED_RISK_LEVELS', 'não configurado')}")
logger.debug(f"Tipo de ambiente atual: {os.getenv('ENV_TYPE', 'development')}")
logger.debug(f"Permitir consulta de informações sensíveis: {os.getenv('ALLOW_SENSITIVE_INFO', 'false')}")

# Tenta importar o conector MySQL
try:
    import mysql.connector
    logger.debug("Conector MySQL importado com sucesso")
    mysql_available = True
except ImportError as e:
    logger.critical(f"Não foi possível importar o conector MySQL: {str(e)}")
    logger.critical("Por favor, verifique se o pacote mysql-connector-python está instalado: pip install mysql-connector-python")
    mysql_available = False

# Obtém a configuração do servidor das variáveis de ambiente
host = os.getenv('HOST', '127.0.0.1')
port = int(os.getenv('PORT', '3000'))
logger.debug(f"Configuração do servidor: host={host}, port={port}")

# Cria uma instância do servidor MCP
logger.debug("Criando instância do servidor MCP...")
mcp = FastMCP("Servidor de Consultas MySQL", "cccccccccc", host=host, port=port, debug=True, endpoint='/sse')
logger.debug("Instância do servidor MCP criada com sucesso")

# Registra as ferramentas de consulta MySQL básicas
register_mysql_tool(mcp)

# Registra as ferramentas de consulta de metadados MySQL
register_metadata_tools(mcp)
logger.debug("Ferramentas de consulta de metadados registradas")

# Registra as ferramentas de consulta de informações do banco de dados MySQL
register_info_tools(mcp)
logger.debug("Ferramentas de consulta de informações do banco de dados registradas")

# Registra as ferramentas de consulta avançada de estrutura de tabela MySQL
register_schema_tools(mcp)
logger.debug("Ferramentas de consulta avançada de estrutura de tabela registradas")

def start_server():
    """Wrapper síncrono para iniciar o servidor SSE"""
    logger.debug("Iniciando servidor de consultas MySQL...")
    
    print(f"Iniciando servidor SSE de consultas MySQL...")
    print(f"Servidor escutando em {host}:{port}/sse")
    
    try:
        # Verifica se a configuração do MySQL é válida
        from src.db.mysql_operations import get_db_config
        db_config = get_db_config()
        if mysql_available and not db_config['database']:
            logger.warning("Nome do banco de dados não configurado, verifique a variável de ambiente MYSQL_DATABASE")
            print("Aviso: Nome do banco de dados não configurado, verifique a variável de ambiente MYSQL_DATABASE")
        
        # Inicia o servidor usando a função run_app
        logger.debug("Iniciando servidor com mcp.run('sse')...")
        mcp.run('sse')
    except Exception as e:
        logger.exception(f"Erro durante a execução do servidor: {str(e)}")
        print(f"Erro durante a execução do servidor: {str(e)}")
    
if __name__ == "__main__":
    # Garante que as ferramentas sejam registradas após a inicialização
    start_server()
