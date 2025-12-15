import re

def limpar_status_rastreamento(texto: str) -> str:
    """
    Mantém o DESCRITIVO COMPLETO do status retornado pela transportadora (Jamef/Rodonaves),
    apenas removendo ruídos comuns (parênteses, data/hora no final etc).
    Não reduz para 2-3 palavras.
    """
    if not texto:
        return ""

    t = str(texto)

    # 1) Remove conteúdo entre parênteses (opcional, mas costuma ser ruído)
    t = re.sub(r"\([^)]*\)", "", t)

    # 2) Remove datas e horários (formatos comuns)
    t = re.sub(r"\b\d{1,2}/\d{1,2}/\d{4}\b", "", t)  # 20/10/2025
    t = re.sub(r"\b\d{1,2}:\d{2}\b", "", t)          # 12:59

    # 3) Remove separadores soltos que ficam após tirar data/hora
    t = re.sub(r"\s*[\|\-–—]\s*$", "", t)            # trailing "|", "-", "–", "—"
    t = re.sub(r"^\s*[\|\-–—]\s*", "", t)            # leading "|", "-", "–", "—"

    # 4) Normaliza espaços e pontuação
    t = re.sub(r"\s{2,}", " ", t).strip()
    t = t.strip().rstrip(".:,;").strip()

    return t
