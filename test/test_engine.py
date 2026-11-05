"""Engine behavior in stub mode — no model, no onnxruntime import."""
import numpy as np
import pytest

from app.engine import LunarEngine


@pytest.fixture()
def engine():
    return LunarEngine(stub=True)


def test_stub_status(engine):
    st = engine.status()
    assert st["stub"] is True
    assert st["loaded"] is False


def test_stub_load_instant(engine):
    engine.load()
    assert engine.ready


@pytest.mark.asyncio
async def test_stub_stream_yields_audio(engine):
    engine.load()
    cfg = {
        "voice": "af_heart", "lang": "id", "speed": 1.0,
        "sentence_pause": 0.25, "clause_pause": 0.1,
        "streaming": True, "first_chunk_fast": True, "max_chunk_chars": 160,
        "pron_dict_enabled": True, "pron_dict": {},
    }
    chunks = [c async for c in engine.synth_stream("Halo guys, selamat datang.", cfg)]
    assert len(chunks) == 2
    assert chunks[0].first is True and chunks[0].seq == 0
    assert chunks[0].text == "Halo guys,"
    assert chunks[0].sample_rate == 24000
    assert isinstance(chunks[0].audio, np.ndarray) and len(chunks[0].audio) > 0
    assert np.max(np.abs(chunks[0].audio)) <= 1.0


@pytest.mark.asyncio
async def test_pron_dict_applied(engine):
    engine.load()
    cfg = {
        "voice": "af_heart", "lang": "id", "speed": 1.0,
        "sentence_pause": 0.25, "clause_pause": 0.1,
        "streaming": True, "first_chunk_fast": False, "max_chunk_chars": 160,
        "pron_dict_enabled": True, "pron_dict": {"gg": "gee gee"},
    }
    chunks = [c async for c in engine.synth_stream("gg", cfg)]
    assert len(chunks) == 1
    assert chunks[0].text == "gee gee"


@pytest.mark.asyncio
async def test_overrides_respected(engine):
    engine.load()
    cfg = {
        "voice": "af_heart", "lang": "id", "speed": 1.0,
        "sentence_pause": 0.25, "clause_pause": 0.1,
        "streaming": True, "first_chunk_fast": False, "max_chunk_chars": 160,
        "pron_dict_enabled": True, "pron_dict": {},
    }
    from app.textproc import Overrides
    chunks = [c async for c in engine.synth_stream("test", cfg, Overrides(voice="am_adam", lang="en-us", speed=1.5))]
    assert len(chunks) == 1


@pytest.mark.asyncio
async def test_stats_tracked(engine):
    engine.load()
    cfg = {
        "voice": "af_heart", "lang": "id", "speed": 1.0,
        "sentence_pause": 0.25, "clause_pause": 0.1,
        "streaming": True, "first_chunk_fast": False, "max_chunk_chars": 160,
        "pron_dict_enabled": True, "pron_dict": {},
    }
    _ = [c async for c in engine.synth_stream("satu dua tiga.", cfg)]
    snap = engine.stats.snapshot()
    assert snap["requests"] == 1
    assert snap["chunks"] >= 1
    assert snap["first_chunk_p50_ms"] is not None


@pytest.mark.asyncio
async def test_empty_text_yields_nothing(engine):
    engine.load()
    cfg = {
        "voice": "af_heart", "lang": "id", "speed": 1.0,
        "sentence_pause": 0.25, "clause_pause": 0.1,
        "streaming": True, "first_chunk_fast": True, "max_chunk_chars": 160,
        "pron_dict_enabled": True, "pron_dict": {},
    }
    chunks = [c async for c in engine.synth_stream("   ", cfg)]
    assert chunks == []
