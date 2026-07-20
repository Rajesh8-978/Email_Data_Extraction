from flask import Flask, request, jsonify, render_template
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
import re

from recognizers.singapore_recognizers import singapore_recognizers
from recognizers.business_recognizers import business_recognizers
from recognizers.gliner_recognizer import GlinerRecognizer
from entity_collector import collect_entities, group_entities
from entity_rules import ENTITY_RULES

app = Flask(__name__)
print("Open anonymizer UI: http://localhost:5001/", flush=True)

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
    "BANKRUPT_NAME": 78,
    "CREDITOR_NAME": 76,
    "GOVERNMENT_AGENCY": 74,
    "LAW_FIRM": 72,
    "ORGANIZATION": 70,
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


def _person_aliases(value):
    stopwords = {
        "and", "the", "for", "son", "daughter", "mr", "ms", "mrs", "mdm", "dr",
    }
    return {
        token
        for token in re.findall(r"[A-Za-z][A-Za-z'\u2019-]*", value)
        if len(token) >= 3 and token.casefold() not in stopwords
    }


def _replace_detected_values(text, entities):
    """Replace repeated values and safe person aliases missed at later occurrences."""
    candidates = {}

    for entity in entities:
        entity_type = entity["entity_type"]
        value = " ".join(str(entity["value"]).split()).strip(" ,.;:")
        if len(value) < 3 or "<" in value or ">" in value:
            continue

        values = {value}
        if entity_type in {"PERSON", "BANKRUPT_NAME"}:
            values.update(_person_aliases(value))

        for candidate in values:
            key = candidate.casefold()
            previous = candidates.get(key)
            if previous is None or _entity_priority(entity) > ENTITY_PRIORITY.get(previous[1], 0):
                candidates[key] = (candidate, entity_type)

    for value, entity_type in sorted(
        candidates.values(),
        key=lambda item: (-len(item[0]), -ENTITY_PRIORITY.get(item[1], 0)),
    ):
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(value)}(?![A-Za-z0-9_])"
        if entity_type in MASK_ENTITY_TYPES:
            replacement = lambda match: _mask_value(match.group(0))
        else:
            replacement = f"<{entity_type}>"
        text = re.sub(pattern, replacement, text, flags=re.I)

    return text


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
    anonymized_text = _mask_labeled_identifiers(anonymized_text)
    anonymized_text = _replace_detected_values(anonymized_text, collected_entities)
    anonymized_text = _final_regex_cleanup(anonymized_text)
    return anonymized_text, items


def _mask_match(match):
    return _mask_value(match.group(0))


