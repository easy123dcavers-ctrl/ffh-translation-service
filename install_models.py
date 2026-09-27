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
ALLOWED = {"es", "fr", "ja"}

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

    pair = (SOURCE, TARGET)

    if pair not in installed:
        package = next(
            (
                p for p in available
                if p.from_code == SOURCE
                and p.to_code == TARGET
            ),
            None,
        )

        if package is None:
            raise RuntimeError(
                f"No Argos model available for {SOURCE}->{TARGET}"
            )

        print(f"Installing {SOURCE}->{TARGET}: {package}")
        argostranslate.package.install_from_path(
            package.download()
        )

    installed = {
        (p.from_code, p.to_code)
        for p in argostranslate.package.get_installed_packages()
    }

    if pair not in installed:
        raise RuntimeError(
            f"Argos model verification failed; missing: {pair}"
        )

    print(
        f"FFH Argos model verified in {MODEL_DIR}: "
        f"{SOURCE}->{TARGET}"
    )


if __name__ == "__main__":
    main()
