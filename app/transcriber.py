from __future__ import annotations

from pathlib import Path

from faster_whisper import WhisperModel

from app import config


ALLOWED_MODELS = {"tiny.en", "base.en", "small.en", "medium.en"}


class LocalWhisperTranscriber:
    """Small wrapper around faster-whisper for local English transcription."""

    def __init__(
        self,
        model_name: str = config.WHISPER_MODEL,
        device: str = config.WHISPER_DEVICE,
        compute_type: str = config.WHISPER_COMPUTE_TYPE,
        beam_size: int = config.WHISPER_BEAM_SIZE,
    ) -> None:
        if model_name not in ALLOWED_MODELS:
            allowed = ", ".join(sorted(ALLOWED_MODELS))
            raise ValueError(f"Unsupported model '{model_name}'. Allowed: {allowed}")

        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.beam_size = beam_size
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)

    def transcribe_file(self, wav_path: str | Path) -> str:
        path = Path(wav_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        segments, _info = self.model.transcribe(
            str(path),
            language="en",
            beam_size=self.beam_size,
            vad_filter=True,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        return " ".join(text.split())
