import io
import struct
import wave

import numpy as np
import pytest

from app.wav import wav_bytes


def test_header_layout():
    audio = np.zeros(240, dtype=np.float32)
    data = wav_bytes(audio, 24000)
    assert data[:4] == b"RIFF"
    assert data[8:12] == b"WAVE"
    assert struct.unpack("<I", data[4:8])[0] == len(data) - 8
    # 240 samples * 2 bytes + 44 header
    assert len(data) == 44 + 480


def test_roundtrip():
    audio = np.linspace(-0.9, 0.9, 5000, dtype=np.float32)
    data = wav_bytes(audio, 24000)
    with wave.open(io.BytesIO(data)) as w:
        assert w.getframerate() == 24000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2
        assert w.getnframes() == 5000
        pcm = np.frombuffer(w.readframes(5000), dtype=np.int16)
    assert pcm[0] == pytest.approx(int(-0.9 * 32767), abs=2)


def test_clipping():
    audio = np.array([2.0, -2.0, 0.0], dtype=np.float32)
    data = wav_bytes(audio, 24000)
    pcm = np.frombuffer(data[44:], dtype=np.int16)
    assert pcm[0] == 32767
    assert pcm[1] == -32767
    assert pcm[2] == 0
