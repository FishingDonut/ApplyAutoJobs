import typer
import json
import os
from rich.console import Console
from rich.table import Table
from .db.database import create_db_and_tables, get_session
from .db.models import Vaga
from .db.migrate_csv import migrate as run_migration
from .scrapers.search import search_and_save
from .core.ai import GeminiEngine
from .bots.gupy import GupyBot
from sqlmodel import select
from docxtpl import DocxTemplate
from docx import Document

app = typer.Typer(help="JobSpy AI - Assistente de Carreira no Terminal")
console = Console()

TEMPLATE_PATH = "templates/template-2.0.docx"
OUTPUT_DIR = "meus_curriculos"

@app.command()
def setup():
    """Inicializa o banco de dados MySQL."""
    console.print("[yellow]Inicializando banco de dados...[/yellow]")
    create_db_and_tables()
    console.print("[green]Banco de dados pronto![/green]")

@app.command()
def migrate():
    """Migra os dados do antigo vagas_central.csv para o MySQL."""
    console.print("[yellow]Iniciando migração de CSV para MySQL...[/yellow]")
    run_migration()

@app.command()
def search(
    termo: str = typer.Argument(..., help="Termo de busca (ex: 'Programador React')"),
    local: str = typer.Option("remoto", help="Localização da vaga"),
    remoto: bool = typer.Option(True, help="Se a vaga deve ser remota"),
    limite: int = typer.Option(20, help="Limite de vagas para buscar")
):
    """Busca novas vagas e as salva no banco de dados."""
    setup()
    console.print(f"[bold blue]Buscando vagas para: {termo}...[/bold blue]")
    novas = search_and_save(termo, local, remoto, limite)
    console.print(f"[bold green]Sucesso![/bold green] {novas} novas vagas encontradas.")

@app.command()
def list(limit: int = 10):
    """Lista as últimas vagas salvas no banco de dados."""
    with get_session() as session:
        statement = select(Vaga).order_by(Vaga.data_descoberta.desc()).limit(limit)
        vagas = session.exec(statement).all()
        
        table = Table(title="Últimas Vagas Encontradas")
        table.add_column("ID", style="cyan")
        table.add_column("Título", style="magenta")
        table.add_column("Empresa", style="green")
        table.add_column("Site", style="yellow")
        table.add_column("Status", style="blue")
        
        for v in vagas:
            table.add_row(str(v.id), v.titulo, v.empresa, v.site, v.status)
        
        console.print(table)

@app.command()
def apply(vaga_id: int):
    """Adapta o currículo e tenta aplicar para uma vaga via ID."""
    with get_session() as session:
        vaga = session.get(Vaga, vaga_id)
        if not vaga:
            console.print(f"[bold red]Vaga ID {vaga_id} não encontrada![/bold red]")
            return

        console.print(f"[yellow]Adaptando currículo para: {vaga.titulo} na {vaga.empresa}...[/yellow]")
        
        # Extrair texto do template
        doc_base = Document(TEMPLATE_PATH)
        texto_base = "\n".join([p.text for p in doc_base.paragraphs if p.text])
        
        # IA Adaptação
        ai = GeminiEngine()
        res_raw = ai.adaptar_curriculo(vaga.descricao, texto_base)
        dados = json.loads(res_raw)
        contexto = dados.get('adaptacao', {})
        
        # Salvar Docx
        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        nome_arq = f"{vaga_id}_{vaga.empresa}.docx".replace(" ", "_")
        caminho_final = os.path.join(OUTPUT_DIR, nome_arq)
        
        doc = DocxTemplate(TEMPLATE_PATH)
        doc.render(contexto)
        doc.save(caminho_final)
        
        console.print(f"[green]Currículo gerado em: {caminho_final}[/green]")
        vaga.arquivo_curriculo = caminho_final
        vaga.status = "Currículo Gerado"
        session.add(vaga)
        session.commit()

        if vaga.site == "Gupy":
            if typer.confirm("Deseja tentar aplicação automática via Gupy?"):
                bot = GupyBot()
                if bot.aplicar(vaga.link, caminho_final):
                    vaga.status = "Candidatado"
                    session.add(vaga)
                    session.commit()
                    console.print("[bold green]Aplicação finalizada![/bold green]")

if __name__ == "__main__":
    app()
