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
    compact = re.sub(r"\s+", "", value)
    return bool(re.fullmatch(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63}", compact, re.I))


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


def _valid_email_date(value: str, context: str) -> bool:
    if _valid_date(value, context):
        return True
    return bool(re.fullmatch(
        r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?[,]?\s+\d{1,2}\s+"
        r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
        r"(?:[,]?\s+\d{4})?",
        value.strip(),
        re.I,
    )) and _context_has(context, ("on", "at", "email", "sent", "received"))


def _normalize_person(value: str) -> str:
    cleaned = " ".join(value.split()).strip(" ,.;:")
    cleaned = re.sub(r"^(?:Mr|Ms|Mrs|Mdm|Dr)\.?\s+", "", cleaned, flags=re.I)
    normalized_tokens = []
    for token in cleaned.split():
        if token.casefold() in {"s/o", "d/o"}:
            normalized_tokens.append(token.upper())
        elif token.isupper() and len(token) > 1:
            normalized_tokens.append(token.title())
        elif token.islower():
            normalized_tokens.append(token.capitalize())
        else:
            normalized_tokens.append(token)
    return " ".join(normalized_tokens)


def _valid_person(value: str, context: str) -> bool:
    value = _normalize_person(value)
    if any(char.isdigit() for char in value):
        return False
    words = value.split()
    blocked_single = {
        "madam", "sir", "thanks", "thank", "regards", "dear", "hi",
        "hello", "subject", "comments", "customer", "agent", "group",
        "mon", "tue", "wed", "thu", "fri", "sat", "sun",
        "monday", "tuesday", "wednesday", "thursday", "friday",
        "saturday", "sunday", "jan", "feb", "mar", "apr", "may",
        "jun", "jul", "aug", "sep", "oct", "nov", "dec",
        "january", "february", "march", "april", "june", "july",
        "august", "september", "october", "november", "december",
        "tagged", "true", "pls", "please", "rgds", "best", "nomad",
    }
    if len(words) == 1:
        return (
            value.lower() not in blocked_single
            and value[:1].isupper()
            and re.fullmatch(r"[A-Z][A-Za-z'â€™-]{2,}", value)
            and _context_has(context, ("dear", "regards", "agent", "by", "from", "to"))
        )
    if not 2 <= len(words) <= 7:
        return False
    blocked = {
        "wilkie edge", "land transport", "private trustees", "office hours",
        "public holidays", "outbound email", "customer service",
        "tagged true", "responded by", "pte ltd", "corporate advisory",
        "dear shanel", "dear lynn", "dear madam", "dear sir", "best rgds",
        "land transport authority of singapore", "rabbit carrot gun pte ltd",
    }
    blocked_tokens = {
        "dear", "pls", "please", "tagged", "true", "director", "manager",
        "executive", "authority", "transport", "government", "agency",
        "pte", "ltd", "limited", "llp", "llc", "inc", "corp", "corporate",
        "advisory", "ocbc", "dbs", "uob", "bank", "wan", "n",
    }
    lowered_words = {word.lower().strip(".,:;") for word in words}
    if value.lower() in blocked or lowered_words & blocked_tokens:
        return False
    if value.isupper() and len(words) > 1 and not _context_has(
        context, ("agent", "by", "from", "to", "dear", "regards")
    ):
        return False
    return all(
        re.fullmatch(r"(?:[A-Za-z][A-Za-z'’-]*|D/O|S/O)", word, re.I)
        for word in words
    )


def _valid_bankrupt_name(value: str, context: str) -> bool:
    if not _valid_person(value, context):
        return False

    name = re.escape(_normalize_person(value))
    compact_context = " ".join(context.split())

    # A trustee of the bankrupt's estate is a person, but is not the bankrupt.
    if re.search(
        rf"(?:appointed\s+)?trustees?\s+of\s+the\s+bankrupt['\u2019]?s\s+estate"
        rf".{{0,180}}\b{name}\b",
        compact_context,
        re.I,
    ):
        return False

    positive_patterns = (
        rf"bankruptcy\s+estate\s+of\s+{name}\b",
        rf"Proof\s+of\s+Debt(?:\s+lodged)?\s+against(?:\s+the\s+bankruptcy\s+estate\s+of)?\s+{name}\b",
        rf"\b{name}\b\s+Bankruptcy\s+(?:No|Number)\b",
        rf"(?:Name\s+of\s+(?:the\s+)?Bankrupt|Bankrupt(?:'s)?\s+Name)\s*[:#-]\s*{name}\b",
        rf"\bI\s+(?:was|am|have\s+been)\s+(?:adjudicated\s+|made\s+|declared\s+)?"
        rf"(?:a\s+)?bankrupt\b.{{0,400}}(?:Regards\s+)?{name}\b",
    )
    return any(re.search(pattern, compact_context, re.I) for pattern in positive_patterns)


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
        r"HC[ /-]\d{2,6}[/ -]\d{4}|"
        r"(?:BANKRUPTCY|BANKRUPT|CASE)[\s:#-]*[A-Z/ -]*\d{2,6}(?:[/ -]\d{2,4})?",
        cleaned,
        re.I,
    ))
    has_case_label_nearby = _context_has(
        context,
        (
            "hc/b", "bankruptcy no", "bankruptcy number", "case no", "case number",
            "adjudicated bankrupt", "bankruptcy estate", "bankrupt under",
        ),
    )
    return has_case_shape and has_case_label_nearby


