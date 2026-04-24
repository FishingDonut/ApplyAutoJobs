from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, ListItem, ListView, Static, Markdown, Label, RichLog
from textual.binding import Binding
from sqlmodel import select
from ..db.database import get_session
from ..db.models import Vaga
import webbrowser
import threading
import os

class JobDetail(Static):
    """Widget para exibir os detalhes da vaga."""
    def update_job(self, vaga: Vaga):
        match_color = "green" if vaga.match_score >= 80 else "yellow" if vaga.match_score >= 50 else "red"
        content = f"# {vaga.titulo}\n\n"
        content += f"**Empresa:** {vaga.empresa} | **Plataforma:** {vaga.site}\n\n"
        content += f"### 📊 Análise de Match: [{match_color}]{vaga.match_score}%[/]\n"
        content += f"**🛠️ Tech Stack:** {vaga.tech_stack or 'N/A'}\n"
        content += f"**💰 Salário:** {vaga.salario_estimado or 'Não informado'}\n\n"
        content += f"**💡 Justificativa:** {vaga.justificativa or 'Sem análise.'}\n\n"
        content += "---\n"
        if vaga.arquivo_curriculo:
            content += f"**📄 Currículo Gerado:** `{vaga.arquivo_curriculo}`\n\n"
        content += f"**Status:** {vaga.status} | **Data:** {vaga.data_descoberta.strftime('%d/%m/%Y')}\n"
        content += vaga.descricao or "Sem descrição disponível."
        self.query_one(Markdown).update(content)

class JobListItem(ListItem):
    """Item customizado para a lista de vagas."""
    def __init__(self, vaga: Vaga):
        super().__init__()
        self.vaga = vaga

    def compose(self) -> ComposeResult:
        status_color = "blue" if self.vaga.status == "Novo" else "green" if self.vaga.status == "Candidatado" else "yellow"
        match_color = "green" if self.vaga.match_score >= 80 else "yellow" if self.vaga.match_score >= 50 else "red"
        yield Label(f"[{status_color}]{self.vaga.status:12}[/] [{match_color}]{self.vaga.match_score:3}%[/] [b]{self.vaga.titulo:40}[/] @ {self.vaga.empresa}")

