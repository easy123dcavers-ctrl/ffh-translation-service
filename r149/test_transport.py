"""Offline R149 exact loopback transport and fail-close regressions; no real model."""
import json
import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler,HTTPServer
from r149.guarded_transport import GuardedLoopbackModel,ENDPOINT
from r136.broker import Denied
SECRET='R149-Offline-Synthetic-Only-Do-Not-Use-On-Hosted-Backend-12345'

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        size=int(self.headers.get('Content-Length',0))
        payload=json.loads(self.rfile.read(size))
        q=payload.get('q')
        data={'status':'provisional_candidate','draft':'Synthetic draft',
              'human_approved':False,'production_writes':0}
        if q=='held':data={'status':'held','human_approved':False,'production_writes':0}
        if q=='forged_review':data['human_approved']=True
        if q=='forged_publication':data['production_writes']=1
        if q=='bad_format':data={'something':'unsafe'}
        if q=='redirect':
            self.send_response(302);self.send_header('Location','https://untrusted.invalid/');
            self.end_headers();return
        output=json.dumps(data).encode()
        if q=='huge':output=b' '+b' ' * 9000
        self.send_response(200);self.send_header('Content-Type','application/json');
        self.send_header('Content-Length',str(len(output)));self.end_headers()
        self.wfile.write(output)
    def log_message(self,*args):pass

class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['FFH_R149_EPHEMERAL_ONLY']='1'
        cls.srv=HTTPServer(('127.0.0.1',17849),Handler)
        cls.thread=threading.Thread(target=cls.srv.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown();cls.srv.server_close()
    def adapter(self):return GuardedLoopbackModel(SECRET,timeout=2)
    def test_01_fixed_loopback_route(self):self.assertEqual(ENDPOINT,'http://127.0.0.1:17849/experimental/guarded-translate')
    def test_02_real_http_provisional(self):
        x=self.adapter()('es','A clean English synthetic phrase.')
        self.assertEqual(x['status'],'provisional_candidate')
        self.assertEqual(x['production_writes'],0)
    def test_03_model_held(self):self.assertEqual(self.adapter()('es','held')['status'],'held')
    def test_04_wrong_target_no_http(self):
        with self.assertRaises(Denied):self.adapter()('ja','word')
    def test_05_client_cannot_switch_endpoint(self):
        with self.assertRaises(ValueError):GuardedLoopbackModel(SECRET,endpoint='https://example.com/')
    def test_06_missing_secret_denied(self):
        with self.assertRaises(ValueError):GuardedLoopbackModel('abc')
    def test_07_no_production_execution_mode(self):
        os.environ.pop('FFH_R149_EPHEMERAL_ONLY',None)
        try:
            with self.assertRaises(ValueError):GuardedLoopbackModel(SECRET)
        finally:os.environ['FFH_R149_EPHEMERAL_ONLY']='1'
    def test_08_autoapproval_refused(self):
        with self.assertRaises(Denied):self.adapter()('es','forged_review')
    def test_09_publication_refused(self):
        with self.assertRaises(Denied):self.adapter()('es','forged_publication')
    def test_10_invalid_response_fail_closed(self):
        with self.assertRaises(Denied):self.adapter()('es','bad_format')
    def test_11_redirect_token_leak_refused(self):
        with self.assertRaises(Denied):self.adapter()('es','redirect')
    def test_12_oversized_response_rejected(self):
        with self.assertRaises(Denied):self.adapter()('es','huge')
if __name__=='__main__':unittest.main(verbosity=2)
