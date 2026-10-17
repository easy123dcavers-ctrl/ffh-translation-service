"""R151 LIVE staging Edge negative tests. No member JWT or model call used."""
import json,urllib.request,urllib.error,re,pathlib,subprocess,tempfile,unittest
URL='https://hlsjzjnondimwhqbgjqm.supabase.co/functions/v1/ffh-r151-synthetic-model-bridge'
PUB='sb_publishable_ZoYvYGbu9rJlPhHjM-3t3g_MqFWGkL2'
ORIGIN='https://easy123dcavers-ctrl.github.io'
BODY=json.dumps({'request_id':'R151_negative_request_1234567890'}).encode()
def call(*,method='POST',token=None,origin=ORIGIN,body=BODY):
 headers={'apikey':PUB,'Origin':origin,'Content-Type':'application/json'}
 if token is not None:headers['Authorization']='Bearer '+token
 req=urllib.request.Request(URL,method=method,data=body if method=='POST' else None,headers=headers)
 try:
  with urllib.request.urlopen(req,timeout=18) as r:return r.status,r.headers, r.read()
 except urllib.error.HTTPError as err:return err.code,err.headers,err.read()
class Boundaries(unittest.TestCase):
 def test_01_no_bearer_rejected(self):
  status,headers,body=call()
  self.assertEqual(status,401,body[:350])
  self.assertEqual(json.loads(body)['status'],'not_authenticated')
 def test_02_forged_bearer_rejected(self):
  status,_,body=call(token='fake.'+'a'*50+'.signature')
  self.assertEqual(status,401,body[:400])
 def test_03_wrong_origin_rejected(self):
  status,_,body=call(origin='https://evil.example')
  self.assertEqual(status,403,body[:350])
 def test_04_correct_preflight(self):
  status,headers,_=call(method='OPTIONS')
  self.assertEqual(status,204)
  self.assertEqual(headers.get('Access-Control-Allow-Origin'),ORIGIN)
 def test_05_no_publish_or_model_secret_in_browser(self):
  page=pathlib.Path('docs/index.html').read_text('utf8')
  js=pathlib.Path('docs/r151.js').read_text('utf8')
  for forbidden in ('SUPABASE_SERVICE_ROLE_KEY','sb_secret_','onrender.com',
                    '/translate','localStorage','sessionStorage','document.cookie'):
   self.assertNotIn(forbidden,js)
  self.assertIn('<script src="./r151.js"></script>',page)
  self.assertIn('id="r151" disabled',page)
 def test_06_browser_script_parses(self):
  with tempfile.TemporaryDirectory() as p:
   f=pathlib.Path(p)/'r151.js';f.write_text(pathlib.Path('docs/r151.js').read_text('utf8'),encoding='utf8')
   proc=subprocess.run(['node','--check',str(f)],capture_output=True,timeout=10)
   self.assertEqual(proc.returncode,0,proc.stderr.decode()[:400])
 def test_07_all_model_text_server_pinned(self):
  s=pathlib.Path('r151/edge/core.mjs').read_text('utf8')
  self.assertIn("export const TEXT='FFH R146 interface label for staging verification.'",s)
  self.assertIn("export const TARGET='es'",s)
  self.assertIn("body:JSON.stringify({q:TEXT,source:'en',target:TARGET})",s)
  self.assertNotIn('Deno.env.get',s)
 def test_08_finalizer_not_exposed_browser(self):
  sql=pathlib.Path('r151/01_staging_durable_model_gate.sql').read_text('utf8')
  self.assertIn('TO service_role;',sql)
  self.assertIn('FROM PUBLIC,anon,authenticated;',sql)
  self.assertEqual(sql.count('FORCE ROW LEVEL SECURITY'),3)
  self.assertIn('r.receipt_hash=v_receipt_hash AND r.user_hash=v_user_hash',sql)
if __name__=='__main__':unittest.main(verbosity=2)
