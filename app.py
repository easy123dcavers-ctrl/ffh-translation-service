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
TARGETS = {"es": "Spanish", "fr": "French", "ja": "Japanese"}
CONFIGURED_TARGET = os.environ.get("FFH_TARGET_LANGUAGE", "es").strip().lower()
MAX_BATCH_ITEMS = 25

if CONFIGURED_TARGET not in TARGETS:
    raise RuntimeError(f"Unsupported FFH_TARGET_LANGUAGE: {CONFIGURED_TARGET}")

def installed_pairs():
    return {(p.from_code, p.to_code) for p in argostranslate.package.get_installed_packages()}

def configured_pair():
    return (SOURCE, CONFIGURED_TARGET)

def configured_model_installed():
    return configured_pair() in installed_pairs()

def translate_text(q):
    return argostranslate.translate.translate(q, SOURCE, CONFIGURED_TARGET)

@app.get("/")
def root():
    installed = configured_model_installed()
    return jsonify({
        "service": SERVICE_NAME,
        "status": "ok" if installed else "degraded",
        "source": SOURCE,
        "configured_target": CONFIGURED_TARGET,
        "configured_target_name": TARGETS[CONFIGURED_TARGET],
        "available_targets": [CONFIGURED_TARGET] if installed else [],
        "missing_models": [] if installed else [f"{SOURCE}->{CONFIGURED_TARGET}"],
        "max_batch_items": MAX_BATCH_ITEMS,
    })

@app.get("/health")
def health():
    if not configured_model_installed():
        return jsonify({"status":"degraded","service":SERVICE_NAME,"configured_target":CONFIGURED_TARGET,
                        "missing_models":[f"{SOURCE}->{CONFIGURED_TARGET}"]}), 503
    return jsonify({"status":"ok","service":SERVICE_NAME,"configured_target":CONFIGURED_TARGET})

@app.get("/languages")
def languages():
    installed = configured_model_installed()
    targets = [CONFIGURED_TARGET] if installed else []
    return jsonify([{"code":SOURCE,"name":"English","targets":targets},
                    *([{"code":CONFIGURED_TARGET,"name":TARGETS[CONFIGURED_TARGET],"targets":[]}] if installed else [])])

def validate_target(source, target):
    if source != SOURCE:
        return jsonify({"error":"FFH currently supports source=en only"}), 400
    if target != CONFIGURED_TARGET:
        return jsonify({"error":"unsupported target language for this service instance",
                        "configured_target":CONFIGURED_TARGET}), 400
    if not configured_model_installed():
        return jsonify({"error":f"model not installed: {SOURCE}->{CONFIGURED_TARGET}"}), 503
    return None

@app.post("/translate")
def translate():
    payload = request.get_json(silent=True) or {}
    q = payload.get("q")
    source = payload.get("source", SOURCE)
    target = payload.get("target")
    if not isinstance(q, str) or not q.strip():
        return jsonify({"error":"q must be a non-empty string"}), 400
    bad = validate_target(source, target)
    if bad: return bad
    try:
        translated = translate_text(q)
    except Exception:
        app.logger.exception("Argos translation failed")
        return jsonify({"error":"translation failed"}), 500
    return jsonify({"translatedText":translated})

@app.post("/translate-batch")
def translate_batch():
    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    source = payload.get("source", SOURCE)
    target = payload.get("target")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_BATCH_ITEMS:
        return jsonify({"error":f"items must contain 1-{MAX_BATCH_ITEMS} entries"}), 400
    bad = validate_target(source, target)
    if bad: return bad
    results = []
    for i, item in enumerate(items):
        if isinstance(item, str):
            item_id, q = str(i), item
        elif isinstance(item, dict):
            item_id, q = str(item.get("id", i)), item.get("q")
        else:
            results.append({"id":str(i),"ok":False,"error":"invalid item"})
            continue
        if not isinstance(q, str) or not q.strip():
            results.append({"id":item_id,"ok":False,"error":"q must be a non-empty string"})
            continue
        try:
            results.append({"id":item_id,"ok":True,"translatedText":translate_text(q)})
        except Exception:
            app.logger.exception("Argos batch item failed")
            results.append({"id":item_id,"ok":False,"error":"translation failed"})
    return jsonify({"target":CONFIGURED_TARGET,"count":len(results),"results":results})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
