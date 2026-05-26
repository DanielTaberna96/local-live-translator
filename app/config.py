from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "output"

# Capture settings.
CHUNK_SECONDS = 4
CAPTURE_SECONDS = 10
SAMPLE_RATE = 16000
SAMPLE_WIDTH_BYTES = 2

# None means: auto-select the default WASAPI loopback output device.
AUDIO_DEVICE_INDEX = None

# faster-whisper settings.
WHISPER_MODEL = "small.en"
WHISPER_DEVICE = "cpu"  # "cpu" or "cuda"
WHISPER_COMPUTE_TYPE = "int8"  # CPU-friendly default. Use "float16" for CUDA.
WHISPER_BEAM_SIZE = 5

# Argos Translate language pair.
SOURCE_LANG = "en"
TARGET_LANG = "es"

# Pipeline behavior.
MIN_TRANSCRIPT_CHARS = 2
