# Arquivo: get_channel_ids.py
# Descrição: Utilitário para listar os IDs de todos os seus canais e grupos.

import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from app.config import config

async def main():
    """
    Este script se conecta à sua conta do Telegram e lista todos os
    seus canais e supergrupos com seus respectivos títulos e IDs.
    """
    print("Iniciando conexão para listar canais...")
    
    if config.TELETHON_SESSION_STRING:
        print("Usando String de Sessão do arquivo .env...")
        session = StringSession(config.TELETHON_SESSION_STRING)
    else:
        print("String de Sessão não encontrada no .env. Usando arquivo 'bot_session' local...")
        session = "bot_session"
    
    async with TelegramClient(session, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH) as client:
        print("Conectado com sucesso. Buscando seus canais e grupos...")
        
        dialogs = await client.get_dialogs()
        
        print("\n--- LISTA DE CANAIS E GRUPOS ---")
        print("Copie os IDs dos canais que você quer monitorar e cole no seu arquivo 'config.json'.\n")
        
        for dialog in dialogs:
            if dialog.is_channel:
                print(f"Nome: {dialog.title:<50} | ID: {dialog.id}")

        print("\n--- FIM DA LISTA ---")


if __name__ == "__main__":
    asyncio.run(main())
