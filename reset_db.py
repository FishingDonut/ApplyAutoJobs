from jobspy_ai.db.database import engine
from sqlmodel import SQLModel
from jobspy_ai.db.models import Vaga, Perfil

def reset():
    print("Deletando tabelas existentes...")
    SQLModel.metadata.drop_all(engine)
    print("Criando novas tabelas com o esquema atualizado...")
    SQLModel.metadata.create_all(engine)
    print("Sucesso!")

if __name__ == "__main__":
    reset()
