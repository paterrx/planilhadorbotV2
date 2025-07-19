# Arquivo: dashboard.py
# Descrição: Dashboard interativo para gerenciar os canais do Telegram monitorados.

import streamlit as st
import json
import os
import asyncio
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from app.config import config

CONFIG_PATH = os.path.join(config.PROJECT_ROOT, 'config.json')
SESSION_STRING = config.TELETHON_SESSION_STRING
API_ID = config.TELEGRAM_API_ID
API_HASH = config.TELEGRAM_API_HASH

def load_monitored_config():
    if not os.path.exists(CONFIG_PATH):
        return []
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('telegram_channel_ids', [])

def save_monitored_config(channel_ids):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump({'telegram_channel_ids': channel_ids}, f, indent=4)

@st.cache_data(ttl=3600)
def get_all_my_channels():
    st.info("Buscando sua lista de canais no Telegram... Isso pode levar um momento.")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    with TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH) as client:
        dialogs = client.loop.run_until_complete(client.get_dialogs())
    channels = {f"{dialog.title} (ID: {dialog.id})": dialog.id for dialog in dialogs if dialog.is_channel}
    return channels

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
        
        monitored_channels_names = []
        for name, channel_id in all_channels_map.items():
            if channel_id in monitored_ids:
                st.sidebar.success(name)
                monitored_channels_names.append(name)

        if not monitored_channels_names:
            st.sidebar.warning("Nenhum canal está sendo monitorado.")

        st.divider()
        st.subheader("Selecione os Canais para Monitorar")
        
        selected_channels = st.multiselect(
            label="Escolha um ou mais canais da sua lista. Os já selecionados estão marcados.",
            options=all_channels_map.keys(),
            default=monitored_channels_names
        )

        if st.button("Salvar Alterações", type="primary", use_container_width=True):
            new_monitored_ids = [all_channels_map[name] for name in selected_channels]
            save_monitored_config(new_monitored_ids)
            st.success("✅ Configuração salva com sucesso! O robô principal irá atualizar o monitoramento em breve.")
            st.rerun()

    except Exception as e:
        st.error(f"Ocorreu um erro ao conectar com o Telegram: {e}")
        st.warning("Verifique se sua TELETHON_SESSION_STRING está correta e válida.")