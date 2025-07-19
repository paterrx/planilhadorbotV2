# Arquivo: app/services/bet_processor_service.py
# Versão: 2.2 - Adicionada "blindagem" contra JSONs malformados da IA (KeyError).

import logging
import json
from telethon.tl.custom import Message
from app.services.ai_service import AIService
from app.services.api_football_service import ApiFootballService
from app.services.google_search_service import GoogleSearchService

class BetProcessorService:
    def __init__(self, ai: AIService, api_football: ApiFootballService, google_search: GoogleSearchService):
        self.ai = ai
        self.api_football = api_football
        self.google_search = google_search

    async def process_message(self, message: Message, channel_name: str):
        logging.info(f"Iniciando processamento para msg ID {message.id} do canal '{channel_name}'")
        image_bytes = await message.download_media(file=bytes) if message.photo else None

        # 1. Extração Inicial
        initial_analysis = await self.ai.initial_extraction(message.text, image_bytes, channel_name)
        if initial_analysis.get('message_type') != 'nova_aposta':
            logging.warning(f"Msg {message.id} classificada como '{initial_analysis.get('message_type')}'. Ignorando.")
            return None, "Ignored"

        bet_data = initial_analysis.get('data', {})
        entry = bet_data.get('entradas', [{}])[0]
        
        # --- NOVA BLINDAGEM ---
        # Verifica se a extração inicial conseguiu encontrar os dados mínimos necessários.
        if not entry or 'jogos' not in entry:
            logging.error(f"A análise inicial da IA para a msg {message.id} falhou em extrair a chave 'jogos'. Pulando aposta.")
            # Retorna os dados que temos para que não quebre a escrita na planilha, mas sem enriquecimento.
            bet_data['home_team_id'] = 'ERRO_IA'
            bet_data['away_team_id'] = 'ERRO_IA'
            return {'data': bet_data}, "ProcessingError"
        # --- FIM DA BLINDAGEM ---

        post_date_str = message.date.strftime('%d/%m/%Y %H:%M')

        # 2. IA Gera a Query de Busca
        search_query = await self.ai.generate_search_query(entry, post_date_str)
        if not search_query:
            logging.warning("IA não conseguiu gerar uma query de busca para msg {message.id}. Usando dados originais.")
            bet_data['home_team_id'] = ''
            bet_data['away_team_id'] = ''
            return {'data': bet_data}, "OriginalData"

        # 3. Executa a Busca na Web
        search_results = self.google_search(search_query)

        # 4. IA Analisa os Resultados da Busca para Validar
        validated_data = await self.ai.analyze_search_results(entry, search_query, search_results, post_date_str)

        # 5. Enriquecimento Final
        if validated_data and validated_data.get("partida_encontrada"):
            logging.info(f"Validação via Pesquisa Ativa bem-sucedida para msg {message.id}.")
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
            logging.warning(f"Pesquisa Ativa falhou para msg {message.id}. Usando dados originais.")
            bet_data['home_team_id'] = ''
            bet_data['away_team_id'] = ''
        
        return {'data': bet_data}, "Success"