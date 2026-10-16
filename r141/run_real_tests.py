"""Run BOTH R140 reference and R141 exact R139 real-Postgres suites."""
import os
import sys
import unittest
from r140.pg_ephemeral_tests import setup, PgIntegration
from r141.pg_original_parity_tests import OriginalR139RealPg
def main():
    if os.getenv("FFH_R140_EPHEMERAL_ONLY")!="1":
        raise RuntimeError("R141 production forbidden")
    setup()
    loader=unittest.TestLoader()
    suite=unittest.TestSuite((loader.loadTestsFromTestCase(PgIntegration),
                               loader.loadTestsFromTestCase(OriginalR139RealPg)))
    result=unittest.TextTestRunner(verbosity=2,stream=sys.stdout).run(suite)
    print("R141_22_REFERENCE_PLUS_23_ORIGINAL_REAL_POSTGRES",
          {"run":result.testsRun,"failures":len(result.failures),"errors":len(result.errors),
           "passed":result.wasSuccessful()},flush=True)
    if result.testsRun!=45 or not result.wasSuccessful():
        return 1
    print("R141_EXACT_R139_LEDGER_REAL_POSTGRES_PASS_NOT_PRODUCTION",flush=True)
    return 0
if __name__=="__main__":
    raise SystemExit(main())
