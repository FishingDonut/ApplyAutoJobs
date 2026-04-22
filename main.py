import os
import csv
import json
import time
import re
import pandas as pd
import webbrowser
from datetime import datetime
from google import genai
from jobspy import scrape_jobs
from docxtpl import DocxTemplate
from docx import Document
from dotenv import load_dotenv

# Importação do roteador central
from dispatcher import identificar_e_aplicar

# Carrega variáveis de ambiente
load_dotenv()

# Configuração do Gemini
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("ERRO: GOOGLE_API_KEY não encontrada no arquivo .env")
    exit()

# --- CONFIGURAÇÕES ---
CARGO_PADRAO = "Programador React"
LOCALIZACAO_PADRAO = "remoto"
REMOTO = True
LIMITE_BUSCA = 20
TEMPLATE_PATH = "templates/template-2.0.docx"
OUTPUT_DIR = "meus_curriculos"
DB_FILE = "vagas_central.csv" # Nosso "Banco de Dados" em CSV
MODELO = "gemini-2.0-flash"
# --------------------

PROMPT_SISTEMA = ""
if os.path.exists("prompt.txt"):
    with open("prompt.txt", "r", encoding="utf-8") as f:
        PROMPT_SISTEMA = f.read()

client = genai.Client(api_key=API_KEY)

# --- FUNÇÕES DE BANCO DE DADOS (CSV) ---

def inicializar_db():
    if not os.path.exists(DB_FILE):
        df = pd.DataFrame(columns=[
            'Data_Descoberta', 'Titulo', 'Empresa', 'Link', 'Site', 
            'Status', 'Arquivo_Curriculo', 'Termo_Pesquisa', 'Descricao'
        ])
        df.to_csv(DB_FILE, index=False, sep=';', encoding='utf-8-sig')

def carregar_db():
    return pd.read_csv(DB_FILE, sep=';', encoding='utf-8-sig')

def salvar_vagas_novas(jobs_df, termo):
    db = carregar_db()
    links_existentes = db['Link'].tolist()
    novas_vagas = []

    for _, row in jobs_df.iterrows():
        link = row.get('job_url') or row.get('url') or ""
        if link and link not in links_existentes:
            site = "Gupy" if "gupy.io" in link.lower() else "LinkedIn" if "linkedin.com" in link.lower() else "Outro"
            novas_vagas.append({
                'Data_Descoberta': datetime.now().strftime("%Y-%m-%d"),
                'Titulo': row['title'],
                'Empresa': row['company'],
                'Link': link,
                'Site': site,
                'Status': 'Novo',
                'Arquivo_Curriculo': '',
                'Termo_Pesquisa': termo,
                'Descricao': row['description']
            })
    
    if novas_vagas:
        novas_df = pd.DataFrame(novas_vagas)
        db = pd.concat([db, novas_df], ignore_index=True)
        db.to_csv(DB_FILE, index=False, sep=';', encoding='utf-8-sig')
        return len(novas_vagas)
    return 0

def atualizar_status_vaga(link, status, arquivo=""):
    db = carregar_db()
    idx = db.index[db['Link'] == link].tolist()
    if idx:
        db.at[idx[0], 'Status'] = status
        if arquivo:
            db.at[idx[0], 'Arquivo_Curriculo'] = arquivo
        db.to_csv(DB_FILE, index=False, sep=';', encoding='utf-8-sig')

# --- FUNÇÕES DE IA ---

def call_gemini_with_retry(prompt, max_retries=3):
    time.sleep(2)
    for i in range(max_retries):
        try:
            response = client.models.generate_content(
                model=MODELO,
                contents=prompt,
                config={'system_instruction': PROMPT_SISTEMA}
            )
            return response.text.strip()
        except Exception as e:
            if "429" in str(e):
                print(f"   [Cota Esgotada] Aguardando reset...")
                raise e
            time.sleep(10)
    raise Exception("Falha na API.")

def processar_ia_completa(vaga_desc, curriculo_base):
    prompt = f"""
    OBJETIVO: Adaptar meu currículo para a vaga.
    VAGA: {vaga_desc}
    BASE: {curriculo_base}
    Retorne JSON: {{ 'analise': {{ 'keywords': [] }}, 'adaptacao': {{ 'summary': '', 'skills': '', 'highlights': '', 'exp_1_desc': '', 'exp_2_desc': '' }} }}
    """
    return call_gemini_with_retry(prompt)

# --- UTILITÁRIOS ---

