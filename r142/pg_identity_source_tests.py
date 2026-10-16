"""R142 real PostgreSQL 16 FFH schema compatibility, all accounts FABRICATED.

NO live Auth, actual password/user records, production updates, migrations or
FFH safety project alterations. This verifies the exact structural account +
registry lookup strategy and its SQL privileges, not Supabase Auth getUser().
"""
import unittest
from r142.schema_matched import RegisteredReadOnly,NotAuthorized,AUTHORIZED_MEMBER_SQL,AUTHORIZED_NORMAL_SOURCE_SQL
from r140.pg_ephemeral_tests import conn,OWNER,OTHER,SECRET,PAYLOAD,nonce
from r139.postgres_ledger import make_staged_postgres_broker
from r136.broker import Denied
from uuid import UUID
from datetime import datetime,timezone

SESSION='00000000-0000-4000-8000-000000000031'
OTHER_SESSION='00000000-0000-4000-8000-000000000032'
TEXT='Ferment the diced vegetables in a clean container.'
SOURCE_HASH='b'*64
TERMS='2026-09-17-v1'

def build_schema():
    with conn('postgres') as db:
        with db.cursor() as c:
            c.execute('CREATE SCHEMA auth')
            c.execute('REVOKE ALL ON SCHEMA auth FROM PUBLIC')
            c.execute('''CREATE TABLE auth.users (
              id uuid PRIMARY KEY, email_confirmed_at timestamptz,
              is_anonymous boolean, deleted_at timestamptz, banned_until timestamptz)''')
            c.execute('''CREATE TABLE auth.sessions(
              id uuid PRIMARY KEY,user_id uuid REFERENCES auth.users(id),
              not_after timestamptz)''')
            c.execute('CREATE TABLE public.ffh_member_profiles (user_id uuid PRIMARY KEY)')
            c.execute('''CREATE TABLE public.ffh_terms_acceptances
              (user_id uuid NOT NULL,terms_version text NOT NULL,
               PRIMARY KEY(user_id,terms_version))''')
            c.execute('''CREATE TABLE public.ffh_staff_roles
              (user_id uuid PRIMARY KEY,role text NOT NULL,active boolean NOT NULL)''')
            c.execute('''CREATE TABLE public.ffh_translation_memory
              (source_hash text PRIMARY KEY,source_text text NOT NULL,
               source_class text,is_safety_critical boolean)''')
            c.execute('''CREATE TABLE public.ffh_translation_accuracy_review
              (source_hash text PRIMARY KEY,translation_gate text)''')
            c.execute('''CREATE TABLE public.ffh_translation_protected_source_overrides
              (source_hash text PRIMARY KEY)''')
            c.execute("""CREATE FUNCTION public.ffh_current_terms_version()
              RETURNS text LANGUAGE sql IMMUTABLE
              AS $$ SELECT '2026-09-17-v1'::text $$""")
            # Conservative TEST subset of real FFH text safety matcher.
            c.execute("""CREATE FUNCTION public.ffh_translation_learning_is_safety_text(p_text text)
              RETURNS boolean LANGUAGE sql IMMUTABLE AS
              $$ SELECT coalesce(p_text ~* '(unsafe|pressure|botuli|pathogen|mou?ld)',false) $$""")
            for func in ("ffh_current_terms_version()",
                         "ffh_translation_learning_is_safety_text(text)"):
                c.execute(f'REVOKE ALL ON FUNCTION public.{func} FROM PUBLIC')
                c.execute(f'GRANT EXECUTE ON FUNCTION public.{func} TO ffh_r140_reader')
            c.execute('GRANT USAGE ON SCHEMA auth TO ffh_r140_reader')
            c.execute('''GRANT SELECT (id,email_confirmed_at,is_anonymous,deleted_at,banned_until)
                         ON auth.users TO ffh_r140_reader''')
            c.execute('''GRANT SELECT (id,user_id,not_after)
                         ON auth.sessions TO ffh_r140_reader''')
            for table in ('ffh_member_profiles','ffh_terms_acceptances',
                          'ffh_staff_roles','ffh_translation_memory',
                          'ffh_translation_accuracy_review',
                          'ffh_translation_protected_source_overrides'):
                c.execute(f'GRANT SELECT ON public.{table} TO ffh_r140_reader')
                c.execute(f'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY')
                c.execute(f'''CREATE POLICY r142_reader_select ON public.{table}
                          FOR SELECT TO ffh_r140_reader USING (true)''')
            db.commit()

