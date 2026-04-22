import os
from sqlmodel import SQLModel, create_engine, Session
from dotenv import load_dotenv

load_dotenv()

MYSQL_URL = os.getenv("MYSQL_URL", "mysql+pymysql://root:root@localhost:3306/jobspy")

engine = create_engine(MYSQL_URL)

def create_db_and_tables():
    from .models import Vaga, Perfil # Garantir que os modelos são importados antes de criar
    SQLModel.metadata.create_all(engine)

def get_session():
    return Session(engine)
