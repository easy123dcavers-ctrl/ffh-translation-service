import os
from flask import Flask, jsonify, request
import argostranslate.translate

app = Flask(__name__)
SERVICE_NAME = "ffh-translation-service"
SOURCE = "en"
TARGETS = {"es": "Spanish", "fr": "French", "ja": "Japanese"}

@app.get("/")
def root():
    return jsonify({"service": SERVICE_NAME, "status": "ok", "source": SOURCE, "targets": sorted(TARGETS)})

@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": SERVICE_NAME})

@app.get("/languages")
def languages():
    return jsonify([
        {"code": "en", "name": "English", "targets": sorted(TARGETS)},
        *[{"code": code, "name": name, "targets": []} for code, name in TARGETS.items()],
    ])

@app.post("/translate")
def translate():
    payload = request.get_json(silent=True) or {}
    q = payload.get("q")
    source = payload.get("source", SOURCE)
    target = payload.get("target")
    if not isinstance(q, str) or not q.strip():
        return jsonify({"error": "q must be a non-empty string"}), 400
    if source != SOURCE:
        return jsonify({"error": "FFH currently supports source=en only"}), 400
    if target not in TARGETS:
        return jsonify({"error": "unsupported target language", "supported_targets": sorted(TARGETS)}), 400
    try:
        translated = argostranslate.translate.translate(q, source, target)
    except Exception:
        app.logger.exception("Argos translation failed")
        return jsonify({"error": "translation failed"}), 500
    return jsonify({"translatedText": translated})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
