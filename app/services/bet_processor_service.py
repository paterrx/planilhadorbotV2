# Arquivo: app/services/bet_processor_service.py
# Versão: Final - Fluxo simplificado com chamada única de IA.

import logging
from telethon.tl.custom import Message
from app.services.ai_service import AIService
from app.services.api_football_service import ApiFootballService

class BetProcessorService:
    def __init__(self, ai: AIService, api_football: ApiFootballService):
        self.ai = ai
        self.api_football = api_football

    async def process_message(self, message: Message, channel_name: str):
        logging.info(f"Iniciando processamento para msg ID {message.id} do canal '{channel_name}'")
        image_bytes = await message.download_media(file=bytes) if message.photo else None

        # 1. Análise e Validação em Uma Etapa
        analysis_result = await self.ai.analyze_and_validate(message.text, image_bytes, channel_name)
        
        if analysis_result.get('message_type') != 'nova_aposta':
            logging.warning(f"Msg {message.id} classificada como '{analysis_result.get('message_type')}'. Ignorando.")
            return None, "Ignored"

        bet_data = analysis_result.get('data', {})
        entry = bet_data.get('entradas', [{}])[0]
        
        # 2. Busca de IDs com os Dados já Validados
        jogos_text = entry.get('jogos')
        data_evento = bet_data.get('data_evento_completa')

        if jogos_text and data_evento:
            logging.info(f"Buscando IDs para a partida validada: '{jogos_text}'")
            fixture, reason = await self.api_football.find_match_by_name(jogos_text, data_evento)
            
            if reason == "Success" and fixture:
                bet_data['home_team_id'] = fixture['teams']['home']['id']
                bet_data['away_team_id'] = fixture['teams']['away']['id']
                logging.info(f"IDs da API-Football encontrados: {bet_data['home_team_id']}, {bet_data['away_team_id']}")
            else:
                bet_data['home_team_id'] = "NAO_ENCONTRADO"
                bet_data['away_team_id'] = "NAO_ENCONTRADO"
                logging.warning(f"Partida validada pela IA não encontrada na API-Football. Razão: {reason}")
        else:
            bet_data['home_team_id'] = ''
            bet_data['away_team_id'] = ''
            logging.warning(f"Dados de 'jogos' ou 'data_evento_completa' ausentes após análise da IA para msg {message.id}.")
        
        return analysis_result, "Success"