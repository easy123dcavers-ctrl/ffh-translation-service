"""Offline, no-network, stdlib checks for the pinned Argos build source transformer."""
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from r109_prepare_lightweight_source import (
    LAZY_IMPORT, PINNED_SHA, STANZA_IMPORT,
    patch_text, build,
)


class R109PatchTests(unittest.TestCase):
    def setUp(self):
        self.sbd = """from __future__ import annotations
import os
import stanza
from minisbd import SBDetect
"""
        self.req = """ctranslate2>=4.0,<5
stanza==1.10.1
minisbd
spacy
"""
        self.setup = '''setup(name="argostranslate", version="1.11.0")'''

    def test_expected_upstream_patch(self):
        sbd, req, setup = patch_text(self.sbd, self.req, self.setup)
        self.assertIn(LAZY_IMPORT.strip(), sbd)
        self.assertNotIn("stanza==", req)
        self.assertIn("minisbd", req)
        self.assertIn("spacy", req)
        self.assertIn('version="1.11.0+ffhlite1"', setup)

    def test_missing_import_fails_closed(self):
        with self.assertRaises(ValueError):
            patch_text(self.sbd.replace("import stanza", ""), self.req, self.setup)

    def test_duplicate_import_fails_closed(self):
        with self.assertRaises(ValueError):
            patch_text(self.sbd + STANZA_IMPORT, self.req, self.setup)

    def test_mismatched_dependency_fails_closed(self):
        with self.assertRaises(ValueError):
            patch_text(self.sbd, self.req.replace("stanza==1.10.1","stanza==9"), self.setup)

    def test_mismatched_version_fails_closed(self):
        with self.assertRaises(ValueError):
            patch_text(self.sbd, self.req, self.setup.replace("1.11.0", "2.0"))

    def test_fixture_bundle_has_attribution_and_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            source, dest = Path(temp) / "unmodified", Path(temp) / "patched"
            (source / "argostranslate").mkdir(parents=True)
            (source / "argostranslate" / "sbd.py").write_text(self.sbd)
            (source / "requirements.txt").write_text(self.req)
            (source / "setup.py").write_text(self.setup)
            (source / "README.md").write_text("synthetic test")
            (source / "LICENSE").write_text("test license")
            report = build(source,dest,allow_fixture=True)
            self.assertTrue((dest / "LICENSE").exists())
            self.assertEqual(report["upstream_commit_sha"], "TEST_FIXTURE")
            self.assertTrue((dest / "FFH-LIGHTWEIGHT-TEST-MANIFEST.json").exists())
            self.assertIn(LAZY_IMPORT.strip(),
                          (dest / "argostranslate/sbd.py").read_text())
            with self.assertRaises(ValueError):
                build(source,dest,allow_fixture=True)

    def test_source_commit_hash_required_on_production_builder_path(self):
        self.assertEqual(len(PINNED_SHA), 40)
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                build(Path(temp),Path(temp)/"patched")


if __name__ == "__main__":
    unittest.main()
