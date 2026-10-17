/**
 * FFH R151 fixed-sentence staging experiment.
 * NEVER use with FFH production Supabase. Does not ingest, publish, approve,
 * or accept user-supplied text; calls an EXISTING public Render translation
 * model only for a fixed harmless preapproved test sentence.
 */
export const STAGING='https://hlsjzjnondimwhqbgjqm.supabase.co';
export const PAGES='https://easy123dcavers-ctrl.github.io';
export const RENDER='https://ffh-translation-service.onrender.com/translate';
export const TEXT='FFH R146 interface label for staging verification.';
export const TARGET='es';
const JSON_HEADERS={'Content-Type':'application/json; charset=utf-8',
  'Cache-Control':'no-store, private, max-age=0',
  'Pragma':'no-cache','X-Content-Type-Options':'nosniff','Vary':'Origin'};
function response(code,status,origin,extra={}) {
  const h={...JSON_HEADERS};
  if(origin===PAGES){h['Access-Control-Allow-Origin']=PAGES;
    h['Access-Control-Allow-Headers']='apikey,authorization,content-type';
    h['Access-Control-Allow-Methods']='POST, OPTIONS';
    h['Access-Control-Max-Age']='60';}
  return new Response(code===204?null:JSON.stringify({
    status,human_approved:false,production_writes:0,...extra
  }),{status:code,headers:h});
}
async function bounded(response,max=4096){
  if(!response?.ok||response.redirected)return null;
  if(!(response.headers.get('content-type')||'').toLowerCase().includes('application/json'))return null;
  const len=response.headers.get('content-length');
  if(len!=null && (!/^\d+$/.test(len)||Number(len)>max))return null;
  if(!response.body)return null;
  const reader=response.body.getReader();const chunks=[];let n=0;
  try{for(;;){const {done,value}=await reader.read();if(done)break;
    n+=value.byteLength;if(n>max)return null;chunks.push(value);}}
  finally{reader.releaseLock();}
  const bytes=new Uint8Array(n);let i=0;
  for(const c of chunks){bytes.set(c,i);i+=c.byteLength;}
  try{return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}
  catch{return null;}
}
async function body(req){
  if(!req.body)return null;
  const len=req.headers.get('content-length');
  if(len!==null&&(!/^\d+$/.test(len)||Number(len)>256))return null;
  const read=req.body.getReader(),pieces=[];let n=0;
  try{for(;;){const {done,value}=await read.read();if(done)break;
    n+=value.byteLength;if(n>256)return null;pieces.push(value);}}
  finally{read.releaseLock();}
  const bytes=new Uint8Array(n);let i=0;for(const x of pieces){bytes.set(x,i);i+=x.byteLength;}
  try{return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));}
  catch{return null;}
}
function jwtSession(jwt){
  try{
    const part=jwt.split('.')[1];
    if(!part||part.length>4096)return null;
    const normalized=part.replace(/-/g,'+').replace(/_/g,'/');
    const decoded=atob(normalized.padEnd(Math.ceil(normalized.length/4)*4,'='));
    const json=JSON.parse(decoded);
    const session=json?.session_id;
    return typeof session==='string'&&
      /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(session)
      ?session:null;
  }catch{return null;}
}
export function createR151Handler({publishableKey,serviceRoleKey,fetchImpl=fetch,
                                  modelTimeoutMs=100000}={}){
  if(typeof publishableKey!=='string'||!/^sb_publishable_[A-Za-z0-9_-]{12,}$/.test(publishableKey))
    throw new Error('Missing public staging key');
  if(typeof fetchImpl!=='function')throw new Error('Missing fetch adapter');
  if(!Number.isInteger(modelTimeoutMs)||modelTimeoutMs<1000||modelTimeoutMs>110000)
    throw new Error('Invalid model timeout');
  return async function(req){
    const origin=req.headers.get('origin');
    if(origin!==null&&origin!==PAGES)return response(403,'origin_denied',origin);
    if(req.method==='OPTIONS')return response(204,'',origin);
    if(req.method!=='POST')return response(405,'method_not_allowed',origin);
    // The secret must come from the staging Edge environment; never GitHub Pages.
    if(typeof serviceRoleKey!=='string'||serviceRoleKey.length<32)
      return response(503,'server_configuration_held',origin);
    const bearer=req.headers.get('authorization');
    if(typeof bearer!=='string'||bearer.length>8200||
       !/^Bearer [A-Za-z0-9._-]{30,8192}$/.test(bearer))
      return response(401,'not_authenticated',origin);
    if(!(req.headers.get('content-type')||'').startsWith('application/json'))
      return response(415,'json_required',origin);
    const input=await body(req);
    if(!input||typeof input!=='object'||Array.isArray(input)||
       Object.keys(input).join(',')!=='request_id'||
       typeof input.request_id!=='string'||!/^[A-Za-z0-9_-]{16,96}$/.test(input.request_id))
      return response(400,'invalid_request_id',origin);
    const token=bearer.slice(7), sid=jwtSession(token);
    if(!sid)return response(401,'session_missing',origin);
    const nonce=input.request_id;
    const commonHeaders={apikey:publishableKey,Authorization:bearer,Accept:'application/json'};
    const call=async(url,init={},max=4096,timeout=5000)=>{
      const res=await fetchImpl(url,{...init,
        headers:{...commonHeaders,...init.headers},redirect:'error',cache:'no-store',
        signal:AbortSignal.timeout(timeout)});
      return bounded(res,max);
    };
    let admitted=false, uid=null, finalizationAttempted=false;
    const finalize=async(modelOk)=>{
      finalizationAttempted=true;
      return call(STAGING+'/rest/v1/rpc/ffh_r151_finish',{
        method:'POST',headers:{
          apikey:serviceRoleKey,Authorization:'Bearer '+serviceRoleKey,
          'Content-Type':'application/json'},
        body:JSON.stringify({p_user:uid,p_session:sid,p_nonce:nonce,p_model_ok:modelOk})
      });
    };
    try{
      // Online Auth verifies the token; the R150 broker checks live session,
      // profile, terms, and registered non-safety source, independently.
      const member=await call(STAGING+'/auth/v1/user');
      if(!member||typeof member.id!=='string'||
        !/^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(member.id)||
        member.is_anonymous===true)return response(401,'member_auth_failed',origin);
      uid=member.id;
      const check=async()=>{
        const v=await call(STAGING+'/functions/v1/ffh-r150-auth-broker-stage',{
          method:'POST',headers:{'Content-Type':'application/json'},
          body:JSON.stringify({action:'preflight',source:TEXT,target:TARGET})
        });
        return v?.status==='r150_authenticated_stage_ready_model_off'&&
          v?.model_connected===false&&v?.human_approved===false&&v?.production_writes===0;
      };
      if(!(await check()))return response(403,'member_or_source_held',origin);
      const admission=await call(STAGING+'/rest/v1/rpc/ffh_r151_admit',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({p_nonce:nonce})
      });
      if(!admission||typeof admission.status!=='string')
        return response(503,'admission_unavailable',origin);
      if(admission.status!=='admitted'){
        const codes={duplicate:409,quota_exceeded:429,source_held:422,unauthorized:403,bad_nonce:400};
        return response(codes[admission.status]||403,admission.status,origin);
      }
      admitted=true;
      // Existing Render service is NOT reconfigured/deployed. Only the fixed
      // harmless synthetic English test phrase is sent; no JWT or member data.
      const modelResponse=await fetchImpl(RENDER,{
        method:'POST',redirect:'error',cache:'no-store',
        headers:{'Content-Type':'application/json',Accept:'application/json'},
        body:JSON.stringify({q:TEXT,source:'en',target:TARGET}),
        signal:AbortSignal.timeout(modelTimeoutMs)
      });
      const generated=await bounded(modelResponse,4096);
      const translation=generated?.translatedText;
      const plausible=typeof translation==='string'&&translation.trim()!==''&&
        translation.length<=800&&translation!==TEXT&&!/[\u0000-\u001f\u007f]/.test(translation);
      // Before finalization, check auth, current terms and source again; the
      // PostgreSQL service-only finalizer rechecks them atomically one last time.
      const eligible=plausible && await check();
      const terminal=await finalize(Boolean(eligible));
      if(!eligible||terminal?.status!=='done'||
         terminal.human_approved!==false||terminal.production_writes!==0)
        return response(423,'held_after_final_checks',origin);
      return response(200,'provisional_candidate',origin,{
        draft:translation,target:TARGET,model_connected:true,
        disclaimer:'STAGING DRAFT ONLY — not reviewed, saved, or published.'
      });
    }catch{
      if(admitted&&!finalizationAttempted&&uid){
        try{await finalize(false);}catch{/* unknown terminal outcome; no replay */}
      }
      return response(503,'staging_model_unavailable_no_replay',origin);
    }
  };
}
