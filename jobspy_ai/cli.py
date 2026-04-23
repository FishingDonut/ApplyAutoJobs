import typer
import json
import os
import click
from rich.console import Console
from rich.table import Table
from .db.database import create_db_and_tables, get_session
from .db.models import Vaga, Perfil
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
PROFILE_PATH = "perfil.json"

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
    """Lista as últimas vagas salvas no banco de dados com análise de match."""
    with get_session() as session:
        statement = select(Vaga).order_by(Vaga.data_descoberta.desc()).limit(limit)
        vagas = session.exec(statement).all()
        
        table = Table(title="Últimas Vagas Encontradas")
        table.add_column("ID", style="cyan")
        table.add_column("Título", style="magenta")
        table.add_column("Empresa", style="green")
        table.add_column("Match (%)", style="bold yellow")
        table.add_column("Tech Stack", style="blue")
        table.add_column("Salário", style="green")
        table.add_column("Status", style="white")
        
        for v in vagas:
            score = v.match_score or 0
            match_style = "bold green" if score >= 80 else "bold yellow" if score >= 50 else "red"
            table.add_row(
                str(v.id), 
                v.titulo, 
                v.empresa, 
                f"[{match_style}]{score}%[/]", 
                v.tech_stack or "-",
                v.salario_estimado or "-",
                v.status
            )
        
        console.print(table)

@app.command()
def dashboard():
    """Abre o painel interativo (TUI) para gerenciar vagas."""
    from .tui.dashboard import JobSpyDashboard
    dashboard_app = JobSpyDashboard()
    dashboard_app.run()

@app.command()
def profile():
    """Abre o perfil no seu editor padrão para edição rápida e segura."""
    if not os.path.exists(PROFILE_PATH):
        default_profile = {
            "nome": "Seu Nome",
            "email": "seu@email.com",
            "telefone": "(00) 00000-0000",
            "linkedin": "https://linkedin.com/in/seu-perfil",
            "resumo": "Escreva aqui seu resumo profissional...",
            "skills": "Python, React, etc.",
            "exp_1": "Experiência recente...",
            "exp_2": "Experiência anterior..."
        }
        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(default_profile, f, indent=4, ensure_ascii=False)
    
    console.print(f"[yellow]Abrindo {PROFILE_PATH} no seu editor padrão...[/yellow]")
    # click.edit abre o editor padrão e espera fechar
    click.edit(filename=PROFILE_PATH)
    
    # Sincronizar com o Banco de Dados após a edição
    try:
        with open(PROFILE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        with get_session() as session:
            # Tenta sincronizar com a tabela Perfil
            profile_db = session.query(Perfil).first()
            if not profile_db:
                profile_db = Perfil(nome=data.get("nome", "Usuário"), json_data=json.dumps(data, ensure_ascii=False))
            else:
                profile_db.nome = data.get("nome", profile_db.nome)
                profile_db.json_data = json.dumps(data, ensure_ascii=False)
            
            session.add(profile_db)
            session.commit()
            
        console.print("[bold green]✅ Perfil editado e sincronizado com o Banco de Dados![/bold green]")
    except Exception as e:
        console.print(f"[bold red]❌ Erro ao ler ou sincronizar o perfil: {e}[/bold red]")

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
