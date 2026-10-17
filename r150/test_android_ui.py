"""R150 GitHub Pages-only Android UI safety gate. Never production site."""
import pathlib,re,subprocess,tempfile,unittest
class R150Page(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.html=pathlib.Path('docs/index.html').read_text('utf8')
  cls.js=pathlib.Path('docs/r150.js').read_text('utf8')
 def test_01_script_referenced(self):
  self.assertIn('<script src="./r150.js"></script>',self.html)
 def test_02_control_initially_disabled(self):
  self.assertIn('id="r150" disabled',self.html)
 def test_03_enable_only_after_existing_member_gate(self):
  a=self.html.index("report('Your staging Member check PASSED.")
  b=self.html.index("el('r150').disabled=false;")
  self.assertLess(a,b)
 def test_04_exact_staging_function_not_render(self):
  self.assertIn("BASE+'/functions/v1/ffh-r150-auth-broker-stage'",self.js)
  self.assertNotIn('onrender.com',self.js)
 def test_05_uses_existing_actual_member_token(self):
  self.assertIn("Authorization:'Bearer '+token",self.js)
 def test_06_only_read_only_preflight(self):
  self.assertIn("action:'preflight'",self.js)
  self.assertIn("source:SOURCE,target:'ja'",self.js)
 def test_07_strictly_model_off(self):
  self.assertIn("result.model_connected!==false",self.js)
  self.assertIn("result.production_writes!==0",self.js)
  self.assertIn("result.human_approved!==false",self.js)
 def test_08_no_secrets_or_browser_token_storage(self):
  for s in ('localStorage','sessionStorage','document.cookie','sb_secret_','service_role','/translate','request_id'):
   self.assertNotIn(s,self.js)
 def test_09_browser_javascript_valid(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=pathlib.Path(tmp,'test.js');p.write_text(self.js,'utf8')
   run=subprocess.run(['node','--check',str(p)],capture_output=True,timeout=15)
   self.assertEqual(run.returncode,0,run.stderr.decode()[:500])
if __name__=='__main__': unittest.main(verbosity=2)
