# 🕵️ JobSpy AI - Automação de Carreira (CLI)

O **JobSpy AI** é uma plataforma modular de linha de comando (CLI) projetada para automatizar o processo de busca, análise e candidatura a vagas de emprego. O sistema une Web Scraping, Banco de Dados Relacional, Automação de Navegadores (RPA) e Inteligência Artificial Generativa (Gemini 2.0 Flash) para aumentar exponencialmente a taxa de conversão em processos seletivos.

---

## 🏗️ Arquitetura de Software

O projeto adota uma arquitetura modular, orientada a domínios, visando escalabilidade e resiliência contra mudanças em plataformas de emprego (como Gupy e LinkedIn).

### Camadas do Sistema

1. **`cli.py` (Apresentação / Interface):** 
   - Utiliza o framework **Typer** e **Rich**.
   - Atua como orquestrador, recebendo comandos do usuário e despachando tarefas para os módulos inferiores. Não contém regras de negócio.
2. **`core/` (Inteligência & Negócios):**
   - Centraliza o motor de Inteligência Artificial (`GeminiEngine`).
   - Responsável por processar a descrição da vaga, cruzar com o perfil do candidato (`perfil.json`) e gerar um currículo docx sob medida via `docxtpl`.
3. **`scrapers/` (Descoberta de Dados):**
   - Isola a lógica de extração de vagas usando `python-jobspy`.
   - Coleta dados de fontes como Indeed e LinkedIn e entrega objetos padronizados para a camada de persistência.
4. **`bots/` (RPA / Automação):**
   - Scripts Playwright especializados por plataforma (ex: `GupyBot`).
   - Recebem a URL da vaga e o currículo adaptado. Navegam nas páginas, detectam campos dinâmicos e delegam a resposta das perguntas para a IA.
5. **`db/` (Persistência de Dados):**
   - Utiliza **MySQL** através do ORM **SQLModel** (baseado em SQLAlchemy).
   - Garante a integridade dos dados (vagas únicas por URL, status de candidatura, logs de erro).

---

## 🔄 Ciclo de Vida e Interação

O fluxo de dados segue uma esteira de automação clara:

1. **Descoberta:** O scraper busca vagas baseadas em termos, salva no MySQL com status `Novo` e previne duplicatas (Unique Link).
2. **Triagem (Planejado):** O sistema listará as vagas com cálculos de `Match Score` baseados na descrição vs. perfil.
3. **Adaptação:** O usuário solicita a aplicação. A IA reescreve o template Word (Summary, Skills, Experiência) focado 100% nas palavras-chave da vaga selecionada.
4. **Aplicação (RPA):** O Bot abre a página. Quando encontra testes lógicos, **pausa** (Human in the Loop). Quando encontra formulários de texto ou múltipla escolha, lê o HTML, envia para o Gemini como contexto e injeta a resposta na tela.

---

## 🎯 Escopo do Sistema

### O que o sistema FAZ:
- ✅ Busca agregada de vagas em múltiplas plataformas simultaneamente.
- ✅ Persistência local em banco de dados relacional para controle de Kanban pessoal.
- ✅ Adaptação semântica de currículos (.docx) em tempo real via LLM.
- ✅ Preenchimento automatizado de formulários baseados em perfis estruturados (JSON).
- ✅ Navegação autônoma em sites complexos via Playwright.

### O que o sistema NÃO FAZ:
- ❌ **Testes Comportamentais / Lógicos:** O sistema não resolve testes técnicos ou psicométricos. Ele detecta esses gatilhos e delega a ação ao humano.
- ❌ **Criação de Conta:** Pressupõe-se que o usuário já tenha sessão ativa nas plataformas suportadas (mantidas via `.sessao_gupy` etc.).
- ❌ **Garantia de Emprego:** O sistema otimiza o currículo para sistemas ATS, mas a aprovação depende do background real do candidato e do desempenho nas entrevistas.

---

## 🚀 Setup e Instalação

### Pré-requisitos
- Python 3.10+
- Servidor MySQL rodando localmente ou via Docker.
- Google AI Studio API Key.

### 1. Clonar e Instalar
```bash
git clone <seu-repo>
cd JobSpyTest
pip install -e .
playwright install chrome
```

### 2. Variáveis de Ambiente (`.env`)
```env
GOOGLE_API_KEY=sua_chave_gemini
MYSQL_URL=mysql+pymysql://usuario:senha@localhost:3306/jobspy
```

### 3. Banco de Dados
```bash
# Cria as tabelas necessárias no banco
jobspy setup

# Se tiver dados legados em CSV, pode migrar usando:
jobspy migrate
```

### 4. Utilização Básica
```bash
# Buscar vagas de Analista
jobspy search "Analista de Dados" --limit 50 --remote

# Listar vagas encontradas
jobspy list

# Aplicar para uma vaga (Adapta o CV e abre o robô)
jobspy apply 1
```

---
*Documentação de Arquitetura elaborada para garantir estabilidade, clareza e onboarding rápido de novos desenvolvedores.*
