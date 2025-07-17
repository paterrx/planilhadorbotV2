# Arquivo: app/main.py
# Descrição: O bot principal do Telegram.
# Versão: 10.1 - Lógica final de enriquecimento de dados antes de planilhar.

import asyncio
import json
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from app.config import config
from app.services.db_service import DbService
from app.services.ai_service import AIService
from app.services.sheets_service import SheetsService
from app.services.api_football_service import ApiFootballService

db = DbService(config)
ai = AIService(config)
sheets = SheetsService(config)
api_football = ApiFootballService(config, ai)

if config.TELETHON_SESSION_STRING:
    session = StringSession(config.TELETHON_SESSION_STRING)
else:
    session = config.SESSION_FILE
client = TelegramClient(session, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH)

@client.on(events.NewMessage(chats=config.TELEGRAM_CHANNEL_IDS))
async def handle_new_message(event):
    message = event.message
    channel_id, message_id, channel_name = event.chat_id, message.id, event.chat.title
    print(f"\n--- Nova Mensagem: {channel_name} ({message_id}) ---")

    if db.is_message_processed(channel_id, message_id):
        print("Mensagem já processada.")
        return

    image_bytes = await message.download_media(file=bytes) if message.photo else None
    
    print("Analisando com a IA...")
    analysis_result = await ai.analyze_message(message.text, image_bytes)
    
    print("--- Resposta da IA (Debug) ---\n", json.dumps(analysis_result, indent=2, ensure_ascii=False), "\n----------------------------")
    
    message_type = analysis_result.get('message_type')
    bet_info = analysis_result.get('data', analysis_result)
    
    if bet_info and ('tipster' not in bet_info or not bet_info.get('tipster')):
        bet_info['tipster'] = channel_name
        
    if message_type == 'nova_aposta':
        message_link = f"https://t.me/c/{str(channel_id).replace('-100', '')}/{message_id}"
        
        home_id, away_id = '', ''
        sport_type = bet_info.get('esporte', '').lower()
        if 'futebol' in sport_type:
            print("  -> Aposta de Futebol. Buscando IDs...")
            entry = bet_info.get('entradas', [{}])[0]
            jogos_str = entry.get('jogos_concatenados', entry.get('jogos', ''))
            data_evento = bet_info.get('data_evento_completa', '')
            
            primeiro_jogo = jogos_str.split(' & ')[0]
            
            if primeiro_jogo and data_evento:
                fixture, reason = await api_football.find_match_by_name(primeiro_jogo, data_evento)
                if reason == "Success" and fixture:
                    home_id = fixture['teams']['home']['id']
                    away_id = fixture['teams']['away']['id']
                    print(f"    -> IDs encontrados para '{primeiro_jogo}': {home_id}, {away_id}")
        
        sheets.write_bet(analysis_result, message_link, home_id, away_id)

    db.add_processed_message(channel_id, message_id)
    print("--- Processamento Concluído ---")

async def main():
    print("Iniciando o PlanilhadorBot v10.1...")
    db.setup_database()
    
    print("Conectando ao Telegram...")
    await client.start()
    print("Bot conectado.")
    
    if not isinstance(client.session, StringSession) and hasattr(client.session, 'save') and client.session.save():
        print("\n--- ATENÇÃO: String de Sessão ---")
        print(f"TELETHON_SESSION_STRING='{client.session.save()}'\n")

    print(f"Ouvindo {len(config.TELEGRAM_CHANNEL_IDS)} canais...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nERRO INESPERADO: {e}")