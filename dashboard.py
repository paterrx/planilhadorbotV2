# Arquivo: dashboard.py
# Versão: 3.0 - Corrigida a lógica de conexão assíncrona com Telethon para ser compatível com Streamlit.

import streamlit as st
import json
import os
import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors.rpcerrorlist import ApiIdInvalidError
from app.config import config

# --- Constantes e Configurações ---
CONFIG_PATH = os.path.join(config.PROJECT_ROOT, 'config.json')
SESSION_STRING = config.TELETHON_SESSION_STRING
API_ID = config.TELEGRAM_API_ID
API_HASH = config.TELEGRAM_API_HASH

# --- Funções de Lógica ---

def load_monitored_config():
    """Carrega a configuração atual do config.json."""
    if not os.path.exists(CONFIG_PATH):
        return []
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            return data.get('telegram_channel_ids', [])
        except json.JSONDecodeError:
            return []

def save_monitored_config(channel_ids):
    """Salva a nova lista de IDs no config.json."""
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump({'telegram_channel_ids': channel_ids}, f, indent=4)

async def fetch_channels_async():
    """Função assíncrona para buscar os diálogos."""
    async with TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) as client:
        dialogs = await client.get_dialogs()
    return {f"{dialog.title} (ID: {dialog.id})": dialog.id for dialog in dialogs if dialog.is_channel}

@st.cache_data(ttl=3600) # Cache por 1 hora
def get_all_my_channels():
    """Função síncrona que gerencia o loop de eventos para o Streamlit."""
    st.info("Buscando sua lista de canais no Telegram... Isso pode levar um momento.")
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:  # 'There is no current event loop...'
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(fetch_channels_async())

# --- Interface do Dashboard ---
st.set_page_config(page_title="Gerenciador de Canais", layout="wide")
st.title("🚀 Dashboard de Gerenciamento de Canais - Planilhador-Gemini")
st.markdown("Adicione ou remova canais para o robô monitorar em tempo real.")

if not all([SESSION_STRING, API_ID, API_HASH]):
    st.error("ERRO: As variáveis de ambiente TELETHON_SESSION_STRING, TELEGRAM_API_ID e TELEGRAM_API_HASH precisam estar definidas!")
else:
    try:
        all_channels_map = get_all_my_channels()
        monitored_ids = load_monitored_config()

        st.sidebar.header("Canais Monitorados Atualmente")
        
        monitored_channels_names = [name for name, channel_id in all_channels_map.items() if channel_id in monitored_ids]

        for name in monitored_channels_names:
            st.sidebar.success(name)

        if not monitored_channels_names:
            st.sidebar.warning("Nenhum canal está sendo monitorado.")

        st.divider()
        
        st.subheader("Selecione os Canais para Monitorar")
        
        selected_channels = st.multiselect(
            label="Escolha um ou mais canais da sua lista. Os já selecionados estão marcados.",
            options=sorted(list(all_channels_map.keys())),
            default=monitored_channels_names
        )

        if st.button("Salvar Alterações", type="primary", use_container_width=True):
            new_monitored_ids = [all_channels_map[name] for name in selected_channels]
            save_monitored_config(new_monitored_ids)
            st.success("✅ Configuração salva com sucesso! O robô principal irá atualizar o monitoramento em breve.")
            st.rerun()

    except ApiIdInvalidError:
        st.error("Ocorreu um erro ao conectar com o Telegram: API_ID ou API_HASH inválidos. Verifique suas variáveis de ambiente.")
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado ao conectar com o Telegram: {e}")
        st.warning("Verifique se sua TELETHON_SESSION_STRING está correta e válida. Se o erro persistir, pode ser necessário gerar uma nova string.")