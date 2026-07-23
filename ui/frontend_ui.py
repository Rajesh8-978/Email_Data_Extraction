from pathlib import Path

import requests
from flask import Flask, jsonify, request, send_from_directory


UI_DIR = Path(__file__).resolve().parent
DEFAULT_API_BASE = "https://presidio-test-api.bravesand-5605c72b.southeastasia.azurecontainerapps.io"
REQUEST_TIMEOUT_SECONDS = 300

app = Flask(__name__, static_folder=str(UI_DIR), static_url_path="")
api_session = requests.Session()
api_session.trust_env = False


def _api_base():
    api_base = request.form.get("api_base") or (request.get_json(silent=True) or {}).get("api_base")
    api_base = (api_base or DEFAULT_API_BASE).strip().rstrip("/")
    if not api_base.startswith(("http://", "https://")):
        return None, jsonify({"error": "API base URL must start with http:// or https://"}), 400
    return api_base, None, None


def _json_response(response):
    try:
        return jsonify(response.json()), response.status_code
    except ValueError:
        return jsonify({
            "error": "API returned a non-JSON response.",
            "status_code": response.status_code,
            "details": response.text[:1000],
        }), response.status_code


def _proxy_error(error):
    return jsonify({
        "error": "Could not connect to the API. Check that the Azure API URL is correct and the app is running.",
        "details": str(error),
    }), 502


@app.route("/", methods=["GET"])
def index():
    return send_from_directory(UI_DIR, "index.html")


@app.route("/ui.config.json", methods=["GET"])
def config():
    return jsonify({"default_api_base": DEFAULT_API_BASE})


@app.route("/proxy/text/extracted-entities", methods=["POST"])
def proxy_text_extraction():
    api_base, error_response, status = _api_base()
    if error_response:
        return error_response, status

    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    language = data.get("language", "en")

    try:
        response = api_session.post(
            f"{api_base}/api/extracted-entities",
            json={"text": text, "language": language},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return _json_response(response)
    except requests.RequestException as error:
        return _proxy_error(error)


@app.route("/proxy/text/anonymized-text", methods=["POST"])
def proxy_text_anonymization():
    api_base, error_response, status = _api_base()
    if error_response:
        return error_response, status

    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    language = data.get("language", "en")

    try:
        response = api_session.post(
            f"{api_base}/api/anonymized-text",
            json={"text": text, "language": language},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return _json_response(response)
    except requests.RequestException as error:
        return _proxy_error(error)


@app.route("/proxy/pdf/extracted-entities", methods=["POST"])
def proxy_pdf_extraction():
    return _proxy_pdf("/api/pdf/extracted-entities")


@app.route("/proxy/pdf/anonymized-text", methods=["POST"])
def proxy_pdf_anonymization():
    return _proxy_pdf("/api/pdf/anonymized-text")


def _proxy_pdf(endpoint):
    api_base, error_response, status = _api_base()
    if error_response:
        return error_response, status

    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "Upload one PDF file."}), 400

    form_data = {
        "language": request.form.get("language", "en"),
        "email_message_id": request.form.get("email_message_id", "1"),
    }
    files = {
        "file": (uploaded.filename, uploaded.stream, uploaded.mimetype or "application/pdf")
    }

    try:
        response = api_session.post(
            f"{api_base}{endpoint}",
            data=form_data,
            files=files,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        return _json_response(response)
    except requests.RequestException as error:
        return _proxy_error(error)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
