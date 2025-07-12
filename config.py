import os
import json
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env para o ambiente
load_dotenv()

class Config:
    # --- Segredos e Chaves de API ---
    TELEGRAM_API_ID = os.getenv('TELEGRAM_API_ID')
    TELEGRAM_API_HASH = os.getenv('TELEGRAM_API_HASH')
    TELETHON_SESSION_STRING = os.getenv('TELETHON_SESSION_STRING')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
    API_FOOTBALL_KEY = os.getenv('API_FOOTBALL_KEY')
    GOOGLE_CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS_JSON')

    # --- Configurações do Bot ---
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            _config_json = json.load(f)
            TELEGRAM_CHANNEL_IDS = _config_json.get('telegram_channel_ids', [])
    except FileNotFoundError:
        print("AVISO: O arquivo 'config.json' não foi encontrado. O bot não ouvirá nenhum canal.")
        TELEGRAM_CHANNEL_IDS = []

    # --- Caminhos de Arquivos ---
    DB_PATH = 'data/bets.db'
    PROMPT_PATH = 'prompts/main_prompt.txt'
    CONTEXT_DIR = 'context'

    # --- Carregamento de Arquivos de Contexto ---
    @staticmethod
    def _load_context_file(filename):
        """Função auxiliar para carregar um arquivo de texto da pasta de contexto."""
        try:
            with open(os.path.join(Config.CONTEXT_DIR, filename), 'r', encoding='utf-8') as f:
                # Remove linhas vazias e espaços em branco
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"AVISO: Arquivo de contexto '{filename}' não encontrado.")
            return []

    VALID_CASAS = _load_context_file('casas.txt')
    VALID_ESPORTES = _load_context_file('esporte.txt')
    VALID_TIPOS_APOSTA = _load_context_file('tiposDeAposta.txt')
    VALID_TIPSTERS = _load_context_file('tipster.txt')

# Cria uma instância da configuração para ser importada em outros módulos
config = Config()

# Validação inicial de configuração
if not all([config.TELEGRAM_API_ID, config.TELEGRAM_API_HASH, config.GEMINI_API_KEY, config.SPREADSHEET_ID, config.GOOGLE_CREDENTIALS_JSON]):
    raise ValueError("Uma ou mais variáveis de ambiente essenciais não foram definidas no arquivo .env.")
