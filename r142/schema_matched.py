"""R142 schema-compatible real PostgreSQL AUTHORIZATION probe; no real FFH users.

This is a synthetic role/terms/session SOURCE-CHECK adapter. A `validated_uid`
is assumed to have come from a separately trusted online Supabase Auth /user
call. IT IS NOT JWT VERIFICATION. Never accept an untrusted UID from a browser.
Exactly two registered parameterized SQL statements with read-only DB role.
"""
from __future__ import annotations
from uuid import UUID
from r136.broker import User, Verdict

AUTHORIZED_MEMBER_SQL = '''
SELECT
  u.id::text AS user_id,
  (u.email_confirmed_at IS NOT NULL
     AND COALESCE(u.is_anonymous, FALSE) = FALSE
     AND u.deleted_at IS NULL
     AND (u.banned_until IS NULL OR u.banned_until <= now())) AS account_ok,
  EXISTS (
    SELECT 1 FROM auth.sessions s
    WHERE s.id = %s::uuid AND s.user_id = u.id
      AND (s.not_after IS NULL OR s.not_after > now())
  ) AS current_session_ok,
  EXISTS (
    SELECT 1 FROM public.ffh_member_profiles mp WHERE mp.user_id = u.id
  ) AS has_member_profile,
  EXISTS (
    SELECT 1 FROM public.ffh_terms_acceptances ta
    WHERE ta.user_id = u.id
      AND ta.terms_version = public.ffh_current_terms_version()
  ) AS terms_ok,
  COALESCE(r.role, 'member') AS effective_role
FROM auth.users u
LEFT JOIN public.ffh_staff_roles r ON r.user_id = u.id
  AND r.active IS TRUE AND r.role IN ('owner','admin','moderator')
WHERE u.id = %s::uuid
LIMIT 1
'''
AUTHORIZED_NORMAL_SOURCE_SQL = '''
SELECT
    m.source_hash,
    m.source_class,
    m.is_safety_critical,
    a.translation_gate,
    EXISTS (
      SELECT 1 FROM public.ffh_translation_protected_source_overrides o
      WHERE o.source_hash=m.source_hash
    ) AS manually_protected,
    public.ffh_translation_learning_is_safety_text(m.source_text)
      AS conservative_safety_match
FROM public.ffh_translation_memory m
LEFT JOIN public.ffh_translation_accuracy_review a
  ON a.source_hash=m.source_hash
WHERE m.source_text = %s
LIMIT 2
'''
ROLES={'member':'Member','moderator':'Moderator','admin':'Admin','owner':'Owner'}
class NotAuthorized(Exception):pass
def canonical_uuid(x):
    if type(x)!=str:raise NotAuthorized("verified UUID required")
    try: canonical=str(UUID(x))
    except (ValueError,TypeError,AttributeError):raise NotAuthorized("verified UUID required") from None
    if canonical!=x:raise NotAuthorized("noncanonical UUID")
    return x
class RegisteredReadOnly:
    """DB connection has SELECT on only staged auth/source columns, NO writes."""
    def __init__(self,connection_factory):
        if not callable(connection_factory):raise ValueError("trusted read connection required")
        self.factory=connection_factory
    def fetch(self,sql,params,limit):
        if not ((sql==AUTHORIZED_MEMBER_SQL and len(params)==2 and limit==1) or
                (sql==AUTHORIZED_NORMAL_SOURCE_SQL and len(params)==1 and limit==2)):
            raise NotAuthorized("unregistered SQL prohibited")
        db=None
        try:
            db=self.factory()
            if db.autocommit:raise NotAuthorized("read-only transaction required")
            with db.cursor() as cur:
                cur.execute('SET TRANSACTION READ ONLY')
                cur.execute("SET LOCAL statement_timeout = '4000ms'")
                cur.execute(sql,params)
                names=[col[0] for col in cur.description]
                if len(names)!=len(set(names)):raise NotAuthorized("duplicate result columns")
                rows=cur.fetchmany(limit+1)
                if len(rows)>limit:raise NotAuthorized("ambiguous results")
                result=[dict(zip(names,row,strict=True)) for row in rows]
                db.rollback()
                return result
        except Exception:
            if db:
                try:db.rollback()
                except Exception:pass
            raise NotAuthorized("read-only auth/source query denied") from None
        finally:
            if db:db.close()
    def member(self,validated_uid,untrusted_session_selector):
        uid=canonical_uuid(validated_uid)
        sid=canonical_uuid(untrusted_session_selector)
        rows=self.fetch(AUTHORIZED_MEMBER_SQL,(sid,uid),1)
        if len(rows)!=1 or rows[0].get('user_id')!=uid:return None
        row=rows[0]
        if any(row.get(x) is not True for x in ('account_ok','current_session_ok','has_member_profile','terms_ok')):
            return None
        role=row.get('effective_role')
        if type(role)!=str or role not in ROLES:return None
        return User(uid,ROLES[role])
    def source(self,text):
        if type(text)!=str or not 1<=len(text)<=500:return Verdict(False,'invalid')
        rows=self.fetch(AUTHORIZED_NORMAL_SOURCE_SQL,(text,),2)
        if len(rows)!=1:return Verdict(False,'missing or ambiguous')
        row=rows[0]
        if (type(row.get('source_hash'))!=str or not row['source_hash'] or
            row.get('source_class') not in ('ui','content') or
            row.get('is_safety_critical') is not False or
            row.get('translation_gate')!='normal' or
            row.get('manually_protected') is not False or
            row.get('conservative_safety_match') is not False):
            return Verdict(False,'safety exclusion')
        return Verdict(True,'explicit safe canonical')
