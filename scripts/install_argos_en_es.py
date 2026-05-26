from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from argostranslate import package, translate

from app import config
from app.translator import OfflineArgosTranslator


def is_installed() -> bool:
    languages = translate.get_installed_languages()
    source = next((lang for lang in languages if lang.code == config.SOURCE_LANG), None)
    target = next((lang for lang in languages if lang.code == config.TARGET_LANG), None)
    return bool(source and target and source.get_translation(target))


def main() -> None:
    if is_installed():
        print("Argos en->es package is already installed.")
    else:
        print("Downloading Argos package index and installing en->es package...")
        package.update_package_index()
        available_packages = package.get_available_packages()
        selected = next(
            (
                pkg
                for pkg in available_packages
                if pkg.from_code == config.SOURCE_LANG and pkg.to_code == config.TARGET_LANG
            ),
            None,
        )
        if selected is None:
            raise RuntimeError("Could not find Argos package en->es in the package index.")
        package_path = selected.download()
        package.install_from_path(package_path)
        print("Installed Argos en->es package.")

    translator = OfflineArgosTranslator()
    print(translator.translate("This is an offline translation test."))


if __name__ == "__main__":
    main()
