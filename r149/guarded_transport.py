"""R149 disposable CI-only model transport. NOT a public Render URL/client API.
Only loopback, server-only guarded token, fixed endpoint; never user bearer JWT.
"""
import hmac
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from r136.broker import Denied

ENDPOINT='http://127.0.0.1:17849/experimental/guarded-translate'
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise RuntimeError('redirect forbidden')
class GuardedLoopbackModel:
    def __init__(self,secret:str,endpoint=ENDPOINT,timeout=120):
        if os.getenv('FFH_R149_EPHEMERAL_ONLY')!='1':
            raise ValueError('CI-only guarded loopback model')
        if endpoint!=ENDPOINT:
            raise ValueError('fixed loopback endpoint required')
        if not isinstance(secret,str) or len(secret)<32 or len(secret)>512:
            raise ValueError('missing server-held guarded secret')
        if not isinstance(timeout,(int,float)) or not 0<timeout<=150:
            raise ValueError('bounded model timeout required')
        self._secret=secret
        self._timeout=timeout
        self._open=urllib.request.build_opener(NoRedirect())
    def __call__(self,target,text):
        if target!='es' or not isinstance(text,str) or len(text)>500 or not text:
            raise Denied(422,'CI model only accepts synthetic English-to-Spanish')
        payload=json.dumps({'source':'en','target':target,'q':text},
                           ensure_ascii=False,separators=(',',':')).encode()
        req=urllib.request.Request(ENDPOINT,data=payload,method='POST',
            headers={'Content-Type':'application/json','Accept':'application/json',
                'Authorization':'Bearer '+self._secret})
        try:
            with self._open.open(req,timeout=self._timeout) as response:
                if response.status!=200:raise RuntimeError('guarded model denied')
                if 'application/json' not in (response.headers.get('Content-Type') or ''):
                    raise RuntimeError('unexpected model content type')
                raw=response.read(8193)
                if len(raw)>8192:raise RuntimeError('oversize model response')
                result=json.loads(raw)
        except Exception:
            raise Denied(502,'guarded translation unavailable; no replay') from None
        if not isinstance(result,dict) or result.get('status') not in ('held','provisional_candidate'):
            raise Denied(502,'invalid model response; do not replay')
        if result.get('human_approved') is not False or result.get('production_writes')!=0:
            raise Denied(502,'untrusted translation approval fields')
        return result