class JobSpyDashboard(App):
    """Aplicativo TUI principal com Logs em tempo real."""
    TITLE = "JobSpy AI Dashboard"
    CSS = """
    Screen {
        background: #1e1e1e;
    }
    #main-container {
        height: 70%;
    }
    #log-container {
        height: 30%;
        border-top: tall #333;
        background: #121212;
    }
    #job-list {
        width: 40%;
        height: 100%;
        border-right: solid #333;
        background: #252525;
    }
    #job-detail {
        width: 60%;
        height: 100%;
        padding: 1 2;
    }
    RichLog {
        color: #00ff00;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Sair", show=True),
        Binding("o", "open_link", "Abrir Link", show=True),
        Binding("i", "ignore_job", "Ignorar", show=True),
        Binding("r", "refresh", "Atualizar", show=True),
        Binding("g", "generate_resume", "Gerar Currículo", show=True),
        Binding("a", "apply_job", "Adaptar & Aplicar", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Horizontal():
                yield ListView(id="job-list")
                with Vertical(id="job-detail"):
                    yield Markdown(id="detail-markdown")
        with Container(id="log-container"):
            yield Label(" [bold yellow]CONSOLE DE LOGS EM TEMPO REAL[/]")
            yield RichLog(id="app-logs", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh()
        self.log_message("[bold green]Sistema pronto! Escolha uma vaga e pressione 'A' para aplicar.[/]")

    def log_message(self, message: str):
        self.query_one("#app-logs", RichLog).write(message)

    def action_refresh(self) -> None:
        """Carrega as vagas do banco de dados MySQL."""
        list_view = self.query_one("#job-list", ListView)
        list_view.clear()
        
        with get_session() as session:
            statement = select(Vaga).order_by(Vaga.data_descoberta.desc()).limit(50)
            vagas = session.exec(statement).all()
            
            for vaga in vagas:
                list_view.append(JobListItem(vaga))
        
        if vagas:
            list_view.index = 0
            self.update_detail(vagas[0])

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item:
            self.update_detail(event.item.vaga)

    def update_detail(self, vaga: Vaga) -> None:
        md = self.query_one("#detail-markdown", Markdown)
        match_color = "green" if vaga.match_score >= 80 else "yellow" if vaga.match_score >= 50 else "red"
        
        content = f"# {vaga.titulo}\n\n"
        content += f"**Empresa:** {vaga.empresa} | **Plataforma:** {vaga.site}\n\n"
        content += f"### 📊 Análise de Match: [{match_color}]{vaga.match_score}%[/]\n"
        content += f"**🛠️ Tech Stack:** {vaga.tech_stack or 'N/A'}\n"
        content += f"**💰 Salário:** {vaga.salario_estimado or 'Não informado'}\n\n"
        content += f"**💡 Justificativa:** {vaga.justificativa or 'Sem análise.'}\n\n"
        content += "---\n"
        if vaga.arquivo_curriculo:
            content += f"**📄 Currículo Gerado:** `{vaga.arquivo_curriculo}`\n\n"
        content += f"**Status:** {vaga.status} | **Data:** {vaga.data_descoberta.strftime('%d/%m/%Y')}\n\n"
        content += vaga.descricao or "Sem descrição disponível."
        md.update(content)

    def action_open_link(self) -> None:
        list_view = self.query_one("#job-list", ListView)
        if list_view.highlighted_child:
            webbrowser.open(list_view.highlighted_child.vaga.link)

    def action_ignore_job(self) -> None:
        list_view = self.query_one("#job-list", ListView)
        if list_view.highlighted_child:
            vaga = list_view.highlighted_child.vaga
            with get_session() as session:
                db_vaga = session.get(Vaga, vaga.id)
                db_vaga.status = "Ignorada"
                session.add(db_vaga)
                session.commit()
            self.log_message(f"[yellow]Vaga '{vaga.titulo}' ignorada.[/]")
            self.action_refresh()

    def action_generate_resume(self) -> None:
        list_view = self.query_one("#job-list", ListView)
        if list_view.highlighted_child:
            vaga = list_view.highlighted_child.vaga
            thread = threading.Thread(target=self.run_generate_process, args=(vaga.id,))
            thread.start()

    def run_generate_process(self, vaga_id: int):
        from ..cli import generate_resume_logic
        import io
        from contextlib import redirect_stdout

        self.log_message(f"[bold cyan]Iniciando geração de currículo para ID {vaga_id}...[/bold cyan]")
        
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                generate_resume_logic(vaga_id, logger=self.log_message)
            
            self.app.call_from_thread(self.action_refresh)
            self.log_message("[bold green]✅ Geração de currículo finalizada![/bold green]")
        except Exception as e:
            self.log_message(f"[bold red]❌ Erro na geração: {e}[/bold red]")

    def action_apply_job(self) -> None:
        list_view = self.query_one("#job-list", ListView)
        if list_view.highlighted_child:
            vaga = list_view.highlighted_child.vaga
            # Rodar aplicação em uma thread separada para não travar a TUI
            thread = threading.Thread(target=self.run_apply_process, args=(vaga.id,))
            thread.start()

    def run_apply_process(self, vaga_id: int):
        from ..cli import apply
        from rich.console import Console
        import io
        from contextlib import redirect_stdout

        self.log_message(f"[bold blue]Iniciando aplicação para ID {vaga_id}...[/]")
        
        # Captura o output do comando CLI para mostrar no log da TUI
        f = io.StringIO()
        try:
            with redirect_stdout(f):
                # Importamos aqui para evitar circular import
                from ..cli import apply_logic
                apply_logic(vaga_id, logger=self.log_message)
            
            self.app.call_from_thread(self.action_refresh)
            self.log_message("[bold green]✅ Processo finalizado![/]")
        except Exception as e:
            self.log_message(f"[bold red]❌ Erro no processo: {e}[/]")
