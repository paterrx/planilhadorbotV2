# Arquivo: app/main.py
# Descrição: O bot principal do Telegram.
# Versão: 11.0 - Lógica de enriquecimento de dados aprimorada e centralizada.

import asyncio
import json
from telethon import TelegramClient, events
from telethon.sessions import StringSession

from app.config import config
from app.services.db_service import DbService
from app.services.ai_service import AIService
from app.services.sheets_service import SheetsService
from app.services.api_football_service import ApiFootballService

# --- Inicialização dos Serviços ---
db = DbService(config)
ai = AIService(config)
sheets = SheetsService(config)
api_football = ApiFootballService(config, ai)

# --- Configuração do Cliente Telethon ---
if config.TELETHON_SESSION_STRING:
    session = StringSession(config.TELETHON_SESSION_STRING)
else:
    session = config.SESSION_FILE
client = TelegramClient(session, int(config.TELEGRAM_API_ID), config.TELEGRAM_API_HASH)

@client.on(events.NewMessage(chats=config.TELEGRAM_CHANNEL_IDS))
async def handle_new_message(event):
    """Lida com novas mensagens nos canais monitorados."""
    message = event.message
    channel_id, message_id, channel_name = event.chat_id, message.id, event.chat.title
    print(f"\n--- Nova Mensagem: {channel_name} (ID: {message_id}) ---")

    if db.is_message_processed(channel_id, message_id):
        print("Mensagem já processada anteriormente. Pulando.")
        return

    image_bytes = await message.download_media(file=bytes) if message.photo else None
    
    print("Analisando mensagem com a IA...")
    analysis_result = await ai.analyze_message(message.text, image_bytes)
    
    print("--- Resposta da IA (Debug) ---\n", json.dumps(analysis_result, indent=2, ensure_ascii=False), "\n----------------------------")
    
    message_type = analysis_result.get('message_type')
    
    # Garante que a chave 'data' exista para evitar erros
    if 'data' not in analysis_result:
        analysis_result['data'] = {}
        
    bet_info = analysis_result.get('data')

    # Se o tipster não for identificado pela IA, usa o nome do canal
    if bet_info and ('tipster' not in bet_info or not bet_info.get('tipster')):
        bet_info['tipster'] = channel_name
        
    if message_type == 'nova_aposta':
        print("Tipo: Nova Aposta. Prosseguindo com o enriquecimento de dados...")
        message_link = f"https://t.me/c/{str(channel_id).replace('-100', '')}/{message_id}"
        
        # Inicializa os IDs como vazios no dicionário
        bet_info['home_team_id'] = ''
        bet_info['away_team_id'] = ''
        
        sport_type = bet_info.get('esporte', '').lower()
        if 'futebol' in sport_type:
            print("  -> Aposta de Futebol. Buscando IDs dos times...")
            entry = bet_info.get('entradas', [{}])[0]
            # Usa 'jogos_concatenados' como prioridade, fallback para 'jogos'
            jogos_str = entry.get('jogos_concatenados', entry.get('jogos', ''))
            data_evento = bet_info.get('data_evento_completa', '')
            
            # Pega apenas o primeiro jogo da string para buscar o fixture
            primeiro_jogo = jogos_str.split(' & ')[0]
            
            if primeiro_jogo and data_evento:
                fixture, reason = await api_football.find_match_by_name(primeiro_jogo, data_evento)
                if reason == "Success" and fixture:
                    home_id = fixture['teams']['home']['id']
                    away_id = fixture['teams']['away']['id']
                    print(f"    -> IDs encontrados para '{primeiro_jogo}': Home={home_id}, Away={away_id}")
                    # Adiciona os IDs diretamente ao dicionário da aposta
                    bet_info['home_team_id'] = home_id
                    bet_info['away_team_id'] = away_id
                else:
                    print(f"    -> Não foi possível encontrar os IDs para '{primeiro_jogo}'. Razão: {reason}")
        
        # Envia o dicionário completo e enriquecido para o sheets_service
        sheets.write_bet(analysis_result, message_link)

    db.add_processed_message(channel_id, message_id)
    print("--- Processamento Concluído ---")

async def main():
    """Função principal para iniciar o bot."""
    print("Iniciando o PlanilhadorBot v11.0...")
    db.setup_database()
    
    print("Conectando ao Telegram...")
    await client.start()
    print("Bot conectado e pronto.")
    
    # Salva a string de sessão se for a primeira execução
    if not isinstance(client.session, StringSession) and hasattr(client.session, 'save') and client.session.save():
        print("\n--- ATENÇÃO: Nova String de Sessão Gerada ---")
        print("Copie a linha abaixo e cole no seu arquivo .env para logins futuros:")
        print(f"TELETHON_SESSION_STRING='{client.session.save()}'\n")

    print(f"Monitorando {len(config.TELEGRAM_CHANNEL_IDS)} canais...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nERRO CRÍTICO E INESPERADO no main.py: {e}")