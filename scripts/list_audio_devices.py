from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.audio_capture import list_devices, select_loopback_device


def main() -> None:
    devices = list_devices()
    try:
        selected = select_loopback_device()
        selected_index = int(selected["index"])
    except Exception:
        selected_index = None

    for device in devices:
        index = int(device["index"])
        markers = []
        if device.get("isWasapi"):
            markers.append("WASAPI")
        if device.get("isLoopbackDevice"):
            markers.append("LOOPBACK")
        if selected_index == index:
            markers.append("AUTO_SELECTED")

        marker_text = f" [{' | '.join(markers)}]" if markers else ""
        print(
            f"{index:>3} | {device.get('hostApiName', ''):<18} | "
            f"in={int(device.get('maxInputChannels', 0)):<2} "
            f"out={int(device.get('maxOutputChannels', 0)):<2} | "
            f"{device.get('name', '')}{marker_text}"
        )


if __name__ == "__main__":
    main()
