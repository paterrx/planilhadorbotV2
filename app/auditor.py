# Arquivo: app/auditor.py
# Versão: 10.1 - Lógica final com reconstrução segura usando JSON plano.

import asyncio
import pandas as pd
import re
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors.rpcerrorlist import SearchQueryEmptyError, MessageIdInvalidError

from app.config import config, Config
from app.services.ai_service import AIService
from app.services.sheets_service import SheetsService
from app.services.api_football_service import ApiFootballService

class Auditor:
    def __init__(self, cfg: Config, sheets_svc: SheetsService, ai_svc: AIService, api_football_svc: ApiFootballService):
        if cfg.TELETHON_SESSION_STRING: session = StringSession(cfg.TELETHON_SESSION_STRING)
        else: session = cfg.SESSION_FILE
        self.client = TelegramClient(session, int(cfg.TELEGRAM_API_ID), cfg.TELEGRAM_API_HASH)
        self.sheets = sheets_svc
        self.ai = ai_svc
        self.api_football = api_football_svc
        self.tipster_channel_map = {}
        self.fallback_channel_id = None

    async def _build_tipster_map(self):
        print("Mapeando Tipsters para IDs de Canais...")
        temp_map = {}
        for channel_id in config.TELEGRAM_CHANNEL_IDS:
            try:
                entity = await self.client.get_entity(channel_id)
                temp_map[entity.title] = entity.id
            except Exception as e:
                print(f"  -> AVISO: Não foi possível acessar o canal com ID {channel_id}. Erro: {e}")
        peixe_esperto_name = "Peixe Esperto - Águas"
        for channel_title, channel_id in temp_map.items():
            if peixe_esperto_name.lower() in channel_title.lower():
                self.fallback_channel_id = channel_id
                print(f"  -> Canal de fallback definido para '{channel_title}' (ID: {self.fallback_channel_id})")
                break
        valid_tipsters = [t for t in config.VALID_TIPSTERS if t and t.strip() and t.strip() != '-']
        for tipster_name in valid_tipsters:
            found = False
            for channel_title, channel_id in temp_map.items():
                if tipster_name.lower() in channel_title.lower():
                    self.tipster_channel_map[tipster_name] = channel_id
                    print(f"  -> Mapeado: '{tipster_name}' -> Canal '{channel_title}' (ID: {channel_id})")
                    found = True
                    break
            if not found:
                print(f"  -> AVISO: Tipster '{tipster_name}' de 'tipster.txt' não foi mapeado. Usará fallback se encontrado na planilha.")

    async def find_original_message(self, bet_row):
        link = bet_row.get('Message Link')
        if link and 't.me/c/' in link:
            try:
                match = re.search(r't.me/c/(\d+)/(\d+)', link)
                if match:
                    channel_id = int("-100" + match.group(1))
                    msg_id = int(match.group(2))
                    return await self.client.get_messages(channel_id, ids=msg_id)
            except (ValueError, MessageIdInvalidError): pass
            except Exception as e: print(f"    -> Erro ao buscar por link {link}: {e}")
        tipster_name = bet_row.get('Tipster')
        channel_id = self.tipster_channel_map.get(tipster_name, self.fallback_channel_id)
        if not channel_id: return None
        search_query = bet_row.get('Entrada') or bet_row.get('Descrição da Aposta') or bet_row.get('Jogos')
        if search_query: search_query = " ".join(str(search_query).split()[:4])
        else: return None
        try:
            async for message in self.client.iter_messages(channel_id, search=search_query, limit=5):
                 return message
        except Exception: return None
        return None

    async def run_reconstruction(self, source_worksheet_name: str):
        print("Conectando ao Telegram para auditoria...")
        await self.client.connect()
        await self._build_tipster_map()
        
        original_df = self.sheets.get_all_bets_from_worksheet(source_worksheet_name)
        if original_df.empty:
            print(f"A aba de origem '{source_worksheet_name}' está vazia ou não foi encontrada. Encerrando.")
            await self.client.disconnect()
            return
            
        print(f"\n--- Auditoria iniciada. Lendo {len(original_df)} linhas da aba '{source_worksheet_name}'. ---")
        reconstructed_rows_data = []
        # Garante que Bet ID seja string para evitar erros no drop_duplicates
        original_df['Bet ID'] = original_df['Bet ID'].astype(str)
        unique_bets_df = original_df.drop_duplicates(subset='Bet ID', keep='first')

        for index, bet_row in unique_bets_df.iterrows():
            bet_id = bet_row.get('Bet ID')
            if not bet_id: continue
            
            try:
                print(f"\n-> Auditando Aposta ID {bet_id}...")
                original_message = await self.find_original_message(bet_row)
                if not original_message:
                    print(f"  -> Mensagem não encontrada. Mantendo a primeira linha original.")
                    reconstructed_rows_data.append(bet_row.to_dict())
                    continue

                print("  -> Mensagem encontrada. Reanalisando com a IA...")
                analysis_result = await self.ai.analyze_message(original_message.text, await original_message.download_media(file=bytes))
                
                if analysis_result.get('message_type') != 'nova_aposta':
                    print(f"  -> Reanálise não resultou em 'nova_aposta'. Mantendo dados originais.")
                    reconstructed_rows_data.append(bet_row.to_dict())
                    continue

                message_link = f"https://t.me/c/{str(original_message.chat_id).replace('-100', '')}/{original_message.id}"
                
                # A função _format_json_to_row_data agora lida com o JSON plano
                row_data = self.sheets._format_json_to_row_data(
                    analysis_result, message_link,
                    existing_bet_id=bet_id,
                    existing_status=bet_row.get('Situação', 'Pendente')
                )
                
                if row_data:
                    reconstructed_rows_data.append(row_data)
                    print("  -> Aposta reanalisada e corrigida com sucesso.")
                else:
                    reconstructed_rows_data.append(bet_row.to_dict())

            except Exception as e:
                print(f"  -> ERRO INESPERADO ao auditar aposta {bet_id}: {e}. Mantendo dados originais.")
                reconstructed_rows_data.append(bet_row.to_dict())

        if reconstructed_rows_data:
            reconstructed_df = pd.DataFrame(reconstructed_rows_data)
            self.sheets.write_reconstructed_sheet(reconstructed_df)
        else:
            print("\nNenhuma linha foi processada para reconstrução.")
        await self.client.disconnect()
        print("\nCiclo de auditoria e reconstrução concluído.")

async def main():
    ABA_PARA_AUDITAR = "APOSTAS"
    print(f"Iniciando Auditor Reconstrutor na aba '{ABA_PARA_AUDITAR}'...")
    ai_service = AIService(config)
    sheets_service = SheetsService(config)
    api_football_service = ApiFootballService(config, ai_service)
    auditor = Auditor(config, sheets_service, ai_service, api_football_service)
    await auditor.run_reconstruction(ABA_PARA_AUDITAR)

if __name__ == "__main__":
    asyncio.run(main())