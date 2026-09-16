import json

from resume_extractor import extract_resume


file_path = "../sample_data/sample_resume.pdf"

resume_data = extract_resume(file_path)

print(json.dumps(
    resume_data,
    indent=4,
    ensure_ascii=False
))