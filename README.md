# Servidor de Consultas MySQL

Este é um servidor de consultas MySQL baseado no framework MCP (Model-Controller-Provider) que oferece funcionalidades de operações em banco de dados MySQL através do SSE (Server-Sent Events).

## Funcionalidades

- Construído com o framework FastMCP
- Suporte a transmissão de dados em tempo real via SSE (Server-Sent Events)
- Interface de consulta para banco de dados MySQL
- Sistema completo de registro de logs
- Gerenciamento automático de transações (commit/rollback)
- Suporte a configuração via variáveis de ambiente
- Mecanismo de segurança para SQL
  - Controle de níveis de risco
  - Proteção contra injeção de SQL
  - Interceptação de operações perigosas
  - Verificação obrigatória de cláusulas WHERE
  - Retorno automático do número de linhas afetadas
- Mecanismo de proteção de informações sensíveis
- Formatação e aprimoramento automático dos resultados das consultas de metadados

## Funcionalidades da API

O sistema oferece quatro categorias principais de ferramentas:

### Ferramentas de Consulta Básica

- `mysql_query`: Executa consultas SQL arbitrárias, suportando consultas parametrizadas

### Ferramentas de Consulta de Metadados

- `mysql_show_tables`: Obtém lista de tabelas do banco de dados, suportando correspondência por padrão e limitação de resultados
- `mysql_show_columns`: Obtém informações das colunas da tabela
- `mysql_describe_table`: Descreve a estrutura da tabela
- `mysql_show_create_table`: Obtém a declaração de criação da tabela

### Ferramentas de Consulta de Informações do Banco de Dados

- `mysql_show_databases`: Obtém lista de todos os bancos de dados, suportando filtragem de bancos de dados do sistema
- `mysql_show_variables`: Obtém variáveis do servidor MySQL
- `mysql_show_status`: Obtém informações de status do servidor MySQL

### Ferramentas de Consulta Avançada de Estrutura de Tabela

- `mysql_show_indexes`: Obtém informações de índices da tabela
- `mysql_show_table_status`: Obtém informações de status da tabela
- `mysql_show_foreign_keys`: Obtém informações de chaves estrangeiras da tabela
- `mysql_paginate_results`: Fornece funcionalidade de paginação de resultados

## Requisitos do Sistema

- Python 3.6+
- Servidor MySQL
- Dependências:
  - mysql-connector-python
  - python-dotenv
  - mcp (framework FastMCP)

## Passos de Instalação

1. Clone o projeto localmente:
```bash
git clone [URL do projeto]
cd mysql-query-server
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure as variáveis de ambiente:
   - Copie o arquivo `.env.example` e renomeie para `.env`
   - Modifique as configurações no arquivo `.env` conforme necessário

## Configuração de Variáveis de Ambiente

Configure os seguintes parâmetros no arquivo `.env`:

### Configurações Básicas
- `HOST`: Endereço de escuta do servidor (padrão: 127.0.0.1)
- `PORT`: Porta de escuta do servidor (padrão: 3000)
- `MYSQL_HOST`: Endereço do servidor MySQL
- `MYSQL_PORT`: Porta do servidor MySQL
- `MYSQL_USER`: Nome de usuário do MySQL
- `MYSQL_PASSWORD`: Senha do MySQL
- `MYSQL_DATABASE`: Nome do banco de dados MySQL

### Configurações de Segurança do SQL
- `ENV_TYPE`: Tipo de ambiente (development/production)
- `ALLOWED_RISK_LEVELS`: Níveis de risco permitidos (LOW/MEDIUM/HIGH/CRITICAL)
- `BLOCKED_PATTERNS`: Padrões SQL bloqueados (expressões regulares, separados por vírgula)
- `ENABLE_QUERY_CHECK`: Ativar verificação de segurança do SQL (true/false)
- `ALLOW_SENSITIVE_INFO`: Permitir consulta de informações sensíveis (true/false)
- `SENSITIVE_INFO_FIELDS`: Lista de padrões de campos sensíveis personalizados (separados por vírgula)

## Detalhes do Mecanismo de Segurança

### Controle de Níveis de Risco
- LOW: Operações de consulta (SELECT) e operações de metadados (SHOW, DESCRIBE, etc.)
- MEDIUM: Modificações básicas de dados (INSERT, UPDATE/DELETE com WHERE)
- HIGH: Alterações estruturais (CREATE/ALTER) e UPDATE sem WHERE
- CRITICAL: Operações perigosas (DROP/TRUNCATE) e DELETE sem WHERE

### Diferenças entre Ambientes
- Ambiente de Desenvolvimento:
  - Permite operações de risco mais alto
  - Não oculta informações sensíveis
  - Fornece mensagens de erro detalhadas
- Ambiente de Produção:
  - Permite apenas operações de risco LOW por padrão
  - Restringe estritamente modificações de dados
  - Oculta automaticamente informações sensíveis
  - Mensagens de erro não expõem detalhes de implementação

### Proteção de Informações Sensíveis
O sistema detecta e oculta automaticamente variáveis/valores de status que contêm as seguintes palavras-chave:
- password, auth, credential, key, secret, private
- ssl, tls, cipher, certificate
- host, path, directory e outras informações de caminho do sistema

### Gerenciamento de Transações
- Transações são submetidas automaticamente para operações de modificação (INSERT/UPDATE/DELETE)
- Transações são revertidas automaticamente em caso de erro
- Retorna o número de linhas afetadas pela operação

## Iniciando o Servidor

Execute o comando abaixo para iniciar o servidor:

```bash
python src/server.py
```

O servidor será iniciado no endereço e porta configurados, por padrão em `http://127.0.0.1:3000/sse`

