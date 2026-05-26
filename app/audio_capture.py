from __future__ import annotations

import time
import wave
from pathlib import Path
from typing import Any

import pyaudiowpatch as pyaudio

from app import config


AudioDevice = dict[str, Any]


def list_devices() -> list[AudioDevice]:
    """Return PyAudio device metadata, annotated with loopback/WASAPI flags."""
    devices: list[AudioDevice] = []
    with pyaudio.PyAudio() as audio:
        for index in range(audio.get_device_count()):
            info = dict(audio.get_device_info_by_index(index))
            host_api = audio.get_host_api_info_by_index(info["hostApi"])
            info["hostApiName"] = host_api.get("name", "")
            info["isWasapi"] = info["hostApiName"].upper() == "WASAPI"
            info["isLoopbackDevice"] = bool(info.get("isLoopbackDevice", False))
            devices.append(info)
    return devices


def get_loopback_devices() -> list[AudioDevice]:
    """Return loopback capture devices exposed by PyAudioWPatch."""
    with pyaudio.PyAudio() as audio:
        return [dict(device) for device in audio.get_loopback_device_info_generator()]


def select_loopback_device(device_index: int | None = None) -> AudioDevice:
    """
    Select a WASAPI loopback device.

    If device_index is provided, it must already be a loopback device. If not,
    this function tries to match the default output device to its loopback pair.
    It never silently falls back to a microphone.
    """
    with pyaudio.PyAudio() as audio:
        if device_index is not None:
            device = dict(audio.get_device_info_by_index(device_index))
            if not device.get("isLoopbackDevice", False):
                raise RuntimeError(
                    f"Device index {device_index} is not a loopback device. "
                    "Refusing to capture microphone/input audio."
                )
            return device

        try:
            wasapi_info = audio.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError as exc:
            raise RuntimeError("WASAPI host API was not found on this system.") from exc

        default_output_index = wasapi_info.get("defaultOutputDevice")
        default_output = (
            dict(audio.get_device_info_by_index(default_output_index))
            if default_output_index is not None and default_output_index >= 0
            else None
        )

        loopbacks = [dict(device) for device in audio.get_loopback_device_info_generator()]
        if not loopbacks:
            raise RuntimeError(
                "No WASAPI loopback devices were found. "
                "Run scripts/list_audio_devices.py and check Windows output devices."
            )

        if default_output:
            default_name = str(default_output.get("name", "")).strip()
            for device in loopbacks:
                if default_name and default_name in str(device.get("name", "")):
                    return device

        return loopbacks[0]


def capture_to_wav(
    output_path: str | Path,
    seconds: int | float,
    device_index: int | None = None,
    sample_rate: int = config.SAMPLE_RATE,
) -> Path:
    """Capture system output audio through WASAPI loopback and write a mono WAV."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    device = select_loopback_device(device_index)
    source_rate = int(device.get("defaultSampleRate") or sample_rate)
    channels = int(device.get("maxInputChannels") or 2)
    frames_per_buffer = 1024

    with pyaudio.PyAudio() as audio:
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=source_rate,
            input=True,
            input_device_index=int(device["index"]),
            frames_per_buffer=frames_per_buffer,
        )
        frames: list[bytes] = []
        deadline = time.monotonic() + float(seconds)
        try:
            while time.monotonic() < deadline:
                frames.append(stream.read(frames_per_buffer, exception_on_overflow=False))
        finally:
            stream.stop_stream()
            stream.close()

    with wave.open(str(output), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(config.SAMPLE_WIDTH_BYTES)
        wav_file.setframerate(source_rate)
        wav_file.writeframes(b"".join(frames))

    return output
