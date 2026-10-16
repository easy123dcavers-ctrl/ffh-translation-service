"""R105 test-runner-only experiment. Mutates disposable installed package, NEVER deploy."""
import hashlib
import importlib.util
from pathlib import Path

spec = importlib.util.find_spec("argostranslate")
if spec is None or spec.origin is None:
    raise RuntimeError("Argos package not installed")
module_file = Path(spec.origin).parent / "sbd.py"
source = module_file.read_text(encoding="utf-8")
anchor = "\nimport stanza\n"
if source.count(anchor) != 1:
    raise RuntimeError("STOP: expected unique eager 'import stanza' in pinned Argos 1.11.0")
# This is a proof-of-concept only: stanza-based SBD will no longer function.
# Production would require an upstream-compatible maintained fork with full tests.
replacement = "\nstanza = None  # R105 DISPOSABLE RUNNER PATCH: MiniSBD ONLY, no Stanza\n"
patched = source.replace(anchor, replacement)
module_file.write_text(patched, encoding="utf-8")
assert patched.count("R105 DISPOSABLE RUNNER PATCH") == 1
print("R105_PATCHED", {"file": str(module_file),
                      "before_sha256": hashlib.sha256(source.encode()).hexdigest(),
                      "after_sha256": hashlib.sha256(patched.encode()).hexdigest(),
                      "production_use": False}, flush=True)
