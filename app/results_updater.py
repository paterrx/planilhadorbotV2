# Arquivo: app/results_updater.py
# Versão: 11.2 - Lógica final e robusta, com busca por ID e fallback inteligente por nome.

import asyncio
import pandas as pd
import re
import sys
import os
from datetime import datetime, timedelta

# Garante que os módulos do app sejam encontrados
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.config import config, Config
from app.services.sheets_service import SheetsService
from app.services.ai_service import AIService
from app.services.api_football_service import ApiFootballService

def determine_bet_outcome(bet_row: pd.Series, fixture: dict):
    """
    Determina o resultado (Green/Red) de uma aposta com base no resultado da partida.
    Esta função pode ser expandida com lógicas mais complexas no futuro.
    """
    try:
        score = fixture.get('score', {}).get('fulltime', {})
        home_goals, away_goals = score.get('home'), score.get('away')

        if home_goals is None or away_goals is None:
            return "Pendente"

        # Concatena a descrição e a entrada para ter mais contexto da aposta
        full_text = (str(bet_row.get('Entrada', '')) + " " + str(bet_row.get('Descrição da Aposta', ''))).lower()
        
        home_team_name = fixture['teams']['home']['name'].lower()
        away_team_name = fixture['teams']['away']['name'].lower()
        
        # Lógica simples para vencedor da partida
        if home_team_name in full_text:
            return "Green" if home_goals > away_goals else "Red"
        if away_team_name in full_text:
            return "Green" if away_goals > home_goals else "Red"
        if 'empate' in full_text or 'draw' in full_text:
             return "Green" if home_goals == away_goals else "Red"
        
        # Lógica para Ambas Marcam (BTTS)
        if 'ambas marcam' in full_text:
            return "Green" if home_goals > 0 and away_goals > 0 else "Red"
        if 'btts não' in full_text:
            return "Green" if home_goals == 0 or away_goals == 0 else "Red"
            
        # Lógica para Gols (Over/Under)
        match = re.search(r'(?:mais de|acima de|over|\+)\s*(\d[\.,]?\d*)', full_text)
        if match:
            limit = float(match.group(1).replace(',', '.'))
            return "Green" if (home_goals + away_goals) > limit else "Red"
        
        match = re.search(r'(menos de|abaixo de|under|-)\s*(\d[\.,]?\d*)', full_text)
        if match:
            limit = float(match.group(1).replace(',', '.'))
            return "Green" if (home_goals + away_goals) < limit else "Red"
            
        return "Revisão Manual"
    except Exception as e:
        print(f"  -> Erro ao determinar resultado: {e}")
        return "Erro"

async def main_loop(sheets: SheetsService, api_football: ApiFootballService):
    """
    Loop principal para o atualizador de resultados.
    """
    print("Iniciando Módulo de Resultados v11.2...")
    while True:
        worksheet_name = sheets._get_current_month_worksheet_name()
        print(f"\nBuscando apostas na aba '{worksheet_name}'...")
        
        pending_bets = sheets.get_pending_bets()
        
        if pending_bets is None or pending_bets.empty:
            print("Nenhuma aposta de futebol pendente encontrada para o período verificado.")
        else:
            print(f"Encontradas {len(pending_bets)} apostas de futebol pendentes para verificação.")
            updates_for_sheets = []
            
            for index, bet in pending_bets.iterrows():
                row_number = int(bet['row_number'])
                home_id = bet.get('Home Team ID')
                away_id = bet.get('Away Team ID')
                jogos_str = bet.get('Jogos', '')
                data_str = bet.get('Data Completa')

                print(f"  -> Processando Linha {row_number}: '{jogos_str}'")

                if not jogos_str or not data_str:
                    print("     -> DEBUG: Dados de jogo ou data ausentes. Pulando.")
                    continue
                
                fixture, reason = None, "NoData"
                
                # Estratégia 1: Busca por IDs (preferencial)
                if home_id and away_id and str(home_id).isdigit() and str(away_id).isdigit():
                    print(f"     -> DEBUG: Buscando por IDs: {home_id} vs {away_id} na data {data_str}")
                    fixture, reason = await api_football.find_match_by_ids(int(home_id), int(away_id), data_str)
                
                # Estratégia 2: Fallback para busca por nome (para dados antigos sem ID)
                if not fixture:
                    primeiro_jogo = jogos_str.split(' & ')[0]
                    print(f"     -> DEBUG: Busca por ID falhou ou IDs ausentes. Buscando por nome: '{primeiro_jogo}'")
                    fixture, reason = await api_football.find_match_by_name(primeiro_jogo, data_str)

                # Processa o resultado da busca
                if reason == "Success" and fixture and fixture.get('fixture', {}).get('status', {}).get('short') == 'FT':
                    outcome = determine_bet_outcome(bet, fixture)
                    if outcome != "Pendente":
                        print(f"    -> Resultado: {outcome}. Adicionando à fila de atualização.")
                        updates_for_sheets.append({'row': row_number, 'col_name': 'Situação', 'value': outcome})
                elif reason != "Success" and reason != "NoData":
                    print(f"    -> Não foi possível encontrar a partida ({reason}). Marcando para revisão manual.")
                    updates_for_sheets.append({'row': row_number, 'col_name': 'Situação', 'value': f"Revisão ({reason})"})
                
                # Respeita o limite de chamadas da API
                await asyncio.sleep(7) # ~8 chamadas por minuto, seguro para o plano gratuito.

            if updates_for_sheets:
                print("\nEnviando atualizações em lote para o Google Sheets...")
                sheets.batch_update_cells(updates_for_sheets, worksheet_name)

        print("\nCiclo de atualização concluído. Aguardando 1 hora.")
        await asyncio.sleep(3600)

async def main():
    """Função principal para o robô de resultados."""
    ai_service = AIService(config)
    sheets_service = SheetsService(config)
    api_football_service = ApiFootballService(config, ai_service)
    await main_loop(sheets_service, api_football_service)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nEncerrando o robô de resultados.")
    except Exception as e:
        print(f"ERRO CRÍTICO no results_updater: {e}")