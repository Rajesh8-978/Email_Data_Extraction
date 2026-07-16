from flask import Flask, request, jsonify
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
import re

from recognizers.singapore_recognizers import singapore_recognizers
from recognizers.business_recognizers import business_recognizers
from recognizers.gliner_recognizer import GlinerRecognizer
from entity_collector import collect_entities, group_entities
from entity_rules import ENTITY_RULES

app = Flask(__name__)

registry = RecognizerRegistry()
registry.load_predefined_recognizers()

analyzer = AnalyzerEngine(
    registry=registry,
    nlp_engine=None
)

# Fixed-format sensitive values are masked:
# first 2 visible + masked middle + last 2 visible.
MASK_ENTITY_TYPES = {
    "BANK_ACCOUNT_NUMBER",
    "BANKRUPTCY_NUMBER",
    "SG_VEHICLE_NUMBER",
    "SG_NRIC_FIN",
    "PHONE_NUMBER",
    "PASSPORT_NUMBER",
}

# All other entities are replaced with an entity tag, for example <PERSON>.
REPLACE_ENTITY_TYPES = set(ENTITY_RULES) - MASK_ENTITY_TYPES

# When two detections overlap, prefer the more specific business entity.
ENTITY_PRIORITY = {
    "SG_NRIC_FIN": 100,
    "PASSPORT_NUMBER": 95,
    "BANK_ACCOUNT_NUMBER": 90,
    "BANKRUPTCY_NUMBER": 90,
    "SG_VEHICLE_NUMBER": 90,
    "PHONE_NUMBER": 90,
    "EMAIL_ADDRESS": 85,
    "URL": 80,
    "BANKRUPT_NAME": 75,
    "CREDITOR_NAME": 75,
    "LAW_FIRM": 70,
    "GOVERNMENT_AGENCY": 70,
    "ORGANIZATION": 65,
    "PERSON": 60,
    "EMAIL_DATE": 55,
    "DATE_TIME": 50,
    "LOCATION": 40,
    "JOB_TITLE": 35,
}

for recognizer in singapore_recognizers():
    analyzer.registry.add_recognizer(recognizer)

for recognizer in business_recognizers():
    analyzer.registry.add_recognizer(recognizer)

analyzer.registry.add_recognizer(GlinerRecognizer())


def _request_data():
    data = request.get_json(silent=True) or {}

    text = data.get("text", "")
    language = data.get("language", "en")
    entities = data.get("entities") or list(ENTITY_RULES)

    if not isinstance(text, str) or not text.strip():
        return None, jsonify({"error": "'text' must be a non-empty string"}), 400
    if not isinstance(entities, list):
        return None, jsonify({"error": "'entities' must be a list"}), 400

    return (text, language, entities, data), None, None


def _analyze_and_collect(text, language, entities, deduplicate=True):
    results = analyzer.analyze(
        text=text,
        language=language,
        entities=entities
    )
    return collect_entities(text, results, entities, deduplicate=deduplicate)


def _collect_from_results(text, results, entities, deduplicate=True):
    return collect_entities(text, results, entities, deduplicate=deduplicate)


def _mask_value(value: str) -> str:
    value = str(value)
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"


def _anonymized_value(entity):
    entity_type = entity["entity_type"]
    value = entity["value"]

    if entity_type in MASK_ENTITY_TYPES:
        return _mask_value(value)

    return f"<{entity_type}>"


def _anonymize_text(text, collected_entities):
    anonymized_text = text
    items = []

    # Replace from right to left so earlier start/end positions do not shift.
    for entity in sorted(_remove_overlaps(collected_entities), key=lambda item: item["start"], reverse=True):
        replacement = _anonymized_value(entity)
        anonymized_text = (
            anonymized_text[:entity["start"]]
            + replacement
            + anonymized_text[entity["end"]:]
        )
        items.append({
            "entity_type": entity["entity_type"],
            "start": entity["start"],
            "end": entity["end"],
            "operator": "mask" if entity["entity_type"] in MASK_ENTITY_TYPES else "replace",
            "original_text": entity["value"],
            "anonymized_text": replacement,
        })

    items.reverse()
    anonymized_text = _final_regex_cleanup(anonymized_text)
    return anonymized_text, items


def _mask_match(match):
    return _mask_value(match.group(0))


