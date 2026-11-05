#!/usr/bin/env python3
"""Latency benchmark — run on your machine to compare variants and threads.

Usage:
  python tools/bench.py                 # current config, few sentences
  python tools/bench.py --variant int8  # quantized model
  python tools/bench.py --threads 2     # limit onnxruntime threads
  python tools/bench.py --full          # both variants, more sentences
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SENTENCES = [
    "Halo guys, selamat datang di stream malam ini.",
    "Oke, kita mulai main sekarang.",
    "Terima kasih sudah nonton, jangan lupa like dan subscribe ya.",
    "Welcome back to the stream, today we try something new.",
    "That was close, almost died right there.",
    "Besok kita lanjut lagi jam delapan malam, jangan lupa ya.",
    "This is a latency benchmark for the lunar voice console on this machine.",
]


async def bench(variant: str, threads: int) -> None:
    import os

    if threads:
        os.environ["LUNAR_ORT_THREADS"] = str(threads)
    from app import config as config_mod
    from app.engine import LunarEngine

    engine = LunarEngine(stub=False)
    t0 = time.perf_counter()
    engine.load(variant)
    engine.warmup()
    print(f"\n=== {variant}{'/' + str(threads) + 't' if threads else ''} "
          f"— load+warmup {time.perf_counter() - t0:.2f}s")

    cfg = dict(config_mod.DEFAULTS)
    firsts: list[float] = []
    totals: list[float] = []
    audio_total = 0.0
    for sentence in SENTENCES:
        t0 = time.perf_counter()
        first = None
        n = 0
        async for chunk in engine.synth_stream(sentence, cfg):
            n += 1
            if first is None:
                first = (time.perf_counter() - t0) * 1000
            audio_total += len(chunk.audio) / chunk.sample_rate
        totals.append((time.perf_counter() - t0) * 1000)
        firsts.append(first)
        print(f"  first {first:7.1f} ms | chunks {n} | total {totals[-1]:7.1f} ms | {sentence[:44]}")

    import statistics

    print(f"  --- first word: p50 {statistics.median(firsts):.0f} ms · "
          f"min {min(firsts):.0f} · max {max(firsts):.0f} · "
          f"RTF {sum(totals) / 1000 / audio_total:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", default="fp32", choices=["fp32", "int8"])
    parser.add_argument("--threads", type=int, default=0)
    parser.add_argument("--full", action="store_true", help="benchmark both variants")
    args = parser.parse_args()

    print("lunar latency benchmark — smaller first-word ms feels more instant")
    variants = ["fp32", "int8"] if args.full else [args.variant]
    for variant in variants:
        asyncio.run(bench(variant, args.threads))


if __name__ == "__main__":
    main()
