"""Tests for R119 client 429-only retry reference: no network is used."""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from r119_client_retry_contract import next_retry_delay, classify_response

class ClientRetryContract(unittest.TestCase):
    def test_first_429_waits_explicit_retry_after(self):
        self.assertEqual(next_retry_delay(429,"2",attempt_index=1),2)
    def test_second_attempt_can_retry_once(self):
        self.assertEqual(next_retry_delay(429,"2",attempt_index=2,already_slept=2),2)
    def test_third_attempt_hard_stop(self):
        self.assertIsNone(next_retry_delay(429,"2",attempt_index=3,already_slept=4))
    def test_401_never_retry(self):
        self.assertIsNone(next_retry_delay(401,"2",attempt_index=1))
    def test_400_never_retry(self):
        self.assertIsNone(next_retry_delay(400,"2",attempt_index=1))
    def test_500_never_retry_without_explicit_policy(self):
        self.assertIsNone(next_retry_delay(500,"2",attempt_index=1))
    def test_503_never_retry_automatically(self):
        self.assertIsNone(next_retry_delay(503,"2",attempt_index=1))
    def test_malformed_retry_after_does_not_loop(self):
        for val in ("","next week","-1","1.2","99999999999","2\n",None,2,"+2"):
            with self.subTest(value=val):
                self.assertIsNone(next_retry_delay(429,val,attempt_index=1))
    def test_unreasonably_large_delay_requires_manual_retry(self):
        self.assertIsNone(next_retry_delay(429,"30",attempt_index=1))
    def test_cumulative_wait_budget(self):
        self.assertIsNone(next_retry_delay(429,"4",attempt_index=2,already_slept=4))
    def test_negative_attempt_not_supported(self):
        self.assertIsNone(next_retry_delay(429,"2",attempt_index=0))
    def test_bearer_failure_stops(self):
        self.assertEqual(classify_response(401,{"error":"unauthorized"},
                         attempt_index=1,retry_after="2")["action"],"stop_and_notify")
    def test_held_never_retried_even_if_429(self):
        self.assertEqual(classify_response(429,{"status":"held","draft":None},
                         attempt_index=1,retry_after="2")["action"],"hold_for_review")
    def test_valid_provisional_returns_not_retries(self):
        self.assertEqual(classify_response(200,{"status":"provisional_candidate"},
                         attempt_index=1)["action"],"return_provisional_only")
    def test_429_only_if_valid_delay(self):
        v=classify_response(429,{"error":"translation service busy"},
                            attempt_index=1,retry_after="2")
        self.assertEqual(v,{"action":"retry_after","delay_seconds":2.0})
    def test_429_with_unsafe_retry_after_stops(self):
        self.assertEqual(classify_response(429,{},attempt_index=1,retry_after="500")
                         ["action"],"stop_and_notify")

if __name__=="__main__":
    unittest.main()
