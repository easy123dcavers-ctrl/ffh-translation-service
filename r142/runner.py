"""R142 REAL PostgreSQL synthetic FFH schema, plus R141 ledger parity."""
import os,sys,unittest
from r140.pg_ephemeral_tests import setup,PgIntegration
from r141.pg_original_parity_tests import OriginalR139RealPg
from r142.pg_identity_source_tests import build_schema,RealSchemaTests
def main():
    if os.getenv('FFH_R140_EPHEMERAL_ONLY')!='1':
        raise RuntimeError('DISPOSABLE CI REQUIRED')
    setup();build_schema()
    load=unittest.TestLoader()
    suite=unittest.TestSuite(load.loadTestsFromTestCase(x) for x in
      (PgIntegration,OriginalR139RealPg,RealSchemaTests))
    result=unittest.TextTestRunner(stream=sys.stdout,verbosity=2).run(suite)
    print('R142_TEST_SUMMARY',
        dict(run=result.testsRun,failures=len(result.failures),errors=len(result.errors),
             passed=result.wasSuccessful(),real_member_auth_verified=False),flush=True)
    if result.testsRun!=81 or not result.wasSuccessful():return 1
    print('R142_POSTGRES_SYNTHETIC_SCHEMA_PASS_NOT_LIVE_SUPABASE_AUTH',flush=True)
    return 0
if __name__=='__main__':raise SystemExit(main())
