"""R119 offline authenticated guarded-endpoint and privacy-contract tests.

A fake Argos package handles invented texts. This test does not connect to
FFH production, Supabase, Netlify, or any user-owned content.
"""
import unittest
from unittest import mock
from test_r116_guarded_api import load, SINGLE, BATCH, TEST_STAGE_TOKEN

class R119AuthenticatedGuardedAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.model_calls = load(True)
        cls.app.testing = True
        cls.globals = cls.app.view_functions[
            "experimental_guarded_translate"].__globals__
    
    def setUp(self):
        self.model_calls.clear()
        self.client = self.app.test_client()
        self.payload = {"source":"en","target":"es","q":"An invented blue notebook."}
        self.batch = {"source":"en","target":"es","items":["An invented blue notebook."]}

    def assertNoCache(self, response):
        self.assertIn("no-store", response.headers.get("Cache-Control",""))
        self.assertEqual(response.headers.get("Pragma"),"no-cache")
        self.assertEqual(response.headers.get("X-Content-Type-Options"),"nosniff")

    def test_01_missing_bearer_is_401_and_no_model_call(self):
        for route, body in ((SINGLE,self.payload),(BATCH,self.batch)):
            r=self.client.post(route,json=body,headers={"Authorization":""})
            self.assertEqual(r.status_code,401)
            self.assertEqual(r.get_json(),{"error":"unauthorized"})
            self.assertNoCache(r)
        self.assertEqual(self.model_calls,[])

    def test_02_incorrect_token_is_401(self):
        for text in ["Bearer incorrect", "Basic "+TEST_STAGE_TOKEN,
                     "bearer "+TEST_STAGE_TOKEN, "Bearer "+TEST_STAGE_TOKEN+"x"]:
            r=self.client.post(SINGLE,json=self.payload,
                               headers={"Authorization":text})
            self.assertEqual(r.status_code,401)
            self.assertNoCache(r)
        self.assertFalse(self.model_calls)

    def test_03_correct_bearer_produces_only_provisional_draft(self):
        r=self.client.post(SINGLE,json=self.payload)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.get_json()["status"],"provisional_candidate")
        self.assertIs(r.get_json()["human_approved"],False)
        self.assertNoCache(r)

    def test_04_short_secret_configuration_fails_closed(self):
        with mock.patch.dict(self.globals, {"GUARDED_STAGE_TOKEN":"short"}):
            r=self.client.post(SINGLE,json=self.payload)
            self.assertEqual(r.status_code,404)
            self.assertEqual(r.get_json(),{"error":"not found"})
            self.assertNoCache(r)

    def test_05_empty_secret_configuration_fails_closed(self):
        with mock.patch.dict(self.globals, {"GUARDED_STAGE_TOKEN":""}):
            r=self.client.post(BATCH,json=self.batch)
            self.assertEqual(r.status_code,404)
            self.assertNoCache(r)

    def test_06_disabled_flag_fails_closed_even_with_correct_token(self):
        with mock.patch.dict(self.globals, {"GUARDED_API_ENABLED":False}):
            r=self.client.post(SINGLE,json=self.payload)
            self.assertEqual(r.status_code,404)
            self.assertNoCache(r)

    def test_07_auth_checked_before_parsing_request_body(self):
        r=self.client.post(SINGLE,data="{not-json",content_type="application/json",
                           headers={"Authorization":""})
        self.assertEqual(r.status_code,401)
        self.assertNoCache(r)

    def test_08_authorized_invalid_json_still_400(self):
        r=self.client.post(BATCH,json=[])
        self.assertEqual(r.status_code,400)
        self.assertNoCache(r)

    def test_09_authorized_body_limit_still_413(self):
        r=self.client.post(SINGLE,json={**self.payload,"q":"S"*(129*1024)})
        self.assertEqual(r.status_code,413)
        self.assertNoCache(r)

    def test_10_held_candidate_never_returns_draft(self):
        r=self.client.post(SINGLE,json={**self.payload,"q":"{{invalid}}"})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.get_json()["status"],"held")
        self.assertIsNone(r.get_json()["draft"])
        self.assertNoCache(r)

    def test_11_busy_is_429_and_cannot_be_cached(self):
        sem=self.globals["GUARDED_CAPACITY"]
        self.assertTrue(sem.acquire(blocking=False))
        try:
            r=self.client.post(SINGLE,json=self.payload)
            self.assertEqual(r.status_code,429)
            self.assertEqual(r.headers.get("Retry-After"),"2")
            self.assertNoCache(r)
        finally:
            sem.release()

    def test_12_secret_never_reflected_in_error_or_health(self):
        for route in (SINGLE,BATCH):
            body=self.payload if route==SINGLE else self.batch
            r=self.client.post(route,json=body,headers={"Authorization":"Bearer bad"})
            self.assertNotIn(TEST_STAGE_TOKEN,r.get_data(as_text=True))
        health=self.client.get("/health")
        self.assertEqual(health.status_code,200)
        self.assertNotIn(TEST_STAGE_TOKEN,health.get_data(as_text=True))

    def test_13_authentication_uses_constant_time_comparison(self):
        expected=self.globals["hmac"].compare_digest
        with mock.patch.object(self.globals["hmac"],"compare_digest",wraps=expected) as spy:
            self.assertEqual(self.client.post(SINGLE,json=self.payload).status_code,200)
            self.assertGreaterEqual(spy.call_count,1)

    def test_14_existing_regular_route_does_not_use_new_staging_auth(self):
        r=self.client.post("/translate",json=self.payload,
                           headers={"Authorization":""})
        self.assertEqual(r.status_code,200)
        # NOTE: this documents a production release BLOCKER; the legacy route
        # does not yet enforce staging auth, and it remains unchanged.
    
if __name__ == "__main__":
    unittest.main()
