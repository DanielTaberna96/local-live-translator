# Local Live Translator

Offline Windows live translator for English audio to Spanish text.

It captures system output audio through WASAPI loopback, transcribes locally with `faster-whisper`, and translates offline with MarianMT (`Helsinki-NLP/opus-mt-en-es`) by default. Argos Translate is available as a lighter fallback. No cloud APIs are used for transcription or translation.

## Features

- Windows system-audio capture through WASAPI loopback.
- Local Whisper transcription with `faster-whisper`.
- GPU mode with CUDA + `float16`.
- Offline EN -> ES translation with MarianMT (`Helsinki-NLP/opus-mt-en-es`) by default.
- Optional Argos Translate backend.
- Always-on-top Tkinter UI.
- Whisper model and translation backend selector.
- Markdown transcript saved per session.
- PyInstaller Windows build.

## Tested Environment

This MVP was built and tested on:

- Windows 10/11.
- Python 3.11.
- NVIDIA GeForce RTX 3080.
- NVIDIA driver with CUDA runtime available.
- `faster-whisper` using CUDA + `float16`.
- WASAPI loopback via PyAudioWPatch.
- Whisper model: `medium.en`.
- MarianMT model: `Helsinki-NLP/opus-mt-en-es`.

Other GPUs or CPU-only setups may require changing `app/config.py`.

## Current Stable Profile

```python
CHUNK_SECONDS = 3
AUDIO_DEVICE_INDEX = None
WHISPER_MODEL = "medium.en"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE_TYPE = "float16"
WHISPER_BEAM_SIZE = 1
TRANSLATION_BACKEND = "marian"
MARIAN_DEVICE = "cuda"
ENABLE_SLIDING_WINDOW = False
ENABLE_SENTENCE_BUFFER = False
```

## Using the Packaged App

Use the whole `dist/LocalLiveTranslator/` folder. Do not move only the `.exe`; it depends on files inside `_internal/`.

Run:

```powershell
dist\LocalLiveTranslator\LocalLiveTranslator.exe
```

In the app:

1. Play English audio through the Windows output device you want to capture.
2. Choose model `medium.en`.
3. Choose backend `marian`.
4. Press `Start`.
5. Read the English transcription and Spanish translation in the window.
6. Use `Open Transcripts` to open saved Markdown transcripts.

Transcripts are saved in:

```text
output/transcripts/
```

The first run may require internet if the Whisper or MarianMT models are not already cached on the machine. After models are installed/cached, runtime transcription and translation are local.

## Running from Source

From the repo root:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Install or verify Argos EN -> ES package if you want the Argos fallback:

```powershell
python scripts\install_argos_en_es.py
```

List audio devices and confirm a `LOOPBACK` device exists:

```powershell
python scripts\list_audio_devices.py
```

Capture a test WAV:

```powershell
python scripts\test_capture_to_wav.py
```

Validate transcription:

```powershell
python scripts\test_transcribe_file.py output\test_capture.wav --model medium.en --device cuda --compute-type float16 --beam-size 1
```

Run the UI:

```powershell
python -m app.ui
```

Run the console pipeline:

```powershell
python -m app.pipeline --translation-backend marian
```

## Configuration

Edit `app/config.py`:

- `CHUNK_SECONDS`: audio chunk size.
- `AUDIO_DEVICE_INDEX`: loopback device index; `None` auto-selects a loopback output.
- `WHISPER_MODEL`: `tiny.en`, `base.en`, `small.en`, `medium.en`, `large-v3-turbo`.
- `WHISPER_DEVICE`: `cpu` or `cuda`.
- `WHISPER_COMPUTE_TYPE`: `int8` for CPU, `float16` for CUDA.
- `WHISPER_BEAM_SIZE`: `1` prioritizes latency.
- `TRANSLATION_BACKEND`: `marian` or `argos`.
- `MARIAN_DEVICE`: `cpu` or `cuda`.
- `MAX_AUDIO_QUEUE_CHUNKS`: backlog limit before old audio is dropped.
- `UI_HISTORY_LINES`: visible history size.
- `SAVE_TRANSCRIPT`: save Markdown transcript per session.

Experimental options:

- `ENABLE_SLIDING_WINDOW`: tested, currently disabled by default because it introduced duplicate/hallucinated text.
- `ENABLE_SENTENCE_BUFFER`: tested, currently disabled by default because it adds latency.
- `ENABLE_GLOSSARY`: optional post-translation replacements.

## Packaging

The recommended build is `onedir`, not `onefile`, because CUDA, Torch, Transformers, and native DLLs make `onefile` slow and harder to debug.

Install PyInstaller:

```powershell
pip install pyinstaller
```

Build:

```powershell
pyinstaller --noconfirm --clean --windowed --name LocalLiveTranslator `
  --collect-all argostranslate `
  --collect-all transformers `
  --collect-all tokenizers `
  --collect-all sentencepiece `
  --collect-all sacremoses `
  --collect-all stanza `
  --collect-all ctranslate2 `
  --collect-all faster_whisper `
  --collect-all nvidia `
  main.py
```

Output:

```text
dist/LocalLiveTranslator/LocalLiveTranslator.exe
```

The build can be several GB.

## Limitations

- This is chunk-based live translation, not true word-by-word streaming ASR.
- Accuracy depends heavily on source audio quality and speaker clarity.
- Proper nouns, company names, and product names may be misrecognized.
- Short chunks can cut phrases; longer chunks add latency.
- First setup may require internet to download models/packages.
- Packaged builds are large due to native ML dependencies.

## Troubleshooting

### Only microphones appear, no loopback

Run:

```powershell
python scripts\list_audio_devices.py
```

Confirm Windows has an active output device and audio is playing. Do not force a microphone device; the app is designed for WASAPI loopback.

### WAV has no audio

- Make sure audio is playing during capture.
- Try another device marked `LOOPBACK`.
- Confirm Windows output is not going to another HDMI/Bluetooth device.

### CUDA fails

Try CPU first:

```powershell
python scripts\test_transcribe_file.py output\test_capture.wav --device cpu --compute-type int8
```

If CUDA says `cublas64_12.dll is not found`, reinstall:

```powershell
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-runtime-cu12
```

### MarianMT is not downloaded

Run the app once with internet or execute a small translation test. The model is cached locally by Hugging Face.

### Latency is high

- Use `medium.en` or `small.en`, not `large-v3-turbo`.
- Keep `WHISPER_BEAM_SIZE = 1`.
- Keep `CHUNK_SECONDS = 3` for the best tested balance.
- Close other GPU-heavy apps.
