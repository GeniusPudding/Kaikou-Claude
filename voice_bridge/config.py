"""Runtime configuration (env-driven) and platform detection.

All other modules import from here rather than reading os.environ directly so
configuration lives in one place and stays test-friendly.
"""

import os
import sys
import tempfile

from dotenv import load_dotenv

# Load a .env from the caller's CWD (install.ps1/install.sh cd into the repo
# root before starting the daemon, so relative lookup is correct).
load_dotenv()

IS_WIN = sys.platform == "win32"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")

SAMPLE_RATE = 16000
CHANNELS = 1

LANGUAGE = os.getenv("VOICE_LANGUAGE", "zh")
AUTO_SUBMIT = os.getenv("VOICE_AUTO_SUBMIT", "1") == "1"
VOICE_MARKER = os.getenv("VOICE_MARKER", " <voice>")
HOLD_THRESHOLD_SEC = float(os.getenv("VOICE_HOLD_THRESHOLD_SEC", "0.25"))
FOCUS_CACHE_TTL_SEC = float(os.getenv("FOCUS_CACHE_TTL_SEC", "0.05"))

# Fallback model used while the GPU is released to other workloads
# (scripts/release-gpu.{ps1,sh}). Lazily loaded on first release so the
# startup cost stays low. Only relevant when primary runs on CUDA.
FALLBACK_MODEL_SIZE = os.getenv("VOICE_FALLBACK_MODEL_SIZE", "small")
FALLBACK_COMPUTE_TYPE = os.getenv("VOICE_FALLBACK_COMPUTE_TYPE", "int8")
SENTINEL_POLL_SEC = float(os.getenv("VOICE_SENTINEL_POLL_SEC", "1.0"))


def _detect_cuda() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


_env_device = os.getenv("WHISPER_DEVICE")
_env_compute = os.getenv("WHISPER_COMPUTE_TYPE")
_env_model = os.getenv("WHISPER_MODEL_SIZE")

DEVICE = _env_device or ("cuda" if _detect_cuda() else "cpu")
COMPUTE_TYPE = _env_compute or ("float16" if DEVICE == "cuda" else "int8")
# large-v3-turbo: same VRAM footprint as medium (4-layer decoder vs 32), ~3-5x
# faster inference, lower WER on Mandarin. Keep small/int8 on CPU because turbo
# is decoder-light but still has the full large encoder.
MODEL_SIZE = _env_model or ("large-v3-turbo" if DEVICE == "cuda" else "small")

LOG_PATH = os.path.join(tempfile.gettempdir(), "claude-voice.log")
PID_PATH = os.path.join(tempfile.gettempdir(), "claude-voice.pid")
# Sentinel file: presence == GPU released to another workload, daemon should
# run on the CPU fallback model. Written by release-gpu, removed by acquire-gpu.
RELEASE_SENTINEL_PATH = os.path.join(tempfile.gettempdir(), "claude-voice.paused")
