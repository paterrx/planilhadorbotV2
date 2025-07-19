# Arquivo: app/main.py
# Versão: 14.1 - Implementado supervisor de config para atualização de canais em tempo real.

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

# --- Variáveis Globais para Gerenciamento Dinâmico ---
current_handlers = {}

def load_channels_from_config():
    """Lê o arquivo config.json e retorna a lista de IDs de canais."""
    config_path = os.path.join(config.PROJECT_ROOT, 'config.json')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('telegram_channel_ids', [])
    except Exception as e:
        logging.error(f"Não foi possível carregar 'config.json': {e}")
        return []

async def config_reloader_task(client: TelegramClient):
    """Tarefa que roda em segundo plano para verificar mudanças no config.json."""
    global current_handlers
    logging.info("[Supervisor] Iniciado. Verificando config.json a cada 60 segundos.")
    
    # Remove o handler antigo se existir (garante limpeza no início)
    if 'main_handler' in current_handlers:
        client.remove_event_handler(current_handlers['main_handler'])
    
    # Adiciona o handler inicial
    initial_channels = load_channels_from_config()
    handler = client.on(events.NewMessage(chats=initial_channels))(handle_new_message)
    current_handlers['main_handler'] = handler
    logging.info(f"[Supervisor] Handler inicial registrado para {len(initial_channels)} canais.")

    while True:
        await asyncio.sleep(60)
        new_channel_ids = load_channels_from_config()
        
        # Pega os chats do handler atual para comparação
        current_handler_chats = current_handlers['main_handler'].chats or []

        # Compara as listas (convertendo para set para ignorar a ordem)
        if set(new_channel_ids) != set(current_handler_chats):
            logging.warning(f"[Supervisor] Mudança detectada no config.json! Atualizando canais monitorados.")
            
            # Remove o handler antigo
            client.remove_event_handler(current_handlers['main_handler'])
            
            # Adiciona o novo handler com a lista de canais atualizada
            new_handler = client.on(events.NewMessage(chats=new_channel_ids))(handle_new_message)
            current_handlers['main_handler'] = new_handler
            
            logging.info(f"[Supervisor] Handler atualizado. Agora monitorando {len(new_channel_ids)} canais.")

# --- Inicialização dos Serviços ---
db = DbService(config)
ai = AIService(config)
sheets = SheetsService(config)
api_football = ApiFootballService(config, ai)
sofascore = SofascoreService()
processor = BetProcessorService(ai, api_football, sofascore)

# --- Cliente Telethon ---
if config.TELETHON_SESSION_STRING:
    session = StringSession(config.TELETHON_SESSION_STRING)
else:
    session = config.SESSION_FILE
client = TelegramClient(session, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH)

# O handler agora é registrado dinamicamente, então a função fica "sozinha"
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
    logging.info("Iniciando o PlanilhadorBot v14.1 (Supervisor de Config)...")
    db.setup_database()
    await client.start()
    logging.info("Bot conectado e pronto.")
    
    # Inicia a tarefa do supervisor em segundo plano
    asyncio.create_task(config_reloader_task(client))
    
    logging.info(f"Monitorando canais dinamicamente...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())