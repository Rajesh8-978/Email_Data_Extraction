from presidio_analyzer import PatternRecognizer, Pattern

def singapore_recognizers():
    nric_fin = PatternRecognizer(
        supported_entity="SG_NRIC_FIN",
        patterns=[
            Pattern(
                name="sg_nric_fin",
                regex=r"\b[STFGM]\d{7}[A-Z]\b",
                score=0.85
            )
        ],
        context=["nric", "fin", "ic", "identity", "singapore"]
    )

    passport = PatternRecognizer(
        supported_entity="PASSPORT_NUMBER",
        patterns=[
            Pattern(
                name="passport_context",
                regex=r"\b[A-Z][0-9]{7,8}\b",
                score=0.55
            )
        ],
        context=["passport", "travel document"]
    )

    vehicle = PatternRecognizer(
        supported_entity="SG_VEHICLE_NUMBER",
        patterns=[
            Pattern(
                name="sg_vehicle_no",
                regex=r"\b[A-Z]{1,3}\d{1,4}[A-Z]\b",
                score=0.65
            )
        ],
        context=["vehicle", "car", "registration", "plate"]
    )

    job_title = PatternRecognizer(
        supported_entity="JOB_TITLE",
        patterns=[
            Pattern(
                name="job_title",
                regex=r"\b(Director|Manager|Partner|CEO|CTO|CFO|COO|CIO|Analyst|Developer|Architect|Consultant|Trustee|Liquidator|Officer|Executive)\b",
                score=0.7
            )
        ],
        context=["designation", "title", "role", "position"]
    )

    return [nric_fin, passport, vehicle, job_title]