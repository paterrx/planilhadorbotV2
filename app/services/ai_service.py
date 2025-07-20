# Arquivo: app/services/ai_service.py
# Versão: Final - Lógica unificada de extração e validação em uma única chamada.

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
                self.main_prompt = f.read()
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

    async def analyze_and_validate(self, message_text, image_bytes, channel_name):
        """Executa a análise e validação completa em uma única chamada de IA."""
        prompt = self.main_prompt.format(channel_name=channel_name)
        content = [prompt, f"\n\nAgora, analise e valide a seguinte mensagem:\n{message_text or 'Mensagem sem texto.'}"]
        
        if image_bytes:
            try: 
                content.append(Image.open(io.BytesIO(image_bytes)))
            except Exception as e: 
                logging.warning(f"Não foi possível processar a imagem: {e}")

        try:
            response = self.model.generate_content(content)
            cleaned_text = self._clean_json_response(response.text)
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            logging.error(f"AI Service - JSONDecodeError. Resposta da IA: {cleaned_text}")
            return {"message_type": "erro_ia", "data": {"error": "JSON inválido na resposta"}}
        except Exception as e:
            logging.error(f"AI Service - Erro na API Gemini: {e}")
            return {"message_type": "erro_ia", "data": {"error": str(e)}}