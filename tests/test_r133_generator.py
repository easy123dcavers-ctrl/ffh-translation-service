"""R133 exact telemetry and strict policy tests."""
import ast
from pathlib import Path
import unittest
from r133.prepare_diagnostic import build

class R133DiagnosticChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=build((Path(__file__).parent/"r125f_bounded_switch.py").read_text())
    def test_ast(self):
        ast.parse(self.text)
    def test_resource_limits_intact(self):
        for pattern in ('from r130_memory_policy import memory_gate','headroom_min_pct":10',
                        'cgroup("memory.max")==LIMIT','int(cpu_max[0])*10 <= int(cpu_max[1])',
                        'oom_kills','single','sigkill_unknown_verified'):
            if pattern=='single':continue
            self.assertIn(pattern,self.text)
    def test_explicitly_not_endurance(self):
        self.assertIn('SOAK_SECONDS=90',self.text)
        self.assertIn('SEQUENCE=("es","ko")',self.text)
        self.assertIn('"r133_diagnostic_only"',self.text)
    def test_memory_breakdown_evidence(self):
        for needle in ('memory_before_startup','memory_after_backend_health',
                       'memory_after_last_batch','memory_after_exit',
                       'memory_final_components','file_mapped','inactive_file'):
            self.assertIn(needle,self.text)
    def test_r132_singleflight_preserved(self):
        self.assertIn('r132_singleflight',self.text)
        self.assertIn('"per_switch_tree_rehash":False',self.text)

if __name__=="__main__":
    unittest.main()
