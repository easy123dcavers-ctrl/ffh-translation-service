"""Offline model manifest validation tests, using invented files only."""
import hashlib
import json
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from r119_verify_model_tree import tree_digest,verify

class ModelTreeVerifier(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"model"
        self.root.mkdir()
        (self.root/"model.bin").write_bytes(b"invented test model")
        self.digest=tree_digest(self.root)
        self.base={"verified_packages":{"de":{"sha256":self.digest["sha256"],
                                               "bytes":self.digest["bytes"]}}}

    def test_01_exact_tree_pass(self):
        result=verify("de",self.root,self.base)
        self.assertEqual(result["status"],"same_files_as_R113_baseline")
        self.assertIs(result["release_certified"],False)

    def test_02_one_byte_mutation_halts(self):
        (self.root/"model.bin").write_bytes(b"invented test modeL")
        with self.assertRaises(ValueError):
            verify("de",self.root,self.base)

    def test_03_additional_file_halts(self):
        (self.root/"extra").write_bytes(b"unexpected")
        with self.assertRaises(ValueError):
            verify("de",self.root,self.base)

    def test_04_missing_file_halts(self):
        (self.root/"model.bin").unlink()
        with self.assertRaises(ValueError):
            verify("de",self.root,self.base)

    def test_05_wrong_target_halts(self):
        with self.assertRaises(ValueError):
            verify("ko",self.root,self.base)

    def test_06_directory_missing_halts(self):
        with self.assertRaises(ValueError):
            verify("de",self.root/"missing",self.base)

    def test_07_nested_files_deterministic(self):
        (self.root/"child").mkdir()
        (self.root/"child"/"segment").write_bytes(b"test")
        first=tree_digest(self.root)
        second=tree_digest(self.root)
        self.assertEqual(first,second)

    def test_08_duplicate_coverage_is_file_based(self):
        self.assertEqual(self.digest["files"],1)
        self.assertEqual(self.digest["bytes"],len(b"invented test model"))

if __name__=="__main__":
    unittest.main()
