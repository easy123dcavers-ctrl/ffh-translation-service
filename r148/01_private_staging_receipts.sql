-- FFH R148 STAGING ONLY. Never run against FFH production.
-- Durable, private, per-member request admission with no model transport.
-- No source text, user UUID, JWT, browser nonce or draft stored in these tables.
CREATE TABLE ffh_r146_sandbox.r148_hmac_key (
  key_slot text PRIMARY KEY CHECK (key_slot='r148-stage-v1'),
  key_bytes bytea NOT NULL CHECK (octet_length(key_bytes)=32)
);
INSERT INTO ffh_r146_sandbox.r148_hmac_key(key_slot,key_bytes)
  VALUES ('r148-stage-v1',extensions.gen_random_bytes(32));
CREATE TABLE ffh_r146_sandbox.r148_receipts (
  receipt_digest text PRIMARY KEY CHECK (receipt_digest ~ '^[0-9a-f]{64}$'),
  user_digest text NOT NULL CHECK (user_digest ~ '^[0-9a-f]{64}$'),
  payload_digest text NOT NULL CHECK (payload_digest ~ '^[0-9a-f]{64}$'),
  state text NOT NULL CHECK (state IN ('held','inflight','unknown','done')),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE ffh_r146_sandbox.r148_quotas (
  user_digest text NOT NULL CHECK (user_digest ~ '^[0-9a-f]{64}$'),
  window_bucket bigint NOT NULL,
  used_count integer NOT NULL CHECK (used_count BETWEEN 1 AND 3),
  PRIMARY KEY(user_digest,window_bucket)
);
ALTER TABLE ffh_r146_sandbox.r148_hmac_key ENABLE ROW LEVEL SECURITY;
ALTER TABLE ffh_r146_sandbox.r148_hmac_key FORCE ROW LEVEL SECURITY;
ALTER TABLE ffh_r146_sandbox.r148_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE ffh_r146_sandbox.r148_receipts FORCE ROW LEVEL SECURITY;
ALTER TABLE ffh_r146_sandbox.r148_quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE ffh_r146_sandbox.r148_quotas FORCE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA ffh_r146_sandbox FROM PUBLIC,anon,authenticated,ffh_r146_reader;
COMMENT ON TABLE ffh_r146_sandbox.r148_receipts IS
  'R148 STAGING ONLY. No tokens, UUIDs, plaintext or translation results. Entries are held without model dispatch.';
COMMENT ON TABLE ffh_r146_sandbox.r148_hmac_key IS
  'R148 independent staging HMAC key. DO NOT copy or reuse as the R139 production-capable receipt epoch.';
