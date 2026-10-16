"""R121 legacy-endpoint staging quarantine checks (invented text, fake Argos).

The quarantine is a test-only migration safeguard. It is OFF by default and
does NOT replace production authentication, sessions, identity or quotas.
"""
import os
import unittest
from unittest import mock

from test_r116_guarded_api import load, SINGLE, BATCH


class R121LegacyQuarantine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with mock.patch.dict(os.environ, {
                "FFH_LEGACY_QUARANTINE_STAGING_ONLY": "true"}):
            cls.stage, cls.stage_calls = load(True)
            cls.unprotected_when_guard_off, cls.unprotected_calls = load(False)
        with mock.patch.dict(os.environ, {
                "FFH_LEGACY_QUARANTINE_STAGING_ONLY": "false"}):
            cls.compat, cls.compat_calls = load(True)
        cls.stage.testing = True

    def setUp(self):
        self.stage_calls.clear()
        self.compat_calls.clear()
        self.client = self.stage.test_client()
        self.sample = {"source":"en","target":"es","q":"The imaginary blue book."}
        self.batched = {"source":"en","target":"es","items":[self.sample["q"]]}

    def test_01_legacy_translate_returns_410(self):
        r = self.client.post("/translate", json=self.sample)
        self.assertEqual(r.status_code, 410)
        self.assertEqual(r.get_json(), {
            "error":"legacy translation route disabled in staging"})
        self.assertFalse(self.stage_calls)

    def test_02_legacy_batch_returns_410_before_parsing(self):
        r = self.client.post("/translate-batch", data="not json",
                             content_type="text/plain")
        self.assertEqual(r.status_code, 410)
        self.assertFalse(self.stage_calls)

    def test_03_guarded_single_remains_available_with_staging_token(self):
        r = self.client.post(SINGLE, json=self.sample)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["status"],"provisional_candidate")
        self.assertIs(r.get_json()["human_approved"],False)

    def test_04_guarded_batch_remains_available(self):
        r = self.client.post(BATCH, json=self.batched)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["count"],1)
        self.assertIs(r.get_json()["human_approved"],False)

    def test_05_unguarded_request_must_not_bypass_quarantine(self):
        # The mock-client automatically injects staging headers on guarded routes only.
        r = self.client.post("/translate", json=self.sample,
                             headers={"Authorization":""})
        self.assertEqual(r.status_code,410)
        self.assertFalse(self.stage_calls)

    def test_06_health_still_responds(self):
        self.assertEqual(self.client.get("/health").status_code,200)

    def test_07_language_listing_still_responds(self):
        self.assertEqual(self.client.get("/languages").status_code,200)

    def test_08_flag_defaults_off_preserves_existing_contract(self):
        with self.compat.test_client() as client:
            r=client.post("/translate",json=self.sample)
            self.assertEqual(r.status_code,200)
        self.assertEqual(self.compat_calls,[self.sample["q"]])

    def test_09_guarded_feature_flag_off_does_not_hide_existing_routes(self):
        with self.unprotected_when_guard_off.test_client() as client:
            r=client.post("/translate",json=self.sample)
            self.assertEqual(r.status_code,200)

    def test_10_legacy_quarantine_excludes_unknown_paths(self):
        r=self.client.get("/not-a-route")
        self.assertEqual(r.status_code,404)

    def test_11_guarded_bad_token_returns_401_even_when_legacy_disabled(self):
        r=self.client.post(SINGLE,json=self.sample,
                           headers={"Authorization":"Bearer wrong"})
        self.assertEqual(r.status_code,401)
        self.assertFalse(self.stage_calls)

    def test_12_url_and_malformed_placeholders_still_held(self):
        for text in ("https://example.invalid/data", "{{not_upper}}"):
            with self.subTest(text=text):
                r=self.client.post(SINGLE,json={**self.sample,"q":text})
                self.assertEqual(r.status_code,200)
                self.assertEqual(r.get_json()["status"],"held")
                self.assertIsNone(r.get_json()["draft"])


if __name__=="__main__":
    unittest.main()