## Estrutura do Projeto

```
.
├── src/                     # Diretório de código-fonte
│   ├── server.py           # Arquivo principal do servidor
│   ├── db/                 # Código relacionado ao banco de dados
│   │   └── mysql_operations.py # Implementação de operações MySQL
│   ├── security/           # Código relacionado à segurança SQL
│   │   ├── interceptor.py   # Interceptor SQL
│   │   ├── query_limiter.py # Verificador de segurança SQL
│   │   └── sql_analyzer.py  # Analisador SQL
│   └── tools/              # Código de ferramentas
│       ├── mysql_tool.py           # Ferramentas de consulta básica
│       ├── mysql_metadata_tool.py  # Ferramentas de consulta de metadados
│       ├── mysql_info_tool.py      # Ferramentas de consulta de informações do banco de dados
│       ├── mysql_schema_tool.py    # Ferramentas de consulta avançada de estrutura de tabela
│       └── metadata_base_tool.py   # Classe base para ferramentas de metadados
├── tests/                  # Diretório de código de testes
├── .env.example            # Arquivo de exemplo de variáveis de ambiente
└── requirements.txt        # Arquivo de dependências do projeto
```

## Solução de Problemas Comuns

### Operação DELETE não executada com sucesso
- Verifique se a operação DELETE contém uma cláusula WHERE
- Operações DELETE sem WHERE são marcadas como nível de risco CRITICAL
- Certifique-se de que o nível CRITICAL está incluído em ALLOWED_RISK_LEVELS (se precisar executar a operação)
- Verifique o valor retornado de linhas afetadas para confirmar se a operação realmente afetou o banco de dados

### Variáveis de ambiente não estão funcionando
- Certifique-se de que a chamada load_dotenv() em server.py ocorre antes da importação de outros módulos
- Reinicie o aplicativo para garantir que as variáveis de ambiente sejam carregadas corretamente
- Verifique a saída do log "Configurações de nível de risco lidas das variáveis de ambiente"

### Operação foi rejeitada pelo mecanismo de segurança
- Verifique se o nível de risco da operação está dentro do permitido
- Se precisar executar uma operação de alto risco, ajuste o ALLOWED_RISK_LEVELS accordingly
- Para UPDATE ou DELETE sem WHERE, adicione uma condição (mesmo que WHERE 1=1) para reduzir o nível de risco

### Não é possível visualizar informações sensíveis
- No ambiente de desenvolvimento, configure ALLOW_SENSITIVE_INFO=true
- No ambiente de produção, as informações sensíveis são ocultadas por padrão, esta é uma característica de segurança

## Sistema de Logs

O servidor inclui um sistema completo de registro de logs, onde você pode visualizar o estado de execução e mensagens de erro tanto no console quanto nos arquivos de log. Os níveis de log podem ser configurados em `server.py`.

## Tratamento de Erros

O servidor inclui um mecanismo completo de tratamento de erros:
- Verificação de importação do conector MySQL
- Validação da configuração do banco de dados
- Verificação de segurança do SQL
- Captura e registro de erros em tempo de execução
- Reversão automática de transações

## Cliente de Teste

O projeto inclui um cliente de teste (`test_client.py`) que demonstra como se conectar ao servidor e executar consultas MySQL. As melhorias recentes incluem:

- Melhor tratamento da sessão SSE:
  - Verificação dupla do ping da sessão
  - Espera adequada para inicialização completa do servidor
  - Tratamento de erros mais robusto
  - Melhor log de eventos SSE

- Melhorias no envio de consultas:
  - Espaçamento adequado entre consultas
  - Verificação de status da sessão antes de enviar consultas
  - Tratamento de respostas SSE mais robusto
  - Timeout ajustado para receber todas as respostas

## Guia de Contribuição

Sinta-se à vontade para enviar Issues e Pull Requests para melhorar o projeto.

## Licença

MIT License

Copyright (c) 2024 MCP MySQL Query Server

特此免费授予任何获得本软件副本和相关文档文件（"软件"）的人不受限制地处理本软件的权利，包括不受限制地使用、复制、修改、合并、发布、分发、再许可和/或出售本软件副本，以及允许本软件的使用者这样做，但须符合以下条件：
上述版权声明和本许可声明应包含在本软件的所有副本或重要部分中。

本软件按"原样"提供，不提供任何形式的明示或暗示的保证，包括但不限于对适销性、特定用途的适用性和非侵权性的保证。在任何情况下，作者或版权持有人均不对任何索赔、损害或其他责任负责，无论是在合同诉讼、侵权行为还是其他方面，产生于、源于或与本软件有关，或与本软件的使用或其他交易有关。