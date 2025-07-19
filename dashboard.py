# Arquivo: dashboard.py
# Versão: 4.0 - Versão final desacoplada do Telethon, lendo de um arquivo JSON.

import streamlit as st
import json
import os
from app.config import config

# --- Constantes e Configurações ---
CONFIG_PATH = os.path.join(config.PROJECT_ROOT, 'config.json')
CHANNELS_PATH = os.path.join(config.PROJECT_ROOT, 'data', 'channels.json')

# --- Funções de Lógica ---

def load_monitored_config():
    if not os.path.exists(CONFIG_PATH): return []
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f).get('telegram_channel_ids', [])

def save_monitored_config(channel_ids):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump({'telegram_channel_ids': channel_ids}, f, indent=4)

@st.cache_data(ttl=3600) # Cache por 1 hora
def load_available_channels():
    st.info("Carregando lista de canais do arquivo `data/channels.json`...")
    if not os.path.exists(CHANNELS_PATH):
        st.error("Arquivo `data/channels.json` não encontrado. Execute o script `update_channels_list.py` primeiro.")
        return {}
    with open(CHANNELS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- Interface do Dashboard ---
st.set_page_config(page_title="Gerenciador de Canais", layout="wide")
st.title("🚀 Dashboard de Gerenciamento de Canais - Planilhador-Gemini")

all_channels_map = load_available_channels()

if not all_channels_map:
    st.warning("A lista de canais está vazia.")
else:
    monitored_ids = load_monitored_config()

    st.sidebar.header("Canais Monitorados Atualmente")
    monitored_channels_names = [name for name, channel_id in all_channels_map.items() if channel_id in monitored_ids]
    for name in sorted(monitored_channels_names):
        st.sidebar.success(name)

    st.divider()
    st.subheader("Selecione os Canais para Monitorar")
    
    selected_channels = st.multiselect(
        label="Escolha os canais da sua lista. Os já selecionados estão marcados.",
        options=sorted(list(all_channels_map.keys())),
        default=monitored_channels_names
    )

    if st.button("Salvar Alterações", type="primary", use_container_width=True):
        new_monitored_ids = [all_channels_map[name] for name in selected_channels]
        save_monitored_config(new_monitored_ids)
        st.success("✅ Configuração salva! O robô principal irá atualizar o monitoramento em breve.")
        st.rerun()