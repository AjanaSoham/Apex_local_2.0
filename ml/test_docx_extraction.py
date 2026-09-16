from parsers import extract_text


file_path = "../sample_data/sample_resume.docx"

text = extract_text(file_path)

print("\nExtracted DOCX text:")
print("=" * 50)
print(text)