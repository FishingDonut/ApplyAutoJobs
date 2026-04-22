from jobspy import scrape_jobs
from sqlmodel import Session, select
from ..db.database import engine
from ..db.models import Vaga
import pandas as pd
from datetime import datetime

def search_and_save(termo: str, localizacao: str = "remoto", remoto: bool = True, limite: int = 20):
    print(f"Buscando vagas para '{termo}' em '{localizacao}' (remoto={remoto})...")
    
    try:
        jobs = scrape_jobs(
            site_name=["indeed", "linkedin", "google"],
            search_term=termo,
            location=localizacao,
            is_remote=remoto,
            results_wanted=limite,
            country_indeed='brazil',
            hours_old=72,
            linkedin_fetch_description=True 
        )
        
        novas_vagas = 0
        with Session(engine) as session:
            for _, row in jobs.iterrows():
                link = row.get('job_url') or row.get('url') or ""
                if link:
                    # Verificar se já existe
                    statement = select(Vaga).where(Vaga.link == link)
                    existing = session.exec(statement).first()
                    
                    if not existing:
                        site = "Gupy" if "gupy.io" in link.lower() else "LinkedIn" if "linkedin.com" in link.lower() else "Outro"
                        vaga = Vaga(
                            titulo=row['title'],
                            empresa=row['company'],
                            link=link,
                            site=site,
                            status='Novo',
                            termo_pesquisa=termo,
                            descricao=row['description']
                        )
                        session.add(vaga)
                        novas_vagas += 1
            
            session.commit()
        return novas_vagas
    except Exception as e:
        print(f"Erro na busca: {e}")
        return 0
