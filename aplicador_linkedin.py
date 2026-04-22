import os
import json
import time
from playwright.sync_api import sync_playwright
from google import genai
from dotenv import load_dotenv

# Carrega configurações
load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=API_KEY)

USER_DATA_DIR = ".sessao_gupy" # Reutilizando a mesma pasta de sessão para simplificar
MODELO = "gemini-2.0-flash"

def carregar_perfil():
    with open("perfil.json", "r", encoding="utf-8") as f:
        return json.load(f)

def carregar_prompt_sistema():
    if os.path.exists("prompt.txt"):
        with open("prompt.txt", "r", encoding="utf-8") as f:
            return f.read()
    return "Você é um especialista em carreiras tech."

PERFIL = carregar_perfil()
PROMPT_SISTEMA = carregar_prompt_sistema()

def gerar_resposta_ia(pergunta, contexto_vaga, opcoes=None):
    """Usa o Gemini para responder perguntas do LinkedIn Easy Apply."""
    # Delay preventivo
    time.sleep(3)
    
    tipo = "ESCOLHA" if opcoes else "RESPOSTA"
    print(f"   [IA LinkedIn] {tipo}: {pergunta[:50]}...")
    
    opcoes_str = f"\nOPÇÕES:\n{json.dumps(opcoes, indent=2, ensure_ascii=False)}" if opcoes else ""
    
    prompt = f"""
    ESTA É UMA PERGUNTA DE UMA CANDIDATURA NO LINKEDIN.
    
    PERFIL DO CANDIDATO:
    {json.dumps(PERFIL, indent=2, ensure_ascii=False)}
    
    PERGUNTA:
    {pergunta}{opcoes_str}
    
    INSTRUÇÃO: Responda de forma curta e profissional. Se for uma pergunta de 'Sim ou Não', responda apenas 'Sim' ou 'Não' conforme o perfil.
    { 'Escolha a opção exata do JSON.' if opcoes else 'Retorne apenas o texto da resposta.' }
    """
    
    try:
        response = client.models.generate_content(
            model=MODELO,
            contents=prompt,
            config={'system_instruction': PROMPT_SISTEMA}
        )
        return response.text.strip()
    except Exception as e:
        print(f"   [ERRO IA] {e}")
        return "Sim" if not opcoes else opcoes[0]

def aplicar_vaga_linkedin(url_vaga, caminho_curriculo):
    """Fluxo de aplicação simplificada no LinkedIn."""
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

        # 1. Tentar clicar em "Candidatura simplificada"
        try:
            btn_easy = page.get_by_label("Candidatura simplificada", exact=False)
            if btn_easy.is_visible():
                btn_easy.click()
                print("   [ROBÔ] Iniciando formulário Easy Apply...")
            else:
                print("   [!] Candidatura simplificada não disponível para esta vaga.")
                return
        except Exception as e:
            print(f"   [!] Erro ao localizar botão Easy Apply: {e}")
            return

        time.sleep(2)

        # 2. Loop de preenchimento do Modal
        tentativas_avancar = 0
        while tentativas_avancar < 10: # Limite de etapas para evitar loop infinito
            
            # Verificar se há perguntas na tela
            labels = page.query_selector_all("label")
            for label_el in labels:
                pergunta = label_el.inner_text().strip()
                if not pergunta: continue
                
                # Tenta identificar o campo associado
                campo_id = label_el.get_attribute("for")
                if campo_id:
                    campo = page.query_selector(f"#{campo_id}")
                    if campo and campo.is_visible() and not campo.input_value():
                        # Se for um input de texto
                        if campo.as_element().tag_name == "input" or campo.as_element().tag_name == "textarea":
                            resposta = gerar_resposta_ia(pergunta, "LinkedIn Modal")
                            campo.fill(resposta)
                            time.sleep(0.5)

            # Tenta tratar Radio Buttons / Checkboxes no Modal
            # LinkedIn costuma usar fieldsets para grupos de perguntas
            
            # Tenta anexar currículo se solicitado
            upload_input = page.query_selector("input[type='file']")
            if upload_input and upload_input.is_visible():
                print(f"   [ROBÔ] Enviando currículo: {caminho_curriculo}")
                upload_input.set_input_files(caminho_curriculo)
                time.sleep(2)

            # Tenta clicar em "Avançar", "Revisar" ou "Enviar candidatura"
            btn_next = page.query_selector("button:has-text('Avançar'), button:has-text('Próximo'), button:has-text('Revisar'), button:has-text('Enviar candidatura')")
            
            if btn_next and btn_next.is_visible():
                texto_btn = btn_next.inner_text()
                print(f"   [ROBÔ] Clicando em: {texto_btn}")
                btn_next.click()
                time.sleep(3)
                
                if "Enviar candidatura" in texto_btn:
                    print("\n[SUCESSO] Candidatura LinkedIn enviada!")
                    break
            else:
                print("   [ROBÔ] Fim do formulário ou bloqueio encontrado.")
                break
            
            tentativas_avancar += 1

        print("\n[ROBÔ] Tarefa LinkedIn concluída.")
        time.sleep(5)

if __name__ == "__main__":
    url = input("URL da vaga LinkedIn: ")
    aplicar_vaga_linkedin(url, "meus_curriculos/Curriculo_Teste.docx")
