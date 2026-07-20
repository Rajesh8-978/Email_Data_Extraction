import re

from presidio_analyzer import EntityRecognizer, Pattern, PatternRecognizer, RecognizerResult


_NAME_TOKEN = r"(?:[A-Za-z][A-Za-z'\u2019.-]*|[A-Z])"
_NAME = rf"{_NAME_TOKEN}(?:[ \t]+(?:(?:s|d)/o|{_NAME_TOKEN})){{0,6}}"
_FORMAL_NAME_TOKEN = r"(?:[A-Z][A-Za-z'\u2019.-]*|[A-Z])"
_FORMAL_NAME = rf"{_FORMAL_NAME_TOKEN}(?:[ \t]+(?:(?:s|d)/o|{_FORMAL_NAME_TOKEN})){{0,6}}"
_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_ORG_TOKEN = r"(?:[A-Z][A-Za-z0-9&'\u2019.-]*|[A-Z]{2,})"
_ORG_NAME = rf"{_ORG_TOKEN}(?:[ \t]+{_ORG_TOKEN}){{0,8}}"


class TargetedDocumentRecognizer(EntityRecognizer):
    """High-precision document patterns for addresses and contextual person names."""

    _patterns = {
        "EMAIL_ADDRESS": [
            (
                re.compile(
                    r"(?im)^[ \t\u00a0]*E[ \t\u00a0]+(?P<value>"
                    r"(?:[A-Za-z0-9._%+-][ \t\u00a0]*){2,64}@[ \t\u00a0]*"
                    r"(?:[A-Za-z0-9-][ \t\u00a0]*){2,63}"
                    r"(?:\.[ \t\u00a0]*(?:[A-Za-z][ \t\u00a0]*){2,20})+)"
                    r"[ \t\u00a0]*$"
                ),
                0.96,
            ),
        ],
        "EMAIL_DATE": [
            (
                re.compile(
                    rf"(?i)\bon\s+(?P<value>(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:day)?[,]?\s+"
                    rf"\d{{1,2}}\s+{_MONTH}(?:[,]?\s+\d{{4}})?)(?=\s+at\b)"
                ),
                0.96,
            ),
        ],
        "BANKRUPTCY_NUMBER": [
            (
                re.compile(
                    r"(?i)(?P<value>\b(?:HC\s*/?\s*)?B\s*/\s*\d{1,6}\s*/\s*\d{4}\b)"
                ),
                0.97,
            ),
            (
                re.compile(r"(?i)(?P<value>\bHC\s+\d{1,6}\s*/\s*\d{4}\b)"),
                0.94,
            ),
        ],
        "LOCATION": [
            (
                re.compile(
                    r"(?im)(?P<value>\b(?:Blk(?:ock)?\s+)?\d{1,5}\s+[^\n.;]{1,160}?"
                    r"\bSingapore\s+\d{6}\b)"
                ),
                0.96,
            ),
            (
                re.compile(
                    r"(?im)(?P<value>\b(?:Blk(?:ock)?\s+)?\d{1,5}\s+[^\n.;]{1,160}?"
                    r"\b(?:Road|Street|Avenue|Drive|Lane|Walk|Close|Boulevard|Place|"
                    r"Crescent|Highway|Terrace|Way)\b[^\n.;]{0,120}?\b\d{6}\b)"
                ),
                0.94,
            ),
            (
                re.compile(
                    r"(?im)(?P<value>\b\d{1,5}\s+[A-Za-z0-9'\u2019.,# /\r\n-]{1,160}?,\s*"
                    r"[A-Z]{1,2}\d[A-Z\d]?\s+\d[A-Z]{2}\b)"
                ),
                0.94,
            ),
        ],
        "PERSON": [
            (re.compile(rf"(?im)^Agent\s*\r?\n(?P<value>{_NAME})\s*$"), 0.94),
            (re.compile(rf"(?i)\bby\s+(?P<value>{_NAME})\s+on\s+"), 0.92),
            (re.compile(rf"(?im)^to\s+(?P<value>{_NAME})\s+on\s+"), 0.92),
            (
                re.compile(
                    rf"(?im)^(?:Dear|Hi)\s+(?P<value>(?!(?:Sir|Madam)\b){_NAME})\s*[,!]*\s*$"
                ),
                0.90,
            ),
            (
                re.compile(
                    rf"(?im)^(?:Kind regards|Best regards|Regards|Yours sincerely)\s*,?\s*\r?\n"
                    rf"(?P<value>{_NAME})\s*$"
                ),
                0.92,
            ),
            (
                re.compile(rf"\b(?:Mr|Ms|Mrs|Mdm|Dr)\.?\s+(?P<value>{_FORMAL_NAME})"),
                0.90,
            ),
            (
                re.compile(
                    rf"\b(?i:wife|husband|sister|brother|son|daughter),?\s+"
                    rf"(?:(?i:Mr|Ms|Mrs|Mdm|Dr))?\.?\s*(?P<value>{_FORMAL_NAME})(?=[,.;\n])"
                ),
                0.90,
            ),
        ],
        "BANKRUPT_NAME": [
            (
                re.compile(
                    rf"(?i)\bbankruptcy\s+estate\s+of\s+(?P<value>{_NAME})"
                    rf"(?=[,.;\n])"
                ),
                0.98,
            ),
            (
                re.compile(
                    rf"(?i)\bProof\s+of\s+Debt(?:\s+lodged)?\s+against\s+"
                    rf"(?:the\s+bankruptcy\s+estate\s+of\s+)?(?P<value>{_NAME})"
                    rf"(?=[,.;\n-])"
                ),
                0.98,
            ),
            (
                re.compile(
                    rf"(?im)^(?P<value>{_NAME})\s*\r?\nBankruptcy\s+(?:No|Number)\.?\s*[:#]?"
                ),
                0.97,
            ),
            (
                re.compile(
                    rf"(?i)\b(?:Name\s+of\s+(?:the\s+)?Bankrupt|Bankrupt(?:'s)?\s+Name)"
                    rf"\s*[:#-]\s*(?P<value>{_NAME})(?=[,.;\n])"
                ),
                0.98,
            ),
            (
                re.compile(
                    rf"(?is)\bI\s+(?:was|am|have\s+been)\s+"
                    rf"(?:adjudicated\s+|made\s+|declared\s+)?(?:a\s+)?bankrupt\b"
                    rf".{{0,400}}?\bRegards\s*\r?\n(?P<value>{_NAME})(?=\s*(?:\r?\n|$))"
                ),
                0.96,
            ),
        ],
        "JOB_TITLE": [
            (
                re.compile(
                    r"(?P<value>\b(?:(?:Managing|Senior|Principal|Assistant|Deputy|Associate|Chief)\s+)?"
                    r"(?:Director|Manager|Partner|CEO|CTO|CFO|COO|CIO|Analyst|Developer|Architect|"
                    r"Consultant|Trustee|Liquidator|Officer|Executive)\b)"
                ),
                0.92,
            ),
        ],
        "ORGANIZATION": [
            (
                re.compile(
                    r"(?im)^(?P<value>RSM[ \t]+Corporate[ \t]+Advisory[ \t]*\r?\n"
                    r"Pte[ \t]+Ltd)[ \t]*$"
                ),
                0.97,
            ),
            (
                re.compile(
                    rf"(?P<value>\b{_ORG_NAME}[ \t]+(?i:Pte\.?[ \t]+Ltd\.?|Ltd\.?|Limited|"
                    rf"LLP|LLC|Inc\.?|Corporation|Company|Association)\b)"
                ),
                0.96,
            ),
            (
                re.compile(
                    r"(?i)(?P<value>\b(?:RSM(?:\s+Singapore)?|AIA|UOB|OCBC|ANEXT|V&P\s+Credit)\b)"
                ),
                0.91,
            ),
        ],
        "CREDITOR_NAME": [
            (
                re.compile(r"(?i)(?P<value>\b(?:IRAS|UOB|OCBC|ANEXT)\b)"),
                0.92,
            ),
        ],
        "GOVERNMENT_AGENCY": [
            (
                re.compile(
                    r"(?i)(?P<value>\b(?:Accounting\s+and\s+Corporate\s+Regulatory\s+Authority|"
                    r"Central\s+Provident\s+Fund\s+Board|Land\s+Transport\s+Authority(?:\s+of\s+Singapore)?|"
                    r"Corporate\s+Filing\s+and\s+Enforcement\s+Department|Vehicle\s+Licensing\s+Division|"
                    r"Ministry\s+of\s+Law|Official\s+Assignee|CPF\s+Board|ACRA|IRAS|LTA|CPF)\b)"
                ),
                0.96,
            ),
        ],
    }

    def __init__(self):
        super().__init__(
            supported_entities=list(self._patterns),
            supported_language="en",
        )

    def analyze(self, text, entities, nlp_artifacts=None):
        results = []
        for entity_type in set(entities) & set(self.supported_entities):
            for pattern, score in self._patterns[entity_type]:
                for match in pattern.finditer(text):
                    start, end = match.span("value")
                    results.append(
                        RecognizerResult(
                            entity_type=entity_type,
                            start=start,
                            end=end,
                            score=score,
                        )
                    )
        return results


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

    return [
        email_date,
        bank_account,
        bankruptcy_number,
        phone_number,
        url,
        email_header_person,
        TargetedDocumentRecognizer(),
    ]
