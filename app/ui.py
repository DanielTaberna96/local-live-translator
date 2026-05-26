"""
UI intentionally not implemented yet.

Per project requirements, tkinter must wait until these console validations pass:
1. output/test_capture.wav contains real system audio.
2. scripts/test_transcribe_file.py transcribes that audio in English.
3. app/translator.py translates English to Spanish offline.
"""


def main() -> None:
    raise RuntimeError("UI is blocked until the console validation checklist passes.")


if __name__ == "__main__":
    main()
