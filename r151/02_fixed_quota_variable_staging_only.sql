-- R151 targeted staging-only repair. Must match deployed unsafe source first.
DO $guard$
BEGIN
  IF pg_catalog.position('VALUES(user_hash,slot,1)' IN pg_catalog.pg_get_functiondef('public.ffh_r151_admit(text)'::regprocedure)) = 0 THEN
    RAISE EXCEPTION 'Unexpected R151 function source: stop without changing anything';
  END IF;
END;
$guard$;
CREATE OR REPLACE FUNCTION public.ffh_r151_admit(p_nonce text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=''
AS $body$
DECLARE
  u uuid;
  s_text text;
  sid uuid;
  acct boolean; sess boolean; profile boolean; terms boolean; role_name text;
  key bytea; v_user_hash text; v_receipt_hash text; inserted text;
  slot bigint; used int;
BEGIN
  u:=auth.uid();
  s_text:=auth.jwt()->>'session_id';
  IF u IS NULL OR s_text IS NULL OR s_text !~
    '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
  THEN RETURN pg_catalog.jsonb_build_object('status','unauthorized'); END IF;
  IF p_nonce IS NULL OR p_nonce !~ '^[A-Za-z0-9_-]{16,96}$'
  THEN RETURN pg_catalog.jsonb_build_object('status','bad_nonce'); END IF;
  sid:=s_text::uuid;
  SELECT account_ok,current_session_ok,has_member_profile,terms_ok,effective_role
  INTO acct,sess,profile,terms,role_name
  FROM ffh_r146_sandbox.member_status(u,sid);
  IF acct IS DISTINCT FROM true OR sess IS DISTINCT FROM true
      OR profile IS DISTINCT FROM true OR terms IS DISTINCT FROM true
      OR role_name IS NULL OR role_name NOT IN('member','moderator','admin','owner')
  THEN RETURN pg_catalog.jsonb_build_object('status','unauthorized'); END IF;
  IF ffh_r146_sandbox.safe_source('FFH R146 interface label for staging verification.')
      IS DISTINCT FROM true
  THEN RETURN pg_catalog.jsonb_build_object('status','source_held'); END IF;
  SELECT hmac_key INTO key FROM ffh_r146_sandbox.r151_secret WHERE slot='r151-v1';
  IF pg_catalog.octet_length(key) IS DISTINCT FROM 32
  THEN RAISE EXCEPTION 'missing R151 staging HMAC key'; END IF;
  v_user_hash:=pg_catalog.encode(extensions.hmac(
      pg_catalog.convert_to('R151-USER/'||u::text,'UTF8'),key,'sha256'),'hex');
  v_receipt_hash:=pg_catalog.encode(extensions.hmac(
      pg_catalog.convert_to('R151-RECEIPT/'||v_user_hash||'/'||p_nonce,'UTF8'),key,'sha256'),'hex');
  slot:=pg_catalog.floor(pg_catalog.date_part('epoch',pg_catalog.clock_timestamp())/60)::bigint;
  BEGIN
    INSERT INTO ffh_r146_sandbox.r151_receipts(receipt_hash,user_hash,status)
      VALUES(v_receipt_hash,v_user_hash,'inflight')
      ON CONFLICT(receipt_hash) DO NOTHING RETURNING receipt_hash INTO inserted;
    IF inserted IS NULL THEN RETURN pg_catalog.jsonb_build_object('status','duplicate'); END IF;
    INSERT INTO ffh_r146_sandbox.r151_quotas(user_hash,minute_bucket,used_count)
      VALUES(v_user_hash,slot,1)
      ON CONFLICT(user_hash,minute_bucket) DO UPDATE
      SET used_count=ffh_r146_sandbox.r151_quotas.used_count+1
      WHERE ffh_r146_sandbox.r151_quotas.used_count<3
      RETURNING used_count INTO used;
    IF used IS NULL THEN RAISE SQLSTATE 'P0151' USING MESSAGE='quota exceeded'; END IF;
  EXCEPTION WHEN SQLSTATE 'P0151' THEN
    RETURN pg_catalog.jsonb_build_object('status','quota_exceeded');
  END;
  RETURN pg_catalog.jsonb_build_object('status','admitted',
      'model_connected',false,'human_approved',false,'production_writes',0);
END;
$body$;

REVOKE ALL ON FUNCTION public.ffh_r151_admit(text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ffh_r151_admit(text) TO authenticated;
