"""FFH R102: offline-only cache contract tests (no Argos or production access)."""
import unittest
from translation_cache import TranslationCache


class FakeClock:
    now = 0.0

    def __call__(self):
        return self.now


class TranslationCacheTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.cache = TranslationCache(max_entries=2, ttl_seconds=10,
                                      max_source_chars=10, max_output_chars=20,
                                      clock=self.clock)
        self.calls = 0

    def do(self, source="A", source_lang="en", target="es", generation="v1",
           error=False, output="translated"):
        def compute():
            self.calls += 1
            if error:
                raise RuntimeError("temporary translator failure")
            return output
        return self.cache.run(source, source_lang, target, generation, compute)

    def test_identical_source_reused_once(self):
        self.assertEqual(self.do(), "translated")
        self.assertEqual(self.do(), "translated")
        self.assertEqual(self.calls, 1)

    def test_language_and_model_isolation(self):
        self.do()
        self.do(target="fr")
        self.do(generation="v2")
        self.assertEqual(self.calls, 3)

    def test_ttl_expiration(self):
        self.do()
        self.clock.now = 9.9
        self.do()
        self.assertEqual(self.calls, 1)
        self.clock.now = 10.0
        self.do()
        self.assertEqual(self.calls, 2)

    def test_max_entries_eviction(self):
        self.do(source="A")
        self.do(source="B")
        self.do(source="C")
        self.do(source="A")
        self.assertEqual(self.calls, 4)
        self.assertLessEqual(len(self.cache.entries), 2)

    def test_errors_not_cached(self):
        with self.assertRaises(RuntimeError):
            self.do(error=True)
        self.do()
        self.assertEqual(self.calls, 2)

    def test_empty_draft_not_cached(self):
        self.do(output="")
        self.do(output="")
        self.assertEqual(self.calls, 2)

    def test_oversized_input_or_output_not_cached(self):
        self.do(source="ABCDEFGHIJK")
        self.do(source="ABCDEFGHIJK")
        self.assertEqual(self.calls, 2)
        self.do(source="B", output="Z" * 21)
        self.do(source="B", output="Z" * 21)
        self.assertEqual(self.calls, 4)

    def test_exact_strings_no_normalization(self):
        self.do(source="jar")
        self.do(source="jar ")
        self.assertEqual(self.calls, 2)

    def test_clear_invalidates(self):
        self.do()
        self.cache.clear()
        self.do()
        self.assertEqual(self.calls, 2)


if __name__ == "__main__":
    unittest.main()
