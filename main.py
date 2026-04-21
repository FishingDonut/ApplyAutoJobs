import csv
from jobspy import scrape_jobs

# --- AJUSTE ESTES VALORES ---
CARGO = "Programador Jr"
LOCALIZACAO = "remoto"
LIMITE_VAGAS = 15
# ----------------------------

print(f"Buscando vagas para '{CARGO}' em '{LOCALIZACAO}'...")

try:
    jobs = scrape_jobs(
        site_name=["indeed", "google", "glassdoor", "linkedin"], # linkedin
        search_term=CARGO,
        location=LOCALIZACAO,
        results_wanted=LIMITE_VAGAS,
        hours_old=168,           # Vagas postadas nos últimos 7 dias (168h)
        country_indeed='brazil', # Ajustado para o mercado brasileiro
        
        # linkedin_fetch_description=True # Pega descrição completa (mais lento)
    )

    if not jobs.empty:
        print(f"\nSucesso! Encontradas {len(jobs)} vagas.")
        
        # Mostra as primeiras 5 vagas no terminal
        colunas_exibicao = ['title', 'company', 'location', 'job_url']
        print(jobs[colunas_exibicao].head())

        # Salva o arquivo CSV com codificação para o Excel brasileiro (utf-8-sig + ;)
        jobs.to_csv("vagas_encontradas.csv", 
                    index=False, 
                    quoting=csv.QUOTE_NONNUMERIC, 
                    encoding='utf-8-sig', 
                    sep=';')
        
        print(f"\nArquivo 'vagas_encontradas.csv' gerado com sucesso!")
        print("Dica: Você pode abrir este arquivo diretamente no Excel.")
    else:
        print("\nNenhuma vaga encontrada. Tente mudar o termo de busca.")

except Exception as e:
    print(f"Ocorreu um erro na busca: {e}")
