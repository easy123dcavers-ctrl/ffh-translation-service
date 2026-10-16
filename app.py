import os
import hmac
import fcntl
import stat
from pathlib import Path
from threading import BoundedSemaphore

APP_ROOT = Path(__file__).resolve().parent
MODEL_DIR = APP_ROOT / ".argos" / "packages"

os.environ["ARGOS_PACKAGES_DIR"] = str(MODEL_DIR)
os.environ.setdefault("ARGOS_DEVICE_TYPE", "cpu")

from flask import Flask, jsonify, request
import argostranslate.package
import argostranslate.translate
from translation_cache import TranslationCache
from protected_translation import guarded_candidate, hold
import re

app = Flask(__name__)

SERVICE_NAME = "ffh-translation-service"
SOURCE = "en"
TARGETS = {"es": "Spanish", "fr": "French", "ja": "Japanese", "de": "German", "ar": "Arabic", "tl": "Filipino", "ko": "Korean", "vi": "Vietnamese", "zh": "Simplified Chinese"}
CONFIGURED_TARGET = os.environ.get("FFH_TARGET_LANGUAGE", "es").strip().lower()
MULTILINGUAL = os.environ.get("FFH_MULTILINGUAL", "false").lower() == "true"
MAX_BATCH_ITEMS = 25

# R102 experimental optimization: DISABLED by default.
# Process-local cache holds at most 128 short inputs for 10 minutes.
# Restart/redeploy the service when the installed model changes; a restart clears it.
CACHE_ENABLED = os.environ.get("FFH_TRANSLATION_CACHE_ENABLED", "false").lower() == "true"
CACHE_MODEL_GENERATION = os.environ.get("FFH_TRANSLATION_CACHE_GENERATION", "process-start")
CACHE = TranslationCache(max_entries=128, ttl_seconds=600)

# R116 STAGING EXPERIMENT: OFF by default. Not a public/member API release.
# Existing /translate and /translate-batch semantics are unchanged.
GUARDED_API_ENABLED = os.environ.get(
    "FFH_GUARDED_API_STAGING_ONLY", "false"
).lower() == "true"
# R118: process-local admission; only valid with one Gunicorn worker.
GUARDED_CAPACITY = BoundedSemaphore(value=1)
MAX_GUARDED_BODY_BYTES = 128 * 1024
# A staging credential must be supplied through runtime secret configuration.
GUARDED_STAGE_TOKEN = os.environ.get("FFH_GUARDED_STAGING_TOKEN", "")
# R121: STAGING-ONLY opt-in quarantine after clients are migrated.
# Defaults off. Does not secure or change existing production routes.
LEGACY_QUARANTINE_STAGING_ONLY = os.environ.get(
    "FFH_LEGACY_QUARANTINE_STAGING_ONLY", "false"
).lower() == "true"
MIN_STAGE_TOKEN_LENGTH = 32
GUARDED_LINK = re.compile(
    r"(?i)(?:https?://|www\.)|[\w.+-]+@[\w.-]+\.[a-z]{2,}"
)

if CONFIGURED_TARGET not in TARGETS:
    raise RuntimeError(f"Unsupported FFH_TARGET_LANGUAGE: {CONFIGURED_TARGET}")

def installed_pairs():
    return {(p.from_code, p.to_code) for p in argostranslate.package.get_installed_packages()}

def configured_pair():
    return (SOURCE, CONFIGURED_TARGET)

def supported_targets():
    return sorted({p.to_code for p in argostranslate.package.get_installed_packages() if p.from_code == SOURCE})

def configured_model_installed():
    return bool(supported_targets()) if MULTILINGUAL else configured_pair() in installed_pairs()

def translate_text(q, target=None):
    effective_target = target or CONFIGURED_TARGET
    if not CACHE_ENABLED:
        return argostranslate.translate.translate(q, SOURCE, effective_target)
    return CACHE.run(
        q, SOURCE, effective_target, CACHE_MODEL_GENERATION,
        lambda: argostranslate.translate.translate(q, SOURCE, effective_target),
    )

