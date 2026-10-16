"""Disposable FFH authorization/source tables adjacent to real GoTrue auth.*."""
import os
from r140.pg_ephemeral_tests import conn
def setup():
    if os.getenv("FFH_R143_EPHEMERAL_ONLY")!="1":
        raise RuntimeError("production not allowed")
    with conn("postgres") as db:
        with db.cursor() as c:
            for table in ("users","sessions"):
                c.execute("""SELECT count(*) FROM information_schema.tables
                   WHERE table_schema='auth' AND table_name=%s""",(table,))
                if c.fetchone()[0]!=1:raise RuntimeError("GoTrue auth migration missing")
            c.execute("CREATE TABLE public.ffh_member_profiles (user_id uuid PRIMARY KEY)")
            c.execute("""CREATE TABLE public.ffh_terms_acceptances(
                user_id uuid,terms_version text,PRIMARY KEY(user_id,terms_version))""")
            c.execute("""CREATE TABLE public.ffh_staff_roles (
                user_id uuid PRIMARY KEY,role text,active boolean)""")
            c.execute("""CREATE TABLE public.ffh_translation_memory (
                source_hash text PRIMARY KEY,source_text text NOT NULL,
                source_class text,is_safety_critical boolean)""")
            c.execute("""CREATE TABLE public.ffh_translation_accuracy_review (
                source_hash text PRIMARY KEY,translation_gate text)""")
            c.execute("""CREATE TABLE public.ffh_translation_protected_source_overrides (
                source_hash text PRIMARY KEY)""")
            c.execute("""CREATE FUNCTION public.ffh_current_terms_version()
                RETURNS text LANGUAGE sql IMMUTABLE
                AS $$ SELECT '2026-09-17-v1'::text $$""")
            c.execute("""CREATE FUNCTION public.ffh_translation_learning_is_safety_text(p_text text)
                RETURNS boolean LANGUAGE sql IMMUTABLE
                AS $$ SELECT coalesce(p_text ~* '(unsafe|pressure|botuli|pathogen|mou?ld)',false) $$""")
            for fn in ("ffh_current_terms_version()",
                        "ffh_translation_learning_is_safety_text(text)"):
                c.execute(f"REVOKE ALL ON FUNCTION public.{fn} FROM PUBLIC")
                c.execute(f"GRANT EXECUTE ON FUNCTION public.{fn} TO ffh_r140_reader")
            c.execute("GRANT USAGE ON SCHEMA auth TO ffh_r140_reader")
            c.execute("""GRANT SELECT (id,email_confirmed_at,is_anonymous,deleted_at,banned_until)
                    ON auth.users TO ffh_r140_reader""")
            c.execute("""GRANT SELECT (id,user_id,not_after)
                    ON auth.sessions TO ffh_r140_reader""")
            for table in ("ffh_member_profiles","ffh_terms_acceptances",
              "ffh_staff_roles","ffh_translation_memory",
              "ffh_translation_accuracy_review","ffh_translation_protected_source_overrides"):
                c.execute(f"GRANT SELECT ON public.{table} TO ffh_r140_reader")
                c.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
                c.execute(f"""CREATE POLICY r143_reader_select ON public.{table}
                    FOR SELECT TO ffh_r140_reader USING (true)""")
