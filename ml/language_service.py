"""Language stub — this service only processes English resumes."""

import unicodedata


def normalize_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).replace("\x00", "")


def detect_language(text: str) -> dict[str, object]:
    """Always returns English; multilanguage support has been removed."""
    return {"language": "en", "supported": True}
