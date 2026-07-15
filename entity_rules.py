import re
from dataclasses import dataclass
from typing import Callable


Validator = Callable[[str, str], bool]
Normalizer = Callable[[str], str]


@dataclass(frozen=True)
class EntityRule:
    min_score: float
    validator: Validator
    normalizer: Normalizer = lambda value: " ".join(value.split())


def _context_has(context: str, words: tuple[str, ...]) -> bool:
    lowered = context.lower()
    return any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in words)


def _valid_email(value: str, _: str) -> bool:
    return bool(re.fullmatch(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63}", value, re.I))


def _valid_date(value: str, context: str) -> bool:
    value = value.strip()
    # Reject bare years, weekdays, months and unrelated short numbers.
    if re.fullmatch(r"\d{4}", value) or value.lower() in {
        "mon", "tue", "wed", "thu", "fri", "sat", "sun",
        "monday", "tuesday", "wednesday", "thursday", "friday",
        "saturday", "sunday", "jan", "feb", "mar", "apr", "may",
        "jun", "jul", "aug", "sep", "oct", "nov", "dec",
    }:
        return False
    date_pattern = (
        r"(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4})|"
        r"(?:\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
        r"May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?),?\s+\d{2,4})|"
        r"(?:(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
        r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
        r"Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{2,4})"
    )
    return bool(re.search(date_pattern, value, re.I)) or (
        bool(re.fullmatch(r"\d{1,2}:\d{2}\s*(?:AM|PM)", value, re.I))
        and _context_has(context, ("date", "sent", "received", "email", "on", "at"))
    )


def _valid_person(value: str, _: str) -> bool:
    value = " ".join(value.split()).strip(" ,.;:")
    if any(char.isdigit() for char in value):
        return False
    words = value.split()
    if not 2 <= len(words) <= 7:
        return False
    blocked = {
        "wilkie edge", "land transport", "private trustees", "office hours",
        "public holidays", "outbound email", "customer service",
    }
    return value.lower() not in blocked and all(
        re.fullmatch(r"(?:[A-Za-z][A-Za-z'’-]*|D/O|S/O)", word, re.I)
        for word in words
    )


def _valid_sg_vehicle(value: str, context: str) -> bool:
    compact = re.sub(r"[\s-]", "", value).upper()
    return bool(re.fullmatch(r"[A-Z]{1,3}\d{1,4}[A-Z]", compact)) and _context_has(
        context, ("vehicle", "registration", "plate", "car", "coe")
    )


def _valid_bank_account(value: str, context: str) -> bool:
    digits = re.sub(r"[\s-]", "", value)
    if not digits.isdigit() or not 6 <= len(digits) <= 18:
        return False
    if re.fullmatch(r"(?:19|20)\d{6}", digits):  # YYYYMMDD
        return False
    return _context_has(
        context,
        ("account", "account no", "account number", "bank", "beneficiary", "iban", "swift")
    )


def _valid_bankruptcy_number(value: str, context: str) -> bool:
    cleaned = " ".join(value.split()).strip(" ,.;:")
    digits = re.sub(r"\D", "", cleaned)
    if len(digits) < 4:
        return False
    if re.fullmatch(r"\d{1,2}(?:-\d{1,2})?", cleaned):
        return False
    if re.fullmatch(r"(?:19|20)\d{6}", digits):  # YYYYMMDD-like reference/date
        return False
    has_case_shape = bool(re.fullmatch(
        r"(?:HC/)?B[/ -]?\d{2,6}[/ -]?\d{4}|"
        r"(?:BANKRUPTCY|BANKRUPT|CASE)[\s:#-]*[A-Z/ -]*\d{2,6}(?:[/ -]\d{2,4})?",
        cleaned,
        re.I,
    ))
    has_case_label_nearby = _context_has(
        context, ("hc/b", "bankruptcy no", "bankruptcy number", "case no", "case number")
    )
    return has_case_shape and has_case_label_nearby


def _valid_phone(value: str, context: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("65") and len(digits) == 10:
        digits = digits[2:]
    return len(digits) == 8 and digits[0] in "3689" and _context_has(
        context,
        (
            "tel", "telephone", "phone", "mobile", "contact", "contactable",
            "call", "hp", "handphone", "whatsapp",
        )
    )


def _valid_nric_fin(value: str, _: str) -> bool:
    return bool(re.fullmatch(r"[STFGM]\d{7}[A-Z]", value.strip(), re.I))


def _valid_passport(value: str, context: str) -> bool:
    return bool(re.fullmatch(r"[A-Z][A-Z0-9]{7,8}", value.strip(), re.I)) and _context_has(
        context, ("passport", "travel document")
    )


def _valid_named_entity(value: str, _: str) -> bool:
    cleaned = " ".join(value.split())
    return len(cleaned) >= 3 and not cleaned.isdigit()


def _valid_url(value: str, _: str) -> bool:
    return bool(re.fullmatch(r"https?://[^\s]+|www\.[^\s]+", value.rstrip(".,;)"), re.I))


def _valid_job_title(value: str, _: str) -> bool:
    return bool(re.fullmatch(
        r"(?:Managing\s+)?(?:Director|Manager|Partner|CEO|CTO|CFO|COO|CIO|"
        r"Analyst|Developer|Architect|Consultant|Trustee|Liquidator|Officer|Executive)",
        " ".join(value.split()),
        re.I,
    ))


def _compact_upper(value: str) -> str:
    return re.sub(r"[\s-]", "", value).upper()


ENTITY_RULES = {
    "EMAIL_ADDRESS": EntityRule(0.80, _valid_email, lambda v: v.strip().lower()),
    "EMAIL_DATE": EntityRule(0.75, _valid_date),
    "DATE_TIME": EntityRule(0.80, _valid_date),
    "PERSON": EntityRule(0.82, _valid_person),
    "BANK_ACCOUNT_NUMBER": EntityRule(0.75, _valid_bank_account, lambda v: re.sub(r"\s+", "", v)),
    "BANKRUPTCY_NUMBER": EntityRule(0.75, _valid_bankruptcy_number, _compact_upper),
    "SG_VEHICLE_NUMBER": EntityRule(0.65, _valid_sg_vehicle, _compact_upper),
    "SG_NRIC_FIN": EntityRule(0.80, _valid_nric_fin, _compact_upper),
    "PHONE_NUMBER": EntityRule(0.75, _valid_phone, lambda v: re.sub(r"[^\d+]", "", v)),
    "PASSPORT_NUMBER": EntityRule(0.75, _valid_passport, _compact_upper),
    "URL": EntityRule(0.70, _valid_url, lambda v: v.rstrip(".,;)")),
    "LOCATION": EntityRule(0.82, _valid_named_entity),
    "JOB_TITLE": EntityRule(0.70, _valid_job_title),
    "ORGANIZATION": EntityRule(0.82, _valid_named_entity),
    "CREDITOR_NAME": EntityRule(0.82, _valid_named_entity),
    "BANKRUPT_NAME": EntityRule(0.82, _valid_person),
    "LAW_FIRM": EntityRule(0.80, _valid_named_entity),
    "GOVERNMENT_AGENCY": EntityRule(0.80, _valid_named_entity),
}
