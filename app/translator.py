from __future__ import annotations

import re
from typing import Protocol

from argostranslate import translate

from app import config


class TextTranslator(Protocol):
    def translate(self, text: str) -> str:
        ...


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
        translated = self.translation.translate(normalized)
        return apply_glossary(translated)


def apply_glossary(text: str) -> str:
    if not config.ENABLE_GLOSSARY:
        return text

    result = text
    for source, replacement in config.TRANSLATION_GLOSSARY.items():
        result = re.sub(re.escape(source), replacement, result, flags=re.IGNORECASE)
    return result


class OfflineMarianTranslator:
    """Offline MarianMT wrapper using a locally cached Hugging Face model."""

    def __init__(
        self,
        model_name: str = config.MARIAN_MODEL,
        device: str = config.MARIAN_DEVICE,
    ) -> None:
        import torch
        from transformers import MarianMTModel, MarianTokenizer

        self.device_name = device
        self.torch_device = torch.device("cuda" if device == "cuda" and torch.cuda.is_available() else "cpu")
        self.tokenizer = MarianTokenizer.from_pretrained(model_name)
        self.model = MarianMTModel.from_pretrained(model_name).to(self.torch_device)
        self.model.eval()

    def translate(self, text: str) -> str:
        normalized = " ".join(text.split())
        if not normalized:
            return ""

        batch = self.tokenizer([normalized], return_tensors="pt", padding=True, truncation=True)
        batch = {key: value.to(self.torch_device) for key, value in batch.items()}
        generated = self.model.generate(**batch, max_new_tokens=160, num_beams=1)
        translated = self.tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
        return apply_glossary(translated)


def create_translator() -> TextTranslator:
    return create_translator_for_backend(config.TRANSLATION_BACKEND)


def create_translator_for_backend(backend_name: str) -> TextTranslator:
    backend = backend_name.lower()
    if backend == "argos":
        return OfflineArgosTranslator()
    if backend == "marian":
        return OfflineMarianTranslator()
    raise ValueError(f"Unsupported TRANSLATION_BACKEND: {config.TRANSLATION_BACKEND}")
