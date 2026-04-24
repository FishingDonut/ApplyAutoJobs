import re
import json
import math
from collections import Counter
from typing import Dict, List, Tuple

class MatchEngine:
    """
    Motor de Match determinístico baseado em Heurística e Ciência de Dados (Matemática Real).
    Calcula a aderência da vaga ao perfil ou currículo sem usar APIs externas (IA).
    """

    def __init__(self, perfil_json: str = None):
        if perfil_json:
            try:
                self.perfil = json.loads(perfil_json)
            except:
                self.perfil = {}
        else:
            self.perfil = {}
        
        # Extrair e normalizar skills do perfil
        self.user_skills = self._parse_skills(self.perfil.get("skills", ""))
        self.user_summary = self.perfil.get("resumo", "").lower()

    # Converte a string de habilidades do perfil em um conjunto limpo para comparação.
    def _parse_skills(self, skills_str: str) -> set:
        """Transforma string de skills em um conjunto de termos normalizados."""
        if not skills_str: return set()
        tokens = re.split(r'[,;\n]', skills_str.lower())
        return {t.strip() for t in tokens if t.strip()}

    # Remove ruídos e caracteres especiais da descrição da vaga.
    def _normalize_text(self, text: str) -> str:
        """Limpa o texto para facilitar a comparação."""
        if not text: return ""
        text = text.lower()
        # Remove caracteres especiais mantendo espaços
        text = re.sub(r'[^\w\s]', ' ', text)
        return text

    def _get_vectors(self, text1: str, text2: str) -> Tuple[Counter, Counter]:
        """Converte dois textos em vetores de frequência de palavras (Bag of Words)."""
        words1 = re.findall(r'\w+', text1.lower())
        words2 = re.findall(r'\w+', text2.lower())
        return Counter(words1), Counter(words2)

    def calcular_similaridade_cosseno(self, texto1: str, texto2: str) -> float:
        """
        Calcula a similaridade de cossenos entre dois textos.
        Matemática: A · B / (||A|| * ||B||)
        """
        vec1, vec2 = self._get_vectors(texto1, texto2)
        
        intersection = set(vec1.keys()) & set(vec2.keys())
        numerator = sum([vec1[x] * vec2[x] for x in intersection])

        sum1 = sum([vec1[x]**2 for x in vec1.keys()])
        sum2 = sum([vec2[x]**2 for x in vec2.keys()])
        denominator = math.sqrt(sum1) * math.sqrt(sum2)

        if not denominator:
            return 0.0
        else:
            return float(numerator) / denominator

    # Realiza o cruzamento de palavras-chave entre o perfil e a descrição da vaga.
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
            pattern = rf'\b{re.escape(skill)}\b'
            if re.search(pattern, desc_norm):
                found_skills.append(skill)

        # 2. Cálculo do Score Baseado em Skills (Heurística)
        num_found = len(found_skills)
        if num_found == 0:
            score = 10
        elif num_found <= 2:
            score = 40
        elif num_found <= 5:
            score = 70
        else:
            score = min(95, 70 + (num_found * 3))

        tech_stack = ", ".join(found_skills[:8])
        justificativa = (
            f"Encontradas {num_found} competências: {tech_stack}. "
            "Cálculo baseado em correspondência direta."
        )

        return int(score), tech_stack, justificativa

    def recalcular_match_com_curriculo(self, texto_curriculo: str, descricao_vaga: str) -> int:
        """
        Calcula um novo score baseado na similaridade matemática real (Cossenos).
        Útil após a adaptação do currículo pela IA.
        """
        sim = self.calcular_similaridade_cosseno(texto_curriculo, descricao_vaga)
        
        # A similaridade de cosseno em textos naturais raramente chega a 1.0 (100%).
        # Normalizamos para dar um peso maior: ex: 0.3 de similaridade já é um match muito forte.
        # Vamos usar um multiplicador para tornar a nota amigável ao usuário.
        score = int(sim * 200) # Ex: 0.4 -> 80%
        return min(100, max(10, score))