@app.get("/")
def root():
    installed = configured_model_installed()
    return jsonify({
        "service": SERVICE_NAME,
        "status": "ok" if installed else "degraded",
        "source": SOURCE,
        "configured_target": CONFIGURED_TARGET,
        "configured_target_name": TARGETS[CONFIGURED_TARGET],
        "available_targets": supported_targets() if MULTILINGUAL else ([CONFIGURED_TARGET] if installed else []),
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
    targets = supported_targets() if MULTILINGUAL else ([CONFIGURED_TARGET] if installed else [])
    return jsonify([{"code":SOURCE,"name":"English","targets":targets},
                    *([{"code":t,"name":TARGETS.get(t,t),"targets":[]} for t in targets])])

def validated_json_body():
    """Require a JSON object; reject arrays, strings, numbers and missing bodies."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else None

def validate_target(source, target):
    if source != SOURCE:
        return jsonify({"error":"FFH currently supports source=en only"}), 400
    if target not in (supported_targets() if MULTILINGUAL else ([CONFIGURED_TARGET] if configured_model_installed() else [])):
        return jsonify({"error":"unsupported target language for this service instance",
                        "configured_target":CONFIGURED_TARGET, "available_targets":supported_targets()}), 400
    if not configured_model_installed():
        return jsonify({"error":f"model not installed: {SOURCE}->{CONFIGURED_TARGET}"}), 503
    return None

@app.before_request
def quarantine_legacy_stage_paths():
    """During isolated migration testing, prevent bypass of guarded API.
    
    Fail closed on BOTH legacy routes, without touching health/languages.
    This is NOT user/member auth or a public-production migration.
    """
    if (GUARDED_API_ENABLED and LEGACY_QUARANTINE_STAGING_ONLY
            and request.path in ("/translate", "/translate-batch")):
        return jsonify({"error": "legacy translation route disabled in staging"}), 410
    return None


@app.post("/translate")
def translate():
    payload = validated_json_body()
    if payload is None:
        return jsonify({"error":"request body must be a JSON object"}), 400
    q = payload.get("q")
    source = payload.get("source", SOURCE)
    target = payload.get("target")
    if not isinstance(q, str) or not q.strip():
        return jsonify({"error":"q must be a non-empty string"}), 400
    bad = validate_target(source, target)
    if bad: return bad
    try:
        translated = translate_text(q, target)
    except Exception:
        app.logger.exception("Argos translation failed")
        return jsonify({"error":"translation failed"}), 500
    return jsonify({"translatedText":translated})

@app.post("/translate-batch")
def translate_batch():
    payload = validated_json_body()
    if payload is None:
        return jsonify({"error":"request body must be a JSON object"}), 400
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
            results.append({"id":item_id,"ok":True,"translatedText":translate_text(q, target)})
        except Exception:
            app.logger.exception("Argos batch item failed")
            results.append({"id":item_id,"ok":False,"error":"translation failed"})
    return jsonify({"target":target,"count":len(results),"results":results})


# Experimental isolated-stage-only endpoints. Do not enable on Render production.
# They do not call translate_text() or the optional shared translation cache:
# private/member text MUST NOT be placed into a cross-request cache.
@app.after_request
def suppress_guarded_http_caches(response):
    """Guarded responses may contain private text: never cache them."""
    if request.path.startswith("/experimental/guarded-"):
        response.headers["Cache-Control"] = "no-store, private, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def guarded_auth_error():
    # Both disabled and insecurely configured routes are unavailable.
    if not GUARDED_API_ENABLED or len(GUARDED_STAGE_TOKEN) < MIN_STAGE_TOKEN_LENGTH:
        return jsonify({"error": "not found"}), 404
    candidate = request.headers.get("Authorization", "")
    expected = "Bearer " + GUARDED_STAGE_TOKEN
    if not hmac.compare_digest(candidate, expected):
        return jsonify({"error": "unauthorized"}), 401
    return None


def guarded_input_size_error():
    """Do not read potentially unbounded request bodies."""
    if request.content_length is None:
        return jsonify({"error": "request body must be a JSON object"}), 400
    if request.content_length > MAX_GUARDED_BODY_BYTES:
        return jsonify({"error": "request body too large"}), 413
    return None


# R120: single-host, single-container Linux lock shared by Gunicorn workers
# during max-requests worker turnover. NOT a multi-replica/distributed lock.
GUARDED_LOCK_FILE = "/tmp/ffh-guarded-single-instance.lock"

def guarded_busy():
    return jsonify({"error": "translation service busy",
                    "retryable": True, "retry_after_seconds": 2}), 429, {
                        "Retry-After": "2"
                    }


def guarded_admit(fn):
    """Fail fast across threads AND recycling Gunicorn workers in one container."""
    if not GUARDED_CAPACITY.acquire(blocking=False):
        return guarded_busy()
    fd = None
    file_locked = False
    try:
        fd = os.open(GUARDED_LOCK_FILE,
                     os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        details = os.fstat(fd)
        if not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid():
            return jsonify({"error": "translation service unavailable"}), 503
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            file_locked = True
        except BlockingIOError:
            return guarded_busy()
        return fn()
    except OSError:
        # No model request is allowed when the cross-worker lock malfunctions.
        return jsonify({"error": "translation service unavailable"}), 503
    finally:
        if fd is not None:
            if file_locked:
                fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        GUARDED_CAPACITY.release()


def guarded_draft(q, target):
    if isinstance(q, str) and GUARDED_LINK.search(q):
        return hold("unprotected_url_or_email")
    return guarded_candidate(
        q, lambda segment: argostranslate.translate.translate(
            segment, SOURCE, target)
    )


@app.post("/experimental/guarded-translate")
def experimental_guarded_translate():
    auth_error = guarded_auth_error()
    if auth_error is not None:
        return auth_error
    size_error = guarded_input_size_error()
    if size_error is not None:
        return size_error
    body = validated_json_body()
    if body is None:
        return jsonify({"error": "request body must be a JSON object"}), 400
    bad = validate_target(body.get("source", SOURCE), body.get("target"))
    if bad:
        return bad
    return guarded_admit(lambda: jsonify(guarded_draft(
        body.get("q"), body["target"])))


@app.post("/experimental/guarded-translate-batch")
def experimental_guarded_translate_batch():
    auth_error = guarded_auth_error()
    if auth_error is not None:
        return auth_error
    size_error = guarded_input_size_error()
    if size_error is not None:
        return size_error
    body = validated_json_body()
    if body is None:
        return jsonify({"error": "request body must be a JSON object"}), 400
    items = body.get("items")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_BATCH_ITEMS:
        return jsonify({"error": f"items must contain 1-{MAX_BATCH_ITEMS} entries"}), 400
    bad = validate_target(body.get("source", SOURCE), body.get("target"))
    if bad:
        return bad
    def compute_batch():
        response = []
        for i, item in enumerate(items):
            if isinstance(item, str):
                identifier, q = str(i), item
            elif isinstance(item, dict):
                identifier, q = str(item.get("id", i)), item.get("q")
            else:
                identifier, q = str(i), None
            candidate = guarded_draft(q, body["target"])
            response.append({"id": identifier, **candidate})
        return jsonify({"target": body["target"], "count": len(response),
                        "results": response, "human_approved": False})
    return guarded_admit(compute_batch)



if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
