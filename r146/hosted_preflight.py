"""R146 REAL hosted Supabase HTTPS NEGATIVE preflight — no writes, no accounts.

Tests against existing FFH-Language-Safety-Staging project only.
No signup, no JWT issuance, no Auth updates, no DB migrations, no service key.
R143/145 genuine Auth positive proofs remain DISPOSABLE CI ONLY.
"""
import json,os,ssl,unittest,urllib.request,urllib.error,urllib.parse
from urllib.parse import urlsplit

EXPECTED_HOST="hlsjzjnondimwhqbgjqm.supabase.co"
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise AssertionError("Unexpected off-origin redirect")

def fetch(path,bearer=None,apikey=True,method="GET",json_body=None,private_profile=False):
    host=os.environ["FFH_R146_STAGE_URL"]
    key=os.environ.get("FFH_R146_STAGE_PUBLISHABLE_KEY","")
    if (urlsplit(host).scheme!="https" or
        urlsplit(host).netloc!=EXPECTED_HOST or
        urlsplit(host).path or urlsplit(host).query or urlsplit(host).fragment):
        raise AssertionError("Immutable hosted staging HTTPS origin required")
    if not path.startswith("/") or "://" in path or path.startswith("//"):
        raise AssertionError("relative route only")
    if method not in ("GET","HEAD"):raise AssertionError("read-only HTTP methods only")
    h={"Accept":"application/json","User-Agent":"FFH-R146-readonly-staging-preflight/1.0"}
    if apikey:
        if not key.startswith("sb_publishable_"):raise AssertionError("publishable key only")
        h["apikey"]=key
    if bearer is not None:h["Authorization"]="Bearer "+bearer
    if private_profile:h["Accept-Profile"]="ffh_r146_sandbox"
    opener=urllib.request.build_opener(NoRedirect(),
        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    req=urllib.request.Request(host+path,headers=h,method=method)
    try:
        with opener.open(req,timeout=12) as resp:
            out=resp.read(15360)
            return resp.status,dict(resp.headers),out
    except urllib.error.HTTPError as ex:
        data=ex.read(15360)
        return ex.code,dict(ex.headers),data

class HostedStageReadOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.getenv("FFH_R146_READONLY_ONLY")!="1":
            raise RuntimeError("R146 staging readonly guard missing")
        if os.getenv("GITHUB_REF_NAME")!="ffh-r146-hosted-stage-preflight-20261017":
            raise RuntimeError("wrong isolated branch")
    def test_01_tls_staging_project_health(self):
        status,header,body=fetch("/auth/v1/health")
        print("R146_HOSTED_AUTH_HEALTH_STATUS",status,flush=True)
        self.assertEqual(status,200)
    def test_02_auth_settings_hosted(self):
        status,header,body=fetch("/auth/v1/settings")
        print("R146_HOSTED_SETTINGS_STATUS",status,flush=True)
        self.assertEqual(status,200)
        data=json.loads(body)
        self.assertIsInstance(data,dict)
        # Only safe booleans; no identity details or access credentials.
        print("R146_SETTINGS_FLAGS",
            {name:data.get(name) for name in ("external","disable_signup","autoconfirm")
             if name in data},flush=True)
    def test_03_missing_bearer_denied(self):
        status,headers,data=fetch("/auth/v1/user")
        self.assertIn(status,(400,401,403))
    def test_04_invalid_bearer_denied(self):
        status,headers,data=fetch("/auth/v1/user",bearer="invalid-r146-not-a-token")
        self.assertIn(status,(400,401,403))
    def test_05_none_algorithm_fabricated_jwt_denied(self):
        status,headers,data=fetch("/auth/v1/user",bearer="eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIwMDAwMDAwMC0wMDAwLTQwMDAtODAwMC0wMDAwMDAwMDAwMDEifQ.fake")
        self.assertIn(status,(400,401,403))
    def test_06_malformed_bearer_denied(self):
        status,headers,data=fetch("/auth/v1/user",bearer="not-a-JWT")
        self.assertIn(status,(400,401,403))
    def test_07_staging_has_no_ffh_member_registry_rest(self):
        status,headers,data=fetch("/rest/v1/ffh_member_profiles?select=user_id&limit=1")
        print("R146_MISSING_MEMBER_REGISTRY_STATUS",status,flush=True)
        self.assertIn(status,(404,406))
    def test_08_staging_has_no_registered_translation_source_rest(self):
        status,headers,data=fetch("/rest/v1/ffh_translation_memory?select=source_hash&limit=1")
        self.assertIn(status,(404,406))
    def test_09_staging_has_no_current_terms_function(self):
        status,headers,data=fetch("/rest/v1/rpc/ffh_current_terms_version")
        # No valid RPC signature in staging; GET is read-only.
        self.assertIn(status,(404,405,406))
    def test_10_publishable_key_no_privileged_rest_access(self):
        status,headers,data=fetch("/rest/v1/ffh_staff_roles?select=role&limit=1")
        self.assertIn(status,(404,406))


    def test_11_r146_private_schema_not_exposed_in_rest(self):
        status,headers,data=fetch("/rest/v1/member_profiles?select=user_id&limit=1",private_profile=True)
        print("R146_PRIVATE_SCHEMA_ACCESS_STATUS",status,flush=True)
        self.assertEqual(status,406)
    def test_12_r146_member_function_not_exposed(self):
        status,headers,data=fetch("/rest/v1/rpc/member_status?p_uid=00000000-0000-4000-8000-000000000001&p_session=00000000-0000-4000-8000-000000000002",private_profile=True)
        self.assertEqual(status,406)
    def test_13_r146_source_function_not_exposed(self):
        status,headers,data=fetch("/rest/v1/rpc/safe_source?p_text=FFH%20R146%20interface%20label%20for%20staging%20verification.",private_profile=True)
        self.assertEqual(status,406)

if __name__=="__main__":
    unittest.main(verbosity=2)
