"""Shared JSON formatting for PDF batch processing and PDF API uploads."""

import re


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
    """Collapse punctuation and case variants of the same named entity."""
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


def build_extracted_pdf_result(
    entities,
    source_file_name,
    email_message_id=1,
    language="en",
):
    """Return the same JSON object used in pdf_extracted_entities.json."""
    grouped = {entity_type: [] for entity_type in TARGET_ENTITIES}

    for entity in entities:
        entity_type = entity["entity_type"]
        if entity_type in grouped:
            grouped[entity_type].append(entity)

    for entity_type in TARGET_ENTITIES:
        grouped[entity_type] = unique_values(grouped[entity_type], entity_type)

    grouped["PERSON"] = deduplicate_person_values(
        grouped["PERSON"],
        reference_values=grouped["BANKRUPT_NAME"],
    )

    return {
        "EmailMessageId": email_message_id,
        "SourceFileName": source_file_name,
        "ExtractionEngine": "presidio-analyzer",
        "ModelName": "gliner + pattern recognizers",
        "LanguageCode": language,
        "TotalEntitiesFound": len(entities),
        **grouped,
    }


def build_anonymized_pdf_result(
    source_file_name,
    anonymized_text,
    anonymized_item_count,
    email_message_id=1,
):
    """Return the same JSON object used in pdf_anonymized_text.json."""
    return {
        "EmailMessageId": email_message_id,
        "SourceFileName": source_file_name,
        "AnonymizedText": anonymized_text,
        "AnonymizedItemCount": anonymized_item_count,
    }
