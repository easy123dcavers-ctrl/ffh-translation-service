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
CONFIGURED_TARGET = os.environ.get("FFH_TARGET_LANGUAGE", "es").strip().lower()

if CONFIGURED_TARGET not in TARGETS:
    raise RuntimeError(
        f"Unsupported FFH_TARGET_LANGUAGE: {CONFIGURED_TARGET}"
    )


def installed_pairs():
    return {
        (p.from_code, p.to_code)
        for p in argostranslate.package.get_installed_packages()
    }


def configured_pair():
    return (SOURCE, CONFIGURED_TARGET)


def configured_model_installed():
    return configured_pair() in installed_pairs()


@app.get("/")
def root():
    installed = configured_model_installed()

    return jsonify({
        "service": SERVICE_NAME,
        "status": "ok" if installed else "degraded",
        "source": SOURCE,
        "configured_target": CONFIGURED_TARGET,
        "configured_target_name": TARGETS[CONFIGURED_TARGET],
        "available_targets": [
            CONFIGURED_TARGET
        ] if installed else [],
        "missing_models": [] if installed else [
            f"{SOURCE}->{CONFIGURED_TARGET}"
        ],
    })


@app.get("/health")
def health():
    if not configured_model_installed():
        return jsonify({
            "status": "degraded",
            "service": SERVICE_NAME,
            "configured_target": CONFIGURED_TARGET,
            "missing_models": [
                f"{SOURCE}->{CONFIGURED_TARGET}"
            ],
        }), 503

    return jsonify({
        "status": "ok",
        "service": SERVICE_NAME,
        "configured_target": CONFIGURED_TARGET,
    })


@app.get("/languages")
def languages():
    installed = configured_model_installed()
    targets = [CONFIGURED_TARGET] if installed else []

    return jsonify([
        {
            "code": SOURCE,
            "name": "English",
            "targets": targets,
        },
        *([
            {
                "code": CONFIGURED_TARGET,
                "name": TARGETS[CONFIGURED_TARGET],
                "targets": [],
            }
        ] if installed else []),
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

    if target != CONFIGURED_TARGET:
        return jsonify({
            "error": "unsupported target language for this service instance",
            "configured_target": CONFIGURED_TARGET,
        }), 400

    if not configured_model_installed():
        return jsonify({
            "error": f"model not installed: {SOURCE}->{CONFIGURED_TARGET}"
        }), 503

    try:
        translated = argostranslate.translate.translate(
            q,
            SOURCE,
            CONFIGURED_TARGET,
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
