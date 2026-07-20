from presidio_analyzer import EntityRecognizer, RecognizerResult
from gliner import GLiNER


def _chunk_text(text, max_chars=1200, overlap=120):
    """Yield overlapping chunks so long PDF text is not truncated by GLiNER."""
    start = 0
    text_length = len(text)

    while start < text_length:
        end = min(start + max_chars, text_length)
        yield start, text[start:end]
        if end >= text_length:
            break
        start = end - overlap


class GlinerRecognizer(EntityRecognizer):
    def __init__(self):
        self.model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")

        super().__init__(
            supported_entities=[
                "PERSON",
                "ORGANIZATION",
                "CREDITOR_NAME",
                "BANKRUPT_NAME",
                "LAW_FIRM",
                "GOVERNMENT_AGENCY"
            ],
            supported_language="en"
        )

    def analyze(self, text, entities, nlp_artifacts=None):
        label_map = {
            "PERSON": "person",
            "ORGANIZATION": "organization",
            "CREDITOR_NAME": "creditor name",
            "BANKRUPT_NAME": "bankrupt person name",
            "LAW_FIRM": "law firm",
            "GOVERNMENT_AGENCY": "government agency"
        }

        labels = [
            label_map[e]
            for e in entities
            if e in label_map
        ]

        if not labels:
            return []

        chunks = list(_chunk_text(text))
        chunk_predictions = self.model.batch_predict_entities(
            [chunk for _, chunk in chunks],
            labels,
        )

        results = []

        for (chunk_start, _), predictions in zip(chunks, chunk_predictions):
            for item in predictions:
                label = item["label"].upper().replace(" ", "_")

                reverse_map = {
                    "PERSON": "PERSON",
                    "ORGANIZATION": "ORGANIZATION",
                    "CREDITOR_NAME": "CREDITOR_NAME",
                    "BANKRUPT_PERSON_NAME": "BANKRUPT_NAME",
                    "LAW_FIRM": "LAW_FIRM",
                    "GOVERNMENT_AGENCY": "GOVERNMENT_AGENCY"
                }

                entity_type = reverse_map.get(label)
                if not entity_type:
                    continue

                results.append(
                    RecognizerResult(
                        entity_type=entity_type,
                        start=chunk_start + item["start"],
                        end=chunk_start + item["end"],
                        score=float(item.get("score", 0.75))
                    )
                )

        return results
