from __future__ import annotations

import argparse
import math
import queue
import tempfile
import threading
import time
import wave
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from app import config
from app.audio_capture import capture_to_wav
from app.transcriber import ALLOWED_MODELS, LocalWhisperTranscriber
from app.translator import create_translator_for_backend


TranslationCallback = Callable[[str, str], None]
ErrorCallback = Callable[[Exception], None]
StatusCallback = Callable[[str], None]
TranscriptCallback = Callable[[Path], None]


@dataclass
class AudioChunk:
    sequence: int
    path: Path
    captured_at: float


def normalize_for_dedupe(text: str) -> str:
    return " ".join(text.lower().split())


def normalize_word(word: str) -> str:
    return "".join(char.lower() for char in word if char.isalnum())


def extract_new_text(previous: str, current: str) -> str:
    """Return the likely new suffix from a sliding-window transcript."""
    previous_words = previous.split()
    current_words = current.split()
    if not previous_words:
        return current
    if not current_words:
        return ""

    normalized_previous = [normalize_word(word) for word in previous_words]
    normalized_current = [normalize_word(word) for word in current_words]

    best_overlap = 0
    max_overlap = min(len(normalized_previous), len(normalized_current))
    for size in range(1, max_overlap + 1):
        if normalized_previous[-size:] == normalized_current[:size]:
            best_overlap = size

    if best_overlap:
        return " ".join(current_words[best_overlap:]).strip()

    previous_norm = normalize_for_dedupe(previous)
    current_norm = normalize_for_dedupe(current)
    if current_norm in previous_norm:
        return ""
    if previous_norm and current_norm.startswith(previous_norm):
        return current[len(previous) :].strip()
    return current


def write_window_wav(chunks: list[AudioChunk], output_path: Path) -> None:
    """Concatenate recent WAV chunks into a single transcription window."""
    if not chunks:
        raise ValueError("Cannot write a transcription window without chunks.")

    params = None
    frames: list[bytes] = []
    for chunk in chunks:
        with wave.open(str(chunk.path), "rb") as wav_file:
            current_params = wav_file.getparams()
            if params is None:
                params = current_params
            elif (
                current_params.nchannels != params.nchannels
                or current_params.sampwidth != params.sampwidth
                or current_params.framerate != params.framerate
                or current_params.comptype != params.comptype
            ):
                raise RuntimeError("Captured chunks have incompatible WAV formats.")
            frames.append(wav_file.readframes(wav_file.getnframes()))

    with wave.open(str(output_path), "wb") as wav_file:
        wav_file.setparams(params)
        wav_file.writeframes(b"".join(frames))


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        frame_rate = wav_file.getframerate()
        if frame_rate <= 0:
            return 0.0
        return wav_file.getnframes() / frame_rate


class SentenceBuffer:
    """Accumulate chunk text until it looks safe to translate."""

    def __init__(self, max_seconds: int = config.SENTENCE_BUFFER_MAX_SECONDS) -> None:
        self.max_seconds = max_seconds
        self.parts: list[str] = []
        self.started_at: float | None = None

    def add(self, text: str) -> str | None:
        normalized = " ".join(text.split())
        if not normalized:
            return None

        now = time.perf_counter()
        if self.started_at is None:
            self.started_at = now
        self.parts.append(normalized)

        buffered = self.current_text()
        if self._has_strong_sentence_end(buffered):
            return self.flush()
        if self.started_at is not None and now - self.started_at >= self.max_seconds:
            return self.flush()
        return None

    def current_text(self) -> str:
        return " ".join(self.parts).strip()

    def flush(self) -> str | None:
        text = self.current_text()
        self.parts.clear()
        self.started_at = None
        return text or None

    @staticmethod
    def _has_strong_sentence_end(text: str) -> bool:
        return text.rstrip().endswith((".", "?", "!"))


def create_transcript_path() -> Path:
    config.TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return config.TRANSCRIPTS_DIR / f"live_transcript_{timestamp}.md"


