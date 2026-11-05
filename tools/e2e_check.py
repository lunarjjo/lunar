#!/usr/bin/env python3
"""E2E jalur user nyata: start server model asli, koneksi WS, ukur latency.

Menjalankan persis alur yang dirasakan user: buka konsol, ketik, enter,
audio pertama datang. Mencatat: first-audio latency per baris + RTF.
"""
import asyncio
import json
import time

import websockets

URL = "ws://127.0.0.1:8765/ws"

LINES = [
    "Halo guys, selamat datang di stream malam ini.",
    "Oke, kita mulai main sekarang.",
    "Welcome back to the stream!",
    "Terima kasih sudah nonton, jangan lupa like dan subscribe ya.",
    "/en This line is spoken with the English phonemizer.",
]


async def speak(ws, text):
    t0 = time.perf_counter()
    first_ms = None
    n_chunks = 0
    total_audio_s = 0.0
    await ws.send(json.dumps({"type": "speak", "text": text, "mode": "replace", "id": "e2e"}))
    while True:
        msg = await ws.recv()
        if isinstance(msg, bytes):
            n_chunks += 1
            total_audio_s += (len(msg) - 44) / 2 / 24000
            if first_ms is None:
                first_ms = (time.perf_counter() - t0) * 1000
            continue
        data = json.loads(msg)
        if data["type"] == "end":
            return first_ms, n_chunks, total_audio_s, (time.perf_counter() - t0) * 1000
        if data["type"] == "error":
            raise RuntimeError(data["message"])


async def main():
    async with websockets.connect(URL, max_size=64 * 1024 * 1024) as ws:
        hello = json.loads(await ws.recv())
        print(f"hello: v{hello['version']} engine loaded={hello['status']['loaded']} "
              f"stub={hello['status']['stub']} voices={len(hello['status']['voices'])}")
        # warmup pertama (seperti kondisi user setelah boot + warmup otomatis)
        first, chunks, audio_s, total = await speak(ws, "Warmup line.")
        print(f"warmup : first {first:7.0f} ms | chunks {chunks} | audio {audio_s:4.1f}s | total {total:6.0f} ms")
        for line in LINES:
            first, chunks, audio_s, total = await speak(ws, line)
            rtf = (total - 0) / 1000 / audio_s if audio_s else 0
            print(f"line   : first {first:7.0f} ms | chunks {chunks} | audio {audio_s:4.1f}s | "
                  f"total {total:6.0f} ms | rtf~{rtf:.2f} | {line[:52]}")
        # stop di tengah
        t0 = time.perf_counter()
        await ws.send(json.dumps({"type": "speak", "text": "satu. dua. tiga. empat. lima. enam.", "id": "x"}))
        stopped = False
        while True:
            msg = await ws.recv()
            if isinstance(msg, bytes):
                await ws.send(json.dumps({"type": "stop"}))
                continue
            data = json.loads(msg)
            if data["type"] in ("stopped", "end"):
                stopped = data["type"] == "stopped"
                break
        print(f"stop-mid: {'OK (stopped broadcast)' if stopped else 'NOTE: job already finished'} "
              f"in {(time.perf_counter()-t0)*1000:.0f} ms")
        # config live broadcast
        import urllib.request
        req = urllib.request.Request("http://127.0.0.1:8765/api/config",
                                     data=json.dumps({"gain": 0.9}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req)
        msg = json.loads(await ws.recv())
        print(f"broadcast: {msg['type']} gain={msg['config']['gain']}")

asyncio.run(main())
print("E2E-OK")
