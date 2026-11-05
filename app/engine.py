"""The voice engine: one resident Kokoro session, streamed chunk synthesis.

The heavy imports (onnxruntime, kokoro_onnx) happen inside ``load()`` so the
rest of the app — and the test suite — runs without the model present. A stub
mode synthesizes soft sine chimes so the console and server are fully usable
before the model is downloaded.
"""
from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable

import numpy as np

from . import paths, voice_meta
from .textproc import Overrides, apply_pron_dict, parse_overrides, split_for_stream

SAMPLE_RATE = 24000


@dataclass
class Chunk:
    seq: int
    audio: np.ndarray
    sample_rate: int
    synth_ms: int
    text: str
    first: bool = False


@dataclass
class EngineStats:
    requests: int = 0
    chunks: int = 0
    total_synth_ms: float = 0.0
    total_audio_ms: float = 0.0
    first_chunk_ms: list[float] = field(default_factory=lambda: [])

    def snapshot(self) -> dict[str, Any]:
        n = len(self.first_chunk_ms)
        ordered = sorted(self.first_chunk_ms)
        p50 = ordered[n // 2] if n else None
        p95 = ordered[int(n * 0.95)] if n else None
        return {
            "requests": self.requests,
            "chunks": self.chunks,
            "avg_synth_ms": round(self.total_synth_ms / self.chunks, 1) if self.chunks else None,
            "avg_rtf": round(self.total_synth_ms / self.total_audio_ms, 3) if self.total_audio_ms else None,
            "first_chunk_p50_ms": round(p50, 1) if p50 is not None else None,
            "first_chunk_p95_ms": round(p95, 1) if p95 is not None else None,
            "samples": n,
        }


class LunarEngine:
    """Resident TTS engine. Thread-safe for one synthesis at a time."""

    def __init__(self, stub: bool | None = None):
        self._kokoro: Any = None
        self._lock = asyncio.Lock()
        self.stats = EngineStats()
        self.load_ms: float | None = None
        self.loaded_variant: str | None = None
        self.stub = stub if stub is not None else os.environ.get("LUNAR_STUB", "") == "1"
        self._stub_clock = 0.0

    # ------------------------------------------------------------- status --

    @property
    def ready(self) -> bool:
        return self._kokoro is not None

    def model_present(self, variant: str | None = None) -> bool:
        variant = variant or "fp32"
        return paths.model_path(variant).exists() and paths.VOICES_FILE.exists()

    def status(self, variant: str | None = None) -> dict[str, Any]:
        variant = variant or "fp32"
        return {
            "stub": self.stub,
            "model_present": self.model_present(variant),
            "loaded": self._kokoro is not None,
            "variant": self.loaded_variant or variant,
            "load_ms": round(self.load_ms, 2) if self.load_ms else None,
            "voices": voice_meta.catalog(),
            "stats": self.stats.snapshot(),
        }

    # -------------------------------------------------------------- loading --

    def load(self, variant: str = "fp32") -> None:
        """Load the ONNX session. Safe to call repeatedly; reloads on variant change."""
        if self.stub:
            self._kokoro = "stub"
            self.loaded_variant = "stub"
            self.load_ms = 0.0
            return
        if self._kokoro is not None and self.loaded_variant == variant:
            return
        model = paths.model_path(variant)
        if not model.exists() or not paths.VOICES_FILE.exists():
            raise FileNotFoundError(
                f"model files missing: {model.name} / {paths.VOICES_FILE.name} — "
                "run ./run.sh once (auto-download) or POST /api/model/download"
            )
        t0 = time.perf_counter()
        import onnxruntime as rt  # lazy: keeps import cost off the UI path

        from kokoro_onnx import Kokoro

        options = rt.SessionOptions()
        threads = int(os.environ.get("LUNAR_ORT_THREADS", "0"))
        if threads > 0:
            options.intra_op_num_threads = threads
            options.inter_op_num_threads = 1
        session = rt.InferenceSession(
            str(model), options, providers=["CPUExecutionProvider"]
        )
        self._kokoro = Kokoro.from_session(session, str(paths.VOICES_FILE))
        self.loaded_variant = variant
        self.load_ms = (time.perf_counter() - t0) * 1000

    async def reload(self, variant: str) -> None:
        async with self._lock:
            await asyncio.get_running_loop().run_in_executor(None, self._reload_sync, variant)

    def _reload_sync(self, variant: str) -> None:
        self._kokoro = None
        self.load(variant)

    def warmup(self) -> None:
        """Synthesize a dummy clip so the first real line is not the slowest."""
        if self.stub or self._kokoro is None:
            return
        try:
            self._kokoro.create("Ready.", voice="af_heart", speed=1.0, lang="en-us")
        except Exception:
            pass

    # ---------------------------------------------------------- synthesizing --

    def _create(self, text: str, voice: str, speed: float, lang: str,
                sentence_pause: float, clause_pause: float) -> tuple[np.ndarray, int]:
        if self.stub:
            return self._stub_audio(text)
        return self._kokoro.create(
            text, voice=voice, speed=speed, lang=lang,
            trim=True,
            sentence_pause=sentence_pause,
            clause_pause=clause_pause,
        )

    def _stub_audio(self, text: str) -> tuple[np.ndarray, int]:
        """Two soft sine chimes honoring text length — for tests/UI preview."""
        duration = min(max(len(text) * 0.03, 0.25), 1.6)
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
        freq = 520.0 + (hash(text) % 7) * 40.0
        env = np.minimum(1.0, t * 24) * np.minimum(1.0, (duration - t) * 24)
        audio = 0.22 * np.sin(2 * np.pi * freq * t) * env
        return audio.astype(np.float32), SAMPLE_RATE

    async def synth_stream(
        self,
        text: str,
        cfg: dict[str, Any],
        overrides: Overrides | None = None,
    ) -> AsyncGenerator[Chunk, None]:
        """Split, then synthesize chunk by chunk, yielding audio as it is ready.

        Requires the engine to be loaded; callers should ``ensure_loaded`` first.
        """
        ov = overrides or Overrides()
        text, parsed = parse_overrides(text)
        ov.voice = ov.voice or parsed.voice
        ov.lang = ov.lang or parsed.lang
        ov.speed = ov.speed or parsed.speed

        pron = cfg["pron_dict"] if cfg.get("pron_dict_enabled") else {}
        text = apply_pron_dict(text, pron)
        voice = ov.voice or cfg["voice"]
        lang = ov.lang or cfg["lang"]
        speed = ov.speed if ov.speed is not None else cfg["speed"]

        chunks = split_for_stream(
            text,
            first_chunk_fast=cfg["first_chunk_fast"] if cfg["streaming"] else False,
            max_chars=cfg["max_chunk_chars"],
        )
        if not text or not chunks:
            return

        loop = asyncio.get_running_loop()
        t_request = time.perf_counter()
        self.stats.requests += 1
        for seq, piece in enumerate(chunks):
            t0 = time.perf_counter()
            audio, sr = await loop.run_in_executor(
                None,
                self._create,
                piece, voice, speed, lang,
                cfg["sentence_pause"], cfg["clause_pause"],
            )
            synth_ms = (time.perf_counter() - t0) * 1000
            self.stats.chunks += 1
            self.stats.total_synth_ms += synth_ms
            self.stats.total_audio_ms += len(audio) / sr * 1000
            first = seq == 0
            if first:
                self.stats.first_chunk_ms.append((time.perf_counter() - t_request) * 1000)
                self.stats.first_chunk_ms = self.stats.first_chunk_ms[-500:]
            yield Chunk(seq=seq, audio=audio, sample_rate=sr,
                        synth_ms=int(synth_ms), text=piece, first=first)
