# Arquivo: app/update_channels_list.py
# Descrição: Gera/atualiza o arquivo data/channels.json com a lista de canais do usuário.

import asyncio
import json
import os
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from app.config import config

CHANNELS_JSON_PATH = os.path.join(config.PROJECT_ROOT, 'data', 'channels.json')

async def main():
    print("Conectando ao Telegram para buscar a lista de canais...")
    async with TelegramClient(StringSession(config.TELETHON_SESSION_STRING), int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH) as client:
        dialogs = await client.get_dialogs()
    
    channels = {
        f"{dialog.title} (ID: {dialog.id})": dialog.id 
        for dialog in dialogs if dialog.is_channel
    }
    
    os.makedirs(os.path.dirname(CHANNELS_JSON_PATH), exist_ok=True)
    with open(CHANNELS_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(channels, f, indent=4, ensure_ascii=False)
        
    print(f"✅ Sucesso! {len(channels)} canais foram salvos em data/channels.json")

if __name__ == "__main__":
    asyncio.run(main())