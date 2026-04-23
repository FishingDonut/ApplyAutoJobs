import os
import time
import json
import subprocess
import tempfile
from google import genai
from dotenv import load_dotenv

# Interface base para os motores de IA.
# Permite que o sistema troque entre API, CLI ou Local de forma transparente.
class BaseAIEngine:
    def call_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        raise NotImplementedError

    def adaptar_curriculo(self, vaga_desc: str, curriculo_base: str) -> str:
        """
        Gera a adaptação do currículo em formato JSON.
        Este prompt é a base para o pilar de 'Adaptação' do sistema.
        """
        prompt = f"""
        ADAPTE MEU CURRÍCULO PARA ESTA VAGA.
        VAGA: {vaga_desc}
        CURRÍCULO BASE: {curriculo_base}
        Retorne um JSON com a chave 'adaptacao' contendo: summary, skills, highlights, exp_1_desc, exp_2_desc.
        IMPORTANTE: Retorne APENAS o JSON, sem markdown ou explicações.
        """
        return self.call_with_retry(prompt)

# Motor que utiliza a API oficial do Google Gemini.
# Sujeito a limites de cota estritos (Rate Limits).
class GeminiApiEngine(BaseAIEngine):
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.modelo = "gemini-2.0-flash"
        self.client = genai.Client(api_key=self.api_key)
        self.prompt_sistema = self._load_prompt()

    # Carrega o prompt de sistema para dar contexto à IA.
    def _load_prompt(self):
        if os.path.exists("prompt.txt"):
            with open("prompt.txt", "r", encoding="utf-8") as f:
                return f.read()
        return "Você é um especialista em carreiras tech."

    # Tenta realizar a chamada à API com backoff em caso de erro de cota (429).
    def call_with_retry(self, prompt, max_retries=3):
        for i in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.modelo,
                    contents=prompt,
                    config={'system_instruction': self.prompt_sistema}
                )
                return response.text.strip()
            except Exception as e:
                if "429" in str(e):
                    time.sleep(10)
                    continue
                return ""
        return ""

# Motor que utiliza o Gemini CLI via terminal.
# Ideal para contornar limites de API usando a autenticação do próprio terminal do usuário.
class GeminiCliEngine(BaseAIEngine):
    def __init__(self):
        self.prompt_sistema = self._load_prompt()
        self.cli_command = os.getenv("GEMINI_CLI_COMMAND", "gemini")

    # Carrega o prompt de sistema do arquivo prompt.txt.
    def _load_prompt(self):
        if os.path.exists("prompt.txt"):
            with open("prompt.txt", "r", encoding="utf-8") as f:
                return f.read()
        return "Você é um especialista em carreiras tech."

    # Executa o comando do terminal e captura a saída.
    # Usa arquivos temporários para garantir compatibilidade com prompts longos no Windows.
    def call_with_retry(self, prompt, max_retries=3):
        full_prompt = f"{self.prompt_sistema}\n\n{prompt}"
        
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.txt', encoding='utf-8') as tf:
            tf.write(full_prompt)
            temp_path = tf.name

        try:
            # Tenta rodar o comando configurado. 
            # Se for 'gemini', o CLI deve estar no PATH.
            result = subprocess.run(
                [self.cli_command, temp_path], 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                shell=True
            )
            
            if result.returncode != 0:
                print(f"   [ERRO CLI] Terminal retornou erro: {result.stderr.strip()}")
                return ""

            output = result.stdout.strip()
            
            # Limpeza de Markdown
            if "```json" in output:
                output = output.split("```json")[1].split("```")[0].strip()
            elif "```" in output:
                output = output.split("```")[1].split("```")[0].strip()
                
            return output
        except Exception as e:
            print(f"   [ERRO CLI] Falha ao executar subprocesso: {e}")
            return ""
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

# Fábrica para instanciar o motor de IA configurado no .env.
# Promove o desacoplamento entre a lógica de negócio e o provedor de inteligência.
def GeminiEngine():
    load_dotenv()
    provider = os.getenv("AI_PROVIDER", "api").lower()
    
    if provider == "cli":
        return GeminiCliEngine()
    return GeminiApiEngine()
