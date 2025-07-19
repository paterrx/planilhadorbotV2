# Arquivo: app/services/ai_service.py
# Versão: 11.2 - Ajustada a assinatura do generate_search_query para maior robustez.

import google.generativeai as genai
import json
import re
import logging
from PIL import Image
import io
from app.config import config

class AIService:
    def __init__(self, cfg: config):
        self.config = cfg
        genai.configure(api_key=self.config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        self._load_prompts()

    def _load_prompts(self):
        try:
            with open(self.config.PROMPT_PATH, 'r', encoding='utf-8') as f:
                self.extraction_prompt = f.read()
            with open(self.config.QUERY_GENERATOR_PROMPT_PATH, 'r', encoding='utf-8') as f:
                self.query_generator_prompt = f.read()
            with open(self.config.FINAL_ANALYSIS_PROMPT_PATH, 'r', encoding='utf-8') as f:
                self.final_analysis_prompt = f.read()
        except FileNotFoundError as e:
            raise RuntimeError(f"ERRO CRÍTICO: Arquivo de prompt não encontrado: {e.filename}")

    def _clean_json_response(self, text):
        text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```', '', text)
        text = text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)
        return text

    async def initial_extraction(self, message_text, image_bytes, channel_name):
        context_lines = [ f"- Tipsters Válidos (usar o nome do canal): {channel_name}" ]
        full_context = "\n".join(context_lines)
        content = [self.extraction_prompt, full_context, f"\n\nAgora, analise a seguinte mensagem:\n{message_text or 'Mensagem sem texto.'}"]
        
        if image_bytes:
            try: content.append(Image.open(io.BytesIO(image_bytes)))
            except Exception as e: logging.warning(f"Não foi possível processar a imagem: {e}")

        try:
            response = self.model.generate_content(content)
            cleaned_text = self._clean_json_response(response.text)
            result = json.loads(cleaned_text)
            
            if 'data' in result and ('tipster' not in result['data'] or result['data'].get('tipster') is None):
                result['data']['tipster'] = channel_name
            return result
        except json.JSONDecodeError:
            logging.error(f"AI Service (Extract) - JSONDecodeError. Resposta da IA: {cleaned_text}")
            return {"message_type": "erro_ia", "data": {"error": "JSON inválido na extração"}}
        except Exception as e:
            logging.error(f"AI Service (Extract) - Erro na API Gemini: {e}")
            return {"message_type": "erro_ia", "data": {"error": str(e)}}

    async def generate_search_query(self, jogos_text, post_date):
        """Etapa 2: Gera uma query de busca otimizada a partir de um texto simples."""
        prompt = self.query_generator_prompt.format(
            jogos_text=jogos_text,
            post_date=post_date
        )
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logging.error(f"[AI Service] Erro ao gerar query de busca: {e}")
            return ""

    async def analyze_search_results(self, initial_bet_data, search_query, search_results, post_date):
        """Etapa 4: Analisa os resultados da busca e extrai os dados finais."""
        prompt = self.final_analysis_prompt.format(
            initial_bet_data=json.dumps(initial_bet_data, ensure_ascii=False),
            search_query=search_query,
            search_results=search_results,
            post_date=post_date
        )
        try:
            response = self.model.generate_content(prompt)
            cleaned_text = self._clean_json_response(response.text)
            return json.loads(cleaned_text)
        except Exception as e:
            logging.error(f"[AI Service] Erro ao analisar resultados da busca: {e}")
            return {"partida_encontrada": False}