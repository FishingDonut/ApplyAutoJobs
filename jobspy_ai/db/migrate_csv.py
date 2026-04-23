import pandas as pd
import json
from sqlmodel import Session, select
from .database import engine, create_db_and_tables
from .models import Vaga, Perfil
import os

CSV_FILE = "vagas_central.csv"
PROFILE_FILE = "perfil.json"

def migrate():
    create_db_and_tables()
    
    # 1. MIGRAR VAGAS DO CSV
    if os.path.exists(CSV_FILE):
        print(f"[1/2] Iniciando migração de vagas de {CSV_FILE}...")
        try:
            # Lendo com tratamento de tipos e NaNs
            df = pd.read_csv(CSV_FILE, sep=';', encoding='utf-8-sig')
            # Converte todos os NaNs para None (compatível com SQL)
            df = df.where(pd.notnull(df), None)
            
            with Session(engine) as session:
                novas = 0
                erros = 0
                for _, row in df.iterrows():
                    link = str(row['Link']) if row['Link'] else None
                    if not link: continue

                    statement = select(Vaga).where(Vaga.link == link)
                    existing = session.exec(statement).first()
                    
                    if not existing:
                        try:
                            vaga = Vaga(
                                titulo=str(row['Titulo']),
                                empresa=str(row['Empresa']),
                                link=link,
                                site=str(row['Site']),
                                status=str(row['Status'] or "Novo"),
                                arquivo_curriculo=str(row['Arquivo_Curriculo']) if row['Arquivo_Curriculo'] else None,
                                termo_pesquisa=str(row['Termo_Pesquisa'] or "Migração"),
                                descricao=str(row['Descricao']) if row['Descricao'] else None
                            )
                            session.add(vaga)
                            novas += 1
                            # Commit a cada 10 para performance vs segurança
                            if novas % 10 == 0:
                                session.commit()
                        except Exception as e:
                            erros += 1
                            print(f"   [Erro] Falha na vaga {link[:50]}...: {e}")
                
                session.commit()
                print(f"✅ Migração de vagas concluída: {novas} salvas, {erros} falhas.")
        except Exception as e:
            print(f"❌ Erro crítico ao ler CSV: {e}")
    else:
        print(f"⚠️ CSV {CSV_FILE} não encontrado. Pulando vagas.")

    # 2. MIGRAR PERFIL DO JSON
    if os.path.exists(PROFILE_FILE):
        print(f"[2/2] Migrando perfil de {PROFILE_FILE} para o banco...")
        try:
            with open(PROFILE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            with Session(engine) as session:
                profile_db = session.exec(select(Perfil)).first()
                if not profile_db:
                    profile_db = Perfil(
                        nome=data.get("nome", "Usuário"),
                        json_data=json.dumps(data, ensure_ascii=False)
                    )
                    session.add(profile_db)
                else:
                    profile_db.json_data = json.dumps(data, ensure_ascii=False)
                    session.add(profile_db)
                
                session.commit()
                print("✅ Perfil sincronizado com sucesso!")
        except Exception as e:
            print(f"❌ Erro ao migrar perfil: {e}")

if __name__ == "__main__":
    migrate()
