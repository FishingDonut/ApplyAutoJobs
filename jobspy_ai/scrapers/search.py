from jobspy import scrape_jobs
from sqlmodel import Session, select
from ..db.database import engine
from ..db.models import Vaga
from ..core.match import MatchEngine
import pandas as pd
import json
import os
import time

# Ponto de entrada do pilar de Descoberta. Coleta vagas de múltiplas fontes e salva no MySQL.
# Implementa a lógica de evitar duplicatas e realizar o match local imediato para cada vaga.
def search_and_save(termo: str, localizacao: str = "remoto", remoto: bool = True, limite: int = 20):
    print(f"Buscando vagas para '{termo}' em '{localizacao}' (remoto={remoto})...")
    
    perfil_data = "{}"
    if os.path.exists("perfil.json"):
        with open("perfil.json", "r", encoding="utf-8") as f:
            perfil_data = f.read()

    matcher = MatchEngine(perfil_data)
    all_jobs_list = []
    
    # Tentamos sites individualmente para evitar que um erro 403 em um derrube a busca toda.
    # Essa abordagem modular aumenta a resiliência do scraper contra bloqueios temporários.
    sites_para_tentar = ["linkedin", "indeed"]
    
    for site in sites_para_tentar:
        try:
            print(f"   -> Tentando {site}...")
            # Pequeno delay entre sites para evitar flag de bot.
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

    # Consolida os DataFrames de diferentes fontes em uma única estrutura de processamento.
    full_df = pd.concat(all_jobs_list, ignore_index=True)
    novas_vagas = 0

    with Session(engine) as session:
        for _, row in full_df.iterrows():
            link = row.get('job_url') or row.get('url') or ""
            if not link: continue

            # Normalização de link para evitar duplicados causados por parâmetros de rastreio (UTM).
            # Garante que a mesma vaga não seja salva múltiplas vezes se encontrada em fontes diferentes.
            link = str(link).split('?')[0] 

            statement = select(Vaga).where(Vaga.link == link)
            existing = session.exec(statement).first()
            
            if not existing:
                titulo = row.get('title', 'Título não informado')
                empresa = row.get('company', 'Empresa não informada')
                descricao = row.get('description', 'Descrição não capturada.')

                print(f"   [MATCH] Analisando: {titulo[:30]}...")
                site_origem = "Gupy" if "gupy.io" in str(link).lower() else "LinkedIn" if "linkedin.com" in str(link).lower() else "Indeed"
                
                # Cálculo de Match Determinístico (Local) via NLP Básico.
                # Substitui a IA nesta etapa para garantir velocidade e cota infinita.
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
