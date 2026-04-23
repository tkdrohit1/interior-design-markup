from PyPDF2 import PdfReader
import json

def extract_text(file_path):
    try:
        reader = PdfReader(file_path)
        pages_text = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages_text.append({"page": i + 1, "text": text})
        print(json.dumps(pages_text, indent=2))
    except Exception as e:
        print(f"Error extracting text: {e}")

if __name__ == "__main__":
    extract_text("Space_Craft_ Ramachandra_quote 1.pdf")
