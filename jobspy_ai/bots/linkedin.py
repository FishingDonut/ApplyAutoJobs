import os
import json
import time
from playwright.sync_api import sync_playwright
from ..core.ai import GeminiEngine

USER_DATA_DIR = ".sessao_linkedin"

class LinkedInBot:
    def __init__(self):
        self.ai = GeminiEngine()
        self.perfil = self._load_perfil()

    # Carrega as informações do candidato do arquivo de perfil.
    # Fundamental para preencher perguntas sobre experiência e competências no LinkedIn.
    def _load_perfil(self):
        if os.path.exists("perfil.json"):
            with open("perfil.json", "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    # Consulta a IA para decidir seleções e respostas curtas no modal de candidatura.
    # Usado principalmente em perguntas de triagem que variam entre as empresas.
    def responder_pergunta(self, pergunta, opcoes=None):
        print(f"   [LinkedInBot-IA] Analisando: {pergunta[:50]}...")
        opcoes_str = f"\nOPÇÕES:\n{json.dumps(opcoes, indent=2, ensure_ascii=False)}" if opcoes else ""
        
        prompt = f"""
        PERGUNTA LINKEDIN: {pergunta}{opcoes_str}
        PERFIL DO CANDIDATO: {json.dumps(self.perfil, indent=2, ensure_ascii=False)}
        
        INSTRUÇÃO: Se for múltipla escolha, retorne apenas o texto exata da opção. Se for resposta curta, seja direto.
        """
        return self.ai.call_with_retry(prompt)

    # Automatiza o fluxo de "Easy Apply" (Candidatura Simplificada) do LinkedIn.
    # Navega pelo modal, preenche formulários dinâmicos e anexa o currículo adaptado.
    def aplicar(self, url_vaga, caminho_curriculo):
        print(f"\n[ROBÔ LINKEDIN] Acessando: {url_vaga}")
        
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
            time.sleep(3)

            try:
                btn_easy = page.get_by_label("Candidatura simplificada", exact=False)
                if btn_easy.is_visible():
                    btn_easy.click()
                else:
                    print("   [!] Candidatura simplificada não disponível.")
                    return False
            except:
                return False

            time.sleep(2)

            # Loop de preenchimento do Modal do LinkedIn
            for _ in range(10):
                # 1. Perguntas de Texto
                labels = page.query_selector_all("label")
                for label_el in labels:
                    pergunta = label_el.inner_text().strip()
                    campo_id = label_el.get_attribute("for")
                    if campo_id:
                        campo = page.query_selector(f"#{campo_id}")
                        if campo and campo.is_visible() and not campo.input_value():
                            if campo.as_element().tag_name in ["input", "textarea"]:
                                resposta = self.responder_pergunta(pergunta)
                                campo.fill(resposta)

                # 2. Upload de Currículo
                upload_input = page.query_selector("input[type='file']")
                if upload_input and upload_input.is_visible():
                    upload_input.set_input_files(caminho_curriculo)
                    time.sleep(1)

                # 3. Avançar
                btn_next = page.query_selector("button:has-text('Avançar'), button:has-text('Próximo'), button:has-text('Revisar'), button:has-text('Enviar candidatura')")
                if btn_next and btn_next.is_visible():
                    texto = btn_next.inner_text()
                    btn_next.click()
                    time.sleep(2)
                    if "Enviar candidatura" in texto:
                        print("[SUCESSO] Candidatura LinkedIn enviada!")
                        return True
                else:
                    break
            
            return False
