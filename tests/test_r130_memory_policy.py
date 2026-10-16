"""R130 exact 10% cgroup boundary + legacy 20% policy isolation tests."""
import unittest
from r130_memory_policy import MEMORY_HEADROOM_MIN_PERCENT, memory_gate
from r123h_memory_policy import memory_gate as old_gate

MIB=1024*1024
LIM=512*MIB

class TestR130TenPercent(unittest.TestCase):
    def test_requested_threshold(self):
        self.assertEqual(MEMORY_HEADROOM_MIN_PERCENT,10)
    def test_integer_boundary_pass(self):
        self.assertTrue(memory_gate((LIM*9)//10,LIM,0))
    def test_single_byte_beyond_fails(self):
        self.assertFalse(memory_gate((LIM*9)//10+1,LIM,0))
    def test_zero_oom_required(self):
        self.assertFalse(memory_gate((LIM*9)//10,LIM,1))
    def test_legacy_policy_still_protected(self):
        self.assertFalse(old_gate((LIM*9)//10,LIM,0))
    def test_no_float_pass(self):
        with self.assertRaises(TypeError):
            memory_gate(0.9*LIM,LIM,0)
    def test_cgroup_cannot_be_raised(self):
        with self.assertRaises(ValueError):
            memory_gate(0,1024*MIB,0)
    def test_prior_real_peaks(self):
        self.assertTrue(memory_gate(round(459.51*MIB),LIM,0))
        self.assertFalse(memory_gate(round(461.37*MIB),LIM,0))

if __name__=='__main__':
    unittest.main()
