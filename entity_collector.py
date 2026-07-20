from collections import defaultdict
from typing import Iterable

from entity_rules import ENTITY_RULES


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


def _context(text: str, start: int, end: int, radius: int = 80) -> str:
    return text[max(0, start - radius):min(len(text), end + radius)]


def _overlaps(left: dict, right: dict) -> bool:
    return left["start"] < right["end"] and right["start"] < left["end"]


def _priority(item: dict) -> tuple:
    return (
        ENTITY_PRIORITY.get(item["entity_type"], 0),
        item["end"] - item["start"],
        item["confidence"],
    )


def _remove_overlaps(entities: list[dict]) -> list[dict]:
    selected = []
    for item in sorted(
        entities,
        key=lambda entity: (
            -ENTITY_PRIORITY.get(entity["entity_type"], 0),
            -(entity["end"] - entity["start"]),
            -entity["confidence"],
            entity["start"],
        ),
    ):
        overlapping = [chosen for chosen in selected if _overlaps(item, chosen)]
        if not overlapping:
            selected.append(item)
        elif all(_priority(item) > _priority(chosen) for chosen in overlapping):
            selected = [chosen for chosen in selected if chosen not in overlapping]
            selected.append(item)
    return sorted(selected, key=lambda item: (item["start"], item["entity_type"]))


def collect_entities(
    text: str,
    results: Iterable,
    requested_entities=None,
    deduplicate: bool = True,
) -> list[dict]:
    """Validate, normalize and optionally deduplicate Presidio/GLiNER candidates."""
    allowed = set(requested_entities or ENTITY_RULES)
    accepted = []

    for result in results:
        entity_type = result.entity_type
        rule = ENTITY_RULES.get(entity_type)
        if not rule or entity_type not in allowed or result.score < rule.min_score:
            continue

        raw_value = text[result.start:result.end].strip()
        # Business relationships can span a sentence, signature, or short paragraph.
        context_radius = {
            "BANKRUPT_NAME": 500,
            "CREDITOR_NAME": 220,
            "GOVERNMENT_AGENCY": 140,
            "ORGANIZATION": 120,
            "LAW_FIRM": 160,
        }.get(entity_type, 80)
        context = _context(text, result.start, result.end, radius=context_radius)
        if not raw_value or not rule.validator(raw_value, context):
            continue

        accepted.append({
            "entity_type": entity_type,
            "value": raw_value,
            "normalized_value": rule.normalizer(raw_value),
            "start": result.start,
            "end": result.end,
            "confidence": round(float(result.score), 4),
            "context": context,
        })

    if not deduplicate:
        return sorted(accepted, key=lambda item: (item["start"], item["end"], item["entity_type"]))

    # Keep the strongest result for the same type and normalized value.
    strongest = {}
    for item in accepted:
        key = (item["entity_type"], item["normalized_value"].casefold())
        previous = strongest.get(key)
        if previous is None or item["confidence"] > previous["confidence"]:
            strongest[key] = item

    return _remove_overlaps(list(strongest.values()))


def group_entities(entities: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for entity in entities:
        grouped[entity["entity_type"]].append(entity)
    return dict(grouped)
