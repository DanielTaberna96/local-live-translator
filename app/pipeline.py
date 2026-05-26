from __future__ import annotations

import argparse
import tempfile
import time
from pathlib import Path

from app import config
from app.audio_capture import capture_to_wav
from app.transcriber import ALLOWED_MODELS, LocalWhisperTranscriber
from app.translator import OfflineArgosTranslator


def normalize_for_dedupe(text: str) -> str:
    return " ".join(text.lower().split())


def run_console_pipeline(
    chunk_seconds: int = config.CHUNK_SECONDS,
    model_name: str = config.WHISPER_MODEL,
    whisper_device: str = config.WHISPER_DEVICE,
    compute_type: str = config.WHISPER_COMPUTE_TYPE,
    audio_device_index: int | None = config.AUDIO_DEVICE_INDEX,
) -> None:
    """Capture, transcribe, translate, and print results until interrupted."""
    transcriber = LocalWhisperTranscriber(
        model_name=model_name,
        device=whisper_device,
        compute_type=compute_type,
    )
    translator = OfflineArgosTranslator()
    last_text = ""

    print("Console pipeline started. Press Ctrl+C to stop.")
    print(f"Chunk seconds: {chunk_seconds}")
    print(f"Whisper: model={model_name}, device={whisper_device}, compute_type={compute_type}")

    with tempfile.TemporaryDirectory(prefix="local_live_translator_") as tmp_dir:
        chunk_path = Path(tmp_dir) / "chunk.wav"
        while True:
            try:
                capture_to_wav(chunk_path, chunk_seconds, device_index=audio_device_index)
                english = transcriber.transcribe_file(chunk_path)
                if len(english) < config.MIN_TRANSCRIPT_CHARS:
                    continue

                dedupe_key = normalize_for_dedupe(english)
                if dedupe_key == last_text:
                    continue
                last_text = dedupe_key

                spanish = translator.translate(english)
                print(f"EN: {english}")
                print(f"ES: {spanish}")
                print()
            except KeyboardInterrupt:
                print("Stopped.")
                break
            except Exception as exc:
                print(f"ERROR: {type(exc).__name__}: {exc}")
                time.sleep(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live offline EN->ES translator in console.")
    parser.add_argument("--chunk-seconds", type=int, default=config.CHUNK_SECONDS)
    parser.add_argument("--model", choices=sorted(ALLOWED_MODELS), default=config.WHISPER_MODEL)
    parser.add_argument("--device", choices=["cpu", "cuda"], default=config.WHISPER_DEVICE)
    parser.add_argument("--compute-type", default=config.WHISPER_COMPUTE_TYPE)
    parser.add_argument("--audio-device-index", type=int, default=config.AUDIO_DEVICE_INDEX)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_console_pipeline(
        chunk_seconds=args.chunk_seconds,
        model_name=args.model,
        whisper_device=args.device,
        compute_type=args.compute_type,
        audio_device_index=args.audio_device_index,
    )
