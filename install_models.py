"""Install only the three Argos models FFH currently needs."""
import argostranslate.package

REQUIRED = (("en", "es"), ("en", "fr"), ("en", "ja"))

def main():
    argostranslate.package.update_package_index()
    available = argostranslate.package.get_available_packages()
    for source, target in REQUIRED:
        matches = [p for p in available if p.from_code == source and p.to_code == target]
        if not matches:
            raise RuntimeError(f"No Argos model available for {source}->{target}")
        package = matches[0]
        print(f"Installing {source}->{target}: {package}")
        argostranslate.package.install_from_path(package.download())
    print("FFH Argos model installation complete.")

if __name__ == "__main__":
    main()
