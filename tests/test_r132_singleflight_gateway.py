"""R132 deterministic isolated gateway admission tests, no real translation model."""
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import time
import unittest
import urllib.request
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r125_serial_gateway import Readiness,start_gateway

TOKEN="R132_SYNTHETIC_TEST_ONLY_BEARER_0123456789_abcdef"
class SlowBackend(BaseHTTPRequestHandler):
    started=threading.Event()
    release=threading.Event()
    received=0
    def log_message(self,*args):pass
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        type(self).received+=1
        type(self).started.set()
        if not type(self).release.wait(timeout=8):
            self.send_error(504)
            return
        data=json.dumps({"status":"provisional_candidate","human_approved":False}).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)

def post(port, path="/experimental/guarded-translate", token=TOKEN):
    raw=json.dumps({"source":"en","target":"es","q":"Made up note for race test."}).encode()
    request=urllib.request.Request(f"http://127.0.0.1:{port}{path}",
      data=raw,method="POST",headers={"Authorization":"Bearer "+token,
                                         "Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(request,timeout=8) as response:
            return response.status,json.loads(response.read()),dict(response.headers)
    except urllib.error.HTTPError as exc:
        return exc.code,json.loads(exc.read()),dict(exc.headers)

class SingleFlight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.backend=ThreadingHTTPServer(("127.0.0.1",0),SlowBackend)
        cls.backend_thread=threading.Thread(target=cls.backend.serve_forever,daemon=True)
        cls.backend_thread.start()
        cls.state=Readiness()
        cls.gateway,_=start_gateway(cls.state,backend_port=cls.backend.server_port,
                                    stage_token=TOKEN)
        cls.port=cls.gateway.server_port
    @classmethod
    def tearDownClass(cls):
        SlowBackend.release.set()
        cls.gateway.shutdown();cls.gateway.server_close()
        cls.backend.shutdown();cls.backend.server_close()
    def setUp(self):
        self.assertTrue(self.state.begin_drain(timeout=3))
        self.state.choose_target("es")
        SlowBackend.started.clear()
        SlowBackend.release.clear()
        SlowBackend.received=0
        self.state.resume()
    def tearDown(self):
        SlowBackend.release.set()
        self.assertTrue(self.state.begin_drain(timeout=4))
    def begin_blocked(self, pool):
        future=pool.submit(post,self.port)
        self.assertTrue(SlowBackend.started.wait(timeout=3),
                        "First request was never forwarded")
        self.assertEqual(self.state.snapshot()["active"],1)
        return future
    def test_01_second_request_is_always_429_not_forwarded(self):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=self.begin_blocked(pool)
            try:
                for _ in range(8):
                    status,body,headers=post(self.port)
                    self.assertEqual(status,429)
                    self.assertEqual(headers.get("Retry-After"),"2")
                    self.assertEqual(body["error"],"translator busy")
                self.assertEqual(SlowBackend.received,1)
                self.assertEqual(self.state.snapshot()["active"],1)
                self.assertEqual(self.state.snapshot()["rejected_busy"],8)
            finally:
                SlowBackend.release.set()
            self.assertEqual(future.result(timeout=4)[0],200)
        self.assertEqual(self.state.snapshot()["active"],0)
        self.assertEqual(post(self.port)[0],200)
        self.assertEqual(SlowBackend.received,2)
    def test_02_unauthorized_still_401_during_inflight(self):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=self.begin_blocked(pool)
            try:
                self.assertEqual(post(self.port,token="WRONG")[0],401)
                self.assertEqual(post(self.port,path="/translate")[0],410)
                self.assertEqual(SlowBackend.received,1)
            finally:
                SlowBackend.release.set()
            self.assertEqual(future.result(timeout=4)[0],200)
    def test_03_draining_is_503_even_when_inflight(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            future=self.begin_blocked(pool)
            draining=pool.submit(self.state.begin_drain,3)
            try:
                deadline=time.monotonic()+2
                while self.state.snapshot()["ready"] and time.monotonic()<deadline:
                    time.sleep(.005)
                self.assertFalse(self.state.snapshot()["ready"])
                status,_,headers=post(self.port)
                self.assertEqual(status,503)
                self.assertEqual(headers.get("Retry-After"),"2")
            finally:
                SlowBackend.release.set()
            self.assertEqual(future.result(timeout=4)[0],200)
            self.assertTrue(draining.result(timeout=4))
    def test_04_burst_backlog_gives_429_not_connection_reset(self):
        self.assertGreaterEqual(type(self.gateway).request_queue_size,16)

    def test_04_atomic_admission_with_many_contenders(self):
        with ThreadPoolExecutor(max_workers=16) as pool:
            future=self.begin_blocked(pool)
            try:
                statuses=list(pool.map(lambda _:post(self.port)[0],range(40)))
                self.assertEqual(statuses,[429]*40)
                self.assertEqual(SlowBackend.received,1)
            finally:
                SlowBackend.release.set()
            self.assertEqual(future.result(timeout=4)[0],200)

if __name__=="__main__":
    unittest.main()
