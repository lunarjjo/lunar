"""Filesystem layout. Everything lives inside the repo so the app is portable."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = ROOT / "models"
VOICES_DIR = ROOT / "voices"
CONFIG_DIR = ROOT / "config"
CONFIG_FILE = CONFIG_DIR / "config.json"
WEB_DIR = ROOT / "web"

MODEL_FILES = {
    "fp32": MODELS_DIR / "kokoro-v1.0.onnx",
    "int8": MODELS_DIR / "kokoro-v1.0.int8.onnx",
}
VOICES_FILE = VOICES_DIR / "voices-v1.0.bin"


def model_path(variant: str) -> Path:
    return MODEL_FILES[variant]


def ensure_dirs() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    VOICES_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
