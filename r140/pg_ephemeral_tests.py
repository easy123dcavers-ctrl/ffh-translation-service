"""R140 REAL PostgreSQL 16; temporary CI database only, no FFH production."""
import concurrent.futures,os,subprocess,sys,unittest
from r140.pg_real import Ledger,Key,Denied,OWNER,OTHER,SECRET,PAYLOAD
DB='ffh_r140_ephemeral'
def conn(role='ffh_r140_writer'):
    if os.getenv('FFH_R140_EPHEMERAL_ONLY')!='1':raise RuntimeError('ephemeral only')
    if role not in ('ffh_r140_writer','ffh_r140_reader','postgres'):raise ValueError('role')
    import psycopg
    password={'ffh_r140_writer':'r140_writer_ci_fake_only',
              'ffh_r140_reader':'r140_reader_ci_fake_only',
              'postgres':'r140_pg_ci_fake_only'}[role]
    return psycopg.connect(host='127.0.0.1',port=5432,dbname=DB,
                           user=role,password=password,connect_timeout=4)
def setup():
    if os.getenv('FFH_R140_EPHEMERAL_ONLY')!='1':raise RuntimeError('not CI')
    with conn('postgres') as db:
        with db.cursor() as cur:
            cur.execute('CREATE SCHEMA ffh_broker_private')
            cur.execute('REVOKE ALL ON SCHEMA ffh_broker_private FROM PUBLIC')
            cur.execute('CREATE TABLE ffh_broker_private.key_registry (version int PRIMARY KEY,key_fingerprint text NOT NULL)')
            cur.execute("""CREATE TABLE ffh_broker_private.receipts
              (receipt_digest text PRIMARY KEY,user_digest text NOT NULL,
               payload_digest text NOT NULL,state text NOT NULL
               CHECK(state IN ('inflight','unknown','held','done')),
               created_at timestamptz NOT NULL DEFAULT now(),finished_at timestamptz)""")
            cur.execute("""CREATE TABLE ffh_broker_private.quota_windows
              (user_digest text NOT NULL,window_bucket bigint NOT NULL,
               used_count integer NOT NULL CHECK(used_count>=1 AND used_count<=100),
               PRIMARY KEY(user_digest,window_bucket))""")
            cur.execute('REVOKE ALL ON ALL TABLES IN SCHEMA ffh_broker_private FROM PUBLIC')
            from psycopg import sql
            for role,pw in [('ffh_r140_writer','r140_writer_ci_fake_only'),
                            ('ffh_r140_reader','r140_reader_ci_fake_only')]:
                cur.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {}').format(
                    sql.Identifier(role),sql.Literal(pw)))
            cur.execute('GRANT USAGE ON SCHEMA ffh_broker_private TO ffh_r140_writer')
            cur.execute('GRANT SELECT ON ffh_broker_private.key_registry TO ffh_r140_writer')
            cur.execute("""GRANT INSERT (receipt_digest,user_digest,payload_digest,state),
                SELECT (receipt_digest),UPDATE (state,finished_at)
                ON ffh_broker_private.receipts TO ffh_r140_writer""")
            cur.execute("""GRANT INSERT (user_digest,window_bucket,used_count),
                SELECT (user_digest,window_bucket,used_count),UPDATE (used_count)
                ON ffh_broker_private.quota_windows TO ffh_r140_writer""")
            for name in ('receipts','quota_windows'):
                cur.execute(f'ALTER TABLE ffh_broker_private.{name} ENABLE ROW LEVEL SECURITY')
                cur.execute(f'''CREATE POLICY ci_writer_policy
                    ON ffh_broker_private.{name} FOR ALL
                    TO ffh_r140_writer USING (true) WITH CHECK (true)''')
            cur.execute('INSERT INTO ffh_broker_private.key_registry VALUES (1,%s)',
                        (Key(SECRET).marker(),))
            cur.execute('CREATE TABLE public.ffh_r140_sensitive_fixture (id int PRIMARY KEY)')
            cur.execute('INSERT INTO public.ffh_r140_sensitive_fixture VALUES (1)')
