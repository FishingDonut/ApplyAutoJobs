from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, ListItem, ListView, Static, Markdown, Label, RichLog, Input
from textual.binding import Binding
from textual.screen import ModalScreen
from sqlmodel import select
from ..db.database import get_session
from ..db.models import Vaga
import webbrowser
import threading
import os

class SearchBar(ModalScreen):
    """Barra de busca flutuante estilo Neovim/Telescope."""
    BINDINGS = [("escape", "dismiss", "Fechar")]

    def compose(self) -> ComposeResult:
        with Vertical(id="search-container"):
            yield Label(" [bold]$ [/]BUSCAR VAGAS", id="search-label")
            yield Input(placeholder="Termo, Localização (ex: Python, remoto)", id="search-input")
            yield Label(" [dim]Enter para buscar • Esc para cancelar[/]", id="search-hint")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self.dismiss(event.value)
        else:
            self.dismiss(None)

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
        yield Label(f"[dim]{self.vaga.id:<4}[/] [{status_color}]{self.vaga.status:12}[/] [{match_color}]{self.vaga.match_score:3}%[/] [b]{self.vaga.titulo:40}[/] @ {self.vaga.empresa}")

class JobSpyDashboard(App):
    """Aplicativo TUI principal com estética Neovim-like e suporte a temas."""
    TITLE = "JobSpy AI"
    
    # Estado inicial de filtros e ordenação
    current_sort = "id"
    current_platform_filter = None

    CSS = """
    Screen {
        background: $background;
    }
    #main-container {
        height: 85%;
    }
    #log-container {
        height: 15%;
        border-top: solid $panel-lighten-2;
        background: $surface-darken-1;
    }
    #job-list {
        width: 35%;
        height: 100%;
        border-right: solid $panel-lighten-2;
        background: $surface;
    }
    #job-detail {
        width: 65%;
        height: 100%;
        padding: 1 2;
        background: $background;
    }
    RichLog {
        height: 1fr;
        color: $text-muted;
    }
    #search-container {
        width: 60%;
        height: auto;
        align: center top;
        margin-top: 2;
        padding: 1 2;
        border: double $accent;
        background: $panel;
        color: $text;
    }
    #search-label {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #search-input {
        border: solid $panel-lighten-2;
        background: $surface;
        color: $text;
        margin-bottom: 1;
    }
    #search-hint {
        text-align: right;
        color: $text-muted;
    }
    Header {
        background: $accent;
        color: $text;
        text-style: bold;
    }
    Footer {
        background: $panel;
        color: $text;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Sair", show=True),
        Binding("slash", "search_bar", "Buscar", show=True),
        Binding("o", "open_link", "Abrir", show=True),
        Binding("i", "ignore_job", "Ignorar", show=True),
        Binding("r", "refresh", "Recarregar", show=True),
        Binding("a", "apply_job", "Aplicar", show=True),
        Binding("m", "toggle_sort", "Ordenar", show=True),
        Binding("f", "filter_platform", "Filtrar", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Horizontal():
                yield ListView(id="job-list")
                with Vertical(id="job-detail"):
                    yield Markdown(id="detail-markdown")
        with Container(id="log-container"):
            yield RichLog(id="app-logs", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh()
        self.log_message("[bold green]JobSpy pronto. Pressione '/' para buscar novas vagas.[/]")

    def log_message(self, message: str):
        self.query_one("#app-logs", RichLog).write(message)

    def action_toggle_sort(self) -> None:
        """Alterna a ordenação entre ID e Match."""
        self.current_sort = "match" if self.current_sort == "id" else "id"
        sort_name = "Match %" if self.current_sort == "match" else "ID (Mais Recentes)"
        self.log_message(f"[bold cyan]🔄 Ordenação alterada para: {sort_name}[/]")
        self.action_refresh()

    def action_filter_platform(self) -> None:
        """Alterna o filtro de plataforma entre Todas, Gupy e LinkedIn."""
        platforms = [None, "Gupy", "LinkedIn"]
        current = self.current_platform_filter
        next_idx = (platforms.index(current) + 1) % len(platforms)
        self.current_platform_filter = platforms[next_idx]
        
        filter_name = self.current_platform_filter if self.current_platform_filter else "Todas"
        self.log_message(f"[bold cyan]🔄 Filtro alterado para: {filter_name}[/]")
        self.action_refresh()

    def action_refresh(self, filter_term: str = None) -> None:
        """Carrega as vagas do banco de dados MySQL com ordenação e filtros."""
        list_view = self.query_one("#job-list", ListView)
        list_view.clear()

        with get_session() as session:
            # Ordenação
            if self.current_sort == "match":
                statement = select(Vaga).order_by(Vaga.match_score.desc())
            else:
                statement = select(Vaga).order_by(Vaga.id.desc())

            # Filtro de Plataforma
            if self.current_platform_filter:
                statement = statement.where(Vaga.site == self.current_platform_filter)

            if filter_term:
                # Se houver termo de busca, mostramos apenas o que der match parcial (simples)
                vagas = [v for v in session.exec(statement).all() if filter_term.lower() in v.titulo.lower() or filter_term.lower() in v.empresa.lower()]
            else:
                vagas = session.exec(statement.limit(50)).all()

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
            self.log_message(f"[yellow]Ignorada: {vaga.titulo}[/]")
            self.action_refresh()

    def action_search_bar(self) -> None:
        """Abre a barra de busca (Telescope style)."""
        self.push_screen(SearchBar(), self.run_search_process)

    def run_search_process(self, search_term: str) -> None:
        if not search_term:
            return

        self.log_message(f"[bold cyan]🔍 Buscando '{search_term}'...[/]")

        def do_search():
            from ..scrapers.search import search_and_save
            try:
                # Pegamos o termo e dividimos em termo e local se houver vírgula
                partes = search_term.split(",")
                termo = partes[0].strip()
                local = partes[1].strip() if len(partes) > 1 else "remoto"

                novas = search_and_save(termo, local, True, 20)
                self.app.call_from_thread(self.log_message, f"[bold green]✅ Fim: {novas} novas vagas.[/]")
                # Após a busca, atualizamos a lista filtrando pelo termo para mostrar os resultados
                self.app.call_from_thread(self.action_refresh, filter_term=termo)
            except Exception as e:
                self.app.call_from_thread(self.log_message, f"[bold red]❌ Erro: {e}[/]")

        threading.Thread(target=do_search, daemon=True).start()

    def action_apply_job(self) -> None:
        list_view = self.query_one("#job-list", ListView)
        if list_view.highlighted_child:
            vaga = list_view.highlighted_child.vaga
            thread = threading.Thread(target=self.run_apply_process, args=(vaga.id,))
            thread.start()

    def run_apply_process(self, vaga_id: int):
        from ..cli import apply_logic
        import io
        from contextlib import redirect_stdout

        self.log_message(f"[bold blue]Aplicando vaga {vaga_id}...[/]")

        try:
            apply_logic(vaga_id, logger=self.log_message)
            self.app.call_from_thread(self.action_refresh)
        except Exception as e:
            self.log_message(f"[bold red]❌ Erro: {e}[/]")

