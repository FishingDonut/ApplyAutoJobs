import os
import json
import time
from google import genai
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GOOGLE_API_KEY")
MODELO = "gemini-2.0-flash"

class GeminiEngine:
    def __init__(self):
        if not API_KEY:
            raise ValueError("GOOGLE_API_KEY não encontrada no arquivo .env")
        self.client = genai.Client(api_key=API_KEY)
        self.prompt_sistema = self._load_prompt()

    def _load_prompt(self):
        if os.path.exists("prompt.txt"):
            with open("prompt.txt", "r", encoding="utf-8") as f:
                return f.read()
        return "Você é um especialista em recrutamento e seleção."

    def call_with_retry(self, prompt, max_retries=3):
        time.sleep(2)
        for i in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=MODELO,
                    contents=prompt,
                    config={'system_instruction': self.prompt_sistema}
                )
                return response.text.strip()
            except Exception as e:
                if "429" in str(e):
                    time.sleep(10)
                    continue
                time.sleep(5)
        raise Exception("Falha na API do Gemini após múltiplas tentativas.")

    def adaptar_curriculo(self, vaga_desc, curriculo_base):
        prompt = f"""
        OBJETIVO: Adaptar meu currículo para a vaga abaixo.
        VAGA: {vaga_desc}
        BASE: {curriculo_base}
        Retorne JSON: {{ 'analise': {{ 'keywords': [] }}, 'adaptacao': {{ 'summary': '', 'skills': '', 'highlights': '', 'exp_1_desc': '', 'exp_2_desc': '' }} }}
        """
        raw = self.call_with_retry(prompt)
        return self._limpar_json(raw)

    def analisar_vaga(self, vaga_desc, perfil_usuario):
        prompt = f"""
        ANALISE A VAGA ABAIXO CONSIDERANDO O PERFIL DO CANDIDATO.
        
        PERFIL DO CANDIDATO:
        {perfil_usuario}
        
        DESCRIÇÃO DA VAGA:
        {vaga_desc}
        
        RETORNE APENAS UM JSON NO FORMATO:
        {{
            "match_score": (int 0-100),
            "tech_stack": (string com as 5 principais techs separadas por vírgula),
            "salario_estimado": (string ex: "R$ 8.000 - 12.000" ou "Não informado"),
            "justificativa": (string curta explicando a nota)
        }}
        """
        raw = self.call_with_retry(prompt)
        return self._limpar_json(raw)

    def _limpar_json(self, texto):
        texto = texto.replace("```json", "").replace("```", "").strip()
        start = texto.find('{')
        end = texto.rfind('}') + 1
        return texto[start:end] if (start != -1 and end != 0) else texto
