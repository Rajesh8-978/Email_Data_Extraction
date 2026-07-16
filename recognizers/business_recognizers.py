from presidio_analyzer import Pattern, PatternRecognizer


def business_recognizers():
    email_date = PatternRecognizer(
        supported_entity="EMAIL_DATE",
        patterns=[Pattern(
            name="email_date",
            regex=(
                r"\b(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|"
                r"\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|"
                r"Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|"
                r"Nov(?:ember)?|Dec(?:ember)?),?\s+\d{2,4})\b"
            ),
            score=0.85,
        )],
        context=["email", "sent", "received", "date", "on"],
    )

    bank_account = PatternRecognizer(
        supported_entity="BANK_ACCOUNT_NUMBER",
        patterns=[
            Pattern(
                name="bank_account_with_separators",
                regex=r"\b\d{3,6}(?:[ -]\d{2,6}){1,3}\b",
                score=0.78,
            ),
            Pattern(
                name="continuous_bank_account",
                regex=r"\b\d{6,18}\b",
                score=0.75,
            ),
        ],
        context=["bank", "account", "beneficiary", "iban", "swift"],
    )

    bankruptcy_number = PatternRecognizer(
        supported_entity="BANKRUPTCY_NUMBER",
        patterns=[Pattern(
            name="bankruptcy_case_number",
            regex=r"\b(?:HC[/ -]?)?B[/ -]?\d{2,6}[/ -]?\d{4}\b",
            score=0.78,
        )],
        context=["hc/b", "bankruptcy", "bankrupt", "insolvency", "case number", "case no"],
    )

    phone_number = PatternRecognizer(
        supported_entity="PHONE_NUMBER",
        patterns=[
            Pattern(
                name="sg_phone_with_country_code",
                regex=r"(?<!\d)(?:\+65|65)[\s-]?[3689]\d{3}[\s-]?\d{4}(?!\d)",
                score=0.88,
            ),
            Pattern(
                name="sg_phone_without_country_code",
                regex=r"(?<!\d)[3689]\d{3}[\s-]?\d{4}(?!\d)",
                score=0.82,
            ),
        ],
        context=[
            "tel", "telephone", "phone", "mobile", "contact", "contactable",
            "call", "hp", "handphone", "whatsapp",
        ],
    )

    url = PatternRecognizer(
        supported_entity="URL",
        patterns=[
            Pattern(
                name="url",
                regex=r"\bhttps?://[^\s<>()]+|\bwww\.[^\s<>()]+",
                score=0.86,
            )
        ],
        context=["website", "web", "url", "visit", "refer"],
    )

    email_header_person = PatternRecognizer(
        supported_entity="PERSON",
        patterns=[
            Pattern(
                name="agent_name",
                regex=r"(?<=\bAgent\n)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}",
                score=0.86,
            ),
            Pattern(
                name="by_name_on",
                regex=r"(?<=\bby\s)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}(?=\s+on\s)",
                score=0.86,
            ),
            Pattern(
                name="regards_name",
                regex=r"(?<=\bRegards,\n)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}",
                score=0.84,
            ),
            Pattern(
                name="regards_name_no_comma",
                regex=r"(?<=\bRegards\n)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}",
                score=0.84,
            ),
            Pattern(
                name="best_regards_name",
                regex=r"(?<=\bBest regards,\n)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}",
                score=0.84,
            ),
            Pattern(
                name="dear_name",
                regex=r"(?<=\bDear\s)[A-Z][A-Za-z'’.-]+(?:[ \t]+[A-Z][A-Za-z'’.-]+){0,5}",
                score=0.82,
            ),
        ],
        context=["agent", "by", "dear", "regards", "from", "to"],
    )

    return [email_date, bank_account, bankruptcy_number, phone_number, url, email_header_person]
