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

USER_DATA_DIR = ".sessao_gupy"
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
    """Usa o Gemini para responder perguntas ou escolher opções."""
    # Delay preventivo para evitar estourar limites de cota
    time.sleep(3)
    
    tipo = "ESCOLHA" if opcoes else "RESPOSTA DISSERTATIVA"
    print(f"   [IA] Processando {tipo}: {pergunta[:50]}...")
    
    opcoes_str = f"\nOPÇÕES DISPONÍVEIS:\n{json.dumps(opcoes, indent=2, ensure_ascii=False)}" if opcoes else ""
    
    prompt = f"""
    ESTA É UMA PERGUNTA DE UM FORMULÁRIO DE EMPREGO NA GUPY.
    
    PERFIL DO CANDIDATO:
    {json.dumps(PERFIL, indent=2, ensure_ascii=False)}
    
    CONTEXTO DA VAGA:
    {contexto_vaga}
    
    PERGUNTA:
    {pergunta}{opcoes_str}
    
    INSTRUÇÃO: {PERFIL.get('prompt_personalizado_respostas', 'Seja direto e profissional.')}
    
    { 'Escolha a opção MAIS ADEQUADA do JSON acima e retorne APENAS o texto exato da opção.' if opcoes else 'Retorne apenas o texto da resposta (máximo 3 frases).' }
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
        return opcoes[0] if opcoes else "Disponível para discutir em entrevista."

def detectar_teste(page):
    """Verifica se a página atual é um teste que exige atenção humana."""
    conteudo = page.content().lower()
    gatilhos = ["teste de lógica", "teste de raciocínio", "cultura e valores", "raciocínio lógico", "assessment"]
    for gatilho in gatilhos:
        if gatilho in conteudo:
            return True
    return False

def aplicar_vaga_gupy(url_vaga, caminho_curriculo):
    """Fluxo principal de aplicação na Gupy."""
    print(f"\n[ROBÔ GUPY] Iniciando aplicação para: {url_vaga}")
    
    if not os.path.exists(caminho_curriculo):
        print(f"ERRO: Currículo não encontrado em {caminho_curriculo}")
        return

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
        
        # 1. Clicar em "Candidatar-se"
        try:
            page.wait_for_selector("text=/Candidatar-se/i", timeout=10000)
            page.click("text=/Candidatar-se/i")
        except:
            pass

        time.sleep(3)

        while True:
            # --- DETECTOR DE TESTES ---
            if detectar_teste(page):
                print("\n[!!!] ATENÇÃO: Detectei um teste de Lógica ou Cultura.")
                print("Por segurança, o robô pausou. Complete o teste manualmente e clique em 'Próximo' no navegador.")
                print("O robô continuará automaticamente assim que a página de teste for superada.")
                while detectar_teste(page):
                    time.sleep(5)
                print("[ROBÔ] Teste superado, retomando automação...")

            contexto_vaga = page.inner_text("body")[:2000] # Pega o texto da página para contexto
            
            # --- 1. TRATAR CAMPOS DE TEXTO ---
            campos_texto = page.query_selector_all("textarea, input[type='text'], input[type='email']")
            for campo in campos_texto:
                if campo.is_visible() and not campo.input_value():
                    # Tenta achar o label
                    label = page.evaluate("""(el) => {
                        let id = el.getAttribute('aria-labelledby') || el.id;
                        let label = document.querySelector(`label[for='${id}']`) || document.querySelector(`[id='${id}']`);
                        return label ? label.innerText : 'Pergunta desconhecida';
                    }""", campo)
                    
                    resposta = gerar_resposta_ia(label, contexto_vaga)
                    campo.fill(resposta)
                    time.sleep(1)

            # --- 2. TRATAR SELECTS (DROPDOWNS) ---
            selects = page.query_selector_all("select")
            for sel in selects:
                if sel.is_visible():
                    label = "Selecione uma opção" # Simplificação do label para select
                    opcoes = sel.evaluate("(el) => Array.from(el.options).map(o => o.text).filter(t => t.trim() !== '')")
                    if opcoes:
                        escolha = gerar_resposta_ia(label, contexto_vaga, opcoes)
                        sel.select_option(label=escolha)
                        time.sleep(1)

            # --- 3. TRATAR RADIOS (Múltipla Escolha) ---
            # Agrupar radios por nome para tratar como uma única pergunta
            radios = page.query_selector_all("input[type='radio']")
            processados = set()
            for radio in radios:
                name = radio.get_attribute("name")
                if name and name not in processados:
                    if radio.is_visible():
                        # Pega todas as opções desse grupo
                        opcoes_elementos = page.query_selector_all(f"input[name='{name}']")
                        opcoes_texto = []
                        for opt in opcoes_elementos:
                            text = page.evaluate("(el) => el.parentElement.innerText", opt)
                            opcoes_texto.append(text.strip())
                        
                        escolha = gerar_resposta_ia("Escolha uma das opções:", contexto_vaga, opcoes_texto)
                        # Clica na opção escolhida
                        for opt in opcoes_elementos:
                            text = page.evaluate("(el) => el.parentElement.innerText", opt)
                            if escolha in text:
                                opt.click()
                                break
                        processados.add(name)
                        time.sleep(1)

            # --- 4. TRATAR UPLOAD DE CURRÍCULO ---
            upload_input = page.query_selector("input[type='file']")
            if upload_input:
                print(f"   Anexando currículo: {caminho_curriculo}")
                upload_input.set_input_files(caminho_curriculo)
                time.sleep(2)

            # --- 5. NAVEGAÇÃO ---
            btn_proximo = page.query_selector("text=/Próximo|Avançar|Enviar|Concluir/i")
            if btn_proximo and btn_proximo.is_visible():
                btn_proximo.click()
                time.sleep(5)
                
                if "success" in page.url or "applied" in page.url:
                    print("\n[SUCESSO] Candidatura finalizada com sucesso!")
                    break
            else:
                print("   Não encontrei mais botões de avanço. Verifique se há algum campo obrigatório pendente.")
                break

        print("\n[ROBÔ] Tarefa concluída.")
        while len(context.pages) > 0:
            time.sleep(1)

if __name__ == "__main__":
    # Teste rápido (substitua pela URL de uma vaga real da Gupy que você queira)
    url_teste = input("Cole a URL da vaga Gupy para testar: ")
    curriculo_teste = "Curriculo_Adaptado.docx"
    aplicar_vaga_gupy(url_teste, curriculo_teste)
