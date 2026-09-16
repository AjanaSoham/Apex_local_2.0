from parsers import extract_text


file_path = "../sample_data/sample_resume.pdf"

text = extract_text(file_path)

print("\nExtracted text:")
print(text)