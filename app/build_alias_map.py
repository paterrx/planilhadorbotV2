# Arquivo: build_alias_map.py
# Descrição: Ferramenta profissional para criar um mapa de IDs de times.
# Versão: 5.3 - Modificado para continuar o processo a partir de um ponto específico.

import requests
import json
import time
import re
import os
from app.config import config

# Dicionário de apelidos comuns. Podemos expandir isso conforme necessário.
MANUAL_ALIASES = {
    "psg": "paris saint germain",
    "real": "real madrid",
    "barça": "barcelona",
    "man united": "manchester united",
    "man city": "manchester city",
    "inter": "inter milan",
    "atlético-mg": "atletico mineiro",
    "atletico-mg": "atletico mineiro",
    "atlético mg": "atletico mineiro",
    "athletico-pr": "athletico paranaense",
    "athletico pr": "athletico paranaense",
    "fla": "flamengo",
    "mengão": "flamengo",
    "vasco": "vasco da gama",
    "inter de limeira": "inter de limeira",
    "operario pr": "operario"
}

def call_api(endpoint, params=None):
    """Função genérica para chamar a API-Football."""
    headers = {
        'x-rapidapi-key': config.API_FOOTBALL_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    url = f"https://v3.football.api-sports.io/{endpoint}"
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json().get('response', [])
    except requests.exceptions.RequestException as e:
        print(f"  -> Erro de rede ao chamar '{endpoint}': {e}")
        return []

def clean_name_for_key(name):
    """Limpa um nome para ser usado como chave no dicionário."""
    if not name: return ""
    name = name.lower().strip()
    name = re.sub(r'\s*\((f|w|fem|masc|sub\d*)\)', '', name)
    name = name.replace('- feminino', '').replace('- masculino', '')
    return name

def load_existing_mappings(filepath):
    """Carrega o mapa de times existente, se houver."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                print("Arquivo de mapa existente carregado. O script continuará de onde parou.")
                return json.load(f)
        except json.JSONDecodeError:
            print(f"AVISO: Arquivo '{filepath}' mal formatado. Começando um novo.")
            return {}
    return {}

def save_mappings(filepath, data):
    """Salva o dicionário de mapas no arquivo JSON."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"\nERRO ao salvar o arquivo JSON '{filepath}': {e}")

def create_alias_map():
    """
    Busca todos os times, cria um mapa de apelidos para IDs e salva em JSON.
    """
    print("Iniciando a criação do mapa de apelidos e IDs de times...")
    
    mappings_filepath = 'team_mappings.json'
    final_alias_map = load_existing_mappings(mappings_filepath)
    
    countries = call_api('countries')
    if not countries:
        print("ERRO: Não foi possível buscar a lista de países. Verifique sua chave de API.")
        return

    total_countries = len(countries)
    print(f"Encontrados {total_countries} países no total. Verificando times...")
    
    # Ponto de partida (104 para começar depois de Malta, que era o 104)
    start_index = 104 

    for i, country in enumerate(countries):
        # A contagem para o usuário começa em 1, então usamos i+1
        current_position = i + 1

        # Pula os países que já foram processados
        if current_position <= start_index:
            print(f"({current_position}/{total_countries}) Pulando país: {country.get('name')} (já processado).")
            continue

        country_name = country.get('name')
        if not country_name: continue

        print(f"\n({current_position}/{total_countries}) Processando país: {country_name}...")
        
        time.sleep(7) 
        
        teams_in_country = call_api('teams', {'country': country_name})

        if teams_in_country:
            newly_added = 0
            for team_data in teams_in_country:
                team_info = team_data.get('team', {})
                team_id = team_info.get('id')
                official_name = team_info.get('name')

                if not team_id or not official_name: continue

                cleaned_official_name = clean_name_for_key(official_name)
                if cleaned_official_name not in final_alias_map:
                    final_alias_map[cleaned_official_name] = team_id
                    newly_added += 1

            print(f"  -> {len(teams_in_country)} times encontrados. {newly_added} novos adicionados ao mapa.")
            save_mappings(mappings_filepath, final_alias_map)
        else:
            print("  -> Nenhum time encontrado ou erro na API para este país.")

    print(f"\nBusca em todos os países concluída. Total de {len(final_alias_map)} times únicos mapeados.")
    print("Aplicando apelidos manuais...")

    for alias, official_name in MANUAL_ALIASES.items():
        cleaned_official_name = clean_name_for_key(official_name)
        if cleaned_official_name in final_alias_map:
            team_id = final_alias_map[cleaned_official_name]
            final_alias_map[alias] = team_id
        else:
            print(f"  -> AVISO: Nome oficial '{official_name}' para o apelido '{alias}' não foi encontrado no mapa.")

    save_mappings(mappings_filepath, final_alias_map)
    print(f"\nSUCESSO! Arquivo 'team_mappings.json' finalizado com {len(final_alias_map)} apelidos e nomes mapeados.")

if __name__ == "__main__":
    create_alias_map()
