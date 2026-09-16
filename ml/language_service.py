"""Lightweight language identification for resume routing, with no network dependency."""

import re
import unicodedata

LANGUAGE_MARKERS = {
    "es": ("experiencia", "habilidades", "educación", "proyectos", "desarrollador"),
    "fr": ("expérience", "compétences", "formation", "développeur", "projets"),
    "de": ("erfahrung", "kenntnisse", "ausbildung", "entwickler", "projekte"),
    "pt": ("experiência", "habilidades", "educação", "desenvolvedor", "projetos"),
}


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).replace("\x00", "")


def detect_language(text: str) -> dict[str, object]:
    """Detect common Latin-script resume languages; return und for uncertain text."""
    folded = unicodedata.normalize("NFKD", text.lower())
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    scores = {language: sum(bool(re.search(r"(?<!\w)" + marker + r"(?!\w)", folded)) for marker in markers)
              for language, markers in LANGUAGE_MARKERS.items()}
    language, score = max(scores.items(), key=lambda item: item[1])
    if score == 0:
        language = "en" if re.search(r"\b(experience|skills|education|developer)\b", folded) else "und"
    return {"language": language, "confidence": round(min(1.0, score / 3), 2), "supported": language in {"en", "es", "fr", "de", "pt"}}
