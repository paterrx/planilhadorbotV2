# Arquivo: app/results_updater.py
# Versão: Final - Otimizado para rodar a cada 6 horas e arquivar apostas.

import asyncio
import pandas as pd
import re
import sys
import os
from datetime import datetime
import logging

# Garante que os módulos do app sejam encontrados
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import config
from app.services.sheets_service import SheetsService
from app.services.ai_service import AIService
from app.services.api_football_service import ApiFootballService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def determine_bet_outcome(bet_row: pd.Series, fixture: dict):
    """Determina o resultado (Green/Red) de uma aposta."""
    try:
        score = fixture.get('score', {}).get('fulltime', {})
        home_goals, away_goals = score.get('home'), score.get('away')

        if home_goals is None or away_goals is None: return "Pendente"

        full_text = (str(bet_row.get('Entrada', '')) + " " + str(bet_row.get('Descrição da Aposta', ''))).lower()
        
        home_team_name = fixture['teams']['home']['name'].lower()
        away_team_name = fixture['teams']['away']['name'].lower()
        
        if home_team_name in full_text: return "Green" if home_goals > away_goals else "Red"
        if away_team_name in full_text: return "Green" if away_goals > home_goals else "Red"
        if 'empate' in full_text or 'draw' in full_text: return "Green" if home_goals == away_goals else "Red"
        if 'ambas marcam' in full_text: return "Green" if home_goals > 0 and away_goals > 0 else "Red"
        if 'btts não' in full_text or 'não ambas marcam' in full_text: return "Green" if home_goals == 0 or away_goals == 0 else "Red"
            
        match_over = re.search(r'(?:mais de|acima de|over|\+)\s*(\d[\.,]?\d*)', full_text)
        if match_over:
            limit = float(match_over.group(1).replace(',', '.'))
            return "Green" if (home_goals + away_goals) > limit else "Red"
        
        match_under = re.search(r'(?:menos de|abaixo de|under|-)\s*(\d[\.,]?\d*)', full_text)
        if match_under:
            limit = float(match_under.group(1).replace(',', '.'))
            return "Green" if (home_goals + away_goals) < limit else "Red"
            
        return "Revisão Manual"
    except Exception as e:
        logging.error(f"Erro ao determinar resultado: {e}")
        return "Erro na Análise"

async def main_loop(sheets: SheetsService, api_football: ApiFootballService):
    """Loop principal para o atualizador de resultados."""
    logging.info("Iniciando Módulo de Resultados (Otimizado com Arquivamento)...")
    while True:
        try:
            logging.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Buscando apostas pendentes na aba '{sheets.MAIN_WORKSHEET_NAME}'...")
            
            pending_bets = sheets.get_pending_bets()
            
            if pending_bets is not None and not pending_bets.empty:
                logging.info(f"Encontradas {len(pending_bets)} apostas pendentes para verificação.")
                updates_for_sheets = []
                
                for index, bet in pending_bets.iterrows():
                    row_number = int(bet['row_number'])
                    home_id, away_id = bet.get('Home Team ID'), bet.get('Away Team ID')

                    if home_id and away_id and str(home_id).isdigit() and str(away_id).isdigit():
                        fixture, reason = await api_football.find_match_by_ids(int(home_id), int(away_id), bet.get('Data Completa'))
                        if reason == "Success" and fixture and fixture.get('fixture', {}).get('status', {}).get('short') == 'FT':
                            outcome = determine_bet_outcome(bet, fixture)
                            if outcome != "Pendente":
                                logging.info(f"  -> Linha {row_number}: Resultado encontrado - {outcome}.")
                                updates_for_sheets.append({'row': row_number, 'col_name': 'Situação', 'value': outcome})
                        await asyncio.sleep(7)
                
                if updates_for_sheets:
                    logging.info(f"Enviando {len(updates_for_sheets)} atualizações para o Google Sheets...")
                    sheets.batch_update_cells(updates_for_sheets)
            else:
                logging.info("Nenhuma aposta pendente pronta para verificação no momento.")
            
            # --- LÓGICA DE ARQUIVAMENTO ---
            sheets.archive_completed_bets()

        except Exception as e:
            logging.critical(f"ERRO CRÍTICO no loop do results_updater: {e}")

        logging.info(f"Ciclo concluído. Aguardando 6 horas.")
        await asyncio.sleep(21600)

async def main():
    # Carrega apenas os serviços necessários
    ai_svc = AIService(config) # Necessário para o api_football_service
    sheets_service = SheetsService(config)
    api_football_service = ApiFootballService(config, ai_svc)
    await main_loop(sheets_service, api_football_service)

if __name__ == "__main__":
    asyncio.run(main())