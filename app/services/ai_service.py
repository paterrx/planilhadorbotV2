# Arquivo: app/services/ai_service.py
# Versão: 8.2 - LÓGICA FINAL: Adicionado limpador de JSON para resiliência máxima.

import google.generativeai as genai
import json
import re
from PIL import Image
import io
from app.config import Config

class AIService:
    def __init__(self, cfg: Config):
        self.config = cfg
        genai.configure(api_key=self.config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-pro-latest')
        self._load_base_prompt()

    def _load_base_prompt(self):
        try:
            with open(self.config.PROMPT_PATH, 'r', encoding='utf-8') as f:
                self.base_prompt = f.read()
        except FileNotFoundError:
            raise RuntimeError(f"ERRO CRÍTICO: Arquivo de prompt não encontrado em: {self.config.PROMPT_PATH}")

    def _clean_json_response(self, text):
        """Limpa a resposta de texto da IA para corrigir erros comuns de formatação JSON."""
        # Remove os blocos de código ```json e ```
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```', '', text)
        
        # Corrige erros comuns de digitação nas chaves
        text = text.replace('"descrricao_aposta"', '"descricao_aposta"')
        text = text.replace('"entrrada"', '"entrada"')
        
        # Corrige aspas duplas extras dentro dos valores
        text = re.sub(r':\s*""', ': "', text)
        # Usando r'' para string raw para evitar o SyntaxWarning
        text = re.sub(r'""\s*([,}\]])', r'"\1', text)
        
        # Corrige erros numéricos e de nulos
        text = text.replace('nulll', 'null')
        text = re.sub(r'(\d)\.\.(\d)', r'\1.\2', text) # Ex: 2..80 -> 2.80
        
        return text.strip()

    async def analyze_message(self, message_text, image_bytes=None):
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
                print(f"ERRO JSON: Nenhum bloco JSON encontrado após limpeza. Resposta Original: {response.text}")
                return {"message_type": "erro_ia", "data": {"error": "Nenhum JSON na resposta"}}

            return json.loads(json_match.group(0))

        except json.JSONDecodeError as e:
            print(f"ERRO JSON FINAL: {e}. Resposta da IA (após limpeza): {cleaned_text}")
            return {"message_type": "erro_ia", "data": {"error": "JSON inválido"}}
        except Exception as e:
            print(f"ERRO na API Gemini: {e}")
            return {"message_type": "erro_ia", "data": {"error": str(e)}}