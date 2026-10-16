"""Server-only FFH eligibility helper for real GoTrue + RLS.

Only the isolated CI fixture installs this SQL in an unexposed private schema.
No production Supabase migrations are executed. A privileged server DB owner
returns *only* boolean eligibility and role for a specific uid+session pair.
Never expose this RPC in PostgREST, browser, anon, or authenticated roles.
"""
from __future__ import annotations
from r136.broker import User
from r142.schema_matched import RegisteredReadOnly,NotAuthorized,canonical_uuid,ROLES

PRIVATE_MEMBER_SQL="""SELECT user_id, account_ok, current_session_ok, has_member_profile,
  terms_ok, effective_role
FROM ffh_auth_private.member_status(%s::uuid,%s::uuid)"""

CREATE_PRIVATE_SCHEMA_SQL="""CREATE SCHEMA ffh_auth_private AUTHORIZATION postgres"""
CREATE_MEMBER_FUNCTION_SQL="""
CREATE FUNCTION ffh_auth_private.member_status(p_uid uuid,p_session uuid)
RETURNS TABLE(
 user_id text,account_ok boolean,current_session_ok boolean,
 has_member_profile boolean,terms_ok boolean,effective_role text
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path=''
AS $$
SELECT
 u.id::text,
 (u.email_confirmed_at IS NOT NULL
   AND COALESCE(u.is_anonymous,false)=false
   AND u.deleted_at IS NULL
   AND (u.banned_until IS NULL OR u.banned_until<=now())),
 EXISTS (SELECT 1 FROM auth.sessions s WHERE s.id=p_session
    AND s.user_id=u.id AND (s.not_after IS NULL OR s.not_after>now())),
 EXISTS (SELECT 1 FROM public.ffh_member_profiles mp WHERE mp.user_id=u.id),
 EXISTS (SELECT 1 FROM public.ffh_terms_acceptances ta
    WHERE ta.user_id=u.id
    AND ta.terms_version=public.ffh_current_terms_version()),
 COALESCE((SELECT r.role FROM public.ffh_staff_roles r
    WHERE r.user_id=u.id AND r.active IS TRUE
    AND r.role IN ('owner','admin','moderator') LIMIT 1),'member')
FROM auth.users u
WHERE u.id=p_uid
LIMIT 1
$$
"""

def install_disposable_private_auth(cursor):
    cursor.execute(CREATE_PRIVATE_SCHEMA_SQL)
    cursor.execute("REVOKE ALL ON SCHEMA ffh_auth_private FROM PUBLIC")
    cursor.execute(CREATE_MEMBER_FUNCTION_SQL)
    cursor.execute("""REVOKE ALL ON FUNCTION
      ffh_auth_private.member_status(uuid,uuid) FROM PUBLIC""")
    cursor.execute("GRANT USAGE ON SCHEMA ffh_auth_private TO ffh_r140_reader")
    cursor.execute("""GRANT EXECUTE ON FUNCTION
      ffh_auth_private.member_status(uuid,uuid) TO ffh_r140_reader""")
    # Auth private tables intentionally have *no* direct SELECT grant.
    cursor.execute("REVOKE ALL ON auth.users,auth.sessions FROM ffh_r140_reader")

class PrivateMemberReadOnly(RegisteredReadOnly):
    """Server role has execute on only one narrowly scoped Auth helper."""
    def member(self,validated_uid,session_selector):
        uid=canonical_uuid(validated_uid)
        sid=canonical_uuid(session_selector)
        db=None
        try:
            db=self.factory()
            if getattr(db,"autocommit",True):raise NotAuthorized("transaction required")
            with db.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute("SET LOCAL statement_timeout='4000ms'")
                cur.execute(PRIVATE_MEMBER_SQL,(uid,sid))
                names=[d[0] for d in cur.description]
                rows=cur.fetchmany(2)
                db.rollback()
            if len(rows)!=1:return None
            row=dict(zip(names,rows[0],strict=True))
            if row.get("user_id")!=uid:return None
            if any(row.get(x) is not True for x in
                   ("account_ok","current_session_ok","has_member_profile","terms_ok")):
                return None
            role=row.get("effective_role")
            if type(role)!=str or role not in ROLES:return None
            return User(uid,ROLES[role])
        except (NotAuthorized,ValueError):
            raise
        except Exception:
            if db:
                try:db.rollback()
                except Exception:pass
            raise NotAuthorized("private Member authorization unavailable") from None
        finally:
            if db:db.close()
