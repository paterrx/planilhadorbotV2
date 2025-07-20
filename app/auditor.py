# Arquivo: app/auditor.py
# Versão: 14.1 - Corrigido TypeError na instanciação do BetProcessorService.

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
from app.services.bet_processor_service import BetProcessorService
# A importação do Google Search_service não é mais necessária aqui.

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
            except Exception:
                return None
        return None

    async def run_reconstruction(self, source_worksheet_name: str):
        logging.info("Conectando ao Telegram para auditoria...")
        await self.client.connect()
        
        all_records = self.sheets.get_all_records_from_worksheet(source_worksheet_name)
        if not all_records:
            logging.error(f"A aba de origem '{source_worksheet_name}' está vazia. Encerrando.")
            await self.client.disconnect()
            return
        
        original_df = pd.DataFrame(all_records)
        reconstructed_rows = []
        
        logging.info(f"Iniciando auditoria de {len(original_df)} apostas da aba '{source_worksheet_name}'...")

        for index, bet_row in original_df.iterrows():
            bet_id = bet_row.get('Bet ID')
            if not bet_id: continue
            
            logging.info(f"Auditando Bet ID {bet_id}...")
            
            try:
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
            except Exception as e:
                logging.error(f"  -> Erro crítico ao auditar Bet ID {bet_id}: {e}. Mantendo dados originais.")
                reconstructed_rows.append(bet_row.to_dict())

        if reconstructed_rows:
            reconstructed_df = pd.DataFrame(reconstructed_rows)
            self.sheets.write_reconstructed_sheet(reconstructed_df, f"{source_worksheet_name}_CORRIGIDA")
        
        await self.client.disconnect()
        logging.info("Ciclo de auditoria concluído.")

async def main():
    sheets_svc = SheetsService(config)
    ai_svc = AIService(config)
    api_football_svc = ApiFootballService(config, ai_svc)
    # CORREÇÃO: Removido o Google Search_svc daqui.
    processor_svc = BetProcessorService(ai_svc, api_football_svc)
    
    auditor = Auditor(config, sheets_svc, processor_svc)
    
    logging.info(f"Iniciando Auditor Reconstrutor na aba '{SheetsService.MAIN_WORKSHEET_NAME}'...")
    await auditor.run_reconstruction(SheetsService.MAIN_WORKSHEET_NAME)

if __name__ == "__main__":
    asyncio.run(main())