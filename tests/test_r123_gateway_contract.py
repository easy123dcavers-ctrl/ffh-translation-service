"""R123 11 independent stdlib tests for a temporary loopback readiness proxy."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r123_readiness_gateway import Readiness, start_gateway

TOKEN = "R123_SYNTHETIC_ONLY_NO_PRODUCTION_ACCESS_0123456789"


class FakeModel(BaseHTTPRequestHandler):
    entered = threading.Event()
    release = threading.Event()

    def log_message(self, *_):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        obj = json.loads(raw)
        if obj.get("q") == "BLOCK":
            self.entered.set()
            self.release.wait(5)
        blob = json.dumps({"status": "provisional_candidate", "draft": "FAKE",
                           "human_approved": False}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)


def http(port, path, body=None, auth=True, timeout=6):
    headers = {}
    encoded = None if body is None else json.dumps(body).encode()
    if encoded is not None:
        headers["Content-Type"] = "application/json"
    if auth:
        headers["Authorization"] = "Bearer " + TOKEN
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=encoded, headers=headers,
        method="POST" if encoded is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read()), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read()), dict(e.headers)


class GatewayContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend = ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
        cls.worker = threading.Thread(target=cls.backend.serve_forever,daemon=True)
        cls.worker.start()
        cls.readiness = Readiness()
        cls.gateway, cls.thread = start_gateway(
            cls.readiness, backend_port=cls.backend.server_port, stage_token=TOKEN)
        cls.port = cls.gateway.server_port

    @classmethod
    def tearDownClass(cls):
        cls.gateway.shutdown()
        cls.gateway.server_close()
        cls.backend.shutdown()
        cls.backend.server_close()

    def setUp(self):
        self.assertTrue(self.readiness.begin_drain(timeout=2))
        FakeModel.entered.clear()
        FakeModel.release.set()

    def test_01_gateway_starts_unready(self):
        status, body, headers = http(self.port, "/health")
        self.assertEqual(status, 503)
        self.assertEqual(headers["Retry-After"], "2")

    def test_02_legacy_blocked_before_auth(self):
        status, body, _ = http(self.port, "/translate", {"q": "dummy"}, auth=False)
        self.assertEqual(status, 410)

    def test_03_unauthorized_guarded_route_rejected(self):
        status, body, headers = http(self.port,
            "/experimental/guarded-translate", {"q": "test"}, auth=False)
        self.assertEqual(status, 401)
        self.assertIn("no-store", headers["Cache-Control"])

    def test_04_unknown_route_rejected(self):
        self.assertEqual(http(self.port, "/anything")[0], 404)

    def test_05_ready_health_and_provisional_response(self):
        self.readiness.resume()
        self.assertEqual(http(self.port, "/health")[0], 200)
        status, data, headers = http(self.port,
            "/experimental/guarded-translate", {"q": "invented"})
        self.assertEqual(status, 200)
        self.assertIs(data["human_approved"], False)
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertEqual(self.readiness.snapshot()["active"], 0)

    def test_06_draining_rejects_new_requests_while_old_completes(self):
        self.readiness.resume()
        FakeModel.release.clear()
        with ThreadPoolExecutor(max_workers=2) as pool:
            accepted = pool.submit(http, self.port,
                "/experimental/guarded-translate", {"q": "BLOCK"})
            self.assertTrue(FakeModel.entered.wait(timeout=2))
            drain = pool.submit(self.readiness.begin_drain, 4)
            t0 = time.monotonic()
            while self.readiness.snapshot()["ready"] and time.monotonic()-t0<2:
                time.sleep(.01)
            status, data, headers = http(self.port,
                "/experimental/guarded-translate", {"q": "new"})
            self.assertEqual(status, 503)
            self.assertTrue(data["retryable"])
            self.assertEqual(headers["Retry-After"], "2")
            self.assertEqual(http(self.port,"/health")[0], 503)
            FakeModel.release.set()
            self.assertEqual(accepted.result(timeout=3)[0], 200)
            self.assertTrue(drain.result(timeout=3))
        self.assertEqual(self.readiness.snapshot()["active"], 0)

    def test_07_resume_only_after_drained(self):
        self.readiness.resume()
        self.assertEqual(http(self.port,"/health")[0], 200)
        self.assertTrue(self.readiness.begin_drain(timeout=2))
        self.assertEqual(http(self.port,"/health")[0], 503)
        self.readiness.resume()
        self.assertEqual(http(self.port,"/health")[0], 200)

    def test_08_large_payload_fails_without_model(self):
        self.readiness.resume()
        status, data, _ = http(self.port,
            "/experimental/guarded-translate", {"q":"X"*(129*1024)})
        self.assertEqual(status,413)
        self.assertEqual(self.readiness.snapshot()["active"],0)

    def test_09_malformed_authorization_fails_even_when_ready(self):
        self.readiness.resume()
        status, _, _ = http(self.port,
            "/experimental/guarded-translate-batch",{"items":[]},auth=False)
        self.assertEqual(status,401)

    def test_10_down_backend_marks_unknown_outcome_without_replay(self):
        state=Readiness()
        # Valid loopback port with no listener; never makes an external request.
        sock=__import__("socket").socket()
        sock.bind(("127.0.0.1",0))
        dead_port=sock.getsockname()[1]
        sock.close()
        gateway, thread=start_gateway(state,backend_port=dead_port,stage_token=TOKEN)
        try:
            state.resume()
            status, body, _ = http(gateway.server_port,
                "/experimental/guarded-translate",{"q":"invented"})
            self.assertEqual(status,502)
            self.assertEqual(body["error"],"translation outcome unknown")
            self.assertIs(body["retryable"],False)
            self.assertFalse(state.snapshot()["ready"])
            self.assertEqual(http(gateway.server_port,
                "/experimental/guarded-translate",{"q":"invented"})[0],503)
        finally:
            gateway.shutdown()
            gateway.server_close()

    def test_11_reject_weak_gateway_secrets(self):
        with self.assertRaises(ValueError):
            start_gateway(Readiness(),backend_port=1234,stage_token="short")


if __name__=="__main__":
    unittest.main()
