# Arquivo: app/services/ai_service.py
# Versão: 9.0 - Adicionado método de validação para verificação de dados em duas etapas.

import google.generativeai as genai
import json
import re
from PIL import Image
import io
import os
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
            # Carrega o novo prompt de validação
            validation_prompt_path = os.path.join(os.path.dirname(self.config.PROMPT_PATH), 'validation_prompt.txt')
            with open(validation_prompt_path, 'r', encoding='utf-8') as f:
                self.validation_prompt = f.read()
        except FileNotFoundError as e:
            raise RuntimeError(f"ERRO CRÍTICO: Arquivo de prompt não encontrado: {e.filename}")

    def _clean_json_response(self, text):
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```', '', text)
        text = re.sub(r':\s*""', ': "', text)
        text = re.sub(r'""\s*([,}\]])', r'"\1', text)
        return text.strip()

    async def analyze_message(self, message_text, image_bytes=None):
        """Etapa 1: Extrai os dados brutos da mensagem."""
        # ... (código existente sem alterações) ...
        context_header = "\n\n--- CONTEXTO FORNECIDO ---\n"
        context_lines = [
            f"- Tipsters Válidos: {', '.join(self.config.VALID_TIPSTERS)}",
            f"- Casas de Apostas Válidas: {', '.join(self.config.VALID_CASAS)}",
            f"- Esportes Válidos: {', '.join(self.config.VALID_ESPORTES)}",
            f"- Tipos de Aposta Válidos: {', '.join(self.config.VALID_TIPOS_APOSTA)}"
        ]
        full_context = context_header + "\n".join(context_lines)
        content = [self.base_prompt, full_context, f"\n\nAgora, analise a seguinte mensagem do Telegram:\n{message_text or 'Mensagem sem texto.'}"]
        
        if image_bytes:
            try:
                img = Image.open(io.BytesIO(image_bytes))
                content.append(img)
            except Exception as e:
                print(f"Erro ao processar imagem: {e}")

        try:
            response = self.model.generate_content(content)
            cleaned_text = self._clean_json_response(response.text)
            json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
            if not json_match:
                print(f"ERRO JSON: Nenhum bloco JSON encontrado na extração. Resposta: {response.text}")
                return {"message_type": "erro_ia", "data": {"error": "Nenhum JSON na resposta"}}
            return json.loads(json_match.group(0))
        except Exception as e:
            print(f"ERRO na API Gemini (Extração): {e}")
            return {"message_type": "erro_ia", "data": {"error": str(e)}}

    async def validate_bet_data(self, initial_bet_data):
        """Etapa 2: Valida os dados extraídos usando conhecimento geral."""
        print(f"  -> [IA Validação] Verificando dados: {initial_bet_data}")
        prompt = self.validation_prompt.format(initial_data_json=json.dumps(initial_bet_data, ensure_ascii=False, indent=2))
        
        try:
            response = self.model.generate_content(prompt)
            cleaned_text = self._clean_json_response(response.text)
            json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
            if not json_match:
                print(f"  -> [IA Validação] ERRO JSON: Nenhum JSON encontrado. Resposta: {response.text}")
                return {"partida_encontrada": False, "error": "Nenhum JSON na resposta de validação"}
            
            validation_result = json.loads(json_match.group(0))
            print(f"  -> [IA Validação] Resultado: {validation_result}")
            return validation_result
            
        except Exception as e:
            print(f"  -> [IA Validação] ERRO na API Gemini: {e}")
            return {"partida_encontrada": False, "error": str(e)}