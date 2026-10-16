"""R125 routing state is atomic and failure-closed; no production model needed."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from r125_serial_gateway import Readiness,start_gateway
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
import json
import threading
import time
import unittest
import urllib.error
import urllib.request

TOKEN="R125_FAKE_TEST_SECRET_NO_PRODUCTION_DATA_01234567890"
class Dummy(BaseHTTPRequestHandler):
    hit=0
    def log_message(self,*args):pass
    def do_POST(self):
        self.rfile.read(int(self.headers["Content-Length"]))
        self.__class__.hit+=1
        b=json.dumps({"status":"provisional_candidate","human_approved":False}).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(b)))
        self.end_headers();self.wfile.write(b)

def post(port,path,target="es",token=TOKEN):
    b=json.dumps({"source":"en","target":target,"q":"Invented book"}).encode()
    q=urllib.request.Request(f"http://127.0.0.1:{port}{path}",data=b,
        headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(q,timeout=3) as r:
            return r.status,json.loads(r.read()),dict(r.headers)
    except urllib.error.HTTPError as r:
        return r.code,json.loads(r.read()),dict(r.headers)

class SingleModelRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=ThreadingHTTPServer(("127.0.0.1",0),Dummy)
        threading.Thread(target=cls.model.serve_forever,daemon=True).start()
        cls.state=Readiness()
        cls.server,_=start_gateway(cls.state,backend_port=cls.model.server_port,
                                   stage_token=TOKEN)
        cls.port=cls.server.server_port
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close()
        cls.model.shutdown();cls.model.server_close()
    def setUp(self):
        self.assertTrue(self.state.begin_drain(2))
        Dummy.hit=0
        self.state.choose_target("es")
    def test_01_initial_draining_explicit_503(self):
        x=post(self.port,"/experimental/guarded-translate")
        self.assertEqual(x[0],503)
        self.assertEqual(x[2].get("Retry-After"),"2")
        self.assertEqual(Dummy.hit,0)
    def test_02_selected_es_can_proxy(self):
        self.state.resume()
        r=post(self.port,"/experimental/guarded-translate")
        self.assertEqual(r[0],200)
        self.assertEqual(Dummy.hit,1)
    def test_03_wrong_target_cannot_proxy(self):
        self.state.resume()
        x=post(self.port,"/experimental/guarded-translate",target="fr")
        self.assertEqual(x[0],503)
        self.assertEqual(x[1]["error"],"target model not resident")
        self.assertEqual(Dummy.hit,0)
    def test_04_switch_must_drain_first(self):
        self.state.resume()
        with self.assertRaises(RuntimeError):
            self.state.choose_target("fr")
        self.assertTrue(self.state.begin_drain(2))
        self.state.choose_target("fr")
        self.state.resume()
        self.assertEqual(post(self.port,"/experimental/guarded-translate",target="fr")[0],200)
        self.assertEqual(post(self.port,"/experimental/guarded-translate",target="es")[0],503)
    def test_05_unknown_target_cannot_activate(self):
        with self.assertRaises(ValueError):self.state.choose_target("zz")
    def test_06_wrong_stage_bearer_rejected(self):
        self.state.resume()
        self.assertEqual(post(self.port,"/experimental/guarded-translate",token="incorrect")[0],401)
        self.assertEqual(Dummy.hit,0)
    def test_07_legacy_stays_quarantined(self):
        self.state.resume()
        self.assertEqual(post(self.port,"/translate")[0],410)
        self.assertEqual(Dummy.hit,0)
    def test_08_correct_auth_does_not_override_drain(self):
        self.assertEqual(post(self.port,"/experimental/guarded-translate")[0],503)
        self.assertEqual(Dummy.hit,0)

if __name__=="__main__":unittest.main()
