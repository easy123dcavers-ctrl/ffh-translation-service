-- R148 staging-only logged-in request admission. DOES NOT run translator.
-- Security: JWT/user/session from Supabase itself; no client-controlled UID/role.
CREATE FUNCTION public.ffh_r148_stage_admit(
 p_source text, p_target text, p_nonce text
) RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=''
AS $r148$
DECLARE
 v_uid uuid;
 v_session_str text;
 v_session uuid;
 v_account boolean;
 v_live boolean;
 v_profile boolean;
 v_terms boolean;
 v_role text;
 v_secret bytea;
 v_user_digest text;
 v_receipt_digest text;
 v_payload_digest text;
 v_inserted text;
 v_count integer;
 v_bucket bigint;
BEGIN
 v_uid := auth.uid();
 IF v_uid IS NULL THEN
  RETURN pg_catalog.jsonb_build_object('status','denied','model_connected',false);
 END IF;
 v_session_str := auth.jwt()->>'session_id';
 IF v_session_str IS NULL OR v_session_str !~
 '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' THEN
  RETURN pg_catalog.jsonb_build_object('status','denied','model_connected',false);
 END IF;
 v_session := v_session_str::uuid;
 SELECT account_ok,current_session_ok,has_member_profile,terms_ok,effective_role
 INTO v_account,v_live,v_profile,v_terms,v_role
 FROM ffh_r146_sandbox.member_status(v_uid,v_session);
 IF v_account IS DISTINCT FROM true OR v_live IS DISTINCT FROM true
  OR v_profile IS DISTINCT FROM true OR v_terms IS DISTINCT FROM true
  OR v_role IS NULL OR v_role NOT IN ('member','moderator','admin','owner') THEN
  RETURN pg_catalog.jsonb_build_object('status','denied','model_connected',false);
 END IF;
 IF p_source IS NULL OR pg_catalog.length(p_source)<1
  OR pg_catalog.length(p_source)>500 OR p_source<>pg_catalog.btrim(p_source)
  OR p_source ~ '[[:cntrl:]]' OR
  NOT COALESCE(ffh_r146_sandbox.safe_source(p_source),false) THEN
  RETURN pg_catalog.jsonb_build_object('status','source_held','model_connected',false);
 END IF;
 IF p_target IS NULL OR p_target NOT IN ('es','fr','ja','de','ar','tl','ko','vi','zh') THEN
  RETURN pg_catalog.jsonb_build_object('status','unsupported_target','model_connected',false);
 END IF;
 IF p_nonce IS NULL OR p_nonce !~ '^[A-Za-z0-9_-]{16,96}$' THEN
  RETURN pg_catalog.jsonb_build_object('status','invalid_request_id','model_connected',false);
 END IF;
 SELECT key_bytes INTO v_secret FROM ffh_r146_sandbox.r148_hmac_key
 WHERE key_slot='r148-stage-v1';
 IF pg_catalog.octet_length(v_secret) IS DISTINCT FROM 32 THEN
  RAISE EXCEPTION 'R148 private staging key missing';
 END IF;
 v_user_digest:=pg_catalog.encode(extensions.hmac(
    pg_catalog.convert_to('ffh-r148-user:','UTF8') ||
    pg_catalog.convert_to(v_uid::text,'UTF8'),v_secret,'sha256'),'hex');
 v_receipt_digest:=pg_catalog.encode(extensions.hmac(
    pg_catalog.convert_to('ffh-r148-receipt:','UTF8') ||
    pg_catalog.decode(v_user_digest,'hex') ||
    pg_catalog.decode('00','hex') ||
    pg_catalog.convert_to(p_nonce,'UTF8'),v_secret,'sha256'),'hex');
 v_payload_digest:=pg_catalog.encode(extensions.hmac(
    pg_catalog.convert_to('ffh-r148-payload:','UTF8') ||
    pg_catalog.convert_to(p_target,'UTF8') ||
    pg_catalog.decode('00','hex') ||
    pg_catalog.convert_to(p_source,'UTF8'),v_secret,'sha256'),'hex');
 v_bucket:=pg_catalog.floor(pg_catalog.extract(epoch from pg_catalog.clock_timestamp())/60)::bigint;
 -- PL/pgSQL inner exception block is a subtransaction. When quota rejects,
 -- receipt INSERT is rolled back too. Atomic uniqueness prevents double admission.
 BEGIN
  INSERT INTO ffh_r146_sandbox.r148_receipts(
    receipt_digest,user_digest,payload_digest,state)
  VALUES(v_receipt_digest,v_user_digest,v_payload_digest,'held')
  ON CONFLICT(receipt_digest) DO NOTHING
  RETURNING receipt_digest INTO v_inserted;
  IF v_inserted IS NULL THEN
   RETURN pg_catalog.jsonb_build_object('status','duplicate','model_connected',false);
  END IF;
  INSERT INTO ffh_r146_sandbox.r148_quotas(user_digest,window_bucket,used_count)
   VALUES(v_user_digest,v_bucket,1)
   ON CONFLICT(user_digest,window_bucket) DO UPDATE
    SET used_count=ffh_r146_sandbox.r148_quotas.used_count+1
    WHERE ffh_r146_sandbox.r148_quotas.used_count<3
  RETURNING used_count INTO v_count;
  IF v_count IS NULL THEN
   RAISE SQLSTATE 'P0148' USING MESSAGE='R148_QUOTA_ROLLBACK';
  END IF;
 EXCEPTION WHEN SQLSTATE 'P0148' THEN
  RETURN pg_catalog.jsonb_build_object('status','quota_exceeded','model_connected',false);
 END;
 RETURN pg_catalog.jsonb_build_object(
  'status','staging_held','no_replay',true,
  'human_approved',false,'production_writes',0,
  'model_connected',false);
END;
$r148$;
REVOKE ALL ON FUNCTION public.ffh_r148_stage_admit(text,text,text)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ffh_r148_stage_admit(text,text,text)
 TO authenticated;
COMMENT ON FUNCTION public.ffh_r148_stage_admit(text,text,text) IS
'R148 strictly staging-only, authenticated source-allowlisted HMAC receipt and atomic quota; ALWAYS held, never dispatches translation; no plaintext persisted.';