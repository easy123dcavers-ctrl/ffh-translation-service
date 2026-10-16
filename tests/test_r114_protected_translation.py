"""R114 offline privacy-safe contract checks. No real translator or external systems."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from protected_translation import guarded_candidate, content_numbers


class ProtectedTranslationContract(unittest.TestCase):
    def test_marker_never_sent_to_translator(self):
        seen=[]
        def translate(x):
            seen.append(x)
            return x.replace("The note", "La nota").replace("is here", "está aquí")
        result=guarded_candidate("The note {{SAMPLE_ID}} is here.",translate)
        self.assertEqual(result["status"],"provisional_candidate")
        self.assertIn("{{SAMPLE_ID}}",result["draft"])
        self.assertTrue(all("{{SAMPLE_ID}}" not in piece for piece in seen))
        self.assertEqual(len(seen),2)
        self.assertFalse(result["human_approved"])

    def test_multiple_placeholders_keep_order(self):
        result=guarded_candidate("A {{ONE}} B {{TWO}} C",lambda s:s)
        self.assertEqual(result["status"],"provisional_candidate")
        self.assertEqual(result["protected_placeholders"],2)
        self.assertIn("{{ONE}} B {{TWO}}",result["draft"])

    def test_duplicate_placeholders_retained(self):
        output=guarded_candidate("A {{ONE}} and {{ONE}}",lambda s:s)
        self.assertEqual(output["protected_placeholders"],2)
        self.assertEqual(output["draft"].count("{{ONE}}"),2)

    def test_changed_number_held_without_draft(self):
        result=guarded_candidate("Test batch 25 g.",lambda s:s.replace("25","26"))
        self.assertEqual(result["status"],"held")
        self.assertIn("numeric_integrity",result["reasons"])
        self.assertIsNone(result["draft"])

    def test_unit_changes_held(self):
        result=guarded_candidate("Measure 25 mL.",lambda s:s.replace("mL","L"))
        self.assertIn("unit_integrity",result["reasons"])
        self.assertEqual(result["status"],"held")

    def test_unicode_decimal_digits_equivalent(self):
        self.assertEqual(content_numbers("25"), content_numbers("٢٥"))
        result=guarded_candidate("Page 25.",lambda s:"الصفحة ٢٥.")
        self.assertEqual(result["status"],"provisional_candidate")

    def test_numeric_semantics_hold_if_value_changed(self):
        result=guarded_candidate("Count 25 items.",lambda s:"العدد ٢٦ عنصر.")
        self.assertEqual(result["status"],"held")
        self.assertIn("numeric_integrity",result["reasons"])

    def test_malformed_placeholder_held(self):
        for source in ("{{bad}}","{{BROKEN}","{{BROKEN X}}"):
            with self.subTest(source=source):
                self.assertEqual(guarded_candidate(source,lambda x:x)["status"],"held")

    def test_translator_failure_held_without_content(self):
        def fail(_): raise RuntimeError("Sensitive message that must not leak")
        result=guarded_candidate("This is a test.",fail)
        self.assertEqual(result["status"],"held")
        self.assertEqual(result["reasons"],["translator_exception"])
        self.assertNotIn("Sensitive",str(result))

    def test_empty_model_output_held(self):
        result=guarded_candidate("Hello!",lambda s:"")
        self.assertEqual(result["status"],"held")

    def test_input_length_limit_holds(self):
        result=guarded_candidate("A"*4097,lambda s:s)
        self.assertEqual(result["reasons"],["source_too_long"])

    def test_token_count_limit_holds(self):
        result=guarded_candidate(" ".join(["{{X}}"]*21),lambda s:s)
        self.assertEqual(result["reasons"],["too_many_placeholders"])

    def test_missing_translator_held(self):
        self.assertEqual(guarded_candidate("Hello",None)["status"],"held")

    def test_empty_input_held(self):
        for value in ("",None,0,"  "):
            self.assertEqual(guarded_candidate(value,lambda s:s)["status"],"held")

    def test_markers_only_no_translation_calls(self):
        count=[]
        def fn(s): count.append(s); return s
        result=guarded_candidate("{{FIRST}}{{SECOND}}",fn)
        self.assertEqual(result["draft"],"{{FIRST}}{{SECOND}}")
        self.assertEqual(len(count),0)

    def test_clean_content_always_provisional_never_reviewed(self):
        x=guarded_candidate("Blue notebook",lambda s:"Cuaderno azul")
        self.assertEqual(x["status"],"provisional_candidate")
        self.assertFalse(x["human_approved"])
        self.assertEqual(x["production_writes"],0)


if __name__ == "__main__":
    unittest.main()
