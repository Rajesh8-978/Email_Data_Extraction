from pathlib import Path
from pypdf import PdfReader
import requests
import json

from result_formatter import (
    TARGET_ENTITIES,
    build_anonymized_pdf_result,
    build_extracted_pdf_result,
)


PDF_FOLDER = Path("pdfs")
ANONYMIZE_API_URL = "http://localhost:5001/anonymize"
API_TIMEOUT_SECONDS = 600

def read_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    text_parts = []

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)

    return "\n".join(text_parts)


all_results = []
all_anonymized_results = []

pdf_files = sorted(PDF_FOLDER.glob("*.pdf"))
print(f"PDF files found: {len(pdf_files)}")

for email_message_id, pdf in enumerate(pdf_files, start=1):
    print(f"\nReading: {pdf.name}")

    text = read_pdf_text(pdf)
    print(f"Text length: {len(text)}")

    anonymize_response = requests.post(
        ANONYMIZE_API_URL,
        json={
            "text": text,
            "language": "en",
            "entities": TARGET_ENTITIES,
        },
        timeout=API_TIMEOUT_SECONDS,
    )

    anonymize_response.raise_for_status()
    anonymized_data = anonymize_response.json()
    entities = anonymized_data["entities"]
    print(f"Entities found: {len(entities)}")

    all_results.append(build_extracted_pdf_result(
        entities=entities,
        source_file_name=pdf.name,
        email_message_id=email_message_id,
        language="en",
    ))

    all_anonymized_results.append(build_anonymized_pdf_result(
        source_file_name=pdf.name,
        anonymized_text=anonymized_data["anonymized_text"],
        anonymized_item_count=len(anonymized_data["items"]),
        email_message_id=email_message_id,
    ))

with open("pdf_extracted_entities.json", "w", encoding="utf-8") as f:
    json.dump(all_results, f, indent=4, ensure_ascii=False)

with open("pdf_anonymized_text.json", "w", encoding="utf-8") as f:
    json.dump(all_anonymized_results, f, indent=4, ensure_ascii=False)

print(f"\nDone. Total PDF outputs: {len(all_results)}")
print("Saved to pdf_extracted_entities.json")
print("Saved to pdf_anonymized_text.json")
