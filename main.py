import os
import csv
import json
import time
import re
import pandas as pd
from datetime import datetime
from google import genai
from jobspy import scrape_jobs
from docxtpl import DocxTemplate
from docx import Document
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Configuração do Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("ERRO: GOOGLE_API_KEY não encontrada no arquivo .env")
    exit()

# Carregar prompt base (se existir)
def carregar_prompt_base():
    if os.path.exists("prompt.txt"):
        with open("prompt.txt", "r", encoding="utf-8") as f:
            return f.read()
    return "Você é um Ghostwriter de Currículos de Elite."

PROMPT_SISTEMA = carregar_prompt_base()

# Inicializa o cliente com a instrução de sistema
client = genai.Client(api_key=API_KEY)

# --- CONFIGURAÇÕES ---
CARGO = "Programador junior"
LOCALIZACAO = "remoto"
REMOTO = True
LIMITE_VAGAS = 10
TEMPLATE_PATH = "templates/template-2.0.docx"
OUTPUT_DIR = "meus_curriculos"
HISTORY_FILE = "historico_candidaturas.csv"
MODELO = "gemini-flash-latest"
# --------------------

def limpar_nome_arquivo(nome):
    """Remove caracteres especiais para criar um nome de arquivo válido."""
    nome = str(nome) if nome is not None else "Desconhecido"
    nome = re.sub(r'[\\/*?:"<>|]', '', nome)
    return nome.replace(' ', '_')

def salvar_historico(vaga_title, empresa, caminho_arquivo):
    """Adiciona a candidatura à tabela de histórico (CSV)."""
    arquivo_existe = os.path.exists(HISTORY_FILE)
    data_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(HISTORY_FILE, mode='a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f, delimiter=';')
        if not arquivo_existe:
            writer.writerow(['Data/Hora', 'Vaga', 'Empresa', 'Arquivo do Currículo'])
        writer.writerow([data_hora, vaga_title, empresa, caminho_arquivo])

def call_gemini_with_retry(prompt, max_retries=3):
    for i in range(max_retries):
        try:
            # Usando config com system_instruction
            response = client.models.generate_content(
                model=MODELO,
                contents=prompt,
                config={'system_instruction': PROMPT_SISTEMA}
            )
            return response.text.strip()
        except Exception as e:
            if any(err in str(e) for err in ["429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"]):
                wait_time = (i + 1) * 10
                print(f"   [Servidor ocupado ou cota atingida. Aguardando {wait_time}s para tentar novamente...]")
                time.sleep(wait_time)
            else:
                raise e
    raise Exception("Falha na API após tentativas.")

def analisar_vaga(descricao_vaga):
    prompt = f"Analise esta vaga de emprego e extraia os pontos chave conforme definido na instrução do sistema. Retorne um JSON com: 'keywords', 'pain_points', 'ideal_profile' e 'summary'.\n\nDESCRIÇÃO DA VAGA:\n{descricao_vaga}"
    return call_gemini_with_retry(prompt)

def adaptar_curriculo(texto_curriculo, analise_vaga_json):
    prompt = f"Baseado na análise da vaga: {analise_vaga_json}, adapte o currículo abaixo para um match de 100%. Retorne um JSON com as chaves: 'summary', 'skills', 'highlights', 'exp_1_desc', 'exp_2_desc'.\n\nCURRÍCULO ATUAL:\n{texto_curriculo}"
    return call_gemini_with_retry(prompt)

def extrair_texto_docx(caminho):
    doc = Document(caminho)
    return "\n".join([p.text for p in doc.paragraphs if p.text])

def limpar_json_ia(texto):
    return texto.replace("```json", "").replace("```", "").strip()

def buscar_vagas():
    print(f"\n[1/6] Buscando vagas para '{CARGO}' em {LOCALIZACAO}...")
    try:
        jobs = scrape_jobs(
            site_name=["indeed", "linkedin", "google"],
            search_term=CARGO,
            location=LOCALIZACAO,
            is_remote=REMOTO,
            results_wanted=LIMITE_VAGAS,
            country_indeed='brazil',
            hours_old=168,
            linkedin_fetch_description=True 
        )
        return jobs
    except Exception as e:
        print(f"Erro na busca: {e}")
        return pd.DataFrame()

def main():
    if not os.path.exists(TEMPLATE_PATH):
        print(f"ERRO: Template não encontrado.")
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    jobs = buscar_vagas()
    if jobs.empty:
        print("Nenhuma vaga encontrada.")
        return

    print("\nVagas encontradas:")
    for i, (idx, row) in enumerate(jobs.iterrows()):
        print(f"[{i}] {row['title']} - {row['company']}")
    
    try:
        escolha = int(input("\nDigite o número da vaga: "))
        vaga = jobs.iloc[escolha]
    except: return

    print(f"\n[2/6] Analisando vaga: {vaga['title']}...")
    analise_raw = limpar_json_ia(analisar_vaga(vaga['description']))
    analise = json.loads(analise_raw)
    print(f"   Keywords: {', '.join(analise.get('keywords', []))}")

    print("\n[3/6] Lendo currículo base...")
    curriculo_base = extrair_texto_docx(TEMPLATE_PATH)

    print("[4/6] Adaptando conteúdo (Aguardando se necessário)...")
    conteudo_adaptado_raw = limpar_json_ia(adaptar_curriculo(curriculo_base, analise_raw))
    contexto = json.loads(conteudo_adaptado_raw)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    titulo_limpo = limpar_nome_arquivo(vaga['title'])
    empresa_limpa = limpar_nome_arquivo(vaga['company'])
    nome_arquivo = f"{titulo_limpo}_{empresa_limpa}_{timestamp}.docx"
    caminho_final = os.path.join(OUTPUT_DIR, nome_arquivo)

    print(f"[5/6] Salvando currículo em {caminho_final}...")
    doc = DocxTemplate(TEMPLATE_PATH)
    doc.render(contexto)
    doc.save(caminho_final)

    salvar_historico(vaga['title'], vaga['company'], caminho_final)
    print(f"\n[6/6] SUCESSO! Histórico atualizado em '{HISTORY_FILE}'.")

if __name__ == "__main__":
    main()
