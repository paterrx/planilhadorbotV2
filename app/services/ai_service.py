# Arquivo: app/services/ai_service.py
# Versão: 10.0 - Lógica de validação em duas etapas e regras de fallback.

import google.generativeai as genai
import json
import re
import logging
from PIL import Image
import io
from app.config import Config

class AIService:
    def __init__(self, cfg: Config):
        self.config = cfg
        genai.configure(api_key=self.config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        self._load_prompts()

    def _load_prompts(self):
        try:
            with open(self.config.PROMPT_PATH, 'r', encoding='utf-8') as f:
                self.base_prompt = f.read()
            with open(self.config.VALIDATION_PROMPT_PATH, 'r', encoding='utf-8') as f:
                self.validation_prompt = f.read()
        except FileNotFoundError as e:
            raise RuntimeError(f"ERRO CRÍTICO: Arquivo de prompt não encontrado: {e.filename}")

    def _clean_json_response(self, text):
        text = re.sub(r'```json\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'```', '', text)
        text = text.strip()
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)
        return text # Retorna texto original se nenhum JSON for encontrado

    async def analyze_message(self, message_text, image_bytes, channel_name):
        context_lines = [ f"- Tipsters Válidos (usar o nome do canal): {channel_name}" ]
        full_context = "\n".join(context_lines)
        content = [self.base_prompt, full_context, f"\n\nAgora, analise a seguinte mensagem:\n{message_text or 'Mensagem sem texto.'}"]
        
        if image_bytes:
            try: content.append(Image.open(io.BytesIO(image_bytes)))
            except Exception as e: logging.warning(f"Não foi possível processar a imagem: {e}")

        try:
            response = self.model.generate_content(content)
            cleaned_text = self._clean_json_response(response.text)
            result = json.loads(cleaned_text)
            
            # Aplica a regra de fallback do tipster aqui
            if 'data' in result and ('tipster' not in result['data'] or result['data'].get('tipster') is None):
                result['data']['tipster'] = channel_name
            return result
        except json.JSONDecodeError:
            logging.error(f"AI Service (Analyze) - JSONDecodeError. Resposta da IA: {cleaned_text}")
            return {"message_type": "erro_ia", "data": {"error": "JSON inválido na extração"}}
        except Exception as e:
            logging.error(f"AI Service (Analyze) - Erro na API Gemini: {e}")
            return {"message_type": "erro_ia", "data": {"error": str(e)}}

    async def validate_bet_data(self, initial_bet_data):
        logging.info(f"[IA Validação] Verificando dados: {initial_bet_data}")
        prompt = self.validation_prompt.format(initial_data_json=json.dumps(initial_bet_data, ensure_ascii=False, indent=2))
        
        try:
            response = self.model.generate_content(prompt)
            cleaned_text = self._clean_json_response(response.text)
            validation_result = json.loads(cleaned_text)
            logging.info(f"[IA Validação] Resultado: {validation_result}")
            return validation_result
        except json.JSONDecodeError:
            logging.error(f"AI Service (Validate) - JSONDecodeError. Resposta da IA: {cleaned_text}")
            return {"partida_encontrada": False, "error": "JSON inválido na validação"}
        except Exception as e:
            logging.error(f"AI Service (Validate) - Erro na API Gemini: {e}")
            return {"partida_encontrada": False, "error": str(e)}