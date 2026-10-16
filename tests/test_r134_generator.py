"""R134 conservative model settings but unchanged strict resource and security gates."""
import ast
from pathlib import Path
import unittest
from r134.prepare_probe import build

class R134GeneratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=build((Path(__file__).parent/"r125f_bounded_switch.py").read_text())
    def test_python_valid(self):ast.parse(self.text)
    def test_exact_resource_bounds(self):
        for word in ('memory_gate(observed_peak,LIMIT,oom_count()-before_oom)',
                     'headroom_min_pct":10','SOAK_SECONDS=90','cgroup("memory.max")==LIMIT',
                     'int(cpu_max[0])*10 <= int(cpu_max[1])','oom_kills'):
            self.assertIn(word,self.text)
    def test_one_beam_one_batch_one_thread(self):
        self.assertIn('CONFIG={"es":(1,1),"fr":(1,1),"ko":(1,1)',self.text)
        self.assertIn('"--workers","1","--threads","1","--timeout","120"',self.text)
    def test_exact_two_model_diagnostic_gate(self):
        self.assertIn('SEQUENCE=("es","ko")',self.text)
        self.assertNotIn('German must be revisited across circuits',self.text)
        self.assertIn('Both diagnostic targets must be revisited',self.text)
    def test_crash_and_model_provenance(self):
        for word in ('os.killpg(proc.pid, signal.SIGKILL)',
                     'sigkill_unknown_verified','build_time_all_nine_tree_sha_verified',
                     'per_switch_tree_rehash','r134_conservative_inference'):
            self.assertIn(word,self.text)

if __name__=="__main__":unittest.main()
