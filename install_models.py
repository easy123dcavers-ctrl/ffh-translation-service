"""Install and verify only the three Argos models FFH currently needs."""
import os
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
MODEL_DIR = APP_ROOT / ".argos" / "packages"

os.environ["ARGOS_PACKAGES_DIR"] = str(MODEL_DIR)
os.environ.setdefault("ARGOS_DEVICE_TYPE", "cpu")

import argostranslate.package

REQUIRED = (("en", "es"), ("en", "fr"), ("en", "ja"))


def main():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    argostranslate.package.update_package_index()
    available = argostranslate.package.get_available_packages()

    for source, target in REQUIRED:
        installed = {
            (p.from_code, p.to_code)
            for p in argostranslate.package.get_installed_packages()
        }

        if (source, target) in installed:
            print(f"Already installed {source}->{target}")
            continue

        package = next(
            (
                p for p in available
                if p.from_code == source and p.to_code == target
            ),
            None,
        )

        if package is None:
            raise RuntimeError(
                f"No Argos model available for {source}->{target}"
            )

        print(f"Installing {source}->{target}: {package}")
        argostranslate.package.install_from_path(package.download())

    installed = {
        (p.from_code, p.to_code)
        for p in argostranslate.package.get_installed_packages()
    }

    missing = [pair for pair in REQUIRED if pair not in installed]

    if missing:
        raise RuntimeError(
            f"Argos model verification failed; missing: {missing}"
        )

    print(
        f"FFH Argos models verified in {MODEL_DIR}: "
        f"{sorted(installed)}"
    )


if __name__ == "__main__":
    main()
