"""R109 one-process real Argos + Flask smoke, synthetic-only, no writes.

This is NOT a 512MiB cgroup test, not a Gunicorn stress test, and not a quality gate.
Run only after pinned source-build dependencies and one EN->ES model are installed.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import json
from pathlib import Path
import resource
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUTPUT = Path("r109-output")


def mem_mib():
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # Import the deployed module under the same non-production environment.
    import app as webapp
    import argostranslate.sbd
    assert argostranslate.sbd.stanza is None, (
        "Lightweight build unexpectedly loaded Stanza"
    )
    assert "torch" not in sys.modules, "Torch was loaded by the translation engine"
    assert importlib.util.find_spec("stanza") is None, (
        "Heavy Stanza dependency is installed unexpectedly"
    )

    assert webapp.CACHE_ENABLED is False
    assert webapp.MAX_BATCH_ITEMS == 25
    flask = webapp.app
    flask.config["TESTING"] = True
    started = time.perf_counter()
    with flask.test_client() as c:
        info = c.get("/")
        health = c.get("/health")
        languages = c.get("/languages")
        assert info.status_code == 200
        assert health.status_code == 200
        assert languages.status_code == 200
        assert health.get_json()["status"] == "ok"
        assert "es" in info.get_json()["available_targets"]

        one = c.post("/translate", json={
            "q":"The mock notebook has 7 pages.",
            "source":"en","target":"es"
        })
        assert one.status_code == 200
        assert isinstance(one.get_json()["translatedText"], str)
        assert one.get_json()["translatedText"].strip()

        inputs = [{"id":str(i), "q":f"Record {i} is on the shelf."}
                  for i in range(1,26)]
        batch = c.post("/translate-batch",json={
            "items":inputs,"source":"en","target":"es"
        })
        assert batch.status_code == 200
        data=batch.get_json()
        assert data["count"] == 25
        assert len(data["results"]) == 25
        assert all(item["ok"] and item["translatedText"].strip()
                   for item in data["results"])
        assert [item["id"] for item in data["results"]] == [str(i) for i in range(1,26)]
        oversized = c.post("/translate-batch", json={
            "items":["x"]*26,"source":"en","target":"es"
        })
        assert oversized.status_code == 400

        bad_body = c.post("/translate", json=["not a dict"])
        assert bad_body.status_code == 400
        report = {
            "test":"R109-pinned-source-lightweight-real-Argos-Flask-client",
            "argostranslate_distribution_version":
                importlib.metadata.version("argostranslate"),
            "translated_one_and_25_batch_entries": True,
            "invalid_input_returns_400": True,
            "health_ok": True,
            "cache_enabled": webapp.CACHE_ENABLED,
            "stanza_installed": bool(importlib.util.find_spec("stanza")),
            "torch_loaded": "torch" in sys.modules,
            "peak_test_process_mib": mem_mib(),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "full_gunicorn_test_completed": False,
            "enforced_512_mib_memory_limit": False,
            "quality_human_reviewed": False,
            "sample_count": 26,
            "production_writes": 0,
            "netlify_deploys": 0,
            "only_synthetic_data": True,
        }
    (OUTPUT / "real-Argos-Flask-summary.json").write_text(
        json.dumps(report, sort_keys=True, indent=2)+"\n", encoding="utf-8"
    )
    print("R109_SMOKE",json.dumps(report,sort_keys=True),flush=True)
    if report["peak_test_process_mib"] >= 512:
        raise RuntimeError("Process memory exceeds Render 512 MiB limit; STOP")
    if not report["argostranslate_distribution_version"].startswith("1.11.0+ffhlite"):
        raise RuntimeError("Unexpected translator distribution; STOP")

if __name__=="__main__":
    main()
