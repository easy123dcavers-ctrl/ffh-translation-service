"""R150 REAL STAGING Edge HTTPS negative tests. No user or model tokens.
One public staging key extracted from prior GitHub Pages HTML; never service role.
"""
import json,re,unittest,urllib.request,urllib.error,pathlib
BASE='https://hlsjzjnondimwhqbgjqm.supabase.co'
URL=BASE+'/functions/v1/ffh-r150-auth-broker-stage'
PAGES='https://easy123dcavers-ctrl.github.io'
PAGE=pathlib.Path('docs/index.html').read_text('utf-8')
KEY=re.search(r'const PUB="(sb_publishable_[A-Za-z0-9_-]+)"',PAGE)
assert KEY,'Existing staging public key missing from tested GitHub Pages page'
KEY=KEY.group(1)
SAMPLE={'action':'preflight','source':'FFH R146 interface label for staging verification.','target':'ja'}
FAKE='Bearer '+('ABC_'*24)
def request(method='POST',body=None,headers=None):
    h={'apikey':KEY,'Origin':PAGES,'Content-Type':'application/json'}
    h.update(headers or {})
    data=json.dumps(SAMPLE if body is None else body).encode('utf-8') if method=='POST' else None
    req=urllib.request.Request(URL,headers=h,data=data,method=method)
    try:
        with urllib.request.urlopen(req,timeout=15) as r:
            return r.status,dict(r.headers),r.read(4096)
    except urllib.error.HTTPError as e:
        return e.code,dict(e.headers),e.read(4096)
class HostedNegative(unittest.TestCase):
    def test_01_options_preflight(self):
        status,headers,b=request('OPTIONS')
        self.assertEqual(status,204)
    def test_02_get_denied_without_model(self):
        status,headers,b=request('GET')
        self.assertEqual(status,405)
    def test_03_no_token_denied(self):
        status,headers,b=request()
        self.assertEqual(status,401)
        self.assertIn(b'model_connected',b)
    def test_04_bad_origin_denied(self):
        status,headers,b=request(headers={'Origin':'https://hostile.invalid'})
        self.assertEqual(status,403)
        self.assertNotIn('access-control-allow-origin',{k.lower():v for k,v in headers.items()})
    def test_05_bad_target_never_reaches_auth(self):
        status,headers,b=request(body={**SAMPLE,'target':'xxx'},headers={'Authorization':FAKE})
        self.assertEqual(status,400)
    def test_06_client_role_injection_refused(self):
        status,headers,b=request(body={**SAMPLE,'role':'Owner'},headers={'Authorization':FAKE})
        self.assertEqual(status,400)
    def test_07_forged_bearer_fails_auth(self):
        status,headers,b=request(headers={'Authorization':FAKE})
        self.assertIn(status,(401,403))
    def test_08_auth_failure_does_not_approve_or_publish(self):
        status,headers,b=request(headers={'Authorization':FAKE})
        result=json.loads(b)
        self.assertIs(result.get('model_connected'),False)
        self.assertIs(result.get('human_approved'),False)
        self.assertEqual(result.get('production_writes'),0)
if __name__=='__main__':unittest.main(verbosity=2)
