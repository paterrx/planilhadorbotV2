# Arquivo: build_league_map.py
# Descrição: Ferramenta para criar um mapa de nomes de ligas para seus IDs oficiais da API-Football.
# Versão: 5.4 - Lógica de paginação reconstruída com base na documentação oficial para buscar TODAS as ligas.

import requests
import json
import time
from app.config import config

def call_api(endpoint, params=None):
    """Função genérica para chamar a API-Football, agora retornando o objeto de resposta completo."""
    headers = {
        'x-rapidapi-key': config.API_FOOTBALL_KEY,
        'x-rapidapi-host': 'v3.football.api-sports.io'
    }
    url = f"https://v3.football.api-sports.io/{endpoint}"
    try:
        print(f"  -> Chamando API: {url} com parâmetros: {params}")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json() # Retorna o objeto JSON completo
    except requests.exceptions.RequestException as e:
        print(f"  -> Erro de rede ao chamar '{endpoint}': {e}")
        return None

def create_league_mappings():
    """
    Busca todas as ligas da API, lidando com a paginação, e salva um mapa em um arquivo JSON.
    """
    print("Iniciando a criação do mapa de IDs de ligas...")
    
    all_leagues = []
    
    # --- LÓGICA DE PAGINAÇÃO CORRIGIDA ---
    # Primeira chamada para obter a primeira página e o total de páginas.
    print("Buscando a primeira página de ligas...")
    # Usar um parâmetro como 'current=true' pode ajudar a API a retornar uma lista paginada mais estável.
    initial_params = {'current': 'true'}
    initial_data = call_api('leagues', initial_params)
    
    if not initial_data or 'response' not in initial_data or not initial_data['response']:
        print("ERRO: Não foi possível buscar os dados iniciais das ligas. Verifique sua chave de API ou o status do serviço.")
        return

    all_leagues.extend(initial_data['response'])
    
    # Pega o total de páginas do objeto 'paging' da API. Esta é a correção crucial.
    paging_info = initial_data.get('paging', {})
    total_pages = paging_info.get('total', 1)
    current_page = paging_info.get('current', 1)
    
    print(f"Total de páginas a serem buscadas: {total_pages}. Começando o processo...")

    # Loop para buscar as páginas restantes, se houver
    if total_pages > 1:
        for page in range(current_page + 1, total_pages + 1):
            print(f"Buscando página {page}/{total_pages}...")
            # Com o plano pago, um delay curto é suficiente para ser "educado" com a API.
            time.sleep(2) 
            
            page_params = {'current': 'true', 'page': page}
            page_data = call_api('leagues', page_params)
            
            if page_data and 'response' in page_data:
                all_leagues.extend(page_data['response'])
                print(f"  -> {len(page_data['response'])} ligas adicionadas. Total acumulado: {len(all_leagues)}")
            else:
                print(f"  -> AVISO: Não foi possível buscar dados da página {page}. Continuando...")

    # Agora processa a lista completa de ligas
    league_mappings = {}
    for item in all_leagues:
        league_info = item.get('league', {})
        league_id = league_info.get('id')
        league_name = league_info.get('name')

        if league_id and league_name:
            # Salva o nome em minúsculas como chave para facilitar a busca
            league_mappings[league_name.lower()] = {
                "id": league_id,
                "name": league_name # Salva o nome oficial com a formatação correta
            }
    
    print(f"\nBusca concluída. {len(league_mappings)} ligas únicas mapeadas.")

    # Salva o dicionário em um arquivo JSON
    try:
        with open('league_mappings.json', 'w', encoding='utf-8') as f:
            json.dump(league_mappings, f, indent=4, ensure_ascii=False)
        print("\nSUCESSO! Arquivo 'league_mappings.json' criado com todos os IDs de ligas.")
    except Exception as e:
        print(f"\nERRO ao salvar o arquivo JSON: {e}")

if __name__ == "__main__":
    create_league_mappings()
