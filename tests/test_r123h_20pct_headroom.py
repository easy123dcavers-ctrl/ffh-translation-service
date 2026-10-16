"""Exact 20% memory headroom acceptance tests; no model, network or secrets."""
import unittest
from r123h_memory_policy import memory_gate, MIB, EXPECTED_CGROUP_MIB

LIMIT = EXPECTED_CGROUP_MIB * MIB

class HeadroomTwentyPercentContract(unittest.TestCase):
    def test_01_actual_r123_peak_passes(self):
        self.assertTrue(memory_gate(round(284.62*MIB), LIMIT, 0))
    def test_02_exact_80_percent_memory_passes(self):
        self.assertTrue(memory_gate((LIMIT*4)//5, LIMIT, 0))
    def test_03_one_byte_over_threshold_fails(self):
        self.assertFalse(memory_gate((LIMIT*4)//5+1, LIMIT, 0))
    def test_04_old_15_percent_floor_no_longer_passes(self):
        self.assertFalse(memory_gate(round(LIMIT*.85), LIMIT, 0))
    def test_05_near_cap_never_passes(self):
        self.assertFalse(memory_gate(round(LIMIT*.99), LIMIT, 0))
    def test_06_any_oom_kill_fails_even_with_low_memory(self):
        self.assertFalse(memory_gate(150*MIB, LIMIT, 1))
    def test_07_wrong_limit_fails_closed(self):
        with self.assertRaises(ValueError):
            memory_gate(200*MIB,1024*MIB,0)
    def test_08_missing_metrics_fail_closed(self):
        with self.assertRaises(TypeError):
            memory_gate(None,LIMIT,0)
    def test_09_negative_cgroup_reading_fails(self):
        with self.assertRaises(ValueError):
            memory_gate(-1,LIMIT,0)
    def test_10_german_failed_512MiB_peak_is_rejected(self):
        self.assertFalse(memory_gate(512*MIB,LIMIT,1))
    def test_11_20pct_headroom_baseline_can_pass(self):
        self.assertTrue(memory_gate(300*MIB,LIMIT,0))
if __name__=="__main__":
    unittest.main()
