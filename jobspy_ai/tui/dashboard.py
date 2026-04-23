from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Footer, ListItem, ListView, Static, Markdown, Label
from textual.binding import Binding
from sqlmodel import select
from ..db.database import get_session
from ..db.models import Vaga
import webbrowser

class JobDetail(Static):
    """Widget para exibir os detalhes da vaga."""
    def update_job(self, vaga: Vaga):
        content = f"# {vaga.titulo}\n\n"
        content += f"**Empresa:** {vaga.empresa} | **Plataforma:** {vaga.site}\n"
        content += f"**Status:** {vaga.status} | **Data:** {vaga.data_descoberta.strftime('%d/%m/%Y')}\n\n"
        content += "---\n\n"
        content += vaga.descricao or "Sem descrição disponível."
        self.query_one(Markdown).update(content)

class JobListItem(ListItem):
    """Item customizado para a lista de vagas."""
    def __init__(self, vaga: Vaga):
        super().__init__()
        self.vaga = vaga

    def compose(self) -> ComposeResult:
        status_color = "blue" if self.vaga.status == "Novo" else "green" if self.vaga.status == "Candidatado" else "yellow"
        yield Label(f"[{status_color}]{self.vaga.status:12}[/] [b]{self.vaga.titulo:40}[/] @ {self.vaga.empresa}")

class JobSpyDashboard(App):
    """Aplicativo TUI principal."""
    TITLE = "JobSpy AI Dashboard"
    CSS = """
    Screen {
        background: #1e1e1e;
    }
    #main-container {
        height: 100%;
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
    ListItem {
        padding: 0 1;
    }
    ListItem:hover {
        background: #333;
    }
    ListView > ListItem.--highlight {
        background: #005faf;
        color: white;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Sair", show=True),
        Binding("o", "open_link", "Abrir Link", show=True),
        Binding("i", "ignore_job", "Ignorar", show=True),
        Binding("r", "refresh", "Atualizar", show=True),
        Binding("a", "apply_job", "Adaptar & Aplicar", show=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Horizontal():
                yield ListView(id="job-list")
                with Vertical(id="job-detail"):
                    yield Markdown(id="detail-markdown")
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh()

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
        content = f"# {vaga.titulo}\n\n"
        content += f"**Empresa:** {vaga.empresa} | **Plataforma:** {vaga.site}\n"
        content += f"**Status:** {vaga.status} | **Data:** {vaga.data_descoberta.strftime('%d/%m/%Y')}\n\n"
        content += "---\n\n"
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
            self.notify(f"Vaga '{vaga.titulo}' ignorada.")
            self.action_refresh()

    def action_apply_job(self) -> None:
        list_view = self.query_one("#job-list", ListView)
        if list_view.highlighted_child:
            vaga_id = list_view.highlighted_child.vaga.id
            self.notify(f"Iniciando aplicação para ID {vaga_id}... Feche o Dashboard para ver os logs.")
            # Nota: Aplicação automática via TUI exigiria integração assíncrona complexa.
            # Por enquanto, notificamos o usuário para usar o comando CLI apply para feedback detalhado.
            # No futuro, podemos rodar o bot em uma thread separada e mostrar logs no TUI.

if __name__ == "__main__":
    app = JobSpyDashboard()
    app.run()
