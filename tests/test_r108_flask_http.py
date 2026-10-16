"""R108: Real Flask request/response tests with a fake Argos engine.

Installs only Flask in CI. No translation model, no external network calls,
no FFH data, no deployment and no writes to production.
"""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]


def load_flask_app_with_mock_argos():
    # The production app module imports Argos at startup. The test supplies
    # in-process stub modules before that import without editing app.py.
    root = types.ModuleType("argostranslate")
    root.__path__ = []
    pkg = types.ModuleType("argostranslate.package")
    tx = types.ModuleType("argostranslate.translate")
    pkg.get_installed_packages = lambda: [
        types.SimpleNamespace(from_code="en", to_code="es")
    ]

    def mock_translate(text, source, target):
        if text == "RAISE_TEST_EXCEPTION":
            raise RuntimeError("synthetic engine exception")
        if (source, target) != ("en", "es"):
            raise AssertionError("invalid language passed to test translator")
        return "MOCK_ES:" + text

    tx.translate = mock_translate
    root.package = pkg
    root.translate = tx
    stub_modules = {
        "argostranslate": root,
        "argostranslate.package": pkg,
        "argostranslate.translate": tx,
    }
    # Do not overwrite loaded site package modules outside this isolated scope.
    with mock.patch.dict(sys.modules, stub_modules), mock.patch.dict(os.environ, {
        "FFH_TARGET_LANGUAGE": "es",
        "FFH_MULTILINGUAL": "false",
        "FFH_TRANSLATION_CACHE_ENABLED": "false",
    }):
        sys.path.insert(0, str(ROOT))
        try:
            spec = importlib.util.spec_from_file_location(
                "ffh_r108_mocked_app", ROOT / "app.py"
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
    return module.app


class FlaskHTTPContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = load_flask_app_with_mock_argos()
        cls.app.config["TESTING"] = True

    def setUp(self):
        self.client = self.app.test_client()

    def test_get_health_200(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_root_reports_25_batch_limit(self):
        data = self.client.get("/").get_json()
        self.assertEqual(data["max_batch_items"], 25)
        self.assertEqual(data["configured_target"], "es")

    def test_languages_are_single_configured_model(self):
        data = self.client.get("/languages").get_json()
        self.assertEqual(data[0]["targets"], ["es"])

    def test_single_translation_result(self):
        response = self.client.post("/translate", json={
            "q": "sample 7", "source": "en", "target": "es"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {
            "translatedText": "MOCK_ES:sample 7"
        })

    def test_batch_translation_and_ids(self):
        response = self.client.post("/translate-batch", json={
            "items": ["sample 1", {"id": "card-x", "q": "sample 2"}],
            "source": "en", "target": "es"
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["count"], 2)
        self.assertEqual([r["id"] for r in data["results"]], ["0", "card-x"])
        self.assertEqual([r["ok"] for r in data["results"]], [True, True])

    def test_bad_json_roots_fail_with_400(self):
        for body in ([], ["sample"], 5, False, True, None, "sample"):
            for route in ("/translate", "/translate-batch"):
                with self.subTest(route=route, body=body):
                    response = self.client.post(route, json=body)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.get_json()["error"],
                                     "request body must be a JSON object")

    def test_invalid_content_type_or_malformed_json_returns_400(self):
        for route in ("/translate", "/translate-batch"):
            with self.subTest(route=route):
                bad_type = self.client.post(route, data="sample 2",
                                            content_type="text/plain")
                self.assertEqual(bad_type.status_code, 400)
                malformed = self.client.post(route, data="{not-json",
                                             content_type="application/json")
                self.assertEqual(malformed.status_code, 400)

    def test_missing_target_is_400_per_current_api_contract(self):
        for route, payload in (
            ("/translate", {"q": "sample 1", "source": "en"}),
            ("/translate-batch", {"items": ["sample 1"], "source": "en"}),
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.post(
                    route, json=payload).status_code, 400)

    def test_invalid_source_or_target_is_400(self):
        for fields in ({"source": "fr", "target": "es"},
                       {"source": "en", "target": "ja"}):
            self.assertEqual(self.client.post("/translate", json={
                "q": "sample 2", **fields
            }).status_code, 400)

    def test_empty_single_input_is_400(self):
        for text in ("", "   ", 7, None):
            self.assertEqual(self.client.post("/translate", json={
                "q": text, "source": "en", "target": "es"
            }).status_code, 400)

    def test_batch_25_allowed_and_26_rejected(self):
        payload = {"source": "en", "target": "es", "items": ["sample"] * 25}
        success = self.client.post("/translate-batch", json=payload)
        self.assertEqual(success.status_code, 200)
        self.assertEqual(success.get_json()["count"], 25)
        payload["items"].append("sample")
        error = self.client.post("/translate-batch", json=payload)
        self.assertEqual(error.status_code, 400)

    def test_batch_invalid_items_are_isolated(self):
        response = self.client.post("/translate-batch", json={
            "items": ["ok", [], {"id": "bad", "q": ""}],
            "source": "en", "target": "es"
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual([v["ok"] for v in data["results"]],
                         [True, False, False])
        self.assertEqual(data["results"][2]["id"], "bad")

    def test_single_engine_failure_is_sanitized(self):
        with mock.patch.object(self.app.logger, "exception"):
            response = self.client.post("/translate", json={
                "q": "RAISE_TEST_EXCEPTION", "source": "en", "target": "es"
            })
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "translation failed"})

    def test_batch_engine_failure_preserves_other_items(self):
        with mock.patch.object(self.app.logger, "exception"):
            response = self.client.post("/translate-batch", json={
                "items": ["before", "RAISE_TEST_EXCEPTION", "after"],
                "source": "en", "target": "es"
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual([v["ok"] for v in response.get_json()["results"]],
                         [True, False, True])


if __name__ == "__main__":
    unittest.main()