def _normalize_bankruptcy_number(value: str) -> str:
    cleaned = re.sub(r"\s+", "", value).upper()
    if re.fullmatch(r"HC\d{2,6}/\d{4}", cleaned):
        return f"HC/{cleaned[2:]}"
    return cleaned


def _valid_phone(value: str, context: str) -> bool:
    digits = re.sub(r"\D", "", value)
    if digits.startswith("65") and len(digits) == 10:
        digits = digits[2:]
    return len(digits) == 8 and digits[0] in "3689" and _context_has(
        context,
        (
            "tel", "telephone", "phone", "mobile", "contact", "contactable",
            "call", "hp", "handphone", "whatsapp", "t",
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


def _normalize_known_name(value: str) -> str:
    cleaned = " ".join(value.split()).strip(" ,.;:")
    known = {
        "aia": "AIA", "uob": "UOB", "ocbc": "OCBC", "rsm": "RSM",
        "anext": "ANEXT", "iras": "IRAS", "acra": "ACRA", "lta": "LTA",
        "cpf": "CPF", "cpf board": "CPF Board", "v&p credit": "V&P Credit",
    }
    return known.get(cleaned.casefold(), cleaned)


def _normalize_government_agency(value: str) -> str:
    cleaned = " ".join(value.split()).strip(" ,.;:")
    aliases = {
        "lta": "Land Transport Authority of Singapore",
        "land transport authority": "Land Transport Authority of Singapore",
        "land transport authority of singapore": "Land Transport Authority of Singapore",
        "acra": "Accounting and Corporate Regulatory Authority",
        "accounting and corporate regulatory authority": "Accounting and Corporate Regulatory Authority",
        "cpf": "Central Provident Fund Board",
        "cpf board": "Central Provident Fund Board",
        "central provident fund board": "Central Provident Fund Board",
        "iras": "Inland Revenue Authority of Singapore",
    }
    return aliases.get(cleaned.casefold(), cleaned)


def _valid_location(value: str, _: str) -> bool:
    cleaned = " ".join(value.split()).strip(" ,.;:")
    lowered = cleaned.lower()
    blocked = {
        "best rgds", "insolvency", "acra", "gazette", "puvaneswaran",
        "office hours", "public holidays",
    }
    if lowered in blocked:
        return False
    if re.fullmatch(r"\d{1,2}[.:]\d{2}\s*(?:am|pm)?", cleaned, re.I):
        return False
    if re.fullmatch(r"\d+(?:\.\d+)?\s*(?:am|pm)", cleaned, re.I):
        return False
    if any(char.isdigit() for char in cleaned):
        has_address_shape = bool(re.search(
            r"\b(?:road|street|avenue|drive|lane|walk|close|boulevard|place|"
            r"crescent|highway|terrace|way)\b|#\d{1,2}-\d{1,4}|\b\d{6}\b|"
            r"\b[A-Z]{1,2}\d[A-Z\d]?\s+\d[A-Z]{2}\b",
            cleaned,
            re.I,
        ))
        has_known_place = bool(re.search(
            r"\b(?:singapore|london|england|wales|switzerland|malaysia)\b",
            lowered,
        ))
        if not has_address_shape and not has_known_place:
            return False
    return len(cleaned) >= 3 and not cleaned.isdigit()


def _valid_url(value: str, _: str) -> bool:
    return bool(re.fullmatch(r"https?://[^\s]+|www\.[^\s]+", value.rstrip(".,;)"), re.I))


def _valid_job_title(value: str, _: str) -> bool:
    cleaned = " ".join(value.split()).strip(" ,.;:")
    if not cleaned[:1].isupper():
        return False
    return bool(re.fullmatch(
        r"(?:(?:Managing|Senior|Principal|Assistant|Deputy|Associate|Chief)\s+)?"
        r"(?:Director|Manager|Partner|CEO|CTO|CFO|COO|CIO|"
        r"Analyst|Developer|Architect|Consultant|Trustee|Liquidator|Officer|Executive)",
        cleaned,
        re.I,
    ))


def _valid_organization(value: str, _: str) -> bool:
    cleaned = " ".join(value.split()).strip(" ,.;:")
    lowered = cleaned.lower()
    if len(cleaned) < 3 or cleaned.isdigit():
        return False
    blocked = {
        "best rgds", "dear madam", "dear sir", "tagged true", "pte ltd", "ltd",
        "international limited", "international association",
    }
    if lowered in blocked:
        return False
    known = {
        "rsm", "rsm singapore", "aia", "uob", "ocbc", "anext", "v&p credit",
    }
    if lowered in known:
        return True
    return bool(re.search(
        r"\b(?:pte|ltd|limited|llp|llc|inc|corp|corporation|company|bank|"
        r"association|authority|agency|ministry|board|department|services|solutions)\b",
        lowered,
    ))


def _valid_creditor_name(value: str, context: str) -> bool:
    cleaned = " ".join(value.split()).strip(" ,.;:")
    if cleaned.casefold() not in {"iras", "uob", "ocbc", "anext"}:
        return False
    return _context_has(
        context,
        (
            "creditor", "proof of debt", "debt", "loan", "outstanding", "liability",
            "repayment", "payment", "settlement", "redemption", "amount owed", "tax",
        ),
    )


def _valid_law_firm(value: str, context: str) -> bool:
    cleaned = " ".join(value.split()).strip(" ,.;:")
    name_is_legal = bool(re.search(
        r"\b(?:law|legal|chambers|advocates|solicitors)\b",
        cleaned,
        re.I,
    ))
    context_is_legal = bool(re.search(
        r"\b(?:law\s+firm|legal\s+counsel|legal\s+representative|advocates|solicitors)\b",
        context,
        re.I,
    ))
    return _valid_named_entity(cleaned, context) and (name_is_legal or context_is_legal)


def _valid_government_agency(value: str, _: str) -> bool:
    cleaned = " ".join(value.split()).strip(" ,.;:")
    lowered = cleaned.lower()
    known = {
        "lta", "iras", "acra", "cpf", "cpf board",
        "land transport authority", "land transport authority of singapore",
        "central provident fund board", "accounting and corporate regulatory authority",
        "corporate filing and enforcement department", "vehicle licensing division",
        "ministry of law", "official assignee",
    }
    return lowered in known or bool(re.search(
        r"\b(?:authority|ministry|department|agency|board|regulator)\b",
        lowered,
    ))


def _compact_upper(value: str) -> str:
    return re.sub(r"[\s-]", "", value).upper()


ENTITY_RULES = {
    "EMAIL_ADDRESS": EntityRule(
        0.80,
        _valid_email,
        lambda v: re.sub(r"\s+", "", v).lower(),
    ),
    "EMAIL_DATE": EntityRule(0.75, _valid_email_date),
    "DATE_TIME": EntityRule(0.80, _valid_date),
    "PERSON": EntityRule(0.82, _valid_person, _normalize_person),
    "BANK_ACCOUNT_NUMBER": EntityRule(0.75, _valid_bank_account, lambda v: re.sub(r"\s+", "", v)),
    "BANKRUPTCY_NUMBER": EntityRule(0.75, _valid_bankruptcy_number, _normalize_bankruptcy_number),
    "SG_VEHICLE_NUMBER": EntityRule(0.65, _valid_sg_vehicle, _compact_upper),
    "SG_NRIC_FIN": EntityRule(0.80, _valid_nric_fin, _compact_upper),
    "PHONE_NUMBER": EntityRule(0.75, _valid_phone, lambda v: re.sub(r"[^\d+]", "", v)),
    "PASSPORT_NUMBER": EntityRule(0.75, _valid_passport, _compact_upper),
    "URL": EntityRule(0.70, _valid_url, lambda v: v.rstrip(".,;)")),
    "LOCATION": EntityRule(0.82, _valid_location),
    "JOB_TITLE": EntityRule(0.70, _valid_job_title),
    "ORGANIZATION": EntityRule(0.82, _valid_organization, _normalize_known_name),
    "CREDITOR_NAME": EntityRule(0.82, _valid_creditor_name, _normalize_known_name),
    "BANKRUPT_NAME": EntityRule(0.82, _valid_bankrupt_name, _normalize_person),
    "LAW_FIRM": EntityRule(0.80, _valid_law_firm),
    "GOVERNMENT_AGENCY": EntityRule(0.80, _valid_government_agency, _normalize_government_agency),
}
