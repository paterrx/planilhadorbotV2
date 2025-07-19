# Arquivo: app/auditor.py
# Versão: 13.1 - Corrigida a instanciação do BetProcessorService.

import asyncio
import logging
from telethon import TelegramClient
from telethon.sessions import StringSession
import pandas as pd
import re
from telethon.errors.rpcerrorlist import MessageIdInvalidError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

from app.config import config
from app.services.ai_service import AIService
from app.services.sheets_service import SheetsService
from app.services.api_football_service import ApiFootballService
from app.services.google_search_service import GoogleSearchService
from app.services.bet_processor_service import BetProcessorService

class Auditor:
    def __init__(self, cfg, sheets_svc, processor):
        if cfg.TELETHON_SESSION_STRING: 
            session = StringSession(cfg.TELETHON_SESSION_STRING)
        else: 
            session = cfg.SESSION_FILE
        self.client = TelegramClient(session, int(cfg.TELEGRAM_API_ID), cfg.TELEGRAM_API_HASH)
        self.sheets = sheets_svc
        self.processor = processor

    async def find_original_message(self, bet_row):
        link = bet_row.get('Message Link')
        if link and 't.me/c/' in link:
            try:
                match = re.search(r't.me/c/(\d+)/(\d+)', link)
                if match:
                    channel_id = int("-100" + match.group(1))
                    msg_id = int(match.group(2))
                    return await self.client.get_messages(channel_id, ids=msg_id)
            except (ValueError, MessageIdInvalidError):
                logging.warning(f"Link inválido ou mensagem não encontrada para o link: {link}")
            except Exception as e:
                logging.error(f"Erro inesperado ao buscar por link {link}: {e}")
        return None

    async def run_reconstruction(self, source_worksheet_name: str):
        logging.info("Conectando ao Telegram para auditoria...")
        await self.client.connect()
        
        original_df = self.sheets.get_all_bets_from_worksheet(source_worksheet_name)
        if original_df.empty:
            logging.error(f"A aba de origem '{source_worksheet_name}' está vazia. Encerrando.")
            await self.client.disconnect()
            return
            
        reconstructed_rows = []
        unique_bets_df = original_df.drop_duplicates(subset='Bet ID', keep='first').copy()

        for index, bet_row in unique_bets_df.iterrows():
            bet_id = bet_row.get('Bet ID')
            if not bet_id: continue
            
            logging.info(f"Auditando Bet ID {bet_id}...")
            original_message = await self.find_original_message(bet_row)
            
            if not original_message:
                logging.warning(f"  -> Mensagem não encontrada para Bet ID {bet_id}. Mantendo dados originais.")
                reconstructed_rows.append(bet_row.to_dict())
                continue

            processed_bet, status = await self.processor.process_message(original_message, original_message.chat.title)

            if status == "Success" and processed_bet:
                message_link = f"https://t.me/c/{str(original_message.chat_id).replace('-100', '')}/{original_message.id}"
                row_data = self.sheets._format_json_to_row_data(
                    processed_bet, message_link,
                    existing_bet_id=bet_id,
                    existing_status=bet_row.get('Situação', 'Pendente')
                )
                reconstructed_rows.append(row_data)
                logging.info(f"  -> Bet ID {bet_id} re-analisado e corrigido.")
            else:
                logging.warning(f"  -> Re-análise falhou para Bet ID {bet_id}. Mantendo dados originais.")
                reconstructed_rows.append(bet_row.to_dict())

        if reconstructed_rows:
            reconstructed_df = pd.DataFrame(reconstructed_rows)
            if 'Bet ID' in reconstructed_df.columns:
                cols = ['Bet ID'] + [col for col in reconstructed_df.columns if col != 'Bet ID']
                reconstructed_df = reconstructed_df[cols]
            self.sheets.write_reconstructed_sheet(reconstructed_df)
        
        await self.client.disconnect()
        logging.info("Ciclo de auditoria concluído.")

async def main():
    sheets_svc = SheetsService(config)
    ai_svc = AIService(config)
    api_football_svc = ApiFootballService(config, ai_svc)
    google_search_svc = GoogleSearchService()
    processor_svc = BetProcessorService(ai_svc, api_football_svc, google_search_svc)
    
    auditor = Auditor(config, sheets_svc, processor_svc)
    
    aba_para_auditar = sheets_svc._get_current_month_worksheet_name()
    logging.info(f"Iniciando Auditor Reconstrutor v13.1 na aba '{aba_para_auditar}'...")
    await auditor.run_reconstruction(aba_para_auditar)

if __name__ == "__main__":
    asyncio.run(main())