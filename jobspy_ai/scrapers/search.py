from jobspy import scrape_jobs
from sqlmodel import Session, select
from ..db.database import engine
from ..db.models import Vaga
from ..core.ai import GeminiEngine
import pandas as pd
import json
import os
import time

def search_and_save(termo: str, localizacao: str = "remoto", remoto: bool = True, limite: int = 20):
    print(f"Buscando vagas para '{termo}' em '{localizacao}' (remoto={remoto})...")
    
    perfil_data = "{}"
    if os.path.exists("perfil.json"):
        with open("perfil.json", "r", encoding="utf-8") as f:
            perfil_data = f.read()

    ai = GeminiEngine()
    all_jobs_list = []
    
    # Tentamos sites individualmente para evitar que um erro 403 em um derrube a busca toda
    sites_para_tentar = ["linkedin", "indeed"]
    
    for site in sites_para_tentar:
        try:
            print(f"   -> Tentando {site}...")
            # Pequeno delay entre sites para evitar flag de bot
            time.sleep(2)
            
            jobs = scrape_jobs(
                site_name=[site],
                search_term=termo,
                location=localizacao,
                is_remote=remoto,
                results_wanted=max(5, limite // 2),
                country_indeed='brazil'
            )
            
            if not jobs.empty:
                print(f"      [OK] {len(jobs)} vagas encontradas no {site}.")
                all_jobs_list.append(jobs)
            else:
                print(f"      [!] Nenhuma vaga encontrada no {site}.")
                
        except Exception as e:
            print(f"      [FALHA] {site} indisponível no momento: {e}")
            continue

    if not all_jobs_list:
        print("❌ Nenhuma fonte de vagas respondeu com sucesso.")
        return 0

    # Consolida resultados
    full_df = pd.concat(all_jobs_list, ignore_index=True)
    novas_vagas = 0

    with Session(engine) as session:
        for _, row in full_df.iterrows():
            link = row.get('job_url') or row.get('url') or ""
            if not link: continue

            # Normalização de link para evitar duplicados
            link = str(link).split('?')[0] 

            statement = select(Vaga).where(Vaga.link == link)
            existing = session.exec(statement).first()
            
            if not existing:
                titulo = row.get('title', 'Título não informado')
                empresa = row.get('company', 'Empresa não informada')
                descricao = row.get('description', 'Descrição não capturada.')

                print(f"   [IA] Analisando match: {titulo[:30]}...")
                site_origem = "Gupy" if "gupy.io" in str(link).lower() else "LinkedIn" if "linkedin.com" in str(link).lower() else "Indeed"
                
                # Inteligência Artificial
                analise_raw = ai.analisar_vaga(descricao, perfil_data)
                try:
                    analise = json.loads(analise_raw)
                except:
                    analise = {"match_score": 0, "tech_stack": "", "salario_estimado": "Erro", "justificativa": ""}

                vaga = Vaga(
                    titulo=titulo,
                    empresa=empresa,
                    link=link,
                    site=site_origem,
                    status='Novo',
                    termo_pesquisa=termo,
                    descricao=descricao,
                    match_score=analise.get("match_score", 0),
                    tech_stack=analise.get("tech_stack", ""),
                    salario_estimado=analise.get("salario_estimado", ""),
                    justificativa=analise.get("justificativa", "")
                )
                session.add(vaga)
                novas_vagas += 1
        
        session.commit()
    return novas_vagas
