# Arquivo: app/services/sofascore_service.py
# Versão: 1.0 - Serviço para acesso direto a dados via engenharia reversa.

import requests
import logging

class SofascoreService:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
        }
        # TAREFA MANUAL PARA VOCÊ: Encontre a URL de busca correta.
        # 1. Abra o Sofascore no navegador.
        # 2. Pressione F12 para abrir as Ferramentas de Desenvolvedor.
        # 3. Vá na aba "Network" (ou "Rede") e filtre por "Fetch/XHR".
        # 4. Use a busca do site para procurar por um time (ex: "Flamengo").
        # 5. Uma nova linha deve aparecer na aba Network. Clique nela.
        # 6. Copie a URL da "Request URL" e cole aqui.
        self.search_base_url = "https://api.sofascore.com/api/v1/search/all" # <--- CONFIRME E, SE NECESSÁRIO, SUBSTITUA PELA URL REAL

    def get_team_details_from_search(self, query: str):
        if not query or not self.search_base_url: return None
        params = {'q': query}
        logging.info(f"[Sofascore] Buscando termo: '{query}'")
        try:
            response = requests.get(self.search_base_url, headers=self.headers, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if data and data.get('results'):
                for result in data['results']:
                    if result.get('type') == 'team' and result.get('entity'):
                        logging.info(f"[Sofascore] Encontrado: {result['entity'].get('name')}")
                        return result['entity']
            return None
        except Exception as e:
            logging.error(f"[Sofascore] Erro ao buscar por '{query}': {e}")
            return None