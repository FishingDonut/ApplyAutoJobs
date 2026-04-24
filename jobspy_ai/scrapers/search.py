from jobspy import scrape_jobs
from sqlmodel import Session, select, or_, and_
from ..db.database import engine
from ..db.models import Vaga
from ..core.match import MatchEngine
import pandas as pd
import json
import os
import time
import re
import requests
from bs4 import BeautifulSoup

def fetch_description_deep(url, site):
    """
    Tenta capturar a descrição da vaga acessando o link diretamente.
    Implementa padrões específicos para cada plataforma (Senior Level).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- PADRÕES ESPECÍFICOS POR SITE ---
        if site == "LinkedIn":
            # LinkedIn Public Job Page
            desc_el = soup.find('div', class_='description__text') or \
                      soup.find('div', class_='show-more-less-html__markup') or \
                      soup.find('section', class_='description')
            if desc_el: return desc_el.get_text(separator='\n', strip=True)

        elif site == "Gupy":
            # Gupy usa classes específicas ou JSON-LD
            desc_el = soup.find('div', {'data-testid': 'text-description'}) or \
                      soup.find('div', class_='job-description') or \
                      soup.find('section', class_='sc-ef08169e-3') # Classe comum dinâmica
            if desc_el: return desc_el.get_text(separator='\n', strip=True)
            
            # Tenta via JSON-LD
            script_json = soup.find('script', type='application/ld+json')
            if script_json:
                try:
                    data = json.loads(script_json.string)
                    if isinstance(data, list): data = data[0]
                    return data.get('description')
                except: pass

        elif site == "Indeed":
            desc_el = soup.find('div', id='jobDescriptionText') or \
                      soup.find('div', class_='jobsearch-JobComponent-description')
            if desc_el: return desc_el.get_text(separator='\n', strip=True)

        # --- FALLBACK GENÉRICO (Lógica de Limpeza de Texto) ---
        # Se não for nenhum dos acima, remove scripts e estilos e pega o conteúdo útil
        for s in soup(['script', 'style', 'nav', 'header', 'footer']):
            s.decompose()
        
        # Busca por containers longos de texto que provavelmente são a descrição
        main_content = soup.find('main') or soup.find('article') or soup.find('body')
        if main_content:
            text = main_content.get_text(separator='\n', strip=True)
            # Filtro simples: Se o texto for muito curto, ignoramos
            if len(text) > 300:
                return text

    except Exception as e:
        print(f"      [!] Falha no Deep Fetch ({site}): {e}")
        
    return None

# Ponto de entrada do pilar de Descoberta. Coleta vagas de múltiplas fontes e salva no MySQL.
def search_and_save(termo: str, localizacao: str = "remoto", remoto: bool = True, limite: int = 20):
    perfil_data_raw = "{}"
    pais_perfil = "brazil"
    filtro_pais = "Brazil" # Para filtragem posterior no DataFrame
    
    if os.path.exists("perfil.json"):
        with open("perfil.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            perfil_data_raw = json.dumps(data)
            
            # Se o usuário não passou um local específico, usamos a preferência do perfil
            if localizacao == "remoto":
                localizacao = data.get("preferencias", {}).get("regiao_busca", "Brasil")
            
            # Mapeamento e tradução para o motor de busca (LinkedIn/Indeed preferem inglês)
            pais_nome = data.get("dados_pessoais", {}).get("pais", "Brasil").lower()
            if "brasil" in pais_nome: 
                pais_perfil = "brazil"
                filtro_pais = "Brazil"
                # Forçamos "Brazil" em inglês para o parâmetro location do LinkedIn
                if localizacao.lower() == "brasil": localizacao = "Brazil"
            elif "usa" in pais_nome or "estados unidos" in pais_nome: 
                pais_perfil = "usa"
                filtro_pais = "USA"

    print(f"Buscando vagas para '{termo}' em '{localizacao}' (remoto={remoto}, pais={pais_perfil})...")
    matcher = MatchEngine(perfil_data_raw)
    all_jobs_list = []
    
    # Lista de sites para busca via JobSpy API
    sites_para_tentar = ["linkedin", "indeed", "google"]
    
    for site in sites_para_tentar:
        try:
            print(f"   -> Tentando {site}...")
            time.sleep(2)
            
            jobs = scrape_jobs(
                site_name=[site],
                search_term=termo,
                location=localizacao,
                is_remote=remoto,
                results_wanted=max(5, limite // 2),
                country_indeed=pais_perfil,
                description_format="markdown",
                fetch_description=True
            )
            
            if not jobs.empty:
                # FILTRO DE SEGURANCA: Garante que a vaga e do pais correto
                # O JobSpy as vezes traz vagas globais se a localizacao for muito generica.
                if filtro_pais == "Brazil":
                    # Aceitamos se location tiver 'Brazil', 'BR' ou estiver vazia (remoto as vezes vem vazio)
                    # mas para LinkedIn/Indeed, geralmente 'Brazil' ou 'BR' aparece.
                    mask = jobs['location'].str.contains('Brazil|BR|Brasil', case=False, na=True)
                    jobs = jobs[mask]
                
                if not jobs.empty:
                    print(f"      [OK] {len(jobs)} vagas validas encontradas no {site}.")
                    all_jobs_list.append(jobs)
                else:
                    print(f"      [!] Vagas encontradas no {site} nao correspondem ao pais alvo.")
            else:
                print(f"      [!] Nenhuma vaga encontrada no {site}.")
                
        except Exception as e:
            print(f"      [FALHA] {site} indisponível no momento: {e}")
            continue

    if not all_jobs_list:
        print("❌ Nenhuma fonte de vagas respondeu com sucesso.")
        return 0

    full_df = pd.concat(all_jobs_list, ignore_index=True)
    novas_vagas = 0

    with Session(engine) as session:
        for _, row in full_df.iterrows():
            link_original = row.get('job_url') or row.get('url') or ""
            if not link_original: continue

            # Normalização de URL
            link = str(link_original).split('?')[0].rstrip('/')
            link = re.sub(r'https://[a-z]{2}\.linkedin\.com', 'https://www.linkedin.com', link)

            titulo = str(row.get('title', 'Título não informado')).strip()
            empresa = str(row.get('company', 'Empresa não informada')).strip()

            statement = select(Vaga).where(
                or_(
                    Vaga.link == link,
                    and_(Vaga.titulo == titulo, Vaga.empresa == empresa)
                )
            )
            existing = session.exec(statement).first()
            
            if not existing:
                site_origem = "Gupy" if "gupy.io" in str(link).lower() else "LinkedIn" if "linkedin.com" in str(link).lower() else "Indeed"
                
                # Extração de descrição com motor de fallback por site
                raw_desc = row.get('description')
                if pd.isna(raw_desc) or not str(raw_desc).strip() or len(str(raw_desc)) < 150:
                    print(f"      [DEEP FETCH] Tentando capturar descrição completa para: {titulo[:20]}...")
                    descricao = fetch_description_deep(link, site_origem) or 'Descrição não capturada.'
                else:
                    descricao = str(raw_desc).strip()

                print(f"   [MATCH] Analisando: {titulo[:30]}...")
                
                # Cálculo de Match
                score, tech, justificativa = matcher.calcular_match(descricao)

                vaga = Vaga(
                    titulo=titulo,
                    empresa=empresa,
                    link=link,
                    site=site_origem,
                    status='Novo',
                    termo_pesquisa=termo,
                    descricao=descricao,
                    match_score=score,
                    tech_stack=tech,
                    salario_estimado="Sob consulta",
                    justificativa=justificativa
                )
                session.add(vaga)
                novas_vagas += 1
        
        session.commit()
    return novas_vagas