def limpar_json_ia(texto):
    texto = texto.replace("```json", "").replace("```", "").strip()
    start = texto.find('{')
    end = texto.rfind('}') + 1
    return texto[start:end] if (start != -1 and end != 0) else texto

def extrair_texto_docx(caminho):
    return "\n".join([p.text for p in Document(caminho).paragraphs if p.text])

def limpar_nome_arquivo(nome):
    nome = re.sub(r'[\\/*?:"<>|]', '', str(nome))
    return nome.replace(' ', '_')

# --- FLUXOS PRINCIPAIS ---

def buscar_e_guardar():
    termo = input(f"Termo de busca [{CARGO_PADRAO}]: ") or CARGO_PADRAO
    print(f"\n[1/2] Buscando vagas para '{termo}'...")
    try:
        jobs = scrape_jobs(
            site_name=["indeed", "linkedin", "google"],
            search_term=termo,
            location=LOCALIZACAO_PADRAO,
            is_remote=REMOTO,
            results_wanted=LIMITE_BUSCA,
            country_indeed='brazil',
            hours_old=72,
            linkedin_fetch_description=True 
        )
        qtd = salvar_vagas_novas(jobs, termo)
        print(f"Sucesso! {qtd} novas vagas adicionadas ao banco de dados.")
    except Exception as e:
        print(f"Erro na busca: {e}")

def gerenciar_candidaturas():
    db = carregar_db()
    # Filtra vagas que ainda não foram candidatadas
    pendentes = db[db['Status'] != 'Candidatado'].tail(15) # Mostra as 15 últimas
    
    if pendentes.empty:
        print("\nNenhuma vaga pendente no banco de dados. Vá em 'Buscar Novas Vagas'.")
        return

    print("\n--- VAGAS PENDENTES ---")
    for i, (idx, row) in enumerate(pendentes.iterrows()):
        status_str = f"[{row['Status']}]"
        print(f"{i} - {status_str} {row['Titulo']} @ {row['Empresa']} ({row['Site']})")
    
    try:
        escolha = int(input("\nEscolha o número da vaga (ou -1 para voltar): "))
        if escolha == -1: return
        vaga = pendentes.iloc[escolha]
    except: return

    print(f"\nSelecionada: {vaga['Titulo']}")
    print(f"Link: {vaga['Link']}")
    
    # Menu de Ação para a Vaga
    print("1. Abrir no Navegador")
    print("2. Gerar Currículo + Aplicar (IA necessária)")
    print("3. Marcar como Ignorada")
    print("4. Voltar")
    
    acao = input("Ação: ")
    
    if acao == '1':
        webbrowser.open(vaga['Link'])
    
    elif acao == '2':
        curriculo_base = extrair_texto_docx(TEMPLATE_PATH)
        print("[IA] Adaptando currículo...")
        try:
            res_raw = limpar_json_ia(processar_ia_completa(vaga['Descricao'], curriculo_base))
            dados = json.loads(res_raw)
            contexto = dados.get('adaptacao', {})
            
            nome_arq = f"{limpar_nome_arquivo(vaga['Titulo'])}_{limpar_nome_arquivo(vaga['Empresa'])}.docx"
            caminho_final = os.path.join(OUTPUT_DIR, nome_arq)
            
            doc = DocxTemplate(TEMPLATE_PATH)
            doc.render(contexto)
            doc.save(caminho_final)
            
            print(f"Currículo gerado: {caminho_final}")
            atualizar_status_vaga(vaga['Link'], 'Currículo Gerado', caminho_final)
            
            # Tentar aplicar
            resp = input("Deseja tentar aplicação automática agora? (s/n): ").lower()
            if resp == 's':
                if identificar_e_aplicar(vaga['Link'], caminho_final):
                    atualizar_status_vaga(vaga['Link'], 'Candidatado')
        except Exception as e:
            print(f"Erro na IA: {e}")
            if input("Deseja abrir o link manualmente? (s/n): ").lower() == 's':
                webbrowser.open(vaga['Link'])
                
    elif acao == '3':
        atualizar_status_vaga(vaga['Link'], 'Ignorada')

def main():
    inicializar_db()
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
    
    while True:
        print("\n=== RPA GESTOR DE VAGAS ===")
        print("1. Buscar Novas Vagas (Scraper)")
        print("2. Gerenciar/Aplicar Vagas (Tabela)")
        print("3. Sair")
        
        opcao = input("\nEscolha uma opção: ")
        
        if opcao == '1': buscar_e_guardar()
        elif opcao == '2': gerenciar_candidaturas()
        elif opcao == '3': break
        else: print("Opção inválida.")

if __name__ == "__main__":
    main()
