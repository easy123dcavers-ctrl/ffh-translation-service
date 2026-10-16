"""R116: Flask test-client behavioral gates with fake Argos; synthetic-only/no network."""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SINGLE = "/experimental/guarded-translate"
BATCH = "/experimental/guarded-translate-batch"


def load(enabled):
    root = types.ModuleType("argostranslate")
    root.__path__ = []
    pkg = types.ModuleType("argostranslate.package")
    tx = types.ModuleType("argostranslate.translate")
    pkg.get_installed_packages = lambda: [
        types.SimpleNamespace(from_code="en", to_code="es")]
    calls = []
    def translate(text, source, target):
        calls.append(text)
        if (source, target) != ("en", "es"):
            raise AssertionError("Incorrect fake model selection")
        if "RAISE_TEST_EXCEPTION" in text:
            raise ValueError("Private data should not appear in an HTTP response")
        if "BAD_NUMBER" in text:
            return text.replace("25", "26")
        if "BAD_UNIT" in text:
            return text.replace("mL", "L")
        return "ES:" + text
    tx.translate = translate
    root.package = pkg
    root.translate = tx
    env = {
        "FFH_TARGET_LANGUAGE": "es", "FFH_MULTILINGUAL": "false",
        "FFH_TRANSLATION_CACHE_ENABLED": "false",
        "FFH_GUARDED_API_STAGING_ONLY": "true" if enabled else "false"
    }
    stub = {"argostranslate":root, "argostranslate.package":pkg,
            "argostranslate.translate":tx}
    with mock.patch.dict(sys.modules,stub), mock.patch.dict(os.environ,env):
        sys.path.insert(0,str(ROOT))
        try:
            spec = importlib.util.spec_from_file_location(
                "ffh_r116_mock_"+str(enabled),ROOT/"app.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
    module.app.config["TESTING"] = True
    return module.app, calls


class GuardedFlaskContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.enabled_app, cls.calls = load(True)
        cls.disabled_app, cls.disabled_calls = load(False)

    def setUp(self):
        self.calls.clear()
        self.client = self.enabled_app.test_client()

    def payload(self, q, extra=None):
        return {"q":q,"source":"en","target":"es",**(extra or {})}

    def test_01_disabled_by_default(self):
        with self.disabled_app.test_client() as client:
            for route in (SINGLE, BATCH):
                response=client.post(route,json=self.payload("Example"))
                self.assertEqual(response.status_code,404)
        self.assertFalse(self.disabled_calls)

    def test_02_regular_endpoints_unmodified(self):
        response=self.client.post("/translate",json=self.payload("Sample 7"))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.get_json()["translatedText"],"ES:Sample 7")

    def test_03_provisional_never_approved(self):
        r=self.client.post(SINGLE,json=self.payload("The notebook is blue."))
        self.assertEqual(r.status_code,200)
        data=r.get_json()
        self.assertEqual(data["status"],"provisional_candidate")
        self.assertIn("ES:",data["draft"])
        self.assertIs(data["human_approved"],False)
        self.assertEqual(data["production_writes"],0)

    def test_04_exact_placeholder_not_passed_to_model(self):
        q="The note {{SAMPLE_ID}} belongs to the book."
        data=self.client.post(SINGLE,json=self.payload(q)).get_json()
        self.assertEqual(data["status"],"provisional_candidate")
        self.assertIn("{{SAMPLE_ID}}",data["draft"])
        self.assertTrue(all("{{SAMPLE_ID}}" not in sent for sent in self.calls))

    def test_05_duplicate_placeholder_order(self):
        q="A {{ONE}} and {{ONE}} then {{TWO}}"
        data=self.client.post(SINGLE,json=self.payload(q)).get_json()
        self.assertEqual(data["status"],"provisional_candidate")
        self.assertEqual(data["draft"].count("{{ONE}}"),2)
        self.assertIn("{{TWO}}",data["draft"])

    def test_06_number_change_held_without_draft(self):
        data=self.client.post(SINGLE,json=self.payload("BAD_NUMBER 25")).get_json()
        self.assertEqual(data["status"],"held")
        self.assertIn("numeric_integrity",data["reasons"])
        self.assertIsNone(data["draft"])

    def test_07_unit_change_held_without_draft(self):
        data=self.client.post(SINGLE,json=self.payload("BAD_UNIT 20 mL")).get_json()
        self.assertEqual(data["status"],"held")
        self.assertIn("unit_integrity",data["reasons"])
        self.assertIsNone(data["draft"])

    def test_08_error_does_not_leak_source_or_exception(self):
        data=self.client.post(SINGLE,json=self.payload("RAISE_TEST_EXCEPTION")).get_json()
        self.assertEqual(data["status"],"held")
        self.assertEqual(data["reasons"],["translator_exception"])
        self.assertIsNone(data["draft"])
        self.assertNotIn("Private data",str(data))
        self.assertNotIn("RAISE_TEST_EXCEPTION",str(data))

    def test_09_malformed_placeholder_fails_closed(self):
        data=self.client.post(SINGLE,json=self.payload("{{broken}}")).get_json()
        self.assertEqual(data["status"],"held")
        self.assertEqual(data["reasons"],["malformed_placeholder"])
        self.assertFalse(self.calls)

    def test_10_urls_and_emails_held_pre_model(self):
        cases=["Visit https://example.invalid/test", "www.example.invalid",
               "Email demo@example.invalid to learn."]
        for q in cases:
            with self.subTest(q=q):
                self.calls.clear()
                data=self.client.post(SINGLE,json=self.payload(q)).get_json()
                self.assertEqual(data["status"],"held")
                self.assertEqual(data["reasons"],["unprotected_url_or_email"])
                self.assertIsNone(data["draft"])
                self.assertFalse(self.calls)

    def test_11_bounded_source_length(self):
        data=self.client.post(SINGLE,json=self.payload("Z"*4097)).get_json()
        self.assertEqual(data["status"],"held")
        self.assertEqual(data["reasons"],["source_too_long"])
        self.assertFalse(self.calls)

    def test_12_wrong_targets_and_sources(self):
        for change in ({"source":"ja"},{"target":"fr"},{"target":None}):
            with self.subTest(change=change):
                r=self.client.post(SINGLE,json=self.payload("mock",change))
                self.assertEqual(r.status_code,400)

    def test_13_invalid_json_roots(self):
        for route in (SINGLE,BATCH):
            with self.subTest(route=route):
                for body in ([], "text", None, 3):
                    r=self.client.post(route,json=body)
                    self.assertEqual(r.status_code,400)

    def test_14_batch_is_per_item_and_provisional(self):
        items=[{"id":"a","q":"Here is {{TOKEN}}"},
               {"id":"b","q":"BAD_NUMBER 25"},
               {"id":"c","q":"demo@example.invalid"},
               {"id":"d","q":"plain text"}]
        r=self.client.post(BATCH,json={"items":items,"source":"en","target":"es"})
        self.assertEqual(r.status_code,200)
        data=r.get_json()
        self.assertEqual(data["count"],4)
        self.assertEqual([v["id"] for v in data["results"]],["a","b","c","d"])
        self.assertEqual([v["status"] for v in data["results"]],
                         ["provisional_candidate","held","held","provisional_candidate"])
        self.assertTrue(all(v["human_approved"] is False for v in data["results"]))
        self.assertIsNone(data["results"][1]["draft"])
        self.assertIsNone(data["results"][2]["draft"])
        self.assertIs(data["human_approved"],False)

    def test_15_batch_cannot_exceed_25(self):
        for entries in ([],["OK"]*26):
            r=self.client.post(BATCH,json={"items":entries,"source":"en","target":"es"})
            self.assertEqual(r.status_code,400)
        r=self.client.post(BATCH,json={
            "items":["OK"]*25,"source":"en","target":"es"})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.get_json()["count"],25)

    def test_16_batch_bad_items_held(self):
        r=self.client.post(BATCH,json={"items":[None,{"id":"x","q":""},[]],
                                       "source":"en","target":"es"})
        self.assertEqual(r.status_code,200)
        self.assertTrue(all(v["status"]=="held" for v in r.get_json()["results"]))

    def test_17_no_cross_request_cache_for_guarded_paths(self):
        for _ in range(2):
            r=self.client.post(SINGLE,json=self.payload("Repeat this note."))
            self.assertEqual(r.get_json()["status"],"provisional_candidate")
        self.assertEqual(self.calls,["Repeat this note."]*2)

    def test_18_invalid_target_on_batch(self):
        r=self.client.post(BATCH,json={"items":["test"],"source":"en","target":"de"})
        self.assertEqual(r.status_code,400)


if __name__=="__main__":
    unittest.main()
