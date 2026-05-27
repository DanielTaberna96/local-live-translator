# Local Live Translator v0.1.0

Initial Windows MVP.

## Highlights

- Captures Windows system audio using WASAPI loopback.
- Transcribes locally with `faster-whisper`.
- Uses CUDA GPU acceleration for Whisper.
- Translates EN -> ES offline with MarianMT by default.
- Includes Argos Translate as a fallback backend.
- Provides an always-on-top Tkinter UI.
- Saves Markdown transcripts per session.
- Includes a packaged Windows `onedir` build.

## Recommended Runtime Profile

```text
Whisper model: medium.en
Whisper device: cuda
Compute type: float16
Translation backend: marian
Marian device: cuda
Chunk size: 3 seconds
```

## Package

Download and extract:

```text
LocalLiveTranslator-windows-v0.1.0.zip
```

Run:

```text
LocalLiveTranslator/LocalLiveTranslator.exe
```

Do not move the `.exe` out of its folder. It depends on files inside `_internal/`.

## Notes

- First use may require internet if the Whisper or MarianMT models are not cached yet.
- After models are cached, transcription and translation run locally.
- The packaged build is large because it includes native ML dependencies.
- This is chunk-based live translation, not true word-by-word streaming ASR.
