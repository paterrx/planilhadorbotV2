# Arquivo: app/config.py
# Versão: Final com todas as chaves e caminhos.

import os
import json
from dotenv import load_dotenv

class Config:
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
    
    # --- Chaves de API ---
    TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
    TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
    TELETHON_SESSION_STRING = os.getenv('TELETHON_SESSION_STRING')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
    API_FOOTBALL_KEY = os.getenv('API_FOOTBALL_KEY')
    TAVILY_API_KEY = os.getenv('TAVILY_API_KEY')
    GOOGLE_CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS_JSON')
    
    # --- Configurações de Comportamento ---
    RESULT_CHECK_HOURS_AGO = float(os.getenv('RESULT_CHECK_HOURS_AGO', 2.5))
    
    # --- Caminhos de Arquivos ---
    DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
    DB_PATH = os.path.join(DATA_DIR, 'bets.db')
    PROMPTS_DIR = os.path.join(os.path.dirname(__file__), 'prompts')
    PROMPT_PATH = os.path.join(PROMPTS_DIR, 'main_prompt.txt')
    QUERY_GENERATOR_PROMPT_PATH = os.path.join(PROMPTS_DIR, 'query_generator_prompt.txt')
    FINAL_ANALYSIS_PROMPT_PATH = os.path.join(PROMPTS_DIR, 'final_analysis_prompt.txt')
    CONTEXT_DIR = os.path.join(os.path.dirname(__file__), 'context')
    MAPPINGS_DIR = PROJECT_ROOT
    SESSION_FILE = os.path.join(PROJECT_ROOT, "bot_session")

    def __init__(self):
        self.VALID_CASAS = self._load_context_file(self.CONTEXT_DIR, 'casas.txt')
        self.VALID_ESPORTES = self._load_context_file(self.CONTEXT_DIR, 'esporte.txt')
        self.VALID_TIPOS_APOSTA = self._load_context_file(self.CONTEXT_DIR, 'tiposDeAposta.txt')
        self.VALID_TIPSTERS = self._load_context_file(self.CONTEXT_DIR, 'tipster.txt')

        try:
            with open(os.path.join(self.PROJECT_ROOT, 'config.json'), 'r', encoding='utf-8') as f:
                self.TELEGRAM_CHANNEL_IDS = json.load(f).get('telegram_channel_ids', [])
        except FileNotFoundError:
            self.TELEGRAM_CHANNEL_IDS = []
        
        # Garante que o diretório de dados exista
        os.makedirs(self.DATA_DIR, exist_ok=True)

    def _load_context_file(self, context_dir, filename):
        filepath = os.path.join(context_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            return []

config = Config()