def nonce(i):return f'r140_verified_{i:016d}'
class PgIntegration(unittest.TestCase):
    def setUp(self):
        with conn('postgres') as db:
            db.execute('TRUNCATE ffh_broker_private.receipts,ffh_broker_private.quota_windows')
        self.ledger=Ledger(conn)
    def rows(self,sql):
        with conn('postgres') as db:return db.execute(sql).fetchall()
    def test_01_insert_finalize(self):
        self.ledger.admission(OWNER,nonce(1));self.ledger.finish(OWNER,nonce(1),'done')
        self.assertEqual(self.rows('SELECT state FROM ffh_broker_private.receipts'),[('done',)])
    def test_02_duplicate_restart(self):
        self.ledger.admission(OWNER,nonce(1))
        with self.assertRaises(Denied) as x:Ledger(conn).admission(OWNER,nonce(1))
        self.assertEqual(x.exception.status,409)
    def test_03_exact_quota(self):
        for i in range(3):self.ledger.admission(OWNER,nonce(i))
        with self.assertRaises(Denied) as x:self.ledger.admission(OWNER,nonce(3))
        self.assertEqual(x.exception.status,429)
        self.assertEqual(self.rows('SELECT count(*) FROM ffh_broker_private.receipts')[0][0],3)
        self.assertEqual(self.rows('SELECT used_count FROM ffh_broker_private.quota_windows')[0][0],3)
    def test_04_16_connection_duplicate(self):
        def task(i):
            try:Ledger(conn).admission(OWNER,nonce(0));return 200
            except Denied as err:return err.status
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            result=list(pool.map(task,range(16)))
        self.assertEqual(result.count(200),1)
        self.assertEqual(result.count(409),15)
    def test_05_16_connection_quota(self):
        def task(i):
            try:Ledger(conn).admission(OWNER,nonce(i));return 200
            except Denied as err:return err.status
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            result=list(pool.map(task,range(16)))
        self.assertEqual(result.count(200),3)
        self.assertEqual(result.count(429),13)
    def test_06_user_isolation(self):
        for i in range(3):self.ledger.admission(OWNER,nonce(i))
        self.ledger.admission(OTHER,nonce(1))
        self.assertEqual(self.rows('SELECT count(*) FROM ffh_broker_private.receipts')[0][0],4)
    def test_07_hmac_only_at_rest(self):
        self.ledger.admission(OWNER,nonce(1))
        data=str(self.rows('SELECT * FROM ffh_broker_private.receipts'))
        for v in (OWNER,nonce(1),PAYLOAD):self.assertNotIn(v,data)
    def test_08_unknown_and_double_finalization(self):
        self.ledger.admission(OWNER,nonce(1));self.ledger.finish(OWNER,nonce(1),'unknown')
        with self.assertRaises(Denied) as x:self.ledger.finish(OWNER,nonce(1),'done')
        self.assertEqual(x.exception.status,503)
        with self.assertRaises(Denied) as x:self.ledger.admission(OWNER,nonce(1))
        self.assertEqual(x.exception.status,409)
    def test_09_key_change_refused(self):
        wrong=Ledger(conn,secret=b'wrong_r140_ci_epoch_only_0000000000000000')
        with self.assertRaises(Denied) as x:wrong.admission(OWNER,nonce(1))
        self.assertEqual(x.exception.status,503)
        self.assertFalse(self.rows('SELECT * FROM ffh_broker_private.receipts'))
    def test_10_no_reviewed_state(self):
        self.ledger.admission(OWNER,nonce(1))
        with self.assertRaises(ValueError):self.ledger.finish(OWNER,nonce(1),'reviewed')
    def test_11_reader_denied_private(self):
        with conn('ffh_r140_reader') as db:
            with self.assertRaises(Exception):
                db.execute('SELECT * FROM ffh_broker_private.receipts')
    def test_12_writer_denied_public_sensitive(self):
        with conn() as db:
            with self.assertRaises(Exception):
                db.execute('SELECT * FROM public.ffh_r140_sensitive_fixture')
    def test_13_writer_cannot_delete(self):
        self.ledger.admission(OWNER,nonce(1))
        with conn() as db:
            with self.assertRaises(Exception):
                db.execute('DELETE FROM ffh_broker_private.receipts')
    def test_14_writer_cannot_read_payload_column(self):
        self.ledger.admission(OWNER,nonce(1))
        with conn() as db:
            with self.assertRaises(Exception):
                db.execute('SELECT payload_digest FROM ffh_broker_private.receipts')
    def test_15_writer_cannot_create_public_table(self):
        with conn() as db:
            with self.assertRaises(Exception):
                db.execute('CREATE TABLE public.ffh_r140_injected (x int)')
    def test_16_reader_cannot_change_key_epoch(self):
        with conn('ffh_r140_reader') as db:
            with self.assertRaises(Exception):
                db.execute("UPDATE ffh_broker_private.key_registry SET key_fingerprint='x'")
    def test_17_real_child_process_crash_tombstone(self):
        script='from r140.pg_ephemeral_tests import conn,nonce;from r140.pg_real import Ledger,OWNER;import os;Ledger(conn).admission(OWNER,nonce(5));os._exit(29)'
        proc=subprocess.run([sys.executable,'-c',script],cwd=os.getcwd(),env=os.environ.copy(),
                            capture_output=True,timeout=18)
        self.assertEqual(proc.returncode,29,repr(proc.stderr))
        with self.assertRaises(Denied) as x:self.ledger.admission(OWNER,nonce(5))
        self.assertEqual(x.exception.status,409)
    def test_18_writer_cannot_rotate_key(self):
        with conn() as db:
            with self.assertRaises(Exception):
                db.execute("UPDATE ffh_broker_private.key_registry SET key_fingerprint='x'")
    def test_19_invalid_nonce_no_write(self):
        with self.assertRaises(ValueError):self.ledger.admission(OWNER,'short')
        self.assertFalse(self.rows('SELECT * FROM ffh_broker_private.receipts'))
    def test_20_window_uses_server_clock(self):
        self.ledger.admission(OWNER,nonce(1))
        self.assertGreater(self.rows('SELECT window_bucket FROM ffh_broker_private.quota_windows')[0][0],0)
if __name__=='__main__':
    setup();unittest.main()
