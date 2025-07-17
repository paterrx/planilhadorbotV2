# Arquivo: app/services/api_football_service.py
# Versão: 7.5 - Lógica final para interpretar nomes de times, datas e com debug aprimorado.

import requests
import re
import json
import os
import asyncio
from datetime import datetime, timedelta
from app.config import Config
from app.services.ai_service import AIService

class ApiFootballService:
    def __init__(self, cfg: Config, ai_svc: AIService):
        self.config = cfg
        self.ai = ai_svc 
        self.base_url = "https://v3.football.api-sports.io/"
        self.headers = {
            'x-rapidapi-key': self.config.API_FOOTBALL_KEY,
            'x-rapidapi-host': 'v3.football.api-sports.io'
        }
        self.mappings_filepath = os.path.join(self.config.MAPPINGS_DIR, 'team_mappings.json')
        self.team_mappings = self._load_team_mappings()
        self.ignore_list = ["adversário", "oponente", "time a", "time b", "?", "", "none"]

    def _load_team_mappings(self):
        if os.path.exists(self.mappings_filepath):
            try:
                with open(self.mappings_filepath, 'r', encoding='utf-8') as f:
                    print("Mapa de IDs de times local carregado.")
                    return {k.lower(): v for k, v in json.load(f).items()}
            except json.JSONDecodeError: return {}
        return {}

    def _save_team_mappings(self):
        try:
            with open(self.mappings_filepath, 'w', encoding='utf-8') as f:
                json.dump(self.team_mappings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"ERRO ao salvar o mapa de IDs de times: {e}")

    def _clean_name_for_lookup(self, name):
        if not isinstance(name, str): return ""
        # Remove sufixos como [W] ou (F) para a busca inicial
        name = re.sub(r'\s*\[(w|f)\]|\s*\((w|f)\)', ' w', name, flags=re.IGNORECASE)
        return name.lower().strip()

    async def _get_standardized_name_with_ai(self, raw_name):
        prompt = f"""
        Sua tarefa é converter nomes de times de futebol, como os escritos por tipsters brasileiros, para um formato de busca em inglês, padronizado e abreviado, para uma API.
        Regras:
        1.  Traduza nomes de países para o inglês (ex: 'equador' -> 'ecuador').
        2.  Abrevie "sub-21", "sub 21", etc., para "u21".
        3.  Abrevie "women", "feminino", "w", "[w]", "(f)" para "w".
        4.  Mantenha o resto do nome o mais limpo e direto possível.
        5.  Responda APENAS com o nome formatado.
        Exemplos:
        - Input: 'espanha w' -> Resposta: spain w
        - Input: 'inglaterra sub21 feminino' -> Resposta: england u21 w
        - Input: 'américa-mg' -> Resposta: america mineiro
        Agora, converta o seguinte nome: '{raw_name}'
        """
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: self.ai.model.generate_content(prompt))
            return response.text.strip().lower()
        except Exception as e:
            print(f"  -> Erro na IA ao padronizar nome '{raw_name}': {e}")
            return self._clean_name_for_lookup(raw_name)
            
    def _parse_relative_date(self, date_str):
        date_str_lower = str(date_str).lower()
        today = datetime.now()
        time_match = re.search(r'(\d{1,2}:\d{2})', date_str_lower)
        event_time = time_match.group(1) if time_match else "12:00"

        if 'hoje' in date_str_lower: return today.strftime(f'%d/%m/%Y {event_time}')
        if 'amanhã' in date_str_lower: return (today + timedelta(days=1)).strftime(f'%d/%m/%Y {event_time}')
        return date_str

    async def _search_team_on_api(self, search_term):
        if not search_term: return None
        print(f"     -> DEBUG API: Buscando na API pelo termo: '{search_term}'")
        try:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.get(f"{self.base_url}teams", headers=self.headers, params={'search': search_term}, timeout=20)
            )
            response.raise_for_status()
            return response.json().get('response', [])[0] if response.json().get('response') else None
        except requests.exceptions.RequestException as e:
            print(f"  -> [API] Erro de rede ao buscar por '{search_term}': {e}")
            return None
            
    async def _get_team_id(self, team_name):
        clean_name = self._clean_name_for_lookup(team_name)
        if not clean_name or clean_name in self.ignore_list: return None
        if clean_name in self.team_mappings and self.team_mappings.get(clean_name) is not None:
            return self.team_mappings[clean_name]
        
        # Usa a IA para obter o nome padronizado ANTES da busca
        standardized_name = await self._get_standardized_name_with_ai(clean_name)
        print(f"  -> Nome original '{clean_name}' padronizado para busca como: '{standardized_name}'")
        
        found_team = await self._search_team_on_api(standardized_name)

        if not found_team:
            print(f"  -> Nenhum resultado na API para '{standardized_name}'.")
            self.team_mappings[clean_name] = None
            self._save_team_mappings()
            return None
        
        team_id = found_team['team']['id']
        api_official_name = found_team['team']['name']
        print(f"  -> SUCESSO! ID {team_id} encontrado para '{api_official_name}'.")
        self.team_mappings[clean_name] = team_id
        self.team_mappings[standardized_name] = team_id
        self.team_mappings[self._clean_name_for_lookup(api_official_name)] = team_id
        self._save_team_mappings()
        return team_id

    def _parse_event(self, event_description):
        if not isinstance(event_description, str) or not event_description.strip():
            return None, "InvalidDescription"
        delimiters = [' x ', ' vs ', ' v ', ' - ']
        for d in delimiters:
            if d in event_description.lower():
                teams = re.split(d, event_description, maxsplit=1, flags=re.IGNORECASE)
                if len(teams) == 2:
                    return (teams[0].strip(), teams[1].strip()), "Success"
        return None, "ParseError"

    async def find_match_by_ids(self, home_id: int, away_id: int, event_date_str: str):
        if not all([home_id, away_id, event_date_str]): return None, "InvalidInput"
        try:
            parsed_date_str = self._parse_relative_date(event_date_str)
            event_date = datetime.strptime(parsed_date_str.split(" ")[0], '%d/%m/%Y')
        except (ValueError, IndexError):
            print(f"  -> Data do evento '{event_date_str}' inválida.")
            return None, "InvalidDate"
        try:
            params = {'date': event_date.strftime('%Y-%m-%d'), 'team': home_id}
            response = await asyncio.get_running_loop().run_in_executor(
                None, lambda: requests.get(f"{self.base_url}fixtures", headers=self.headers, params=params, timeout=20)
            )
            response.raise_for_status()
            for fixture in response.json().get('response', []):
                if fixture['teams']['away']['id'] == away_id:
                    return fixture, "Success"
            return None, "MatchNotFound"
        except requests.exceptions.RequestException as e:
            print(f"  -> [API] Erro na requisição ao buscar por IDs: {e}")
            return None, "ApiError"

    async def find_match_by_name(self, event_description: str, event_date_str: str):
        parsed_teams, reason = self._parse_event(event_description)
        if not parsed_teams: return None, reason
        home_team_name, away_team_name = parsed_teams
        home_team_id = await self._get_team_id(home_team_name)
        away_team_id = await self._get_team_id(away_team_name)
        if not home_team_id or not away_team_id: return None, "TeamNotFound"
        return await self.find_match_by_ids(home_team_id, away_team_id, event_date_str)