def _final_regex_cleanup(text):
    """Last safety pass for high-confidence structured values and email headers."""
    text = _replace_spaced_email_signatures(text)
    cleanup_patterns = [
        (r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63}", "<EMAIL_ADDRESS>", re.I),
        (r"\bhttps?://[^\s<>()]+|\bwww\.[^\s<>()]+", "<URL>", re.I),
        (
            r"\b(?:(?:HC\s*/?\s*)?B\s*/\s*\d{1,6}\s*/\s*\d{4}|"
            r"HC\s+\d{1,6}\s*/\s*\d{4})\b",
            _mask_match,
            re.I,
        ),
        (r"(?<!\d)(?:\+65|65)[\s-]?[3689]\d{3}[\s-]?\d{4}(?!\d)", _mask_match, re.I),
        (r"(?<!\d)[3689]\d{3}[\s-]?\d{4}(?!\d)", _mask_match, re.I),
        (r"\b[STFGM]\d{7}[A-Z]\b", _mask_match, re.I),
        (
            r"(?<=\bon\s)(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?[,]?\s+\d{1,2}\s+"
            r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
            r"(?:[,]?\s+\d{4})?(?=\s+at\b)",
            "<EMAIL_DATE>",
            re.I,
        ),
        (
            r"\b(?:Blk(?:ock)?\s+)?\d{1,5}\s+[^\n.;]{1,160}?\bSingapore\s+\d{6}\b",
            "<LOCATION>",
            re.I,
        ),
        (
            r"\b\d{1,5}\s+[A-Za-z0-9'\u2019.,# /\r\n-]{1,160}?,\s*"
            r"[A-Z]{1,2}\d[A-Z\d]?\s+\d[A-Z]{2}\b",
            "<LOCATION>",
            re.I,
        ),
    ]

    for pattern, replacement, flags in cleanup_patterns:
        text = re.sub(pattern, replacement, text, flags=flags)

    name_patterns = [
        (r"(?<=\bYours sincerely,\n)[A-Z][A-Za-z'\u2019.-]+(?:[ \t]+[A-Z][A-Za-z'\u2019.-]+){0,6}", "<PERSON>"),
        (r"(?<=\bYours sincerely\n)[A-Z][A-Za-z'\u2019.-]+(?:[ \t]+[A-Z][A-Za-z'\u2019.-]+){0,6}", "<PERSON>"),
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

    text = _mask_labeled_identifiers(text)
    text = _replace_named_business_fallbacks(text)
    text = _mask_contextual_vehicle_numbers(text)
    return text


def _replace_spaced_email_signatures(text):
    """Replace PDF/OCR email text such as 'a d m i n @ e x a m p l e . c o m'."""
    pattern = re.compile(
        r"(?im)(^[ \t\u00a0]*E[ \t\u00a0]+)("
        r"(?:[A-Za-z0-9._%+-][ \t\u00a0]*){2,64}@[ \t\u00a0]*"
        r"(?:[A-Za-z0-9-][ \t\u00a0]*){2,63}"
        r"(?:\.[ \t\u00a0]*(?:[A-Za-z][ \t\u00a0]*){2,20})+)"
        r"(?=[ \t\u00a0]*$)"
    )
    return pattern.sub(lambda match: f"{match.group(1)}<EMAIL_ADDRESS>", text)


def _mask_labeled_identifiers(text):
    patterns = [
        r"(\b(?:Bank\s+)?Account\s+(?:No\.?|Number)\s*[:#]?\s*)(\d[\d -]{4,20}\d)",
        r"(\bPassport\s+(?:No\.?|Number)\s*[:#]?\s*)([A-Z][A-Z0-9]{7,8})",
        r"(\bPolicy\s+No\.?\s*[:#]?\s*)([A-Z0-9][A-Z0-9./-]{5,30})",
        r"(\bAuthentication\s+No\.?\s*[:#]?\s*)([A-Z0-9][A-Z0-9./-]{5,30})",
        r"(\bUEN\s*[:#]?\s*)([A-Z0-9][A-Z0-9./-]{5,30})",
        r"(\bReference\s+(?:No\.?|Number)\s*[:#]?\s*)([A-Z0-9][A-Z0-9./-]{5,30})",
        r"(\bFeedback\s+(?:No\.?|Number)\s*[:#]?\s*)([A-Z0-9][A-Z0-9./-]{5,30}?)(?=-Feedback\s+(?:No\.?|Number)|\s|$)",
        r"(\bOur\s+Ref\s*[:#]?\s*)([A-Z0-9][A-Z0-9./-]{5,40})",
        r"(\bcompany\s+number\s*)(\d{5,20})",
    ]

    for pattern in patterns:
        # A value can appear once with its label and again in a subject or
        # quoted reply without the label. Mask every exact occurrence.
        values = [match.group(2) for match in re.finditer(pattern, text, flags=re.I)]
        for value in sorted(set(values), key=len, reverse=True):
            value_pattern = rf"(?<![A-Za-z0-9]){re.escape(value)}(?![A-Za-z0-9])"
            text = re.sub(
                value_pattern,
                lambda match: _mask_value(match.group(0)),
                text,
                flags=re.I,
            )

    # The agency at the beginning of an "Our Ref" value may already be
    # replaced with a tag. Mask the remaining reference components as well.
    placeholder_reference = (
        r"(\bOur\s+Ref\s*[:#]?\s*<GOVERNMENT_AGENCY>/)"
        r"([A-Z0-9][A-Z0-9./-]{5,40})"
    )
    text = re.sub(
        placeholder_reference,
        lambda match: f"{match.group(1)}{_mask_value(match.group(2))}",
        text,
        flags=re.I,
    )
    return re.sub(r"#\d{5,}", _mask_match, text)


def _replace_named_business_fallbacks(text):
    government_pattern = (
        r"\b(?:Accounting\s+and\s+Corporate\s+Regulatory\s+Authority|"
        r"Central\s+Provident\s+Fund\s+Board|Land\s+Transport\s+Authority(?:\s+of\s+Singapore)?|"
        r"Corporate\s+Filing\s+and\s+Enforcement\s+Department|Vehicle\s+Licensing\s+Division|"
        r"Ministry\s+of\s+Law|Official\s+Assignee|CPF\s+Board|ACRA|IRAS|LTA|CPF)\b"
    )
    text = re.sub(government_pattern, "<GOVERNMENT_AGENCY>", text, flags=re.I)

    organization_pattern = (
        r"\b(?:[A-Z][A-Za-z0-9&'\u2019.-]*|[A-Z]{2,})"
        r"(?:[ \t]+(?:[A-Z][A-Za-z0-9&'\u2019.-]*|[A-Z]{2,})){0,8}[ \t]+"
        r"(?:Pte\.?[ \t]+Ltd\.?|Ltd\.?|Limited|LLP|LLC|Inc\.?|Corporation|Company|Association)\b"
    )
    return re.sub(organization_pattern, "<ORGANIZATION>", text)


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
        overlapping = [chosen for chosen in selected if _overlaps(entity, chosen)]
        if not overlapping:
            selected.append(entity)
        elif all(_is_better_candidate(entity, chosen) for chosen in overlapping):
            # A long result can intersect several shorter results. Remove all
            # losing spans so replacements never use overlapping offsets.
            selected = [chosen for chosen in selected if chosen not in overlapping]
            selected.append(entity)

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


@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        entity_types=sorted(ENTITY_RULES),
        mask_entity_types=sorted(MASK_ENTITY_TYPES),
        replace_entity_types=sorted(REPLACE_ENTITY_TYPES),
    )


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
