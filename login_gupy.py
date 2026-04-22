import os
import time
from playwright.sync_api import sync_playwright

# Pasta onde salvaremos o estado da sessão (login, cookies, etc)
USER_DATA_DIR = ".sessao_gupy"

def login_gupy():
    """
    Abre o navegador para o usuário fazer o login manual na Gupy.
    Quando o usuário fechar o navegador, a sessão estará salva.
    """
    print("\n[LOGIN GUPY] Iniciando navegador em modo persistente...")
    print("Por favor, faça o login manualmente na Gupy no navegador que vai abrir.")
    print("Não feche o terminal. O script será encerrado apenas quando você fechar a janela do navegador.")
    
    with sync_playwright() as p:
        # Lançar navegador persistente
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False, # Abre com a janela visível
            args=["--start-maximized"], # Inicia maximizado
            viewport=None,
            channel="chrome" # Tenta usar o Chrome se estiver instalado, ou o Chromium padrão
        )
        
        page = context.new_page()
        page.goto("https://portal.gupy.io/")
        
        print("\nAguardando você fechar o navegador para salvar o estado...")
        
        # Mantém o script rodando enquanto o navegador estiver aberto
        while len(context.pages) > 0:
            time.sleep(1)
            
        print("\nSessão salva com sucesso! O robô agora pode usar esse perfil para navegar.")

if __name__ == "__main__":
    login_gupy()
