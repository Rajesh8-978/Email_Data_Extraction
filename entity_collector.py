from collections import defaultdict
from typing import Iterable

from entity_rules import ENTITY_RULES


def _context(text: str, start: int, end: int, radius: int = 80) -> str:
    return text[max(0, start - radius):min(len(text), end + radius)]


def collect_entities(text: str, results: Iterable, requested_entities=None) -> list[dict]:
    """Validate, normalize and deduplicate Presidio/GLiNER candidates."""
    allowed = set(requested_entities or ENTITY_RULES)
    accepted = []

    for result in results:
        entity_type = result.entity_type
        rule = ENTITY_RULES.get(entity_type)
        if not rule or entity_type not in allowed or result.score < rule.min_score:
            continue

        raw_value = text[result.start:result.end].strip()
        context = _context(text, result.start, result.end)
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

    # Keep the strongest result for the same type and normalized value.
    strongest = {}
    for item in accepted:
        key = (item["entity_type"], item["normalized_value"].casefold())
        previous = strongest.get(key)
        if previous is None or item["confidence"] > previous["confidence"]:
            strongest[key] = item

    return sorted(strongest.values(), key=lambda item: (item["start"], item["entity_type"]))


def group_entities(entities: list[dict]) -> dict[str, list[dict]]:
    grouped = defaultdict(list)
    for entity in entities:
        grouped[entity["entity_type"]].append(entity)
    return dict(grouped)