def _final_regex_cleanup(text):
    """Last safety pass for high-confidence structured values and email headers."""
    cleanup_patterns = [
        (r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63}", "<EMAIL_ADDRESS>", re.I),
        (r"\bhttps?://[^\s<>()]+|\bwww\.[^\s<>()]+", "<URL>", re.I),
        (r"\b(?:HC[/ -]?)?B[/ -]?\d{2,6}[/ -]?\d{4}\b", _mask_match, re.I),
        (r"(?<!\d)(?:\+65|65)[\s-]?[3689]\d{3}[\s-]?\d{4}(?!\d)", _mask_match, re.I),
        (r"(?<!\d)[3689]\d{3}[\s-]?\d{4}(?!\d)", _mask_match, re.I),
        (r"\b[STFGM]\d{7}[A-Z]\b", _mask_match, re.I),
    ]

    for pattern, replacement, flags in cleanup_patterns:
        text = re.sub(pattern, replacement, text, flags=flags)

    name_patterns = [
        (r"(?<=\bAgent\n)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}", "<PERSON>"),
        (r"(?<=\bby\s)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}(?=\s+on\s)", "<PERSON>"),
        (r"(?<=\bby\s)[A-Za-z][A-Za-z0-9._-]{2,}(?=\s+on\s)", "<PERSON>"),
        (r"(?<=\bto\s)[A-Za-z][A-Za-z0-9._-]{2,}(?=\s+on\s)", "<PERSON>"),
        (r"(?<=\bRegards,\n)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}", "<PERSON>"),
        (r"(?<=\bRegards\n)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}", "<PERSON>"),
        (r"(?<=\bRegards, \n)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}", "<PERSON>"),
        (r"(?<=\bBest regards,\n)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}", "<PERSON>"),
        (r"(?<=\bDear\s)(?!(?:Madam|Sir)\b)(?:Ms\.?|Mr\.?|Mrs\.?|Mdm\.?)?\s*[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}", "<PERSON>"),
        (r"(?<=\bHi\s)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}", "<PERSON>"),
        (r"(?<=\bAttention to\s)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}", "<PERSON>"),
    ]

    for pattern, replacement in name_patterns:
        text = re.sub(pattern, replacement, text)

    text = _mask_contextual_vehicle_numbers(text)
    return text


def _mask_contextual_vehicle_numbers(text):
    vehicle_pattern = r"\b[A-Z]{1,3}\d{1,4}[A-Z]\b"

    def replace_group(match):
        return f"{match.group(1)}{_mask_value(match.group(2))}"

    context_patterns = [
        rf"(\bVehicle\s+)({vehicle_pattern})",
        rf"(\bvehicle,\s*)({vehicle_pattern})",
        rf"(\bvehicle\s+)({vehicle_pattern})",
        rf"(\bregistration\s+(?:number\s+)?)({vehicle_pattern})",
        rf"(\bplate\s+(?:number\s+)?)({vehicle_pattern})",
    ]

    for pattern in context_patterns:
        text = re.sub(pattern, replace_group, text, flags=re.I)

    return text


def _entity_priority(entity):
    return ENTITY_PRIORITY.get(entity["entity_type"], 0)


def _overlaps(left, right):
    return left["start"] < right["end"] and right["start"] < left["end"]


def _is_better_candidate(candidate, current):
    candidate_length = candidate["end"] - candidate["start"]
    current_length = current["end"] - current["start"]
    return (
        _entity_priority(candidate),
        candidate_length,
        candidate["confidence"],
    ) > (
        _entity_priority(current),
        current_length,
        current["confidence"],
    )


def _remove_overlaps(entities):
    selected = []

    for entity in sorted(
        entities,
        key=lambda item: (
            -_entity_priority(item),
            -(item["end"] - item["start"]),
            -item["confidence"],
            item["start"],
        ),
    ):
        overlapping_index = next(
            (index for index, chosen in enumerate(selected) if _overlaps(entity, chosen)),
            None,
        )
        if overlapping_index is None:
            selected.append(entity)
        elif _is_better_candidate(entity, selected[overlapping_index]):
            selected[overlapping_index] = entity

    return sorted(selected, key=lambda item: (item["start"], item["end"]))


@app.route("/analyze", methods=["POST"])
def analyze():
    request_values, error_response, status = _request_data()
    if error_response:
        return error_response, status

    text, language, entities, _ = request_values
    collected = _analyze_and_collect(text, language, entities)
    return jsonify({
        "count": len(collected),
        "entities": collected,
        "grouped": group_entities(collected),
    })


@app.route("/anonymize", methods=["POST"])
def anonymize():
    request_values, error_response, status = _request_data()
    if error_response:
        return error_response, status

    text, language, entities, _ = request_values
    raw_results = analyzer.analyze(
        text=text,
        language=language,
        entities=entities
    )
    collected = _collect_from_results(text, raw_results, entities, deduplicate=False)
    reporting_entities = _collect_from_results(text, raw_results, entities, deduplicate=True)
    anonymized_text, items = _anonymize_text(text, collected)

    return jsonify({
        "anonymized_text": anonymized_text,
        "items": items,
        "count": len(reporting_entities),
        "anonymized_item_count": len(items),
        "entities": reporting_entities,
        "grouped": group_entities(reporting_entities),
        "operator_policy": {
            "mask": sorted(MASK_ENTITY_TYPES),
            "replace": sorted(REPLACE_ENTITY_TYPES),
            "hash": [],
        },
    })


@app.route("/entity-types", methods=["GET"])
def entity_types():
    return jsonify({
        name: {"minimum_confidence": rule.min_score}
        for name, rule in ENTITY_RULES.items()
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})
