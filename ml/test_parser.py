from parsers import extract_text


file_path = "../sample data/resume.docx"


try:
    extracted_text = extract_text(file_path)

    print("========== EXTRACTED TEXT ==========")
    print(extracted_text)

except Exception as error:
    print("Error:", error)