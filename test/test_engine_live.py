"""Real-model tests — self-skip unless the weights are present.

CI and model-less machines run the stub suite only. Locally, after
``./run.sh`` has downloaded the model, set ``LUNAR_LIVE=1`` to include this
suite (it needs ~350 MB of weights on disk).
"""
import os

import numpy as np
import pytest

from app import paths
from app.engine import LunarEngine

pytestmark = pytest.mark.skipif(
    os.environ.get("LUNAR_LIVE") != "1"
    or not paths.model_path("fp32").exists()
    or not paths.VOICES_FILE.exists(),
    reason="LUNAR_LIVE=1 and downloaded model required",
)

CFG = {
    "voice": "af_heart", "lang": "id", "speed": 1.0,
    "sentence_pause": 0.25, "clause_pause": 0.1,
    "streaming": True, "first_chunk_fast": True, "max_chunk_chars": 160,
    "pron_dict_enabled": True, "pron_dict": {},
}


@pytest.fixture(scope="module")
def engine():
    eng = LunarEngine(stub=False)
    eng.load("fp32")
    eng.warmup()
    return eng


@pytest.mark.asyncio
async def test_real_synth_indonesian(engine):
    chunks = [c async for c in engine.synth_stream("Halo guys, selamat datang di stream.", CFG)]
    assert len(chunks) >= 2
    assert chunks[0].text == "Halo guys,"
    assert all(isinstance(c.audio, np.ndarray) and len(c.audio) > 1000 for c in chunks)
    assert all(c.sample_rate == 24000 for c in chunks)


@pytest.mark.asyncio
async def test_first_chunk_latency(engine):
    import time
    t0 = time.perf_counter()
    async for chunk in engine.synth_stream("Halo guys, tes.", CFG):
        first_ms = (time.perf_counter() - t0) * 1000
        break
    # generous ceiling: CI machines vary wildly; this is a smoke assertion
    assert first_ms < 8000


def test_real_voice_catalog_matches_file(engine):
    engine.load("fp32")
    names = engine._kokoro.get_voices()
    assert "af_heart" in names and len(names) >= 50


def test_meta_catalog_matches_bin():
    """voice_meta.ALL_V1_0_VOICES must list exactly what voices-v1.0.bin holds."""
    import numpy as np

    names = set(np.load(str(paths.VOICES_FILE)).keys())
    from app.voice_meta import ALL_V1_0_VOICES

    listed = set(ALL_V1_0_VOICES)
    assert listed == names, f"missing={names - listed} extra={listed - names}"
    # every listed voice must resolve to a supported language except zh/ja
    from app.voice_meta import voice_info

    for name in listed:
        if name[:1] in ("z", "j"):
            assert voice_info(name)["supported"] is False
        else:
            assert voice_info(name)["supported"] is True, name
