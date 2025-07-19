# Arquivo: app/main.py
# Versão: 14.0 - Versão final com monitoramento dinâmico e BetProcessorService.

import asyncio
import logging
import json
import os
from telethon import TelegramClient, events
from telethon.sessions import StringSession

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from app.config import config
from app.services.db_service import DbService
from app.services.ai_service import AIService
from app.services.sheets_service import SheetsService
from app.services.api_football_service import ApiFootballService
from app.services.sofascore_service import SofascoreService
from app.services.bet_processor_service import BetProcessorService

def get_monitored_channels():
    config_path = os.path.join(config.PROJECT_ROOT, 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            ids = data.get('telegram_channel_ids', [])
            logging.info(f"Carregando {len(ids)} canais do config.json para monitoramento.")
            return ids
    except Exception as e:
        logging.error(f"Não foi possível carregar 'config.json': {e}")
        return []

db = DbService(config)
ai = AIService(config)
sheets = SheetsService(config)
api_football = ApiFootballService(config, ai)
sofascore = SofascoreService()
processor = BetProcessorService(ai, api_football, sofascore)

if config.TELETHON_SESSION_STRING:
    session = StringSession(config.TELETHON_SESSION_STRING)
else:
    session = config.SESSION_FILE
client = TelegramClient(session, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH)

@client.on(events.NewMessage(chats=get_monitored_channels))
async def handle_new_message(event):
    message = event.message
    channel_id, message_id, channel_name = event.chat_id, message.id, event.chat.title

    if db.is_message_processed(channel_id, message_id):
        return

    processed_bet, status = await processor.process_message(message, channel_name)
    
    if status == "Success" and processed_bet:
        message_link = f"https://t.me/c/{str(channel_id).replace('-100', '')}/{message_id}"
        sheets.write_bet(processed_bet, message_link)

    db.add_processed_message(channel_id, message_id)
    logging.info(f"--- Processamento da Mensagem {message_id} Concluído ---")

async def main():
    logging.info("Iniciando o PlanilhadorBot v14.0 (Arquitetura Inteligente)...")
    db.setup_database()
    await client.start()
    logging.info("Bot conectado e pronto.")
    if not isinstance(client.session, StringSession):
        logging.warning(f"--- ATENÇÃO: Nova String de Sessão --- \nTELETHON_SESSION_STRING='{client.session.save()}'")
    logging.info(f"Monitorando canais dinamicamente...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())