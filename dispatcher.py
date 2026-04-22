import re
import os
from aplicador_gupy import aplicar_vaga_gupy
from aplicador_linkedin import aplicar_vaga_linkedin

def identificar_e_aplicar(url_vaga, caminho_curriculo):
    """
    Roteador central que decide qual robô usar com base na URL.
    """
    url_vaga = str(url_vaga).lower()

    # 1. GUPY
    if "gupy.io" in url_vaga or "gupy.com" in url_vaga:
        print("\n[ROBÔ] Identificado: Ecossistema GUPY.")
        try:
            aplicar_vaga_gupy(url_vaga, caminho_curriculo)
            return True
        except Exception as e:
            print(f"Erro no aplicador Gupy: {e}")
            return False

    # 2. LINKEDIN
    elif "linkedin.com" in url_vaga:
        print("\n[ROBÔ] Identificado: LINKEDIN.")
        try:
            aplicar_vaga_linkedin(url_vaga, caminho_curriculo)
            return True
        except Exception as e:
            print(f"Erro no aplicador LinkedIn: {e}")
            return False

    # 3. OUTROS (Greenhouse, Lever, etc)
    else:
        print("\n[ROBÔ] Site não suportado para automação total ainda.")
        print(f"Por favor, realize a candidatura manual em: {url_vaga}")
        return False

if __name__ == "__main__":
    # Teste isolado do dispatcher
    url = input("Cole uma URL para testar o roteador: ")
    identificar_e_aplicar(url, "teste.docx")
