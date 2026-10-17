'use strict';
// R150 staging-only hosted edge Member preflight. NO model dispatch, no receipts.
(() => {
 const btn=document.getElementById('r150');
 const status=document.getElementById('r150Status');
 if(!btn||!status)return;
 btn.addEventListener('click',async()=>{
  btn.disabled=true;
  status.textContent='Checking your current Member session on the hosted R150 broker…';
  try{
   if(typeof token!=='string'||token.length<30)throw Error('Please sign in again.');
   const response=await fetch(BASE+'/functions/v1/ffh-r150-auth-broker-stage',{
    method:'POST',
    headers:{apikey:PUB,Authorization:'Bearer '+token,'Content-Type':'application/json'},
    body:JSON.stringify({action:'preflight',source:SOURCE,target:'ja'}),
    cache:'no-store',
    redirect:'error'
   });
   if(!response.ok)throw Error('Server refused authorization (HTTP '+response.status+').');
   const result=await response.json();
   if(result.status!=='r150_authenticated_stage_ready_model_off'||
       result.model_connected!==false||result.human_approved!==false||
       result.production_writes!==0)throw Error('Unexpected broker state; STOP.');
   status.textContent='PASS: your real Android Member session reached the hosted R150 broker. Model remains OFF. No translation or publication.';
  }catch(e){
   status.textContent='R150 not yet verified: '+String(e?.message||'request failed');
  }finally{btn.disabled=false}
 });
})();
