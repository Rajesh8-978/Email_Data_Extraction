from presidio_analyzer import EntityRecognizer, RecognizerResult
from gliner import GLiNER

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
            labels = list(label_map.values())

        predictions = self.model.predict_entities(text, labels)

        results = []

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
                    start=item["start"],
                    end=item["end"],
                    score=float(item.get("score", 0.75))
                )
            )

        return results