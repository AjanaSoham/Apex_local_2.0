from parsers import extract_text
from skill_extractor import extract_skills


file_path = "../sample_data/resume.txt"


raw_text = extract_text(file_path)

skills = extract_skills(raw_text)


print("========== EXTRACTED SKILLS ==========")

for skill in skills:
    print("-", skill)