def append_transcript_entry(path: Path, english: str, spanish: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    with path.open("a", encoding="utf-8") as file:
        file.write(f"## {timestamp}\n\n")
        file.write(f"EN: {english}\n\n")
        file.write(f"ES: {spanish}\n\n")


def _put_latest_audio_chunk(
    audio_queue: queue.Queue[AudioChunk],
    chunk: AudioChunk,
    on_status: StatusCallback | None,
) -> None:
    if audio_queue.full():
        try:
            dropped = audio_queue.get_nowait()
            dropped.path.unlink(missing_ok=True)
            if on_status:
                on_status(f"Dropped old audio; backlog={audio_queue.qsize()}")
        except queue.Empty:
            pass
    audio_queue.put(chunk)


def run_realtime_translation_loop(
    chunk_seconds: int = config.CHUNK_SECONDS,
    model_name: str = config.WHISPER_MODEL,
    whisper_device: str = config.WHISPER_DEVICE,
    compute_type: str = config.WHISPER_COMPUTE_TYPE,
    beam_size: int = config.WHISPER_BEAM_SIZE,
    audio_device_index: int | None = config.AUDIO_DEVICE_INDEX,
    max_queue_chunks: int = config.MAX_AUDIO_QUEUE_CHUNKS,
    translation_backend: str = config.TRANSLATION_BACKEND,
    on_translation: TranslationCallback | None = None,
    on_error: ErrorCallback | None = None,
    on_status: StatusCallback | None = None,
    on_transcript: TranscriptCallback | None = None,
    stop_event: threading.Event | None = None,
) -> None:
    """
    Capture audio continuously while transcribing/translating previous chunks.

    This reduces lost audio versus the simple sequential loop. If processing
    falls behind, old chunks are dropped to keep latency bounded.
    """
    should_stop = stop_event or threading.Event()
    audio_queue: queue.Queue[AudioChunk] = queue.Queue(maxsize=max_queue_chunks)
    capture_done = threading.Event()
    last_text = ""
    sentence_buffer = SentenceBuffer()
    transcript_path = create_transcript_path() if config.SAVE_TRANSCRIPT else None
    if transcript_path and on_transcript:
        on_transcript(transcript_path)
    window_chunk_count = max(1, math.ceil(config.TRANSCRIBE_WINDOW_SECONDS / chunk_seconds))
    recent_chunks: deque[AudioChunk] = deque(maxlen=window_chunk_count)

    if on_status:
        on_status("Loading Whisper model...")
    transcriber = LocalWhisperTranscriber(
        model_name=model_name,
        device=whisper_device,
        compute_type=compute_type,
        beam_size=beam_size,
    )
    if on_status:
        on_status(f"Loading {translation_backend} translator...")
    translator = create_translator_for_backend(translation_backend)

    with tempfile.TemporaryDirectory(prefix="local_live_translator_") as tmp_dir:
        tmp_path = Path(tmp_dir)

        def capture_worker() -> None:
            sequence = 0
            while not should_stop.is_set():
                chunk_path = tmp_path / f"chunk_{sequence:06d}.wav"
                try:
                    if on_status:
                        on_status(f"Capturing audio... backlog={audio_queue.qsize()}")
                    capture_to_wav(chunk_path, chunk_seconds, device_index=audio_device_index)
                    if should_stop.is_set():
                        chunk_path.unlink(missing_ok=True)
                        break
                    _put_latest_audio_chunk(
                        audio_queue,
                        AudioChunk(sequence=sequence, path=chunk_path, captured_at=time.perf_counter()),
                        on_status,
                    )
                    sequence += 1
                except Exception as exc:
                    if on_error:
                        on_error(exc)
                    time.sleep(1)
            capture_done.set()

        capture_thread = threading.Thread(target=capture_worker, daemon=True)
        capture_thread.start()

        while not should_stop.is_set() or not audio_queue.empty():
            try:
                chunk = audio_queue.get(timeout=0.2)
            except queue.Empty:
                if capture_done.is_set():
                    break
                continue

            try:
                if on_status:
                    age = time.perf_counter() - chunk.captured_at
                    on_status(f"Transcribing... backlog={audio_queue.qsize()} lag={age:.1f}s")
                removed_path = recent_chunks[0].path if len(recent_chunks) == recent_chunks.maxlen else None
                recent_chunks.append(chunk)
                if removed_path and removed_path not in [item.path for item in recent_chunks]:
                    removed_path.unlink(missing_ok=True)

                if config.ENABLE_SLIDING_WINDOW:
                    window_path = tmp_path / "transcribe_window.wav"
                    write_window_wav(list(recent_chunks), window_path)
                    window_duration = wav_duration_seconds(window_path)
                    emit_after = max(0.0, window_duration - chunk_seconds - 0.25)
                    segments = transcriber.transcribe_segments(window_path)
                    english = " ".join(
                        segment.text for segment in segments if segment.end >= emit_after
                    )
                    english = " ".join(english.split())
                else:
                    english = transcriber.transcribe_file(chunk.path)

                if len(english) < config.MIN_TRANSCRIPT_CHARS:
                    continue

                dedupe_key = normalize_for_dedupe(english)
                if config.SKIP_DUPLICATE_TRANSCRIPTS and dedupe_key == last_text:
                    continue
                last_text = dedupe_key

                text_to_translate = (
                    sentence_buffer.add(english) if config.ENABLE_SENTENCE_BUFFER else english
                )
                if not text_to_translate:
                    if on_status:
                        on_status(f"Buffering sentence... backlog={audio_queue.qsize()}")
                    continue

                if on_status:
                    on_status(f"Translating... backlog={audio_queue.qsize()}")
                spanish = translator.translate(text_to_translate)
                if transcript_path:
                    append_transcript_entry(transcript_path, text_to_translate, spanish)
                if on_translation:
                    on_translation(text_to_translate, spanish)
            except KeyboardInterrupt:
                should_stop.set()
                break
            except Exception as exc:
                if on_error:
                    on_error(exc)
                time.sleep(1)

        should_stop.set()
        capture_thread.join(timeout=chunk_seconds + 1)
        for chunk in recent_chunks:
            chunk.path.unlink(missing_ok=True)

        buffered = sentence_buffer.flush()
        if buffered:
            spanish = translator.translate(buffered)
            if transcript_path:
                append_transcript_entry(transcript_path, buffered, spanish)
            if on_translation:
                on_translation(buffered, spanish)


def run_translation_loop(
    chunk_seconds: int = config.CHUNK_SECONDS,
    model_name: str = config.WHISPER_MODEL,
    whisper_device: str = config.WHISPER_DEVICE,
    compute_type: str = config.WHISPER_COMPUTE_TYPE,
    beam_size: int = config.WHISPER_BEAM_SIZE,
    audio_device_index: int | None = config.AUDIO_DEVICE_INDEX,
    translation_backend: str = config.TRANSLATION_BACKEND,
    on_translation: TranslationCallback | None = None,
    on_error: ErrorCallback | None = None,
    on_status: StatusCallback | None = None,
    on_transcript: TranscriptCallback | None = None,
    stop_event: threading.Event | None = None,
) -> None:
    """Capture, transcribe, translate, and emit results until stopped."""
    if on_status:
        on_status("Loading Whisper model...")
    transcriber = LocalWhisperTranscriber(
        model_name=model_name,
        device=whisper_device,
        compute_type=compute_type,
        beam_size=beam_size,
    )
    if on_status:
        on_status(f"Loading {translation_backend} translator...")
    translator = create_translator_for_backend(translation_backend)
    last_text = ""
    should_stop = stop_event or threading.Event()
    sentence_buffer = SentenceBuffer()
    transcript_path = create_transcript_path() if config.SAVE_TRANSCRIPT else None
    if transcript_path and on_transcript:
        on_transcript(transcript_path)

    with tempfile.TemporaryDirectory(prefix="local_live_translator_") as tmp_dir:
        chunk_path = Path(tmp_dir) / "chunk.wav"
        while not should_stop.is_set():
            try:
                if on_status:
                    on_status("Capturing audio...")
                capture_to_wav(chunk_path, chunk_seconds, device_index=audio_device_index)
                if should_stop.is_set():
                    break

                if on_status:
                    on_status("Transcribing...")
                english = transcriber.transcribe_file(chunk_path)
                if len(english) < config.MIN_TRANSCRIPT_CHARS:
                    continue

                dedupe_key = normalize_for_dedupe(english)
                if config.SKIP_DUPLICATE_TRANSCRIPTS and dedupe_key == last_text:
                    continue
                last_text = dedupe_key

                text_to_translate = (
                    sentence_buffer.add(english) if config.ENABLE_SENTENCE_BUFFER else english
                )
                if not text_to_translate:
                    if on_status:
                        on_status("Buffering sentence...")
                    continue

                if on_status:
                    on_status("Translating...")
                spanish = translator.translate(text_to_translate)
                if transcript_path:
                    append_transcript_entry(transcript_path, text_to_translate, spanish)
                if on_translation:
                    on_translation(text_to_translate, spanish)
            except KeyboardInterrupt:
                break
            except Exception as exc:
                if on_error:
                    on_error(exc)
                time.sleep(1)

        buffered = sentence_buffer.flush()
        if buffered:
            spanish = translator.translate(buffered)
            if transcript_path:
                append_transcript_entry(transcript_path, buffered, spanish)
            if on_translation:
                on_translation(buffered, spanish)


def run_console_pipeline(
    chunk_seconds: int = config.CHUNK_SECONDS,
    model_name: str = config.WHISPER_MODEL,
    whisper_device: str = config.WHISPER_DEVICE,
    compute_type: str = config.WHISPER_COMPUTE_TYPE,
    beam_size: int = config.WHISPER_BEAM_SIZE,
    audio_device_index: int | None = config.AUDIO_DEVICE_INDEX,
    translation_backend: str = config.TRANSLATION_BACKEND,
) -> None:
    """Capture, transcribe, translate, and print results until interrupted."""
    print("Console pipeline started. Press Ctrl+C to stop.")
    print(f"Chunk seconds: {chunk_seconds}")
    print(
        f"Whisper: model={model_name}, device={whisper_device}, "
        f"compute_type={compute_type}, beam_size={beam_size}"
    )

    def print_translation(english: str, spanish: str) -> None:
        print(f"EN: {english}")
        print(f"ES: {spanish}")
        print()

    def print_error(exc: Exception) -> None:
        print(f"ERROR: {type(exc).__name__}: {exc}")

    run_realtime_translation_loop(
        chunk_seconds=chunk_seconds,
        model_name=model_name,
        whisper_device=whisper_device,
        compute_type=compute_type,
        beam_size=beam_size,
        audio_device_index=audio_device_index,
        translation_backend=translation_backend,
        on_translation=print_translation,
        on_error=print_error,
    )
    print("Stopped.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run live offline EN->ES translator in console.")
    parser.add_argument("--chunk-seconds", type=int, default=config.CHUNK_SECONDS)
    parser.add_argument("--model", choices=sorted(ALLOWED_MODELS), default=config.WHISPER_MODEL)
    parser.add_argument("--device", choices=["cpu", "cuda"], default=config.WHISPER_DEVICE)
    parser.add_argument("--compute-type", default=config.WHISPER_COMPUTE_TYPE)
    parser.add_argument("--beam-size", type=int, default=config.WHISPER_BEAM_SIZE)
    parser.add_argument("--audio-device-index", type=int, default=config.AUDIO_DEVICE_INDEX)
    parser.add_argument("--translation-backend", choices=["argos", "marian"], default=config.TRANSLATION_BACKEND)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_console_pipeline(
        chunk_seconds=args.chunk_seconds,
        model_name=args.model,
        whisper_device=args.device,
        compute_type=args.compute_type,
        beam_size=args.beam_size,
        audio_device_index=args.audio_device_index,
        translation_backend=args.translation_backend,
    )
