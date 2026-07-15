from pathlib import Path
from pypdf import PdfReader
import requests
import json


PDF_FOLDER = Path("pdfs")
API_URL = "http://localhost:5001/analyze"

# Same entity types as ENTITY_RULES in entity_rules.py.
# One PDF will produce one output object with these fields.
TARGET_ENTITIES = [
    "EMAIL_ADDRESS",
    "EMAIL_DATE",
    "DATE_TIME",
    "PERSON",
    "BANK_ACCOUNT_NUMBER",
    "BANKRUPTCY_NUMBER",
    "SG_VEHICLE_NUMBER",
    "SG_NRIC_FIN",
    "PHONE_NUMBER",
    "PASSPORT_NUMBER",
    "URL",
    "LOCATION",
    "JOB_TITLE",
    "ORGANIZATION",
    "CREDITOR_NAME",
    "BANKRUPT_NAME",
    "LAW_FIRM",
    "GOVERNMENT_AGENCY",
]


def read_pdf_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    text_parts = []

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)

    return "\n".join(text_parts)


def unique_values(items):
    seen = set()
    values = []

    for item in items:
        value = item.get("normalized_value") or item.get("value")
        if not value:
            continue

        key = str(value).casefold()
        if key in seen:
            continue

        seen.add(key)
        values.append(value)

    return values


all_results = []

pdf_files = sorted(PDF_FOLDER.glob("*.pdf"))
print(f"PDF files found: {len(pdf_files)}")

for email_message_id, pdf in enumerate(pdf_files, start=1):
    print(f"\nReading: {pdf.name}")

    text = read_pdf_text(pdf)
    print(f"Text length: {len(text)}")

    response = requests.post(
        API_URL,
        json={
            "text": text,
            "language": "en",
            "entities": TARGET_ENTITIES,
        },
        timeout=120,
    )

    response.raise_for_status()
    entities = response.json()["entities"]
    print(f"Entities found: {len(entities)}")

    grouped = {entity_type: [] for entity_type in TARGET_ENTITIES}
    details = {entity_type: [] for entity_type in TARGET_ENTITIES}

    for entity in entities:
        entity_type = entity["entity_type"]
        if entity_type not in grouped:
            continue

        details[entity_type].append({
            "value": entity["value"],
            "normalized_value": entity["normalized_value"],
            "confidence": entity["confidence"],
            "start": entity["start"],
            "end": entity["end"],
            "context": entity["context"],
        })

    for entity_type in TARGET_ENTITIES:
        grouped[entity_type] = unique_values(details[entity_type])

    pdf_result = {
        "EmailMessageId": email_message_id,
        "SourceFileName": pdf.name,
        "ExtractionEngine": "presidio-analyzer",
        "ModelName": "gliner + pattern recognizers",
        "LanguageCode": "en",
        "TotalEntitiesFound": len(entities),
        **grouped,
    }

    all_results.append(pdf_result)

with open("pdf_extracted_entities.json", "w", encoding="utf-8") as f:
    json.dump(all_results, f, indent=4, ensure_ascii=False)

print(f"\nDone. Total PDF outputs: {len(all_results)}")
print("Saved to pdf_extracted_entities.json")
