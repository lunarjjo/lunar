"""Encode float32 mono audio to compact 16-bit PCM WAV bytes (44-byte header)."""
from __future__ import annotations

import numpy as np
import struct


def wav_bytes(audio: np.ndarray, sample_rate: int) -> bytes:
    """Convert float32 [-1, 1] mono audio to WAV bytes (int16 little-endian)."""
    a = np.asarray(audio, dtype=np.float32)
    a = np.clip(a, -1.0, 1.0)
    pcm = (a * 32767.0).astype(np.int16)
    n_bytes = pcm.nbytes
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + n_bytes, b"WAVE",
        b"fmt ", 16,            # PCM chunk size
        1,                      # audio format: PCM
        1,                      # channels: mono
        sample_rate,
        sample_rate * 2,        # byte rate
        2,                      # block align
        16,                     # bits per sample
        b"data", n_bytes,
    )
    return header + pcm.tobytes()
