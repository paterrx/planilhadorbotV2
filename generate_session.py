# Arquivo: generate_session.py
# Descrição: Script dedicado para gerar a Telethon Session String de forma segura.

import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Tente carregar as credenciais do .env ou insira manualmente
try:
    from dotenv import load_dotenv
    import os
    load_dotenv()
    API_ID = os.getenv('TELEGRAM_API_ID')
    API_HASH = os.getenv('TELEGRAM_API_HASH')
except ImportError:
    API_ID = input("Digite seu TELEGRAM_API_ID: ")
    API_HASH = input("Digite seu TELEGRAM_API_HASH: ")

async def main():
    print("Iniciando o processo de geração de String de Sessão...")
    async with TelegramClient(StringSession(), int(API_ID), API_HASH) as client:
        session_string = client.session.save()
        print("\n--- SESSÃO GERADA COM SUCESSO! ---")
        print("Copie a string abaixo (incluindo as aspas simples) e cole no seu .env e nas variáveis do Railway.\n")
        print(f"TELETHON_SESSION_STRING='{session_string}'")
        print("\nProcesso concluído. Você já pode fechar este script.")

if __name__ == "__main__":
    # Adiciona a dependência 'python-dotenv' se não estiver instalada
    try:
        import dotenv
    except ImportError:
        print("Instalando 'python-dotenv' para ler o arquivo .env...")
        import subprocess
        import sys
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])

    asyncio.run(main())