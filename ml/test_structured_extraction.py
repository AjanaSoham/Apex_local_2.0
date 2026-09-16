import json

from parsers import extract_text
from structured_extractor import (
    extract_experience_entries,
    extract_education_entries
)


file_path = "../sample_data/sample_resume.pdf"

text = extract_text(file_path)

experiences = extract_experience_entries(text)
education = extract_education_entries(text)

print("\nEXPERIENCE")
print("=" * 50)

print(json.dumps(
    experiences,
    indent=4,
    ensure_ascii=False
))

print("\nEDUCATION")
print("=" * 50)

print(json.dumps(
    education,
    indent=4,
    ensure_ascii=False
))