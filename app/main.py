# Arquivo: app/main.py
# Versão: 14.2 - Corrigido o bug no supervisor de config para atualização de canais.

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

# --- Lógica de Gerenciamento Dinâmico de Canais ---
current_monitored_channels = set()

def load_channels_from_config():
    config_path = os.path.join(config.PROJECT_ROOT, 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(data.get('telegram_channel_ids', []))
    except Exception as e:
        logging.error(f"Não foi possível carregar 'config.json': {e}")
        return set()

async def config_reloader_task(client: TelegramClient):
    global current_monitored_channels
    logging.info("[Supervisor] Iniciado. Verificando config.json a cada 60 segundos.")
    
    while True:
        await asyncio.sleep(60)
        new_channel_ids = load_channels_from_config()
        
        if new_channel_ids != current_monitored_channels:
            logging.warning(f"[Supervisor] Mudança detectada no config.json! Atualizando canais.")
            
            # Remove handlers para canais que não estão mais na lista
            channels_to_remove = current_monitored_channels - new_channel_ids
            for channel_id in channels_to_remove:
                client.remove_event_handler(handle_new_message, events.NewMessage(chats=[channel_id]))
            
            # Adiciona handlers para novos canais
            channels_to_add = new_channel_ids - current_monitored_channels
            for channel_id in channels_to_add:
                client.add_event_handler(handle_new_message, events.NewMessage(chats=[channel_id]))

            current_monitored_channels = new_channel_ids
            logging.info(f"[Supervisor] Monitoramento atualizado para {len(current_monitored_channels)} canais.")

# --- Inicialização dos Serviços ---
db = DbService(config)
ai = AIService(config)
sheets = SheetsService(config)
api_football = ApiFootballService(config, ai)
sofascore = SofascoreService()
processor = BetProcessorService(ai, api_football, sofascore)

# --- Cliente Telethon ---
if not config.TELETHON_SESSION_STRING:
    raise ValueError("TELETHON_SESSION_STRING não está definida no .env!")
session = StringSession(config.TELETHON_SESSION_STRING)
client = TelegramClient(session, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH)

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
    logging.info("Iniciando o PlanilhadorBot v14.2 (Supervisor Corrigido)...")
    db.setup_database()
    
    # Adiciona os handlers iniciais
    global current_monitored_channels
    current_monitored_channels = load_channels_from_config()
    client.add_event_handler(handle_new_message, events.NewMessage(chats=list(current_monitored_channels)))
    
    await client.start()
    logging.info("Bot conectado e pronto.")
    
    # Inicia a tarefa do supervisor
    asyncio.create_task(config_reloader_task(client))
    
    logging.info(f"Monitorando {len(current_monitored_channels)} canais dinamicamente...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())