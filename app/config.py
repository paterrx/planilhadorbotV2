# Arquivo: app/config.py
# Descrição: Centraliza o carregamento de todas as configurações do projeto.

import os
import json
from dotenv import load_dotenv

class Config:
    """Classe que armazena todas as configurações do projeto."""
    
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    load_dotenv(os.path.join(PROJECT_ROOT, '.env'))
    
    TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
    TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
    TELETHON_SESSION_STRING = os.getenv('TELETHON_SESSION_STRING')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
    API_FOOTBALL_KEY = os.getenv('API_FOOTBALL_KEY')
    GOOGLE_CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS_JSON')
    
    USER_TO_MENTION = os.getenv('USER_TO_MENTION', 'paterrx') 
    NOTIFICATION_CHANNEL_ID = int(os.getenv('NOTIFICATION_CHANNEL_ID', 0))

    DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'bets.db')
    PROMPT_PATH = os.path.join(os.path.dirname(__file__), 'prompts', 'main_prompt.txt')
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
                _config_json = json.load(f)
                self.TELEGRAM_CHANNEL_IDS = _config_json.get('telegram_channel_ids', [])
        except FileNotFoundError:
            self.TELEGRAM_CHANNEL_IDS = []

    def _load_context_file(self, context_dir, filename):
        filepath = os.path.join(context_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            return []

config = Config()
