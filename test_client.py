import asyncio
import aiohttp
import json
import time

async def test_mysql_query():
    """Testa a conexão com o servidor MySQL através da API SSE"""
    try:
        print("Iniciando conexão com o servidor...")
        
        # Configurações do servidor
        host = "localhost"
        port = 3000
        sse_url = f"http://{host}:{port}/sse"
        messages_url = f"http://{host}:{port}/messages/"
        
        print(f"Conectando ao servidor SSE em {sse_url}...")
        
        # Conecta ao servidor SSE para obter o session_id
        async with aiohttp.ClientSession() as session:
            async with session.get(sse_url) as response:
                print(f"Status da conexão: {response.status}")
                
                # Verifica se a conexão foi bem sucedida
                if response.status != 200:
                    print(f"Erro ao conectar ao servidor: {response.status}")
                    return
                
                print("Lendo eventos SSE...")
                
                # Lê as linhas do SSE
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    print(f"Linha recebida: {line}")
                    
                    # Processa a linha
                    if line.startswith('data: '):
                        data = line[6:]
                        print(f"Recebido: {data}")
                        
                        # Verifica se é o session_id
                        if 'session_id=' in data:
                            session_id = data.split('=')[-1]
                            print(f"Session ID: {session_id}")
                            break
                
                if not session_id:
                    print("Erro: não foi possível obter o session_id")
                    return
                
                # Aguarda um momento adicional para garantir inicialização completa
                print("\nAguardando 15 segundos para garantir inicialização completa do servidor...")
                await asyncio.sleep(15)
                
                # Verifica se a sessão está ativa enviando uma requisição de ping
                print("\nVerificando se a sessão está ativa...")
                async with session.get(f"{sse_url}?session_id={session_id}") as ping_response:
                    if ping_response.status != 200:
                        print(f"Aviso: Status da sessão: {ping_response.status}")
                        
                    # Lê todas as linhas da resposta
                    sse_content = await ping_response.text()
                    print(f"Conteúdo SSE: {sse_content}")
                    
                    # Verifica se recebemos o ping de resposta
                    ping_received = False
                    for line in sse_content.split('\n'):
                        if line.startswith('data: '):
                            data = line[6:]
                            if 'ping' in data:
                                ping_received = True
                                print("Ping recebido com sucesso!")
                                break
                    
                    if not ping_received:
                        print("Aviso: Não recebido ping de resposta da sessão")
                        # Aguarda mais um pouco e tenta novamente
                        print("Aguardando mais 5 segundos...")
                        await asyncio.sleep(5)
                        
                        # Tenta novamente
                        async with session.get(f"{sse_url}?session_id={session_id}") as second_ping:
                            if second_ping.status != 200:
                                raise Exception(f"Sessão não está ativa após segunda tentativa: {second_ping.status}")
                                
                            second_content = await second_ping.text()
                            print(f"Segunda tentativa - Conteúdo SSE: {second_content}")
                            
                            # Verifica novamente o ping
                            for line in second_content.split('\n'):
                                if line.startswith('data: '):
                                    data = line[6:]
                                    if 'ping' in data:
                                        ping_received = True
                                        print("Ping recebido na segunda tentativa!")
                                        break
                            
                            if not ping_received:
                                raise Exception("Não recebido ping de resposta da sessão após duas tentativas")
                
                # Agora que temos certeza que a sessão está ativa, vamos enviar as queries
                print("\nSessão ativa. Iniciando envio de queries...")
                
                # Constrói o URL completo com session_id
                full_url = f"http://{host}:{port}/messages/?session_id={session_id}"
                print(f"URL completo: {full_url}")
                
                # Envia consulta SELECT
                print("\nEnviando consulta SELECT...")
                async with session.post(full_url, json={
                    'jsonrpc': '2.0',
                    'id': 1,
                    'method': 'tools/call',
                    'params': {
                        'name': 'mysql_query',
                        'params': {'query': 'SELECT 1'}
                    }
                }) as response:
                    print(f"Status da consulta SELECT: {response.status}")
                    result = await response.text()
                    print(f"Resultado da consulta SELECT: {result}")
                
                # Aguarda um pouco antes de enviar a próxima query
                await asyncio.sleep(2)
                
                # Envia consulta de metadados
                print("Enviando consulta de metadados...")
                async with session.post(full_url, json={
                    'jsonrpc': '2.0',
                    'id': 2,
                    'method': 'tools/call',
                    'params': {
                        'name': 'mysql_show_tables',
                        'params': {'pattern': '%'}
                    }
                }) as response:
                    print(f"Status da consulta de metadados: {response.status}")
                    result = await response.text()
                    print(f"Resultado da consulta de metadados: {result}")
                
                # Aguarda as respostas SSE
                print("\nAguardando respostas SSE...")
                async with session.get(f"{sse_url}?session_id={session_id}") as sse_response:
                    # Mantém a conexão aberta por 60 segundos para receber todas as respostas
                    timeout = 60
                    start_time = time.time()
                    
                    # Lista para armazenar todas as respostas
                    responses = []
                    
                    while time.time() - start_time < timeout:
                        line = await sse_response.content.readline()
                        if not line:
                            break
                            
                        line = line.decode('utf-8').strip()
                        print(f"Recebido: {line}")
                        
                        if line.startswith('data: '):
                            data = line[6:]
                            try:
                                message = json.loads(data)
                                if isinstance(message, dict) and 'id' in message:
                                    responses.append(message)
                                    print(f"\nResultado da consulta {message['id']}: {message}")
                            except json.JSONDecodeError as e:
                                print(f"Erro ao decodificar mensagem: {str(e)}")
                        
                        # Aguarda um pouco entre as leituras
                        await asyncio.sleep(0.1)
                    
                    # Verifica se recebemos todas as respostas esperadas
                    expected_ids = {1, 2}  # IDs das nossas queries
                    received_ids = {msg['id'] for msg in responses}
                    
                    if expected_ids.issubset(received_ids):
                        print("\nTodas as respostas foram recebidas com sucesso!")
                    else:
                        missing_ids = expected_ids - received_ids
                        print(f"\nAviso: Faltaram respostas para as queries com IDs: {missing_ids}")
                    
                    print("\nFechando conexão SSE após 60 segundos...")
                    sse_response.close()
                
    except Exception as e:
        print(f"Erro ao testar o servidor: {str(e)}")

if __name__ == "__main__":
    # Executa o teste
    asyncio.run(test_mysql_query())
