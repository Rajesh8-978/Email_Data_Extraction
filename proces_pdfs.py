from pathlib import Path
from pypdf import PdfReader
import requests
import json
import re


PDF_FOLDER = Path("pdfs")
ANONYMIZE_API_URL = "http://localhost:5001/anonymize"
API_TIMEOUT_SECONDS = 600

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


def _person_parts(value):
    return set(re.findall(r"[a-z]+", value.casefold()))


def deduplicate_person_values(values, reference_values=None):
    """Keep full names and remove shorter aliases such as 'Shanel'."""
    compact_values = {}
    compact_order = []

    for value in values:
        compact_key = re.sub(r"[^a-z]", "", value.casefold())
        previous = compact_values.get(compact_key)
        if previous is None:
            compact_values[compact_key] = value
            compact_order.append(compact_key)
        elif len(value.split()) > len(previous.split()):
            compact_values[compact_key] = value

    candidates = [compact_values[key] for key in compact_order]
    references = list(reference_values or [])
    filtered = []

    for candidate in candidates:
        parts = _person_parts(candidate)
        is_short_alias = any(
            parts < _person_parts(other)
            for other in candidates
            if other != candidate
        )
        is_specific_entity_duplicate = any(
            parts <= _person_parts(other)
            for other in references
        )
        if not is_short_alias and not is_specific_entity_duplicate:
            filtered.append(candidate)

    return filtered


def deduplicate_format_variants(values):
    """Collapse punctuation/case variants of the same named entity."""
    seen = set()
    deduplicated = []
    for value in values:
        key = re.sub(r"[^a-z0-9]", "", value.casefold())
        if key and key not in seen:
            seen.add(key)
            deduplicated.append(value)
    return deduplicated


def unique_values(items, entity_type=None):
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

    if entity_type == "PERSON":
        return deduplicate_person_values(values)
    if entity_type in {
        "ORGANIZATION", "CREDITOR_NAME", "LAW_FIRM", "GOVERNMENT_AGENCY"
    }:
        return deduplicate_format_variants(values)
    return values


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
        grouped[entity_type] = unique_values(details[entity_type], entity_type)

    grouped["PERSON"] = deduplicate_person_values(
        grouped["PERSON"],
        reference_values=grouped["BANKRUPT_NAME"],
    )

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

    all_anonymized_results.append({
        "EmailMessageId": email_message_id,
        "SourceFileName": pdf.name,
        "AnonymizedText": anonymized_data["anonymized_text"],
        "AnonymizedItemCount": len(anonymized_data["items"]),
    })

with open("pdf_extracted_entities.json", "w", encoding="utf-8") as f:
    json.dump(all_results, f, indent=4, ensure_ascii=False)

with open("pdf_anonymized_text.json", "w", encoding="utf-8") as f:
    json.dump(all_anonymized_results, f, indent=4, ensure_ascii=False)

print(f"\nDone. Total PDF outputs: {len(all_results)}")
print("Saved to pdf_extracted_entities.json")
print("Saved to pdf_anonymized_text.json")
