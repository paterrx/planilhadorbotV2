# Arquivo: app/services/sheets_service.py
# Versão: 10.2 - Lógica final com get_pending_bets e abas mensais.

import json
from datetime import datetime, timedelta

import gspread
import pandas as pd
from babel.dates import format_date

from app.config import Config

class SheetsService:
    """Gerencia toda a comunicação com a planilha do Google Sheets."""

    EXPECTED_HEADER = [
        'Dia do Mês', 'Tipster', 'Casa de Apostas', 'Tipo de Aposta', 'Jogos',
        'Descrição da Aposta', 'Entrada', 'ESPORTE', 'ODD', 'Unidade/%', 
        'Situação', 'Bet ID', 'Message Link', 'Data Completa', 'Home Team ID', 'Away Team ID'
    ]

    def __init__(self, cfg: Config):
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
            if 'private_key' in creds_json:
                creds_json['private_key'] = creds_json['private_key'].replace('\\n', '\n')
            return gspread.service_account_from_dict(creds_json)
        except Exception as e:
            print(f"ERRO DE AUTENTICAÇÃO COM GOOGLE: {e}")
            return None

    def _get_current_month_worksheet_name(self):
        return format_date(datetime.now(), "MMMM-YYYY", locale='pt_BR').capitalize()

    def _get_or_create_worksheet(self, title):
        try:
            worksheet = self.spreadsheet.worksheet(title)
            header = worksheet.row_values(1)
            if header != self.EXPECTED_HEADER:
                worksheet.update([self.EXPECTED_HEADER], 'A1')
                worksheet.format('A1:P1', {'textFormat': {'bold': True}})
            return worksheet
        except gspread.exceptions.WorksheetNotFound:
            print(f"AVISO: Aba '{title}' não encontrada. Criando uma nova...")
            worksheet = self.spreadsheet.add_worksheet(title=title, rows="1", cols=len(self.EXPECTED_HEADER))
            worksheet.update([self.EXPECTED_HEADER], 'A1')
            worksheet.format('A1:P1', {'textFormat': {'bold': True}})
            return worksheet

    def get_worksheet(self, worksheet_name=None):
        if worksheet_name is None:
            worksheet_name = self._get_current_month_worksheet_name()
        return self._get_or_create_worksheet(worksheet_name)

    def get_all_bets_from_worksheet(self, worksheet_name):
        try:
            worksheet = self.spreadsheet.worksheet(worksheet_name)
            all_values = worksheet.get_all_values()
            if len(all_values) < 2: 
                return pd.DataFrame(columns=self.EXPECTED_HEADER)
            
            header = all_values[0]
            data = all_values[1:]
            
            df = pd.DataFrame(data, columns=header)
            # Adiciona o índice original para referência posterior
            df['original_index'] = df.index
            return df
        except gspread.exceptions.WorksheetNotFound:
            print(f"ERRO: A aba '{worksheet_name}' não foi encontrada para leitura.")
            return pd.DataFrame()
        except Exception as e:
            print(f"Erro ao buscar todas as apostas da aba '{worksheet_name}': {e}")
            return pd.DataFrame()

    def get_pending_bets(self):
        """Busca apostas pendentes da aba do mês atual que já deveriam ter ocorrido."""
        worksheet_name = self._get_current_month_worksheet_name()
        all_bets = self.get_all_bets_from_worksheet(worksheet_name)
        if all_bets.empty: return None

        pending_bets = all_bets[all_bets['Situação'].str.lower() == 'pendente'].copy()
        if pending_bets.empty: return None
        
        pending_bets['event_datetime'] = pd.to_datetime(pending_bets['Data Completa'], format='%d/%m/%Y %H:%M', errors='coerce')
        pending_bets.dropna(subset=['event_datetime'], inplace=True)

        now_with_margin = datetime.now() - timedelta(hours=3)
        past_pending_bets = pending_bets[pending_bets['event_datetime'] <= now_with_margin].copy()
        
        if past_pending_bets.empty: return None

        past_pending_bets['row_number'] = past_pending_bets['original_index'] + 2
        return past_pending_bets
        
    def write_reconstructed_sheet(self, df: pd.DataFrame):
        try:
            worksheet_title = f"APOSTAS_CORRIGIDA_{datetime.now().strftime('%Y%m%d_%H%M')}"
            worksheet = self._get_or_create_worksheet(worksheet_title)
            
            print(f"Escrevendo {len(df)} linhas na nova aba '{worksheet_title}'...")
            df_to_write = df.reindex(columns=self.EXPECTED_HEADER).fillna('')
            worksheet.update([self.EXPECTED_HEADER] + df_to_write.values.tolist(), 'A1', value_input_option='USER_ENTERED')
            print(f"SUCESSO! Planilha reconstruída salva na aba '{worksheet_title}'.")
        except Exception as e:
            print(f"ERRO ao escrever a planilha reconstruída: {e}")

    def batch_update_cells(self, updates: list, worksheet_name=None):
        if not updates: return
        worksheet = self.get_worksheet(worksheet_name)
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
                print(f"  -> {len(updates)} células atualizadas na aba '{worksheet.title}' com sucesso.")
        except Exception as e:
            print(f"ERRO ao executar a atualização em lote na aba '{worksheet.title}': {e}")

    def _format_value(self, value):
        value_str = str(value or '')
        return "'" + value_str if value_str.startswith("=") else value_str

    def _format_json_to_row_data(self, bet_json, message_link, home_id, away_id, existing_bet_id=None, existing_status=None):
        bet_info = bet_json.get('data', bet_json)
        if not bet_info: return None
        
        entry = bet_info.get('entradas', [bet_info])[0]
        
        data_evento_str = bet_info.get('data_evento_completa', "")
        if not data_evento_str:
            data_evento_str = datetime.now().strftime('%d/%m/%Y %H:%M')
            
        dia_do_mes = ''
        try: dia_do_mes = datetime.strptime(data_evento_str.split(' ')[0], '%d/%m/%Y').day
        except (ValueError, IndexError): dia_do_mes = datetime.now().day
        
        bet_id = existing_bet_id or f"bet_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

        row_data = {
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
            'Home Team ID': home_id,
            'Away Team ID': away_id
        }
        
        return {k: self._format_value(v) for k, v in row_data.items()}

    def write_bet(self, bet_json, message_link, home_id, away_id):
        worksheet = self.get_worksheet()
        row_data = self._format_json_to_row_data(bet_json, message_link, home_id, away_id)
        if not row_data: return

        ordered_row = [row_data.get(h, '') for h in self.EXPECTED_HEADER]
        worksheet.append_rows([ordered_row], value_input_option='USER_ENTERED', insert_data_option='INSERT_ROWS', table_range='A1')
        print(f"Aposta para '{row_data.get('Jogos', 'N/A')}' planilhada com sucesso na aba '{worksheet.title}'.")