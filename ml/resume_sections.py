import re


SECTION_ALIASES = {
    "summary": [
        "summary",
        "professional summary",
        "profile",
        "career profile",
        "objective",
        "career objective",
        "resumen", "perfil", "résumé", "profil", "zusammenfassung", "perfil profissional",
    ],
    "skills": [
        "skills",
        "technical skills",
        "technical expertise",
        "core skills",
        "key skills",
        "competencies",
        "technologies",
        "habilidades", "competencias", "compétences", "kenntnisse", "competências",
    ],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "career history",
        "work history",
        "experiencia", "experiencia laboral", "expérience", "berufserfahrung", "experiência profissional",
    ],
    "education": [
        "education",
        "academic background",
        "educational background",
        "academic qualifications",
        "qualifications",
        "educación", "formation", "ausbildung", "educação",
    ],
    "projects": [
        "projects",
        "personal projects",
        "academic projects",
        "key projects",
    ],
    "certifications": [
        "certifications",
        "certificates",
        "licenses",
    ],
    "achievements": [
        "achievements",
        "awards",
        "honors",
        "accomplishments",
    ],
}


def normalize_heading(line: str) -> str:
    """
    Cleans a possible section heading.
    """

    line = line.lower().strip()

    # Remove common heading symbols.
    line = re.sub(r"[*•|:]+", "", line)

    # Remove extra spaces.
    line = re.sub(r"\s+", " ", line)

    return line.strip()


def detect_section_heading(line: str):
    """
    Returns the standard section name if the line
    appears to be a recognized heading.
    """

    normalized_line = normalize_heading(line)

    for section_name, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            if normalized_line == alias:
                return section_name

    return None


def extract_sections(text: str) -> dict:
    """
    Divides resume text into recognizable sections.
    """

    sections = {
        "header": []
    }

    current_section = "header"

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        detected_section = detect_section_heading(line)

        if detected_section:
            current_section = detected_section

            if current_section not in sections:
                sections[current_section] = []

        else:
            sections[current_section].append(line)

    final_sections = {}

    for section_name, content in sections.items():
        final_sections[section_name] = "\n".join(content).strip()

    return final_sections
