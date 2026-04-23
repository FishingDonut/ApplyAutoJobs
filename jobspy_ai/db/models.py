from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship, Column, TEXT, String

class Vaga(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    data_descoberta: datetime = Field(default_factory=datetime.now)
    titulo: str = Field(max_length=255)
    empresa: str = Field(max_length=255)
    link: str = Field(max_length=767, index=True, unique=True)
    site: str = Field(max_length=50)
    status: str = Field(default="Novo", max_length=50)
    arquivo_curriculo: Optional[str] = Field(default=None, max_length=500)
    termo_pesquisa: str = Field(max_length=255)
    descricao: Optional[str] = Field(default=None, sa_column=Column(TEXT))
    
    # Novas colunas de Inteligência
    match_score: Optional[int] = Field(default=0)
    tech_stack: Optional[str] = Field(default=None, max_length=255)
    salario_estimado: Optional[str] = Field(default=None, max_length=100)
    justificativa: Optional[str] = Field(default=None, sa_column=Column(TEXT))

class Perfil(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(max_length=255)
    json_data: str = Field(sa_column=Column(TEXT)) # Para armazenar o perfil.json completo
    prompt_personalizado: Optional[str] = Field(default=None, sa_column=Column(TEXT))
