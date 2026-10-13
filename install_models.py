"""Install and verify exactly one Argos model for this FFH service."""
import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
MODEL_DIR = APP_ROOT / ".argos" / "packages"

os.environ["ARGOS_PACKAGES_DIR"] = str(MODEL_DIR)
os.environ.setdefault("ARGOS_DEVICE_TYPE", "cpu")

import argostranslate.package

SOURCE = "en"
TARGET = os.environ.get("FFH_TARGET_LANGUAGE", "es").strip().lower()
ALLOWED = {"es", "fr", "ja", "de", "ar", "tl", "ko", "vi", "zh"}
MULTILINGUAL = os.environ.get("FFH_MULTILINGUAL", "false").lower() == "true"
TARGET_LIST = [t.strip() for t in os.environ.get("FFH_TARGET_LANGUAGES", "es,fr,ja,de,ar,tl,ko,vi,zh").split(",") if t.strip()] if MULTILINGUAL else [TARGET]

if TARGET not in ALLOWED:
    raise RuntimeError(
        f"Unsupported FFH_TARGET_LANGUAGE: {TARGET}"
    )


def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    argostranslate.package.update_package_index()
    available = argostranslate.package.get_available_packages()

    installed = {
        (p.from_code, p.to_code)
        for p in argostranslate.package.get_installed_packages()
    }

    for target in TARGET_LIST:
        if target not in ALLOWED:
            raise RuntimeError(f"Unsupported target: {target}")
        pair = (SOURCE, target)
        if pair not in installed:
            package = next((p for p in available if p.from_code == SOURCE and p.to_code == target), None)
            if package is None:
                if MULTILINGUAL:
                    print(f"SKIP unavailable Argos model: {SOURCE}->{target}")
                    continue
                raise RuntimeError(f"No Argos model available for {SOURCE}->{target}")
            print(f"Installing {SOURCE}->{target}: {package}")
            argostranslate.package.install_from_path(package.download())
            installed.add(pair)

    installed = {
        (p.from_code, p.to_code)
        for p in argostranslate.package.get_installed_packages()
    }

    if not MULTILINGUAL and (SOURCE,TARGET) not in installed:
        raise RuntimeError(f"Argos model verification failed; missing: {(SOURCE,TARGET)}")
    print(f"FFH installed models: {sorted(installed)}")


if __name__ == "__main__":
    main()
