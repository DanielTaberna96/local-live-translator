from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app import config
from app.audio_capture import capture_to_wav, select_loopback_device


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture system audio to output/test_capture.wav.")
    parser.add_argument("--seconds", type=int, default=config.CAPTURE_SECONDS)
    parser.add_argument("--device-index", type=int, default=config.AUDIO_DEVICE_INDEX)
    parser.add_argument("--output", default=str(config.OUTPUT_DIR / "test_capture.wav"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    device = select_loopback_device(args.device_index)
    print(f"Capturing WASAPI loopback device {int(device['index'])}: {device.get('name')}")
    print(f"Duration: {args.seconds}s")
    output = capture_to_wav(args.output, args.seconds, device_index=args.device_index)
    print(f"Wrote: {output}")


if __name__ == "__main__":
    main()
