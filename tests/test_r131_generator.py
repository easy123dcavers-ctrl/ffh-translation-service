"""R131 conservative changes to already pinned baseline, no production effects."""
from pathlib import Path
import ast
import unittest
from r131.prepare_endurance import build
from r130.prepare_endurance import build as base_build

SOURCE=Path(__file__).resolve().parent/"r125f_bounded_switch.py"

class R131GeneratorContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=SOURCE.read_text()
        cls.base=base_build(cls.original)
        cls.generated=build(cls.original)
    def test_only_one_full_tree_hash_call_removed(self):
        self.assertEqual(self.base.count('match=verify(target,p,baselines)'),1)
        self.assertNotIn('match=verify(target,p,baselines)',self.generated)
    def test_other_build_time_integrity_coded(self):
        self.assertIn('expected=baselines.get("verified_packages",{}).get(target)',self.generated)
        self.assertIn('"build_time_all_nine_tree_sha_verified":True',self.generated)
    def test_reference_10pct_gate_kept(self):
        self.assertIn('from r130_memory_policy import memory_gate',self.generated)
        self.assertIn('"headroom_min_pct":10',self.generated)
        self.assertIn('"memory_peak_bytes"',self.generated)
    def test_strict_runtime_stability_unmodified(self):
        for token in ('SOAK_SECONDS=1800','sigkill_unknown_verified','oom_kills',
                      'len(report["rounds"])>=2*len(SEQUENCE)',
                      'source="en"', 'os.killpg(proc.pid, signal.SIGKILL)'):
            self.assertIn(token,self.generated)
    def test_only_expected_behavior_modified(self):
        self.assertIn('start_new_session=True',self.generated)
        self.assertIn('cpu.max',self.generated)
        self.assertIn('memory_gate(observed_peak,LIMIT,oom_count()-before_oom)',self.generated)
        self.assertIn('EXPERIMENT_ID',self.generated)
    def test_ast_and_no_new_network_or_db_access(self):
        ast.parse(self.generated)
        self.assertNotIn('supabase',self.generated.lower())
        self.assertNotIn('requests.post',self.generated.lower())

if __name__ == '__main__': unittest.main()
