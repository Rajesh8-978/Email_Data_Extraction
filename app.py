from flask import Flask, request, jsonify
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry

from recognizers.singapore_recognizers import singapore_recognizers
from recognizers.business_recognizers import business_recognizers
from recognizers.gliner_recognizer import GlinerRecognizer
from entity_collector import collect_entities, group_entities
from entity_rules import ENTITY_RULES

app = Flask(__name__)

registry = RecognizerRegistry()
registry.load_predefined_recognizers()

analyzer = AnalyzerEngine(
    registry=registry,
    nlp_engine=None
)

for recognizer in singapore_recognizers():
    analyzer.registry.add_recognizer(recognizer)

for recognizer in business_recognizers():
    analyzer.registry.add_recognizer(recognizer)

analyzer.registry.add_recognizer(GlinerRecognizer())


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json(silent=True) or {}

    text = data.get("text", "")
    language = data.get("language", "en")
    entities = data.get("entities") or list(ENTITY_RULES)

    if not isinstance(text, str) or not text.strip():
        return jsonify({"error": "'text' must be a non-empty string"}), 400
    if not isinstance(entities, list):
        return jsonify({"error": "'entities' must be a list"}), 400

    results = analyzer.analyze(
        text=text,
        language=language,
        entities=entities
    )

    collected = collect_entities(text, results, entities)
    return jsonify({
        "count": len(collected),
        "entities": collected,
        "grouped": group_entities(collected),
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
