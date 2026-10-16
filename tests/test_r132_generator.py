"""Regression: R132 preserves strict 10pct, 0.1cpu, full 30-minute real workload."""
import ast
from pathlib import Path
import unittest
from r132.prepare_endurance import build

class R132GeneratorContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.code=build((Path(__file__).parent/"r125f_bounded_switch.py").read_text())
    def test_parse(self):
        ast.parse(self.code)
    def test_no_sleep_race(self):
        self.assertNotIn("time.sleep(.085)",self.code)
        self.assertIn('state.snapshot()["active"] == 1',self.code)
    def test_all_original_resource_gates(self):
        for word in ('SOAK_SECONDS=1800','from r130_memory_policy import memory_gate',
                     'cgroup("memory.max")==LIMIT','int(cpu_max[0])*10 <= int(cpu_max[1])',
                     'sigkill_unknown_verified','memory_peak_bytes','headroom_min_pct":10'):
            self.assertIn(word,self.code)
    def test_same_model_integrity(self):
        self.assertIn('"build_time_all_nine_tree_sha_verified":True',self.code)
        self.assertIn('"per_switch_tree_rehash":False',self.code)
    def test_backend_cleanup(self):
        self.assertIn('proc.terminate()',self.code)
        self.assertIn('os.killpg(proc.pid, signal.SIGKILL)',self.code)
    def test_limited_staging_scope(self):
        self.assertIn('r132_singleflight',self.code)
        self.assertNotIn('supabase',self.code.lower())

if __name__=="__main__":
    unittest.main()
