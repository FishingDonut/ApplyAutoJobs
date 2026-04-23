import os
import json
import time
from playwright.sync_api import sync_playwright
from ..core.ai import GeminiEngine

USER_DATA_DIR = ".sessao_gupy"

class GupyBot:
    def __init__(self):
        self.ai = GeminiEngine()
        self.perfil = self._load_perfil()

    # Carrega os dados do candidato do arquivo local para alimentar o bot.
    # Serve como a fonte da verdade para o preenchimento automático de campos.
    def _load_perfil(self):
        if os.path.exists("perfil.json"):
            with open("perfil.json", "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    # Aciona a Inteligência Artificial para gerar respostas a perguntas do formulário.
    # É chamada quando o bot encontra uma pergunta dissertativa ou múltipla escolha não trivial.
    def responder_pergunta(self, pergunta, contexto_vaga, opcoes=None):
        """Aciona a IA apenas para perguntas complexas ou dissertativas."""
        tipo = "ESCOLHA" if opcoes else "RESPOSTA DISSERTATIVA"
        print(f"   [GupyBot-IA] Processando {tipo}: {pergunta[:50]}...")
        
        opcoes_str = f"\nOPÇÕES DISPONÍVEIS:\n{json.dumps(opcoes, indent=2, ensure_ascii=False)}" if opcoes else ""
        
        prompt = f"""
        PERGUNTA GUPY: {pergunta}{opcoes_str}
        PERFIL DO CANDIDATO: {json.dumps(self.perfil, indent=2, ensure_ascii=False)}
        CONTEXTO DA VAGA: {contexto_vaga[:1000]}
        
        INSTRUÇÃO: Se for escolha, retorne APENAS o texto da opção exata. Se for dissertativa, responda de forma profissional e curta.
        """
        return self.ai.call_with_retry(prompt)

    # Verifica se a página atual contém testes de lógica ou cultura da Gupy.
    # Essencial para pausar a automação e evitar que o robô tente responder testes humanos.
    def detectar_teste(self, page):
        conteudo = page.content().lower()
        gatilhos = ["teste de lógica", "teste de raciocínio", "cultura e valores", "raciocínio lógico", "assessment"]
        return any(g in conteudo for g in gatilhos)

    # Executa o fluxo de candidatura no navegador visível utilizando Playwright.
    # Orquestra o preenchimento de campos, upload de arquivos e navegação entre etapas.
    def aplicar(self, url_vaga, caminho_curriculo):
        print(f"\n[ROBÔ GUPY] Iniciando aplicação visível para: {url_vaga}")
        
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=False,
                args=["--start-maximized"],
                viewport=None,
                channel="chrome"
            )
            page = context.new_page()
            page.goto(url_vaga)
            
            try:
                page.wait_for_selector("text=/Candidatar-se/i", timeout=10000)
                page.click("text=/Candidatar-se/i")
            except: pass

            time.sleep(3)

            while True:
                # Detector de Testes
                if self.detectar_teste(page):
                    print("\n[!!!] TESTE DETECTADO: Complete manualmente e clique em 'Próximo'.")
                    while self.detectar_teste(page):
                        time.sleep(5)

                contexto_vaga = page.inner_text("body")[:2000]
                
                # 1. Campos de Texto
                campos_texto = page.query_selector_all("textarea, input[type='text'], input[type='email']")
                for campo in campos_texto:
                    if campo.is_visible() and not campo.input_value():
                        label = page.evaluate("(el) => el.getAttribute('aria-labelledby') || el.id", campo)
                        # Tenta preencher do perfil se for um campo comum
                        valor = self.perfil.get(label.lower(), "")
                        if not valor:
                            valor = self.responder_pergunta(label, contexto_vaga)
                        campo.fill(valor)
                        time.sleep(1)

                # 2. Upload de Currículo
                upload_input = page.query_selector("input[type='file']")
                if upload_input and upload_input.is_visible():
                    print(f"   [GupyBot] Anexando currículo: {caminho_curriculo}")
                    upload_input.set_input_files(caminho_curriculo)
                    time.sleep(2)

                # 3. Navegação
                btn_proximo = page.query_selector("text=/Próximo|Avançar|Enviar|Concluir/i")
                if btn_proximo and btn_proximo.is_visible():
                    btn_proximo.click()
                    time.sleep(5)
                    if "success" in page.url or "applied" in page.url:
                        print("[SUCESSO] Candidatura Gupy finalizada!")
                        return True
                else:
                    break
            
            return False
