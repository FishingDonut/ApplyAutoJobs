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
from .bots.linkedin import LinkedInBot
from sqlmodel import select
from docxtpl import DocxTemplate
from docx import Document
import time

app = typer.Typer(help="JobSpy AI - Assistente de Carreira no Terminal")
console = Console()

TEMPLATE_PATH = "templates/template-2.0.docx"
OUTPUT_DIR = "meus_curriculos"
PROFILE_PATH = "perfil.json"

# --- LÓGICA COMPARTILHADA (CLI + TUI) ---

def apply_logic(vaga_id: int, logger=None):
    """Lógica centralizada de aplicação para ser usada pela CLI e pela TUI."""
    def log(msg):
        if logger: logger(msg)
        else: console.print(msg)

    with get_session() as session:
        vaga = session.get(Vaga, vaga_id)
        if not vaga:
            log(f"[bold red]Vaga ID {vaga_id} não encontrada![/bold red]")
            return False

        log(f"[yellow]Adaptando currículo para: {vaga.titulo} na {vaga.empresa}...[/yellow]")
        
        # Extrair texto do template
        if not os.path.exists(TEMPLATE_PATH):
            log(f"[bold red]Template não encontrado em {TEMPLATE_PATH}[/bold red]")
            return False

        doc_base = Document(TEMPLATE_PATH)
        texto_base = "\n".join([p.text for p in doc_base.paragraphs if p.text])
        
        # IA Adaptação
        ai = GeminiEngine()
        res_raw = ai.adaptar_curriculo(vaga.descricao, texto_base)
        
        if not res_raw:
            log("[bold red]❌ A IA não retornou dados para adaptação.[/bold red]")
            return False

        try:
            res_raw = res_raw.replace("```json", "").replace("```", "").strip()
            dados = json.loads(res_raw)
            contexto = dados.get('adaptacao', {})
        except Exception as e:
            log(f"[bold red]❌ Erro no JSON da IA: {e}[/bold red]")
            return False
        
        # Salvar Docx
        if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)
        nome_arq = f"{vaga_id}_{vaga.empresa.replace(' ', '_')}.docx"
        caminho_final = os.path.abspath(os.path.join(OUTPUT_DIR, nome_arq))
        
        doc = DocxTemplate(TEMPLATE_PATH)
        doc.render(contexto)
        doc.save(caminho_final)
        
        log(f"[green]✅ Currículo salvo em: {caminho_final}[/green]")
        vaga.arquivo_curriculo = caminho_final
        vaga.status = "Currículo Gerado"
        session.add(vaga)
        session.commit()

        # Automação
        sucesso = False
        if vaga.site == "Gupy":
            log("[yellow]Iniciando GupyBot...[/yellow]")
            bot = GupyBot()
            sucesso = bot.aplicar(vaga.link, caminho_final)
        elif vaga.site == "LinkedIn":
            log("[yellow]Iniciando LinkedInBot...[/yellow]")
            bot = LinkedInBot()
            sucesso = bot.aplicar(vaga.link, caminho_final)
        
        if sucesso:
            vaga.status = "Candidatado"
            session.add(vaga)
            session.commit()
            log("[bold green]🚀 Candidatura finalizada com sucesso![/bold green]")
            return True
        
        return False

# --- COMANDOS CLI ---

@app.command()
def login(plataforma: str = typer.Argument(..., help="Plataforma para login (gupy ou linkedin)")):
    """Abre o navegador para realizar o login manual e salvar a sessão."""
    from playwright.sync_api import sync_playwright
    user_data = ".sessao_gupy" if plataforma.lower() == "gupy" else ".sessao_linkedin"
    url = "https://portal.gupy.io/" if plataforma.lower() == "gupy" else "https://www.linkedin.com/"
    
    console.print(f"[bold yellow]Iniciando login na {plataforma.upper()}...[/bold yellow]")
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(user_data_dir=user_data, headless=False, channel="chrome")
        page = context.new_page()
        page.goto(url)
        while len(context.pages) > 0: time.sleep(1)
    console.print(f"[bold green]Sessão salva![/bold green]")

@app.command()
def setup():
    """Inicializa o banco de dados MySQL."""
    create_db_and_tables()
    console.print("[green]Banco de dados pronto![/green]")

@app.command()
def search(termo: str, local: str = "remoto", limite: int = 20):
    """Busca novas vagas e as salva no banco de dados."""
    setup()
    novas = search_and_save(termo, local, True, limite)
    console.print(f"[bold green]Sucesso![/bold green] {novas} novas vagas encontradas.")

@app.command()
def list(limit: int = 10):
    """Lista as últimas vagas com detalhes do currículo."""
    with get_session() as session:
        vagas = session.exec(select(Vaga).order_by(Vaga.data_descoberta.desc()).limit(limit)).all()
        table = Table(title="Últimas Vagas")
        table.add_column("ID", style="cyan")
        table.add_column("Título", style="magenta")
        table.add_column("Empresa", style="green")
        table.add_column("Match", style="bold yellow")
        table.add_column("Currículo", style="dim")
        table.add_column("Status", style="white")
        
        for v in vagas:
            curr = "✅" if v.arquivo_curriculo else "❌"
            table.add_row(str(v.id), v.titulo, v.empresa, f"{v.match_score}%", curr, v.status)
        console.print(table)

@app.command()
def dashboard():
    """Abre o painel interativo (TUI)."""
    from .tui.dashboard import JobSpyDashboard
    JobSpyDashboard().run()

@app.command()
def apply(vaga_id: int):
    """Adapta o currículo e aplica para uma vaga."""
    apply_logic(vaga_id)

if __name__ == "__main__":
    app()
