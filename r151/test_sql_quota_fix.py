"""R151 guarded quota SQL repair: lock the precise bug fixed on staging."""
from pathlib import Path
import unittest
SOURCE=Path("r151/02_fixed_quota_variable_staging_only.sql").read_text("utf-8")
class QuotaRepair(unittest.TestCase):
  def test_01_fixed_variable_inside_sql(self):
    body=SOURCE.split("CREATE OR REPLACE FUNCTION public.ffh_r151_admit",1)[1]
    self.assertIn("VALUES(v_user_hash,slot,1)",body)
    self.assertNotIn("VALUES(user_hash,slot,1)",body)
  def test_02_guard_ensures_old_schema(self):
    self.assertIn("pg_catalog.strpos(",SOURCE)
    self.assertIn("'Unexpected R151 function source: stop without changing anything'",SOURCE)
  def test_03_quota_atomic_and_no_dispatch(self):
    for exact in ("ON CONFLICT(user_hash,minute_bucket) DO UPDATE",
        "WHERE ffh_r146_sandbox.r151_quotas.used_count<3",
        "EXCEPTION WHEN SQLSTATE 'P0151'",
        "'status','quota_exceeded'","'model_connected',false"):
      self.assertIn(exact,SOURCE)
    self.assertNotIn("https://",SOURCE)
    self.assertNotIn("/translate",SOURCE)
  def test_04_no_broadened_grants(self):
    self.assertIn("FROM PUBLIC,anon,authenticated;",SOURCE)
    self.assertIn("GRANT EXECUTE ON FUNCTION public.ffh_r151_admit(text) TO authenticated;",SOURCE)
    self.assertNotIn("TO anon;",SOURCE)
  def test_05_old_receipt_ledger_not_touched(self):
    self.assertNotIn("r148_receipts",SOURCE)
    self.assertNotIn("DROP ",SOURCE)
    self.assertNotIn("TRUNCATE ",SOURCE)
if __name__=="__main__":unittest.main(verbosity=2)
