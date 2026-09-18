from pathlib import Path
import re
from pprint import pprint

from structured_extractor import extract_education_entries, extract_experience_entries
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
    # Search line-by-line so dates, CGPAs, and adjacent PDF columns cannot be
    # combined into a single false phone number.
    pattern = re.compile(r"(?<!\d)(?:\+\d{1,3}[\s.-]?)?(?:\(?\d{2,5}\)?[\s.-]?)?\d{3,5}[\s.-]?\d{3,5}(?!\d)")
    lines = text.splitlines()
    prioritized = [
        line for line in lines
        if re.search(r"(?i)\b(?:phone|mobile|contact\s*(?:no|number)?|tel)\b|\+\s*\d", line)
    ]
    for line in prioritized + lines:
        digit_groups = re.findall(r"\d+", line)
        digits = "".join(digit_groups)
        if 10 <= len(digits) <= 15 and not (
            len(digit_groups) > 1
            and all(len(group) == 4 for group in digit_groups)
            and not re.search(r"(?i)\b(?:phone|mobile|contact|tel)\b|\+\s*\d", line)
        ):
            # Prefer the final 10 digits for Indian numbers when OCR has
            # separated the country code or misplaced punctuation.
            if len(digits) > 10 and digits.startswith(("91", "011")):
                digits = digits[-10:]
            return digits
        for match in pattern.finditer(line):
            value = match.group(0).strip(" .-")
            digits = re.sub(r"\D", "", value)
            if 10 <= len(digits) <= 15:
                return value
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

    ignored_exact = {
        "senior secondary",
        "secondary",
        "engineering student",
        "computer science student",
        "about me",
        "education",
        "academic qualification",
        "qualifications",
        "project",
        "aim",
        "strength",
        "personal details",
        "declaration",
        "contact information",
        "profile overview",
        "academic qualification",
        "skills",
        "projects",
        "hobbies",
        "signature",
        "learning programs",
        "miscellaneous",
        "leadership / position of responsibility",
        "technical skills",
        "languages known",
        "hobbies",
    }

    # Contact rows are a strong anchor even when the PDF places the name
    # after the header or contact details.
    for index, line in enumerate(lines):
        if not re.search(r"(?i)\b(?:phone|email|linkedin|github|contact)\b|\+\s*\d", line):
            continue
        for candidate in reversed(lines[max(0, index - 4):index + 1]):
            candidate = candidate.strip(" .:-")
            words = candidate.split()
            if (
                2 <= len(words) <= 4
                and all(re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", word) for word in words)
                and candidate.lower() not in ignored_exact
                and not any(
                    marker in candidate.lower()
                    for marker in ("learning programs", "study jam", "college", "university", "school")
                )
            ):
                return " ".join(word.capitalize() for word in words)

    # Many PDF layouts place the name after the contact details. Prefer a
    # nearby name-like line over arbitrary headings.
    for index, line in enumerate(lines[:40]):
        if line.lower() in ignored_exact or "@" in line or re.search(r"\d", line):
            continue
        if re.search(r"(?i)\b(?:college|university|school|engineering|computer science|student|address|profile|overview|information)\b", line):
            continue
        words = line.split()
        if 2 <= len(words) <= 4 and all(re.fullmatch(r"[A-Za-z][A-Za-z.'-]*", word) for word in words):
            if index == 0 or any(re.search(r"(?i)\b(?:contact|email|phone|address)\b", candidate) for candidate in lines[index:index + 8]):
                return " ".join(word.capitalize() for word in words)

    # Prefer a nearby all-caps header over arbitrary two-word lines in education.
    # nearby all-caps header over arbitrary two-word lines in education.
    for index, line in enumerate(lines):
        if line.lower() in ignored_exact or "@" in line or re.search(r"\d", line):
            continue
        if not re.fullmatch(r"[A-Z][A-Z .'-]{2,}", line):
            continue
        words = line.split()
        if 2 <= len(words) <= 4:
            return line.title()

    for line in lines[:30]:

        line_lower = line.lower()

        if any(word in line_lower for word in ignored_words):
            continue

        if "@" in line:
            continue

        if re.search(r"\d", line):
            continue

        if line.startswith(("*", "-", "•")):
            continue

        line = re.sub(r"^(?:name|candidate name)\s*:\s*", "", line, flags=re.IGNORECASE).strip()
        words = line.split()

        if line_lower in ignored_exact:
            continue
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
    text = text.replace("\ufffd", "'")
    text = text.replace("\u00b7", "|")
    text = text.replace("\u2013", "-")

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

        "experience": extract_experience_entries(cleaned_resume_text),

        "education": extract_education_entries(cleaned_resume_text),

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
