-- FFH R151 STAGING ONLY; authenticated fixed synthetic English->Spanish test.
-- Never run on FFH production. No live recipes, PII, or drafts stored.
-- R148 HELD receipts remain immutable and unreplayed.
CREATE TABLE ffh_r146_sandbox.r151_secret (
  slot text PRIMARY KEY CHECK(slot='r151-v1'),
  hmac_key bytea NOT NULL CHECK(octet_length(hmac_key)=32)
);
INSERT INTO ffh_r146_sandbox.r151_secret(slot,hmac_key)
VALUES('r151-v1',extensions.gen_random_bytes(32));
CREATE TABLE ffh_r146_sandbox.r151_receipts (
  receipt_hash text PRIMARY KEY CHECK(receipt_hash ~ '^[0-9a-f]{64}$'),
  user_hash text NOT NULL CHECK(user_hash ~ '^[0-9a-f]{64}$'),
  status text NOT NULL CHECK(status IN('inflight','done','held')),
  created_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE TABLE ffh_r146_sandbox.r151_quotas (
  user_hash text NOT NULL CHECK(user_hash ~ '^[0-9a-f]{64}$'),
  minute_bucket bigint NOT NULL,
  used_count int NOT NULL CHECK(used_count BETWEEN 1 AND 3),
  PRIMARY KEY(user_hash,minute_bucket)
);
ALTER TABLE ffh_r146_sandbox.r151_secret ENABLE ROW LEVEL SECURITY;
ALTER TABLE ffh_r146_sandbox.r151_secret FORCE ROW LEVEL SECURITY;
ALTER TABLE ffh_r146_sandbox.r151_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE ffh_r146_sandbox.r151_receipts FORCE ROW LEVEL SECURITY;
ALTER TABLE ffh_r146_sandbox.r151_quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE ffh_r146_sandbox.r151_quotas FORCE ROW LEVEL SECURITY;
REVOKE ALL ON ffh_r146_sandbox.r151_secret,ffh_r146_sandbox.r151_receipts,ffh_r146_sandbox.r151_quotas
 FROM PUBLIC,anon,authenticated;

-- User-specific admission and quota are atomic in one SQL transaction.
CREATE FUNCTION public.ffh_r151_admit(p_nonce text)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=''
AS $body$
DECLARE
  u uuid;
  s_text text;
  sid uuid;
  acct boolean; sess boolean; profile boolean; terms boolean; role_name text;
  key bytea; user_hash text; receipt_hash text; inserted text;
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
  user_hash:=pg_catalog.encode(extensions.hmac(
      pg_catalog.convert_to('R151-USER/'||u::text,'UTF8'),key,'sha256'),'hex');
  receipt_hash:=pg_catalog.encode(extensions.hmac(
      pg_catalog.convert_to('R151-RECEIPT/'||user_hash||'/'||p_nonce,'UTF8'),key,'sha256'),'hex');
  slot:=pg_catalog.floor(pg_catalog.date_part('epoch',pg_catalog.clock_timestamp())/60)::bigint;
  BEGIN
    INSERT INTO ffh_r146_sandbox.r151_receipts(receipt_hash,user_hash,status)
      VALUES(receipt_hash,user_hash,'inflight')
      ON CONFLICT(receipt_hash) DO NOTHING RETURNING receipt_hash INTO inserted;
    IF inserted IS NULL THEN RETURN pg_catalog.jsonb_build_object('status','duplicate'); END IF;
    INSERT INTO ffh_r146_sandbox.r151_quotas(user_hash,minute_bucket,used_count)
      VALUES(user_hash,slot,1)
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

-- Only trusted staging Edge Function service_role may finalize; never a browser.
-- A successful finalization rechecks live Auth session/terms/source atomically.
CREATE FUNCTION public.ffh_r151_finish(
    p_user uuid,p_session uuid,p_nonce text,p_model_ok boolean)
RETURNS jsonb LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path=''
AS $body$
DECLARE
 acct boolean; sess boolean; profile boolean; terms boolean; role_name text;
 key bytea; user_hash text; receipt_hash text; new_state text; changed text;
BEGIN
  IF p_nonce IS NULL OR p_nonce !~ '^[A-Za-z0-9_-]{16,96}$'
  THEN RETURN pg_catalog.jsonb_build_object('status','held'); END IF;
  SELECT hmac_key INTO key FROM ffh_r146_sandbox.r151_secret WHERE slot='r151-v1';
  IF pg_catalog.octet_length(key) IS DISTINCT FROM 32
  THEN RAISE EXCEPTION 'missing staging HMAC key'; END IF;
  user_hash:=pg_catalog.encode(extensions.hmac(
      pg_catalog.convert_to('R151-USER/'||p_user::text,'UTF8'),key,'sha256'),'hex');
  receipt_hash:=pg_catalog.encode(extensions.hmac(
      pg_catalog.convert_to('R151-RECEIPT/'||user_hash||'/'||p_nonce,'UTF8'),key,'sha256'),'hex');
  SELECT account_ok,current_session_ok,has_member_profile,terms_ok,effective_role
    INTO acct,sess,profile,terms,role_name
  FROM ffh_r146_sandbox.member_status(p_user,p_session);
  new_state:=CASE WHEN p_model_ok IS TRUE AND acct IS TRUE AND sess IS TRUE
        AND profile IS TRUE AND terms IS TRUE
        AND role_name IN('member','moderator','admin','owner')
        AND ffh_r146_sandbox.safe_source('FFH R146 interface label for staging verification.') IS TRUE
    THEN 'done' ELSE 'held' END;
  UPDATE ffh_r146_sandbox.r151_receipts SET status=new_state,finished_at=now()
    WHERE receipt_hash=receipt_hash AND user_hash=user_hash AND status='inflight'
    RETURNING status INTO changed;
  -- If missing/unknown already-finished receipt: never retry or reveal a draft.
  IF changed IS NULL THEN RETURN pg_catalog.jsonb_build_object('status','not_finalized'); END IF;
  RETURN pg_catalog.jsonb_build_object('status',changed,
      'human_approved',false,'production_writes',0);
END;
$body$;
REVOKE ALL ON FUNCTION public.ffh_r151_admit(text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ffh_r151_admit(text) TO authenticated;
REVOKE ALL ON FUNCTION public.ffh_r151_finish(uuid,uuid,text,boolean)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.ffh_r151_finish(uuid,uuid,text,boolean) TO service_role;
COMMENT ON FUNCTION public.ffh_r151_finish(uuid,uuid,text,boolean)
 IS 'Only staging service_role: final Auth/terms/source recheck before release, no publication.';
