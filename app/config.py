"""Runtime configuration — schema, defaults, persistence, validation.

The minimalist live console only reads a few fields; the config console edits
everything. Changes are validated here so both UIs and the REST API share one
source of truth.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from . import paths

_LOCK = threading.Lock()

DEFAULTS: dict[str, Any] = {
    # voice
    "voice": "af_heart",
    "lang": "id",                 # espeak voice code used for phonemization
    "speed": 1.0,                 # 0.5 .. 2.0
    "sentence_pause": 0.25,       # seconds of silence after a sentence
    "clause_pause": 0.10,         # seconds of silence after a clause
    # streaming / latency
    "streaming": True,            # synthesize + send per sentence chunk
    "first_chunk_fast": True,     # split early at the first comma for instant start
    "max_chunk_chars": 160,       # hard cap per chunk before splitting at commas
    # input behavior
    "enter_mode": "enter",        # "enter" | "ctrl_enter"
    # audio playback (client side, broadcast to all consoles)
    "gain": 1.0,                  # 0.0 .. 2.0
    "inter_chunk_gap_ms": 70,     # pause between streamed chunks on the client
    # appearance
    "theme": "dark",              # "dark" | "light"
    "font_size": 17,              # px
    "show_latency": True,
    "history_limit": 30,
    # engine
    "engine_variant": "fp32",     # "fp32" | "int8"
    "ort_threads": 0,             # 0 = ORT default
    "warmup_on_start": True,
    # pronunciation dictionary: word -> "say it like this" spelling
    "pron_dict_enabled": True,
    "pron_dict": {},
}

SUPPORTED_LANGS = {
    "id": "Indonesian",
    "en-us": "English (US)",
    "en-gb": "English (UK)",
    "es": "Spanish",
    "fr-fr": "French",
    "it": "Italian",
    "pt-br": "Portuguese (BR)",
    "hi": "Hindi",
    "pl": "Polish",
    "de": "German",
}

RANGES = {
    "speed": (0.5, 2.0),
    "sentence_pause": (0.0, 1.0),
    "clause_pause": (0.0, 0.6),
    "gain": (0.0, 2.0),
    "inter_chunk_gap_ms": (0, 600),
    "font_size": (12, 30),
    "history_limit": (0, 200),
    "max_chunk_chars": (40, 400),
    "ort_threads": (0, 16),
}

_CHOICES = {
    "enter_mode": ("enter", "ctrl_enter"),
    "theme": ("dark", "light"),
    "engine_variant": ("fp32", "int8"),
}


def _coerce(key: str, value: Any) -> Any:
    lo, hi = RANGES[key]
    if isinstance(value, bool):
        value = float(value)
    try:
        value = float(value)
    except (TypeError, ValueError):
        return DEFAULTS[key]
    if value != value:  # NaN
        return DEFAULTS[key]
    return type(DEFAULTS[key])(min(max(value, lo), hi))


def sanitize(patch: dict[str, Any]) -> dict[str, Any]:
    """Return a safe, fully-typed config from a (possibly untrusted) patch."""
    out = dict(DEFAULTS)
    if not isinstance(patch, dict):
        return out
    for key, value in patch.items():
        if key not in DEFAULTS:
            continue
        default = DEFAULTS[key]
        if key in RANGES:
            out[key] = _coerce(key, value)
        elif isinstance(default, bool):
            out[key] = bool(value) if not isinstance(value, str) else value.lower() in ("1", "true", "on", "yes")
        elif isinstance(default, str):
            value = str(value)
            if key in _CHOICES and value not in _CHOICES[key]:
                continue
            if key == "voice" and not _valid_voice_name(value):
                continue
            if key == "lang" and value not in SUPPORTED_LANGS:
                continue
            out[key] = value
        elif isinstance(default, int) and not isinstance(default, bool):
            try:
                out[key] = int(value)
            except (TypeError, ValueError):
                continue
        elif isinstance(default, float):
            try:
                out[key] = float(value)
            except (TypeError, ValueError):
                continue
    # pronunciation dictionary: keep only sane entries
    pron = patch.get("pron_dict", DEFAULTS["pron_dict"])
    if isinstance(pron, dict):
        clean = {}
        for k, v in pron.items():
            try:
                k, v = str(k).strip(), str(v).strip()
            except Exception:
                continue
            if k and v and len(k) <= 64 and len(v) <= 128 and len(clean) < 1000:
                clean[k] = v
        out["pron_dict"] = clean
    else:
        out["pron_dict"] = dict(DEFAULTS["pron_dict"])
    return out


def _valid_voice_name(name: str) -> bool:
    return (
        len(name) <= 32
        and all(c.isalnum() or c in "_-" for c in name)
        and name[0].isalpha() if name else False
    )


def load() -> dict[str, Any]:
    paths.ensure_dirs()
    file: Path = paths.CONFIG_FILE
    if file.exists():
        try:
            with open(file, encoding="utf-8") as fp:
                return sanitize(json.load(fp))
        except (OSError, json.JSONDecodeError):
            pass
    return dict(DEFAULTS)


def save(cfg: dict[str, Any]) -> dict[str, Any]:
    paths.ensure_dirs()
    clean = sanitize(cfg)
    with _LOCK:
        tmp = paths.CONFIG_FILE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(clean, fp, indent=2, ensure_ascii=False, sort_keys=True)
        tmp.replace(paths.CONFIG_FILE)
    return clean
