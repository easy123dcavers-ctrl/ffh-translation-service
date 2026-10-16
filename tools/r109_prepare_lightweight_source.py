#!/usr/bin/env python3
"""R109: make a source-level, pinned Argos 1.11.0 lightweight TEST build.

Never rewrites installed site-packages. No network or deployment by this script.
Input must be a checkout of the exact upstream 1.11.0 release commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

UPSTREAM_URL = "https://github.com/argosopentech/argos-translate"
PINNED_SHA = "63b84ecb46c740c7a7c066d58636434d3e893ebf"
ORIGINAL_VERSION = 'version="1.11.0"'
TEST_VERSION = 'version="1.11.0+ffhlite1"'
STANZA_IMPORT = "\nimport stanza\n"
LAZY_IMPORT = "\ntry:\n    import stanza\nexcept ImportError:\n    stanza = None\n"
STANZA_REQUIREMENT = "stanza==1.10.1"


def sha256(s: bytes) -> str:
    return hashlib.sha256(s).hexdigest()


def patch_text(original_sbd: str, original_req: str, original_setup: str):
    """Fail closed if the expected source layout does not match upstream v1.11.0."""
    if original_sbd.count(STANZA_IMPORT) != 1:
        raise ValueError("Upstream sbd.py does not contain exactly one eager stanza import")
    if original_req.splitlines().count(STANZA_REQUIREMENT) != 1:
        raise ValueError("Upstream requirements do not contain one stanza==1.10.1 dependency")
    if original_setup.count(ORIGINAL_VERSION) != 1:
        raise ValueError("Upstream setup.py version differs from 1.11.0")
    sbd = original_sbd.replace(STANZA_IMPORT, LAZY_IMPORT)
    req_lines = [line for line in original_req.splitlines()
                 if line.strip() != STANZA_REQUIREMENT]
    req = "\n".join(req_lines) + "\n"
    setup = original_setup.replace(ORIGINAL_VERSION, TEST_VERSION)
    assert "stanza" not in req.lower()
    assert "stanza = None" in sbd
    assert ORIGINAL_VERSION not in setup
    return sbd, req, setup


def checkout_sha(path: Path):
    result = subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    return result


def build(source: Path, dest: Path, allow_fixture=False):
    source = source.resolve()
    dest = dest.resolve()
    if dest == source or source in dest.parents or dest in source.parents:
        raise ValueError("source and destination must be disjoint directories")
    if not source.is_dir():
        raise ValueError("Source checkout missing")
    if not allow_fixture and checkout_sha(source) != PINNED_SHA:
        raise ValueError("Upstream SHA mismatch: refusing to construct test package")
    expected = {
        "argostranslate/sbd.py": None,
        "requirements.txt": None,
        "setup.py": None,
        "LICENSE": None,
        "README.md": None,
    }
    for path in expected:
        f = source / path
        if not f.is_file():
            raise ValueError(f"Required upstream file missing: {path}")
        expected[path] = f.read_bytes()
    patched = patch_text(
        expected["argostranslate/sbd.py"].decode("utf-8"),
        expected["requirements.txt"].decode("utf-8"),
        expected["setup.py"].decode("utf-8"),
    )
    if dest.exists():
        raise ValueError("Destination already exists; refusing to overwrite")
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns(
        ".git", ".github", "__pycache__", "*.pyc", "build", "dist", "*.egg-info"
    ))
    paths = ("argostranslate/sbd.py", "requirements.txt", "setup.py")
    for name, content in zip(paths, patched):
        (dest / name).write_text(content, encoding="utf-8")
    meta = {
        "intended_usage": "ISOLATED TEST ONLY. NOT A RELEASE. NO PRODUCTION DEPLOYMENT.",
        "upstream_repository": UPSTREAM_URL,
        "upstream_commit_sha": PINNED_SHA if not allow_fixture else "TEST_FIXTURE",
        "upstream_version": "1.11.0",
        "candidate_distribution_version": "1.11.0+ffhlite1",
        "technical_diff": [
            "Argos sbd.py: make optional stanza import guarded by ImportError",
            "requirements.txt: remove stanza==1.10.1 requirement, avoiding torch dependency",
            "setup.py: test-only local version suffix",
        ],
        "environment_requirements": [
            "ARGOS_CHUNK_TYPE=MINISBD",
            "ARGOS_DEVICE_TYPE=cpu",
            "ARGOS_COMPUTE_TYPE=int8",
        ],
        "upstream_source_sha256": {
            k: sha256(v) for k, v in expected.items()
        },
        "patched_sha256": {
            name: sha256(content.encode("utf-8"))
            for name, content in zip(paths, patched)
        },
        "preserve_upstream_license": "LICENSE",
        "stanza_and_spacy_models": "STANZA is not supported in this test build; SPACY remains an existing dependency",
        "review_gate": "Needs offline model and full 512MiB Flask/Gunicorn review before any release",
    }
    (dest / "FFH-LIGHTWEIGHT-TEST-MANIFEST.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print("R109_PATCH_PREPARED", json.dumps({
        "source": str(source), "destination": str(dest),
        "test_only": True, "sha": meta["upstream_commit_sha"]
    }), flush=True)
    return meta


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--upstream", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    build(args.upstream, args.output)


if __name__ == "__main__":
    main()
