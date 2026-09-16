from pathlib import Path
import re
from pprint import pprint

from structured_extractor import extract_experience_blocks
from parsers import extract_text
from resume_sections import extract_sections
from skill_extractor import extract_skills


def extract_email(text: str) -> str:
    pattern = r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"

    match = re.search(pattern, text)

    if match:
        return match.group(0)

    return ""


def extract_phone(text: str) -> str:
    pattern = r"(?<!\d)\+?\d[\d\s().-]{8,}\d(?!\d)"

    match = re.search(pattern, text)

    if match:
        return match.group(0).strip()

    return ""


def extract_candidate_name(text: str) -> str:
    """
    Extracts the candidate name from the beginning of the resume.
    """

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not lines:
        return ""

    ignored_words = [
        "resume",
        "curriculum vitae",
        "cv",
        "objective",
        "executive summary",
        "areas of expertise",
        "product portfolio",
        "experience",
        "education",
        "training",
        "email",
        "phone",
        "mobile",
        "contact",
    ]

    for line in lines[:20]:

        line_lower = line.lower()

        if any(word in line_lower for word in ignored_words):
            continue

        if "@" in line:
            continue

        if re.search(r"\d", line):
            continue

        if line.startswith(("*", "-", "•")):
            continue

        words = line.split()

        if 2 <= len(words) <= 4:
            return line

    return ""


def clean_text(text: str) -> str:
    """
    Performs basic cleaning while preserving
    the original resume information.
    """

    # Convert escaped newline characters into real newlines
    text = text.replace("\\\n", "\n")

    # Remove null characters
    text = text.replace("\x00", "")

    # Replace common OCR bullet errors
    text = text.replace("«", "*")
    text = text.replace("¢", "*")
    text = text.replace("•", "*")

    cleaned_lines = []

    for line in text.splitlines():
        # Replace repeated spaces and tabs with one space
        line = re.sub(r"[ \t]+", " ", line)

        line = line.strip()

        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def extract_resume(file_path: str) -> dict:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Resume file not found: {file_path}"
        )

    supported_extensions = [".pdf", ".docx", ".txt"]

    if path.suffix.lower() not in supported_extensions:
        raise ValueError(
            "Unsupported file type. "
            "Only PDF, DOCX & TXT files are supported."
        )

    raw_text = extract_text(str(path))

    cleaned_resume_text = clean_text(raw_text)

    if not cleaned_resume_text:
        raise ValueError(
            "No readable text could be extracted from this resume."
        )

    sections = extract_sections(cleaned_resume_text)

    skills = extract_skills(cleaned_resume_text)

    resume_data = {
        "file_name": path.name,
        "file_type": path.suffix.lower().replace(".", ""),

        "candidate": {
            "name": extract_candidate_name(
                cleaned_resume_text
            ),
            "email": extract_email(
                cleaned_resume_text
            ),
            "phone": extract_phone(
                cleaned_resume_text
            ),
        },

        "skills": skills,

        "sections": sections,

        "experience": extract_experience_blocks(
            cleaned_resume_text.splitlines()
        ),

        "education": [],

        "raw_text": cleaned_resume_text,
    }

    return resume_data


# --------------------------------------------------
# TEST THE EXPERIENCE EXTRACTOR
# --------------------------------------------------

if __name__ == "__main__":

    resume_path = r"C:\APEX\Local\sample_data\sample_resume.pdf"

    result = extract_resume(resume_path)

    pprint(result)
