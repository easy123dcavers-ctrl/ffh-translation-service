/**
 * FFH R150 STAGING ONLY — hosted no-model auth broker boundary.
 * Pure JS used unmodified by Node security tests and Deno Edge entrypoint.
 * The only upstream URLs are pinned to the isolated Supabase staging project.
 * Does NOT ingest, generate, translate, publish, or consume receipts.
 */
export const STAGING = 'https://hlsjzjnondimwhqbgjqm.supabase.co';
export const PAGES = 'https://easy123dcavers-ctrl.github.io';
export const TARGETS = new Set(['es','fr','ja','de','ar','tl','ko','vi','zh']);
const AUTH = STAGING+'/auth/v1/user';
const PREFLIGHT = STAGING+'/rest/v1/rpc/ffh_r147_member_preflight';
const MAX_BODY = 2048;

function respond(status, label, origin=null) {
  const headers = {
    'Content-Type':'application/json; charset=utf-8',
    'Cache-Control':'no-store, private, max-age=0',
    'Pragma':'no-cache',
    'X-Content-Type-Options':'nosniff',
    'Referrer-Policy':'no-referrer',
    'Vary':'Origin',
  };
  if (origin===PAGES) {
    headers['Access-Control-Allow-Origin']=PAGES;
    headers['Access-Control-Allow-Methods']='POST, OPTIONS';
    headers['Access-Control-Allow-Headers']='authorization,content-type,apikey';
    headers['Access-Control-Max-Age']='60';
  }
  if(status===204) return new Response(null,{status,headers});
  return new Response(JSON.stringify({status:label,model_connected:false,
    production_writes:0,human_approved:false}),{status,headers});
}

async function boundedBody(req) {
  const length=req.headers.get('content-length');
  if(length!==null && (!/^\d+$/.test(length)||Number(length)>MAX_BODY)) return null;
  if(!req.body) return null;
  const reader=req.body.getReader();
  let total=0, parts=[];
  try {
    for (;;) {
      const {done,value}=await reader.read();
      if(done) break;
      total+=value.byteLength;
      if(total>MAX_BODY) return null;
      parts.push(value);
    }
  } finally { reader.releaseLock(); }
  if(!total) return null;
  const buf=new Uint8Array(total);
  let offset=0;
  for(const x of parts){buf.set(x,offset);offset+=x.byteLength;}
  return new TextDecoder('utf-8',{fatal:true}).decode(buf);
}

async function smallJsonResponse(resp,bytes=4096) {
  if(!resp.ok || resp.redirected) return null;
  if(!(resp.headers.get('content-type')||'').toLowerCase().includes('application/json')) return null;
  const length=resp.headers.get('content-length');
  if(length!==null && Number(length)>bytes) return null;
  const reader=resp.body?.getReader();
  if(!reader)return null;
  const chunks=[];let n=0;
  try {for (;;) {
    const {done,value}=await reader.read();
    if(done)break;
    n+=value.byteLength;if(n>bytes)return null;
    chunks.push(value);
  }}finally{reader.releaseLock();}
  const buffer=new Uint8Array(n);let offset=0;
  for(const x of chunks){buffer.set(x,offset);offset+=x.byteLength;}
  try {return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(buffer));}
  catch{return null;}
}

export function createR150Handler({publishableKey,fetchImpl=fetch,timeoutMs=4000}={}) {
  if(typeof publishableKey!=='string' || !/^sb_publishable_[a-zA-Z0-9_-]{12,}$/.test(publishableKey)) {
    throw new Error('A project-scoped public staging publishable key is required');
  }
  if(typeof fetchImpl!=='function'|| !Number.isInteger(timeoutMs)||timeoutMs<500||timeoutMs>5000) {
    throw new Error('Invalid fixed-staging fetch adapter / timeout');
  }
  return async function handler(req) {
    const origin=req.headers.get('origin');
    if(origin!==null && origin!==PAGES) return respond(403,'origin_denied');
    if(req.method==='OPTIONS') return respond(204,'',origin);
    if(req.method!=='POST') return respond(405,'method_not_allowed',origin);
    const bearer=req.headers.get('authorization');
    if(!bearer||bearer.length>8200 || !/^Bearer [A-Za-z0-9._-]{30,8192}$/.test(bearer)) {
      return respond(401,'not_authenticated',origin);
    }
    if(!(req.headers.get('content-type')||'').toLowerCase().startsWith('application/json')) {
      return respond(415,'json_required',origin);
    }
    let parsed;
    try {const raw=await boundedBody(req);parsed=raw?JSON.parse(raw):null;}
    catch{return respond(400,'invalid_json',origin);}
    if(!parsed || typeof parsed!=='object' || Array.isArray(parsed) ||
       Object.keys(parsed).sort().join(',')!=='action,source,target' ||
       parsed.action!=='preflight' ||typeof parsed.source!=='string' ||
       parsed.source.length<1||parsed.source.length>500||
       parsed.source.trim()!==parsed.source||/[\x00-\x1f\x7f]/.test(parsed.source) ||
       typeof parsed.target!=='string' || !TARGETS.has(parsed.target)) {
      return respond(400,'invalid_preflight_input',origin);
    }
    const fixedHeaders={apikey:publishableKey,Authorization:bearer,Accept:'application/json'};
    try {
      const remote = async (url,opts={}) => {
        const response=await fetchImpl(url,{...opts,
          headers:{...fixedHeaders,...opts.headers},redirect:'error',cache:'no-store',
          signal:AbortSignal.timeout(timeoutMs)});
        return smallJsonResponse(response);
      };
      const user=await remote(AUTH);
      if(!user||typeof user.id!=='string'||user.id.length!==36||user.is_anonymous===true) {
        return respond(401,'member_auth_failed',origin);
      }
      const verdict=await remote(PREFLIGHT,{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({p_source:parsed.source,p_target:parsed.target})});
      if(!verdict || verdict.status!=='authorized_preflight_only'||
         verdict.source_eligible!==true ||verdict.target_supported!==true ||
         verdict.model_connected!==false) {
        return respond(403,'member_or_source_denied',origin);
      }
      // No Render hostname, API key or protected model token exists in this module.
      // R150 intentionally cannot dispatch, create a request ledger entry or publish.
      return respond(200,'r150_authenticated_stage_ready_model_off',origin);
    } catch {
      // Fail closed even if Auth/PostgREST times out or redirects.
      return respond(503,'staging_auth_unavailable',origin);
    }
  };
}