"""R135 fails closed on resource and security contract regression."""
import ast
from pathlib import Path
import unittest
from r135.prepare_endurance import build

class R135FullRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text=build((Path(__file__).parent/"r125f_bounded_switch.py").read_text())
    def test_syntax(self):ast.parse(self.text)
    def test_nine_models_two_circuits(self):
        self.assertIn('SOAK_SECONDS=1800',self.text)
        self.assertIn('SEQUENCE=("es","ko","fr","vi","ja","de","ar","tl","zh")',self.text)
        self.assertIn('len(report["rounds"])>=2*len(SEQUENCE)',self.text)
        self.assertIn('German must be revisited across circuits',self.text)
    def test_exact_resource_gates(self):
        for p in ('from r130_memory_policy import memory_gate','cgroup("memory.max")==LIMIT',
                  'int(cpu_max[0])*10 <= int(cpu_max[1])','oom_kills','"headroom_min_pct":10',
                  'memory_peak_bytes','R130 strict tripwire'):
            self.assertIn(p,self.text)
    def test_low_memory_inference(self):
        self.assertIn('CONFIG={"es":(1,1),"fr":(1,1),"ko":(1,1)',self.text)
        self.assertIn('"--workers","1","--threads","1","--timeout","120"',self.text)
        self.assertIn('r135_conservative_inference',self.text)
    def test_staging_held_security(self):
        for p in ('sigkill_unknown_verified','os.killpg(proc.pid, signal.SIGKILL)',
                  'http(url,"/translate"','token="wrong-token"','busy[0]==429',
                  'per_switch_tree_rehash','build_time_all_nine_tree_sha_verified'):
            self.assertIn(p,self.text)
        self.assertNotIn('supabase',self.text.lower())
    def test_one_active_process_and_drain(self):
        self.assertIn('ensure(proc is None',self.text)
        self.assertIn('state.begin_drain',self.text)
        self.assertIn('proc.wait(timeout=12)',self.text)

if __name__=='__main__': unittest.main()
