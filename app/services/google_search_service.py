# Arquivo: app/services/Google Search_service.py
# Versão: 2.0 - Implementação funcional com a API da Tavily.

import logging
from tavily import TavilyClient
from app.config import config

class GoogleSearchService:
    def __init__(self):
        if not config.TAVILY_API_KEY:
            raise ValueError("TAVILY_API_KEY não foi encontrada no .env. Obtenha uma em tavily.com")
        self.client = TavilyClient(api_key=config.TAVILY_API_KEY)

    def search(self, query: str):
        """Executa uma busca na web usando Tavily e retorna os resultados formatados."""
        logging.info(f"[Tavily Search] Executando busca para query: '{query}'")
        try:
            # max_results=5 para obter uma boa quantidade de contexto
            response = self.client.search(query=query, search_depth="basic", max_results=5)
            
            # Formata os resultados para serem fáceis para a IA ler
            formatted_results = []
            if response and response.get('results'):
                for result in response['results']:
                    formatted_results.append(f"Título: {result.get('title')}, URL: {result.get('url')}, Conteúdo: {result.get('content')}")
            
            logging.info(f"[Tavily Search] Encontrados {len(formatted_results)} resultados.")
            return "\n".join(formatted_results)
            
        except Exception as e:
            logging.error(f"[Tavily Search] Erro ao executar a busca: {e}")
            return "Erro ao realizar a busca na web."