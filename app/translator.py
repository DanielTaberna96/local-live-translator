from __future__ import annotations

from argostranslate import translate

from app import config


class OfflineArgosTranslator:
    """Offline Argos Translate wrapper for English to Spanish."""

    def __init__(
        self,
        source_code: str = config.SOURCE_LANG,
        target_code: str = config.TARGET_LANG,
    ) -> None:
        self.source_code = source_code
        self.target_code = target_code
        self.translation = self._load_translation(source_code, target_code)

    @staticmethod
    def _load_translation(source_code: str, target_code: str):
        languages = translate.get_installed_languages()
        source = next((lang for lang in languages if lang.code == source_code), None)
        target = next((lang for lang in languages if lang.code == target_code), None)

        if source is None or target is None:
            raise RuntimeError(
                f"Argos language package {source_code}->{target_code} is not installed. "
                "Run scripts/install_argos_en_es.py once while online."
            )

        translation = source.get_translation(target)
        if translation is None:
            raise RuntimeError(
                f"Argos translation {source_code}->{target_code} is not available. "
                "Run scripts/install_argos_en_es.py once while online."
            )
        return translation

    def translate(self, text: str) -> str:
        normalized = " ".join(text.split())
        if not normalized:
            return ""
        return self.translation.translate(normalized)
