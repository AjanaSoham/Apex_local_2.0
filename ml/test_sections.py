from parsers import extract_text
from resume_sections import extract_sections


file_path = "../sample_data/sample_resume.pdf"

text = extract_text(file_path)

sections = extract_sections(text)

for section_name, section_content in sections.items():
    print("\n" + "=" * 50)
    print(section_name.upper())
    print("=" * 50)
    print(section_content)