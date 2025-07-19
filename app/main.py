# Arquivo: app/main.py
# Descrição: O bot principal do Telegram.
# Versão: 12.0 - Implementado sistema de validação com IA em 2 etapas.

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
    print(f"\n--- Nova Mensagem: {channel_name} (ID: {message_id}) ---")

    if db.is_message_processed(channel_id, message_id):
        print("Mensagem já processada. Pulando.")
        return

    image_bytes = await message.download_media(file=bytes) if message.photo else None
    
    # --- ETAPA 1: Extração Inicial ---
    print("Etapa 1: Extraindo dados brutos com a IA...")
    initial_analysis = await ai.analyze_message(message.text, image_bytes)
    
    print("--- Resposta da Extração (Debug) ---\n", json.dumps(initial_analysis, indent=2, ensure_ascii=False), "\n---------------------------------")
    
    if initial_analysis.get('message_type') != 'nova_aposta':
        print(f"Mensagem classificada como '{initial_analysis.get('message_type')}'. Ignorando.")
        db.add_processed_message(channel_id, message_id)
        return

    # --- ETAPA 2: Validação Inteligente ---
    print("Etapa 2: Validando dados da aposta com a IA...")
    final_bet_data = initial_analysis.get('data', {})
    if not final_bet_data:
        print("ERRO: Bloco 'data' não encontrado na análise inicial.")
        db.add_processed_message(channel_id, message_id)
        return
        
    entry = final_bet_data.get('entradas', [{}])[0]
    data_to_validate = {
        "times": entry.get('jogos_concatenados', entry.get('jogos', '')),
        "data_sugerida": final_bet_data.get('data_evento_completa', '')
    }
    
    validated_data = await ai.validate_bet_data(data_to_validate)

    # --- ETAPA 3: Enriquecimento Final ---
    print("Etapa 3: Enriquecendo com dados validados e buscando IDs...")
    if validated_data and validated_data.get("partida_encontrada"):
        print("  -> Validação bem-sucedida. Atualizando dados da aposta.")
        # Atualiza o dicionário original com os dados corrigidos pela IA
        final_bet_data['data_evento_completa'] = f"{validated_data['data_oficial']} {validated_data.get('hora_oficial', '12:00')}"
        
        jogos_corrigidos = f"{validated_data['time_casa_oficial']} vs {validated_data['time_visitante_oficial']}"
        entry['jogos'] = jogos_corrigidos
        entry['jogos_concatenados'] = jogos_corrigidos
        
        # Se o tipster não foi identificado, usa o nome do canal como fallback
        if 'tipster' not in final_bet_data or not final_bet_data.get('tipster'):
            final_bet_data['tipster'] = channel_name
        
        # Busca na API-Football com os dados agora validados
        fixture, reason = await api_football.find_match_by_name(jogos_corrigidos, final_bet_data['data_evento_completa'])
        if reason == "Success" and fixture:
            final_bet_data['home_team_id'] = fixture['teams']['home']['id']
            final_bet_data['away_team_id'] = fixture['teams']['away']['id']
            print(f"  -> IDs da API-Football encontrados: {final_bet_data['home_team_id']}, {final_bet_data['away_team_id']}")
        else:
            final_bet_data['home_team_id'] = "NAO_ENCONTRADO_API"
            final_bet_data['away_team_id'] = "NAO_ENCONTRADO_API"
            print(f"  -> AVISO: Partida validada pela IA não encontrada na API-Football. Razão: {reason}")
    else:
        print("  -> AVISO: Validação da IA falhou. A aposta será planilhada com os dados originais, sem IDs.")
        if 'tipster' not in final_bet_data or not final_bet_data.get('tipster'):
            final_bet_data['tipster'] = channel_name
        final_bet_data['home_team_id'] = ''
        final_bet_data['away_team_id'] = ''
        
    # --- ETAPA 4: Planilhamento ---
    print("Etapa 4: Escrevendo dados finais na planilha.")
    message_link = f"[https://t.me/c/](https://t.me/c/){str(channel_id).replace('-100', '')}/{message_id}"
    sheets.write_bet({'data': final_bet_data}, message_link)

    db.add_processed_message(channel_id, message_id)
    print("--- Processamento Concluído ---")


async def main():
    print("Iniciando o PlanilhadorBot v12.0 (com Validação IA)...")
    db.setup_database()
    await client.start()
    print("Bot conectado e pronto.")
    if not isinstance(client.session, StringSession):
        print("\n--- ATENÇÃO: Nova String de Sessão ---")
        print(f"TELETHON_SESSION_STRING='{client.session.save()}'\n")
    print(f"Monitorando {len(config.TELEGRAM_CHANNEL_IDS)} canais...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())