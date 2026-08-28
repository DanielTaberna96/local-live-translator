from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "output"
TRANSCRIPTS_DIR = OUTPUT_DIR / "transcripts"

# Capture settings.
CHUNK_SECONDS = 3
CAPTURE_SECONDS = 10
SAMPLE_RATE = 16000
SAMPLE_WIDTH_BYTES = 2

# None means: auto-select the default WASAPI loopback output device.
AUDIO_DEVICE_INDEX = None

# faster-whisper settings.
WHISPER_MODEL = "medium.en"
WHISPER_DEVICE = "cuda"  # "cpu" or "cuda"
WHISPER_COMPUTE_TYPE = "float16"  # Use "int8" for CPU, "float16" for CUDA.
WHISPER_BEAM_SIZE = 1

# Argos Translate language pair.
SOURCE_LANG = "en"
TARGET_LANG = "es"

# Translation backend: "marian" has better quality, "argos" is lighter.
TRANSLATION_BACKEND = "marian"
MARIAN_MODEL = "Helsinki-NLP/opus-mt-en-es"
MARIAN_DEVICE = "cuda"  # "cpu" or "cuda".

# Pipeline behavior.
MIN_TRANSCRIPT_CHARS = 2
SKIP_DUPLICATE_TRANSCRIPTS = False
MAX_AUDIO_QUEUE_CHUNKS = 5
UI_HISTORY_LINES = 20

# Sliding-window transcription reduces boundary losses without running multiple
# Whisper jobs in parallel.
ENABLE_SLIDING_WINDOW = False
TRANSCRIBE_WINDOW_SECONDS = 6

# Optional sentence buffering. Keep disabled for lower live latency.
ENABLE_SENTENCE_BUFFER = False
SENTENCE_BUFFER_MAX_SECONDS = 6

# Post-translation glossary. Keep this focused on domain terms Argos mistranslates.
ENABLE_GLOSSARY = True
TRANSLATION_GLOSSARY = {
    "oleoducto de datos": "pipeline de datos",
    "canalización de datos": "pipeline de datos",
    "tubería de datos": "pipeline de datos",
    "llamada en vivo": "call en vivo",
    "aprendizaje automático": "machine learning",
    "inteligencia empresarial": "business intelligence",
}

# Transcript persistence.
SAVE_TRANSCRIPT = True
