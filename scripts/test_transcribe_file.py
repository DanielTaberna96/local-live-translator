from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import config
from app.transcriber import ALLOWED_MODELS, LocalWhisperTranscriber


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transcribe a WAV file with faster-whisper.")
    parser.add_argument("wav_path", nargs="?", default=str(config.OUTPUT_DIR / "test_capture.wav"))
    parser.add_argument("--model", choices=sorted(ALLOWED_MODELS), default=config.WHISPER_MODEL)
    parser.add_argument("--device", choices=["cpu", "cuda"], default=config.WHISPER_DEVICE)
    parser.add_argument("--compute-type", default=config.WHISPER_COMPUTE_TYPE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    transcriber = LocalWhisperTranscriber(
        model_name=args.model,
        device=args.device,
        compute_type=args.compute_type,
    )
    text = transcriber.transcribe_file(args.wav_path)
    print(text or "[no speech detected]")


if __name__ == "__main__":
    main()
