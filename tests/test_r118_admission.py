"""R118: isolated Flask contract tests; no Argos installed and no FFH data."""
import concurrent.futures
import json
from threading import Event
import unittest
from unittest import mock

from test_r116_guarded_api import load, SINGLE, BATCH


class AdmissionContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app, cls.calls = load(True)
        cls.app.testing = True

    def setUp(self):
        self.client = self.app.test_client()
        self.globals = self.app.view_functions["experimental_guarded_translate"].__globals__

    def body(self, q="The blue notebook is on a table."):
        return {"q": q, "source": "en", "target": "es"}

    def batch(self):
        return {"items": ["A fictional notebook"], "source": "en", "target": "es"}

    def test_regular_routes_are_not_subject_to_admission(self):
        response = self.client.post("/translate", json=self.body())
        self.assertEqual(response.status_code, 200)

    def test_default_capacity_is_one(self):
        sem = self.globals["GUARDED_CAPACITY"]
        self.assertTrue(sem.acquire(blocking=False))
        try:
            self.assertFalse(sem.acquire(blocking=False))
        finally:
            sem.release()

    def test_payload_limit_guarded_single_and_batch(self):
        for path, body in (
            (SINGLE, self.body("X" * (129 * 1024))),
            (BATCH, {"items": ["X"*(129*1024)], "source":"en","target":"es"}),
        ):
            with self.subTest(route=path):
                r=self.client.post(path,json=body)
                self.assertEqual(r.status_code,413)
                self.assertEqual(r.get_json(),{"error":"request body too large"})

    def test_non_json_is_rejected(self):
        for path in (SINGLE,BATCH):
            r=self.client.post(path,data=b"not json",content_type="text/plain")
            self.assertEqual(r.status_code,400)

    def test_one_long_request_makes_second_fail_fast_and_health_responds(self):
        entered, release = Event(), Event()
        original = self.globals["guarded_draft"]
        def blocking(*args):
            entered.set()
            if not release.wait(4):
                raise RuntimeError("synthetic test timed out")
            return original(*args)
        with mock.patch.dict(self.globals, {"guarded_draft": blocking}):
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                def first():
                    with self.app.test_client() as c:
                        return c.post(SINGLE,json=self.body())
                f=pool.submit(first)
                self.assertTrue(entered.wait(2))
                try:
                    busy = self.client.post(SINGLE,json=self.body("Other note"))
                    self.assertEqual(busy.status_code,429)
                    self.assertEqual(busy.headers.get("Retry-After"),"2")
                    self.assertEqual(busy.get_json(),{
                        "error":"translation service busy","retryable":True,
                        "retry_after_seconds":2
                    })
                    self.assertNotIn("Other note",busy.get_data(as_text=True))
                    batch_busy=self.client.post(BATCH,json=self.batch())
                    self.assertEqual(batch_busy.status_code,429)
                    health=self.client.get("/health")
                    self.assertEqual(health.status_code,200)
                finally:
                    release.set()
                self.assertEqual(f.result(timeout=3).status_code,200)

    def test_held_output_and_provisional_output_still_distinct(self):
        r=self.client.post(SINGLE,json=self.body("{{bad}}"))
        self.assertEqual(r.get_json()["status"],"held")
        self.assertIsNone(r.get_json()["draft"])
        r=self.client.post(SINGLE,json=self.body())
        self.assertEqual(r.get_json()["status"],"provisional_candidate")
        self.assertIs(r.get_json()["human_approved"],False)

    def test_semaphore_released_after_single_exception(self):
        def broken(*_):
            raise RuntimeError("invented error")
        with mock.patch.dict(self.globals,{"guarded_draft":broken}):
            with self.assertRaises(RuntimeError):
                self.client.post(SINGLE,json=self.body())
        r=self.client.post(SINGLE,json=self.body())
        self.assertEqual(r.status_code,200)

    def test_semaphore_released_after_batch_exception(self):
        def broken(*_):
            raise RuntimeError("invented error")
        with mock.patch.dict(self.globals,{"guarded_draft":broken}):
            with self.assertRaises(RuntimeError):
                self.client.post(BATCH,json=self.batch())
        r=self.client.post(BATCH,json=self.batch())
        self.assertEqual(r.status_code,200)

    def test_25_item_batch_kept(self):
        r=self.client.post(BATCH,json={
            "items":["Imaginary note"]*25,"source":"en","target":"es"})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.get_json()["count"],25)
        self.assertTrue(all(x["human_approved"] is False for x in r.get_json()["results"]))

    def test_26_item_batch_rejected(self):
        r=self.client.post(BATCH,json={
            "items":["Imaginary note"]*26,"source":"en","target":"es"})
        self.assertEqual(r.status_code,400)

    def test_nonobject_json_root_rejected(self):
        self.assertEqual(self.client.post(BATCH,json=[]).status_code,400)

if __name__=="__main__":
    unittest.main()
