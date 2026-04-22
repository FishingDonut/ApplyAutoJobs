import pandas as pd
from sqlmodel import Session, select
from .database import engine, create_db_and_tables
from .models import Vaga
import os

CSV_FILE = "vagas_central.csv"

def migrate():
    if not os.path.exists(CSV_FILE):
        print(f"CSV {CSV_FILE} não encontrado. Pulando migração.")
        return

    create_db_and_tables()
    
    try:
        df = pd.read_csv(CSV_FILE, sep=';', encoding='utf-8-sig')
    except Exception as e:
        print(f"Erro ao ler CSV: {e}")
        return

    with Session(engine) as session:
        for _, row in df.iterrows():
            # Verificar se já existe
            statement = select(Vaga).where(Vaga.link == row['Link'])
            existing = session.exec(statement).first()
            
            if not existing:
                try:
                    # Tentar converter data se possível
                    data_desc = row['Data_Descoberta']
                    vaga = Vaga(
                        titulo=row['Titulo'],
                        empresa=row['Empresa'],
                        link=row['Link'],
                        site=row['Site'],
                        status=row['Status'],
                        arquivo_curriculo=row['Arquivo_Curriculo'] if pd.notna(row['Arquivo_Curriculo']) else None,
                        termo_pesquisa=row['Termo_Pesquisa'],
                        descricao=row['Descricao'] if pd.notna(row['Descricao']) else None
                    )
                    session.add(vaga)
                except Exception as e:
                    print(f"Erro ao processar linha {row['Link']}: {e}")
        
        session.commit()
    print("Migração concluída com sucesso!")

if __name__ == "__main__":
    migrate()
