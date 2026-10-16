"""R110: fetch and verify the MiniSBD EN model during image BUILD, not at runtime."""
import hashlib
from pathlib import Path

import argostranslate.sbd  # Sets the exact Argos MiniSBD cache dir
from minisbd import SBDetect, models


def main():
    detector = SBDetect("en", use_gpu=False)
    output = detector.sentences("This is a test sentence. The next one is here.")
    if len(output) < 1:
        raise RuntimeError("MiniSBD did not tokenize the sentence fixture")
    model = Path(models.get_model_file("en"))
    if not model.is_file() or model.stat().st_size <= 0:
        raise RuntimeError("MiniSBD EN model not installed to image")
    print("R110_MINISBD_PREINSTALLED", {
        "path": str(model),
        "size": model.stat().st_size,
        "sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
        "runtime_downloads_required": False,
    }, flush=True)


if __name__ == "__main__":
    main()
