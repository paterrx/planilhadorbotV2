# Arquivo: app/services/bet_processor_service.py
# Versão: 1.1 - Resiliente à falha do Sofascore.

import logging
from telethon.tl.custom import Message
from app.services.ai_service import AIService
from app.services.api_football_service import ApiFootballService
from app.services.sofascore_service import SofascoreService

class BetProcessorService:
    def __init__(self, ai: AIService, api_football: ApiFootballService, sofascore: SofascoreService):
        self.ai = ai
        self.api_football = api_football
        self.sofascore = sofascore

    async def process_message(self, message: Message, channel_name: str):
        logging.info(f"Iniciando processamento para msg ID {message.id} do canal '{channel_name}'")
        image_bytes = await message.download_media(file=bytes) if message.photo else None

        initial_analysis = await self.ai.analyze_message(message.text, image_bytes, channel_name)
        if initial_analysis.get('message_type') != 'nova_aposta':
            logging.warning(f"Msg {message.id} classificada como '{initial_analysis.get('message_type')}'. Ignorando.")
            return None, "Ignored"

        bet_data = initial_analysis.get('data', {})
        entry = bet_data.get('entradas', [{}])[0]
        
        # Tenta obter contexto do Sofascore, mas não depende mais dele
        jogos_brutos = entry.get('jogos_concatenados', entry.get('jogos', ''))
        sofascore_context = self.sofascore.get_team_details_from_search(jogos_brutos.split(' vs ')[0])
        
        data_to_validate = {
            "texto_original_aposta": entry,
            "data_postagem": message.date.strftime('%d/%m/%Y %H:%M'),
            "contexto_sofascore": sofascore_context or "Nenhum contexto adicional encontrado."
        }
        
        validated_data = await self.ai.validate_bet_data(data_to_validate)

        if validated_data and validated_data.get("partida_encontrada"):
            logging.info(f"Validação da IA bem-sucedida para msg {message.id}. Atualizando dados.")
            bet_data['data_evento_completa'] = f"{validated_data['data_oficial']} {validated_data.get('hora_oficial', '12:00')}"
            jogos_corrigidos = f"{validated_data['time_casa_oficial']} vs {validated_data['time_visitante_oficial']}"
            entry['jogos'] = jogos_corrigidos
            entry['jogos_concatenados'] = jogos_corrigidos
            
            fixture, reason = await self.api_football.find_match_by_name(jogos_corrigidos, bet_data['data_evento_completa'])
            if reason == "Success" and fixture:
                bet_data['home_team_id'] = fixture['teams']['home']['id']
                bet_data['away_team_id'] = fixture['teams']['away']['id']
                logging.info(f"IDs da API-Football encontrados para msg {message.id}: {bet_data['home_team_id']}, {bet_data['away_team_id']}")
            else:
                bet_data['home_team_id'] = "NAO_ENCONTRADO_API"
                bet_data['away_team_id'] = "NAO_ENCONTRADO_API"
                logging.warning(f"Partida validada pela IA não encontrada na API-Football (Msg ID: {message.id}). Razão: {reason}")
        else:
            logging.warning(f"Validação da IA falhou para msg {message.id}. Planilhando com dados originais.")
            bet_data['home_team_id'] = ''
            bet_data['away_team_id'] = ''
        
        return {'data': bet_data}, "Success"