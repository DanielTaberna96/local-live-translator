from __future__ import annotations

import os
import site
import sys
from dataclasses import dataclass
from pathlib import Path

from app import config


ALLOWED_MODELS = {"tiny.en", "base.en", "small.en", "medium.en", "large-v3-turbo"}
_DLL_DIRECTORY_HANDLES = []


def _add_nvidia_dll_directories() -> None:
    """Make pip-installed NVIDIA CUDA DLLs visible to CTranslate2 on Windows."""
    if sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
        return

    candidates: list[Path] = []
    for site_path in site.getsitepackages():
        nvidia_root = Path(site_path) / "nvidia"
        if nvidia_root.exists():
            candidates.extend(nvidia_root.glob("*\\bin"))

    existing_path = os.environ.get("PATH", "")
    bin_paths: list[str] = []
    for path in candidates:
        if path.exists():
            bin_paths.append(str(path))
            _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(str(path)))

    if bin_paths:
        os.environ["PATH"] = os.pathsep.join(bin_paths + [existing_path])


_add_nvidia_dll_directories()

from faster_whisper import WhisperModel


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


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

    def transcribe_segments(self, wav_path: str | Path) -> list[TranscriptSegment]:
        path = Path(wav_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        segments, _info = self.model.transcribe(
            str(path),
            language="en",
            beam_size=self.beam_size,
            vad_filter=True,
            condition_on_previous_text=False,
            temperature=0,
        )
        return [
            TranscriptSegment(start=segment.start, end=segment.end, text=segment.text.strip())
            for segment in segments
            if segment.text.strip()
        ]

    def transcribe_file(self, wav_path: str | Path) -> str:
        segments = self.transcribe_segments(wav_path)
        text = " ".join(segment.text for segment in segments)
        return " ".join(text.split())