class RealSchemaTests(unittest.TestCase):
    def setUp(self):
        with conn('postgres') as db:
            c=db.cursor()
            c.execute('''TRUNCATE auth.sessions,auth.users,
                public.ffh_member_profiles,public.ffh_terms_acceptances,
                public.ffh_staff_roles,public.ffh_translation_memory,
                public.ffh_translation_accuracy_review,
                public.ffh_translation_protected_source_overrides,
                ffh_broker_private.receipts,ffh_broker_private.quota_windows''')
            c.execute("INSERT INTO auth.users VALUES (%s,now(),false,NULL,NULL)",(OWNER,))
            c.execute("INSERT INTO auth.sessions VALUES (%s,%s,NULL)",(SESSION,OWNER))
            c.execute("INSERT INTO public.ffh_member_profiles VALUES (%s)",(OWNER,))
            c.execute("INSERT INTO public.ffh_terms_acceptances VALUES (%s,%s)",(OWNER,TERMS))
            c.execute("INSERT INTO public.ffh_translation_memory VALUES (%s,%s,'ui',false)",
                      (SOURCE_HASH,TEXT))
            c.execute("INSERT INTO public.ffh_translation_accuracy_review VALUES (%s,'normal')",
                      (SOURCE_HASH,))
            db.commit()
        self.reader=RegisteredReadOnly(lambda:conn('ffh_r140_reader'))
    def admin(self,sql,params=()):
        with conn('postgres') as db:
            result=db.execute(sql,params)
            if result.description:return result.fetchall()
    def user(self):
        return self.reader.member(OWNER,SESSION)
    def source(self,text=TEXT):
        return self.reader.source(text)
    def test_01_good_member(self):
        self.assertEqual(self.user().role,'Member')
    def test_02_banned_account_denied(self):
        self.admin("UPDATE auth.users SET banned_until=now()+interval '5 days'")
        self.assertIsNone(self.user())
    def test_03_expired_ban_allowed(self):
        self.admin("UPDATE auth.users SET banned_until=now()-interval '1 minute'")
        self.assertEqual(self.user().role,'Member')
    def test_04_deleted_account_denied(self):
        self.admin('UPDATE auth.users SET deleted_at=now()')
        self.assertIsNone(self.user())
    def test_05_anonymous_account_denied(self):
        self.admin('UPDATE auth.users SET is_anonymous=true')
        self.assertIsNone(self.user())
    def test_06_email_not_verified_denied(self):
        self.admin('UPDATE auth.users SET email_confirmed_at=NULL')
        self.assertIsNone(self.user())
    def test_07_missing_auth_session_denied(self):
        self.admin('DELETE FROM auth.sessions')
        self.assertIsNone(self.user())
    def test_08_wrong_session_for_user_denied(self):
        self.assertIsNone(self.reader.member(OWNER,OTHER_SESSION))
    def test_09_expired_session_denied(self):
        self.admin("UPDATE auth.sessions SET not_after=now()-interval '1 second'")
        self.assertIsNone(self.user())
    def test_10_current_session_allowed(self):
        self.admin("UPDATE auth.sessions SET not_after=now()+interval '1 hour'")
        self.assertEqual(self.user().role,'Member')
    def test_11_missing_profile_denied(self):
        self.admin('DELETE FROM public.ffh_member_profiles')
        self.assertIsNone(self.user())
    def test_12_missing_terms_denied(self):
        self.admin('DELETE FROM public.ffh_terms_acceptances')
        self.assertIsNone(self.user())
    def test_13_outdated_terms_denied(self):
        self.admin("UPDATE public.ffh_terms_acceptances SET terms_version='old'")
        self.assertIsNone(self.user())
    def test_14_active_moderator(self):
        self.admin("INSERT INTO public.ffh_staff_roles VALUES (%s,'moderator',true)",(OWNER,))
        self.assertEqual(self.user().role,'Moderator')
    def test_15_active_owner(self):
        self.admin("INSERT INTO public.ffh_staff_roles VALUES (%s,'owner',true)",(OWNER,))
        self.assertEqual(self.user().role,'Owner')
    def test_16_inactive_staff_becomes_member(self):
        self.admin("INSERT INTO public.ffh_staff_roles VALUES (%s,'admin',false)",(OWNER,))
        self.assertEqual(self.user().role,'Member')
    def test_17_untrusted_uuid_rejected(self):
        with self.assertRaises(NotAuthorized):self.reader.member("invalid;DROP",SESSION)
    def test_18_untrusted_session_rejected(self):
        with self.assertRaises(NotAuthorized):self.reader.member(OWNER,"invalid")
    def test_19_no_arbitrary_sql(self):
        with self.assertRaises(NotAuthorized):
            self.reader.fetch('SELECT * FROM auth.users',(),1)
    def test_20_readonly_cannot_change_auth(self):
        with self.assertRaises(Exception):
            with conn('ffh_r140_reader') as db:db.execute("DELETE FROM auth.users")
    def test_21_readonly_cannot_change_registry(self):
        with self.assertRaises(Exception):
            with conn('ffh_r140_reader') as db:
                db.execute('DELETE FROM public.ffh_translation_memory')
    def test_22_safe_source(self):
        self.assertTrue(self.source().allowed)
    def test_23_unregistered_source(self):
        self.assertFalse(self.source('fabricated absent English').allowed)
    def test_24_duplicate_source_denied(self):
        self.admin("INSERT INTO public.ffh_translation_memory VALUES (%s,%s,'ui',false)",
                   ('c'*64,TEXT))
        self.assertFalse(self.source().allowed)
    def test_25_safety_flag_denied(self):
        self.admin('UPDATE public.ffh_translation_memory SET is_safety_critical=true')
        self.assertFalse(self.source().allowed)
    def test_26_null_safety_flag_denied(self):
        self.admin('UPDATE public.ffh_translation_memory SET is_safety_critical=NULL')
        self.assertFalse(self.source().allowed)
    def test_27_override_protected_denied(self):
        self.admin('INSERT INTO public.ffh_translation_protected_source_overrides VALUES (%s)',(SOURCE_HASH,))
        self.assertFalse(self.source().allowed)
    def test_28_non_normal_gate_denied(self):
        self.admin("UPDATE public.ffh_translation_accuracy_review SET translation_gate='safety_review_required'")
        self.assertFalse(self.source().allowed)
    def test_29_missing_review_gate_denied(self):
        self.admin('DELETE FROM public.ffh_translation_accuracy_review')
        self.assertFalse(self.source().allowed)
    def test_30_bad_source_class_denied(self):
        self.admin("UPDATE public.ffh_translation_memory SET source_class='special'")
        self.assertFalse(self.source().allowed)
    def test_31_conservative_safety_text_denied(self):
        self.admin("UPDATE public.ffh_translation_memory SET source_text='pressure unsafe'")
        self.assertFalse(self.source('pressure unsafe').allowed)
    def test_32_unknown_role_value_downgrades_member(self):
        self.admin("INSERT INTO public.ffh_staff_roles VALUES (%s,'fabricated_admin',true)",(OWNER,))
        self.assertEqual(self.user().role,'Member')
    def test_33_fabricated_member_broker_receipt_and_held(self):
        hits=[]
        broker=make_staged_postgres_broker(
            lambda bearer:self.user() if bearer=='synthetic-local-proof' else None,
            self.source,
            lambda target,text:(hits.append(1) or {
                'status':'held','human_approved':False,'production_writes':0}),
            lambda:conn('ffh_r140_writer'),SECRET)
        request={'source':'en','target':'fr','text':TEXT,'request_id':nonce(1)}
        self.assertEqual(broker.submit('synthetic-local-proof',request)['status'],'held')
        self.assertEqual(len(hits),1)
        with self.assertRaises(Denied) as e:broker.submit('synthetic-local-proof',request)
        self.assertEqual(e.exception.status,409)
        self.assertEqual(len(hits),1)
    def test_34_fabricated_member_broker_banned_denied_before_ledger(self):
        self.admin("UPDATE auth.users SET banned_until=now()+interval '5 days'")
        hits=[]
        broker=make_staged_postgres_broker(
            lambda bearer:self.user(),self.source,
            lambda target,text:hits.append(1),
            lambda:conn('ffh_r140_writer'),SECRET)
        with self.assertRaises(Denied):
            broker.submit('synthetic-local-proof',
                {'source':'en','target':'ko','text':TEXT,'request_id':nonce(1)})
        self.assertEqual(hits,[])
        self.assertEqual(self.admin('SELECT count(*) FROM ffh_broker_private.receipts'),[(0,)])
    def test_35_fabricated_member_broker_safety_denied_before_ledger(self):
        self.admin('INSERT INTO public.ffh_translation_protected_source_overrides VALUES (%s)',(SOURCE_HASH,))
        hits=[]
        broker=make_staged_postgres_broker(lambda t:self.user(),self.source,
            lambda target,text:hits.append(1),lambda:conn('ffh_r140_writer'),SECRET)
        with self.assertRaises(Denied) as e:
            broker.submit('synthetic-local-proof',
                {'source':'en','target':'ko','text':TEXT,'request_id':nonce(1)})
        self.assertEqual(e.exception.status,422)
        self.assertEqual(hits,[])
        self.assertEqual(self.admin('SELECT count(*) FROM ffh_broker_private.receipts'),[(0,)])
    def test_36_reader_cannot_see_broker_receipts(self):
        with self.assertRaises(Exception):
            with conn('ffh_r140_reader') as db:
                db.execute('SELECT * FROM ffh_broker_private.receipts')
