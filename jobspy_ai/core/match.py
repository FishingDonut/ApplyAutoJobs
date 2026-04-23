import re
import json
from typing import Dict, List, Tuple

class MatchEngine:
    """
    Motor de Match determinístico baseado em Heurística e NLP Básico.
    Calcula a aderência da vaga ao perfil sem usar APIs externas (IA).
    """

    def __init__(self, perfil_json: str):
        try:
            self.perfil = json.loads(perfil_json)
        except:
            self.perfil = {}
        
        # Extrair e normalizar skills do perfil
        self.user_skills = self._parse_skills(self.perfil.get("skills", ""))
        self.user_summary = self.perfil.get("resumo", "").lower()

    # Converte a string de habilidades do perfil em um conjunto limpo para comparação.
    # Garante que variações de pontuação ou caixa não interfiram no match.
    def _parse_skills(self, skills_str: str) -> set:
        """Transforma string de skills em um conjunto de termos normalizados."""
        # Divide por vírgula, ponto e vírgula ou nova linha
        tokens = re.split(r'[,;\n]', skills_str.lower())
        return {t.strip() for t in tokens if t.strip()}

    # Remove ruídos e caracteres especiais da descrição da vaga.
    # Prepara o texto bruto para uma busca de termos técnicos mais precisa.
    def _normalize_text(self, text: str) -> str:
        """Limpa o texto para facilitar a comparação."""
        text = text.lower()
        # Remove caracteres especiais mantendo espaços
        text = re.sub(r'[^\w\s]', ' ', text)
        return text

    # Realiza o cruzamento de palavras-chave entre o perfil e a descrição da vaga.
    # Gera uma pontuação de 0 a 100 baseada na densidade de competências encontradas.
    def calcular_match(self, descricao_vaga: str) -> Tuple[int, str, str]:
        """
        Retorna (score, tech_stack_detectada, justificativa).
        """
        if not descricao_vaga or not self.user_skills:
            return 0, "N/A", "Descrição ou Perfil incompleto."

        desc_norm = self._normalize_text(descricao_vaga)
        
        # 1. Identificar quais skills do usuário estão na vaga
        found_skills = []
        for skill in self.user_skills:
            # Busca exata do termo (com word boundaries)
            pattern = rf'\b{re.escape(skill)}\b'
            if re.search(pattern, desc_norm):
                found_skills.append(skill)

        # 2. Cálculo do Score Baseado em Skills
        # Se a vaga tem muitas das suas skills, o score sobe
        # (Heurística simples: se encontrou mais de 5 skills, score alto)
        num_found = len(found_skills)
        if num_found == 0:
            score = 10
        elif num_found <= 2:
            score = 40
        elif num_found <= 5:
            score = 70
        else:
            score = min(95, 70 + (num_found * 3))

        # 3. Gerar Tech Stack e Justificativa
        tech_stack = ", ".join(found_skills[:8])
        justificativa = (
            f"Encontradas {num_found} competências do seu perfil: {tech_stack}. "
            "Cálculo baseado em correspondência direta de termos técnicos."
        )

        return int(score), tech_stack, justificativa
