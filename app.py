import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
MODEL_DIR = APP_ROOT / ".argos" / "packages"

os.environ["ARGOS_PACKAGES_DIR"] = str(MODEL_DIR)
os.environ.setdefault("ARGOS_DEVICE_TYPE", "cpu")

from flask import Flask, jsonify, request
import argostranslate.package
import argostranslate.translate

app = Flask(__name__)

SERVICE_NAME = "ffh-translation-service"
SOURCE = "en"
TARGETS = {
    "es": "Spanish",
    "fr": "French",
    "ja": "Japanese",
}
REQUIRED = {("en", code) for code in TARGETS}


def installed_pairs():
    return {
        (p.from_code, p.to_code)
        for p in argostranslate.package.get_installed_packages()
    }


def missing_pairs():
    return sorted(REQUIRED - installed_pairs())


@app.get("/")
def root():
    missing = missing_pairs()

    return jsonify({
        "service": SERVICE_NAME,
        "status": "ok" if not missing else "degraded",
        "source": SOURCE,
        "targets": sorted(TARGETS),
        "missing_models": [
            f"{source}->{target}"
            for source, target in missing
        ],
    })


@app.get("/health")
def health():
    missing = missing_pairs()

    if missing:
        return jsonify({
            "status": "degraded",
            "service": SERVICE_NAME,
            "missing_models": [
                f"{source}->{target}"
                for source, target in missing
            ],
        }), 503

    return jsonify({
        "status": "ok",
        "service": SERVICE_NAME,
    })


@app.get("/languages")
def languages():
    pairs = installed_pairs()

    targets = sorted(
        code
        for code in TARGETS
        if (SOURCE, code) in pairs
    )

    return jsonify([
        {
            "code": SOURCE,
            "name": "English",
            "targets": targets,
        },
        *[
            {
                "code": code,
                "name": name,
                "targets": [],
            }
            for code, name in TARGETS.items()
            if (SOURCE, code) in pairs
        ],
    ])


@app.post("/translate")
def translate():
    payload = request.get_json(silent=True) or {}

    q = payload.get("q")
    source = payload.get("source", SOURCE)
    target = payload.get("target")

    if not isinstance(q, str) or not q.strip():
        return jsonify({
            "error": "q must be a non-empty string"
        }), 400

    if source != SOURCE:
        return jsonify({
            "error": "FFH currently supports source=en only"
        }), 400

    if target not in TARGETS:
        return jsonify({
            "error": "unsupported target language",
            "supported_targets": sorted(TARGETS),
        }), 400

    if (source, target) not in installed_pairs():
        return jsonify({
            "error": f"model not installed: {source}->{target}"
        }), 503

    try:
        translated = argostranslate.translate.translate(
            q,
            source,
            target,
        )
    except Exception:
        app.logger.exception("Argos translation failed")
        return jsonify({
            "error": "translation failed"
        }), 500

    return jsonify({
        "translatedText": translated
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(
        host="0.0.0.0",
        port=port,
    )
