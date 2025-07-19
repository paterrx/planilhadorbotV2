# Arquivo: app/services/sheets_service.py
# Versão: Final - Lógica para aba principal "APOSTAS" e arquivamento automático.

import json
from datetime import datetime, timedelta
import gspread
import pandas as pd
from babel.dates import format_date
import logging
from app.config import config

class SheetsService:
    EXPECTED_HEADER = [
        'Dia do Mês', 'Tipster', 'Casa de Apostas', 'Tipo de Aposta', 'Jogos',
        'Descrição da Aposta', 'Entrada', 'ESPORTE', 'ODD', 'Unidade/%', 
        'Situação', 'Bet ID', 'Message Link', 'Data Completa', 'Home Team ID', 'Away Team ID'
    ]
    MAIN_WORKSHEET_NAME = "APOSTAS"

    def __init__(self, cfg: config):
        self.config = cfg
        self.client = self._authenticate()
        if not self.client:
            raise RuntimeError("Não foi possível autenticar com o Google Sheets.")
        self.spreadsheet = self.client.open_by_key(self.config.SPREADSHEET_ID)

    def _authenticate(self):
        try:
            creds_json_str = self.config.GOOGLE_CREDENTIALS_JSON
            if not creds_json_str: raise ValueError("GOOGLE_CREDENTIALS_JSON no .env está vazio.")
            creds_json = json.loads(creds_json_str)
            creds_json['private_key'] = creds_json['private_key'].replace('\\n', '\n')
            return gspread.service_account_from_dict(creds_json)
        except Exception as e:
            logging.error(f"ERRO DE AUTENTICAÇÃO COM GOOGLE: {e}")
            return None

    def _get_or_create_worksheet(self, title):
        try:
            worksheet = self.spreadsheet.worksheet(title)
        except gspread.exceptions.WorksheetNotFound:
            logging.warning(f"Aba '{title}' não encontrada. Criando uma nova...")
            worksheet = self.spreadsheet.add_worksheet(title=title, rows="1", cols=len(self.EXPECTED_HEADER))
        
        # Garante que o cabeçalho esteja correto
        header = worksheet.row_values(1)
        if header != self.EXPECTED_HEADER:
            worksheet.update([self.EXPECTED_HEADER], 'A1')
            worksheet.format('A1:P1', {'textFormat': {'bold': True}})
        return worksheet

    def get_all_records_from_worksheet(self, worksheet_name):
        try:
            worksheet = self.spreadsheet.worksheet(worksheet_name)
            return worksheet.get_all_records()
        except gspread.exceptions.WorksheetNotFound:
            logging.warning(f"A aba '{worksheet_name}' não foi encontrada para leitura.")
            return []
        except Exception as e:
            logging.error(f"Erro ao buscar todos os registros da aba '{worksheet_name}': {e}")
            return []

    def get_pending_bets(self):
        all_records = self.get_all_records_from_worksheet(self.MAIN_WORKSHEET_NAME)
        if not all_records: return None
        
        df = pd.DataFrame(all_records)
        if df.empty: return None

        df['row_number'] = df.index + 2
        
        pending_bets = df[df['Situação'].astype(str).str.strip().str.lower() == 'pendente'].copy()
        if pending_bets.empty: return None

        pending_bets['event_datetime'] = pd.to_datetime(pending_bets['Data Completa'], dayfirst=True, errors='coerce')
        valid_dates_bets = pending_bets.dropna(subset=['event_datetime']).copy()

        check_time = datetime.now() - timedelta(hours=self.config.RESULT_CHECK_HOURS_AGO)
        return valid_dates_bets[valid_dates_bets['event_datetime'] <= check_time]

    def _format_json_to_row_data(self, bet_json, message_link, existing_bet_id=None, existing_status=None):
        bet_info = bet_json.get('data', bet_json)
        if not bet_info: return None
        
        entry = bet_info.get('entradas', [{}])[0]
        
        data_evento_str = bet_info.get('data_evento_completa', "")
        if data_evento_str:
            try:
                dia_do_mes = datetime.strptime(data_evento_str.split(' ')[0], '%d/%m/%Y').day
            except (ValueError, IndexError):
                dia_do_mes = datetime.now().day
        else:
            dia_do_mes = datetime.now().day
        
        bet_id = existing_bet_id or f"bet_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        return {
            'Dia do Mês': dia_do_mes,
            'Tipster': bet_info.get('tipster'),
            'Casa de Apostas': bet_info.get('casa_de_aposta'),
            'Tipo de Aposta': bet_info.get('tipo_aposta'),
            'Jogos': entry.get('jogos_concatenados', entry.get('jogos')),
            'Descrição da Aposta': entry.get('descricao_concatenada', entry.get('descricao_aposta')),
            'Entrada': entry.get('entrada_concatenada', entry.get('entrada')),
            'ESPORTE': bet_info.get('esporte'),
            'ODD': entry.get('odd'),
            'Unidade/%': entry.get('unidade_percentual'),
            'Situação': existing_status or bet_info.get('situacao', 'Pendente'),
            'Bet ID': bet_id,
            'Message Link': message_link,
            'Data Completa': data_evento_str,
            'Home Team ID': bet_info.get('home_team_id'),
            'Away Team ID': bet_info.get('away_team_id')
        }

    def write_bet(self, bet_json, message_link):
        worksheet = self._get_or_create_worksheet(self.MAIN_WORKSHEET_NAME)
        row_data = self._format_json_to_row_data(bet_json, message_link)
        if not row_data: return
        
        ordered_row = [str(row_data.get(h, '')) for h in self.EXPECTED_HEADER]
        worksheet.append_row(ordered_row, value_input_option='USER_ENTERED')
        logging.info(f"Aposta para '{row_data.get('Jogos')}' planilhada com sucesso na aba '{worksheet.title}'.")
    
    def batch_update_cells(self, updates: list):
        if not updates: return
        worksheet = self._get_or_create_worksheet(self.MAIN_WORKSHEET_NAME)
        try:
            header = worksheet.row_values(1)
            col_map = {name: i + 1 for i, name in enumerate(header)}
            batch_requests = []
            for update in updates:
                row, col_name, value = update.get('row'), update.get('col_name'), update.get('value')
                if not all([row, col_name, value is not None]): continue
                col_index = col_map.get(col_name)
                if col_index:
                    cell_a1 = gspread.utils.rowcol_to_a1(row, col_index)
                    batch_requests.append({'range': cell_a1, 'values': [[value]]})
            
            if batch_requests:
                worksheet.batch_update(batch_requests, value_input_option='USER_ENTERED')
                logging.info(f"{len(updates)} células atualizadas na aba '{worksheet.title}' com sucesso.")
        except Exception as e:
            logging.error(f"Erro ao executar a atualização em lote: {e}")

    def write_reconstructed_sheet(self, df: pd.DataFrame, title: str):
        worksheet = self._get_or_create_worksheet(title)
        logging.info(f"Escrevendo {len(df)} linhas na aba de reconstrução '{title}'...")
        df_to_write = df.reindex(columns=self.EXPECTED_HEADER).fillna('')
        worksheet.update([self.EXPECTED_HEADER] + df_to_write.values.tolist(), 'A1', value_input_option='USER_ENTERED')
        logging.info(f"Planilha reconstruída salva com sucesso na aba '{title}'.")
        
    def archive_completed_bets(self):
        logging.info("Iniciando processo de arquivamento de apostas finalizadas...")
        main_sheet = self._get_or_create_worksheet(self.MAIN_WORKSHEET_NAME)
        all_records = main_sheet.get_all_records()
        if not all_records:
            logging.info("Nenhuma aposta para arquivar.")
            return

        df = pd.DataFrame(all_records)
        df['row_number'] = df.index + 2
        
        completed_statuses = ['green', 'red', 'revisão manual', 'erro na análise', 'erro ia']
        completed_bets = df[df['Situação'].str.lower().isin(completed_statuses)].copy()
        if completed_bets.empty:
            logging.info("Nenhuma aposta finalizada para arquivar.")
            return

        completed_bets['event_date'] = pd.to_datetime(completed_bets['Data Completa'], dayfirst=True, errors='coerce')
        completed_bets.dropna(subset=['event_date'], inplace=True)
        
        bets_by_month = completed_bets.groupby(completed_bets['event_date'].dt.to_period('M'))
        
        rows_to_delete = []
        for period, bets_in_month in bets_by_month:
            month_sheet_name = format_date(period.to_timestamp(), "MMMM-YYYY", locale='pt_BR').capitalize()
            if month_sheet_name == self.MAIN_WORKSHEET_NAME: continue # Não arquiva na própria aba
            
            logging.info(f"Arquivando {len(bets_in_month)} apostas para '{month_sheet_name}'...")
            month_sheet = self._get_or_create_worksheet(month_sheet_name)
            
            bets_to_write_df = bets_in_month.reindex(columns=self.EXPECTED_HEADER).fillna('')
            rows_to_append = bets_to_write_df.values.tolist()
            month_sheet.append_rows(rows_to_append, value_input_option='USER_ENTERED')
            
            rows_to_delete.extend(bets_in_month['row_number'].tolist())

        if rows_to_delete:
            logging.info(f"Removendo {len(rows_to_delete)} linhas arquivadas da aba '{self.MAIN_WORKSHEET_NAME}'...")
            # Deleta as linhas em lotes, da última para a primeira
            for row_num in sorted(rows_to_delete, reverse=True):
                try:
                    main_sheet.delete_rows(row_num)
                except Exception as e:
                    logging.error(f"Erro ao deletar linha {row_num}: {e}")
        
        logging.info("Processo de arquivamento concluído.")