"""Local server: static console UI, REST config, realtime speech over WebSocket.

Everything binds to 127.0.0.1 by default — lunar is a personal live-voice
console, not a public service.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, config, paths, voice_meta
from .downloader import BackgroundDownloader
from .engine import LunarEngine
from .textproc import Overrides
from .wav import wav_bytes

STATE: dict[str, Any] = {}
DOWNLOADER = BackgroundDownloader()


def create_app(stub: bool | None = None, engine: LunarEngine | None = None) -> FastAPI:
    app = FastAPI(title="lunar", version=__version__, docs_url=None, redoc_url=None)

    STATE["config"] = config.load()
    STATE["engine"] = engine or LunarEngine(
        stub=stub if stub is not None else os.environ.get("LUNAR_STUB") == "1"
    )
    STATE["clients"] = set()
    STATE["started"] = time.time()

    engine = STATE["engine"]
    cfg = STATE["config"]

    if not engine.stub and engine.model_present(cfg["engine_variant"]) and cfg["warmup_on_start"]:
        # Load + warm in a background thread so the server is up instantly.
        def _boot() -> None:
            try:
                engine.load(cfg["engine_variant"])
                engine.warmup()
                print(f"[lunar] engine ready ({cfg['engine_variant']}) in {engine.load_ms:.0f} ms")
            except Exception as exc:  # noqa: BLE001
                print(f"[lunar] engine load deferred: {exc}")

        import threading
        threading.Thread(target=_boot, name="lunar-engine-boot", daemon=True).start()

    # ------------------------------------------------------------------ REST --

    @app.get("/api/config")
    def get_config() -> dict:
        return STATE["config"]

    @app.post("/api/config")
    async def post_config(patch: dict) -> dict:
        if patch.get("reset") is True:
            clean = config.save({})
        else:
            merged = {**STATE["config"], **patch}
            clean = config.save(merged)
        old_variant = STATE["config"]["engine_variant"]
        old_threads = STATE["config"]["ort_threads"]
        STATE["config"] = clean
        await _broadcast({"type": "config", "config": clean})
        if clean["engine_variant"] != old_variant or clean["ort_threads"] != old_threads:
            os.environ["LUNAR_ORT_THREADS"] = str(clean["ort_threads"])
            asyncio.get_running_loop().create_task(_engine_reload(clean["engine_variant"]))
        return clean

    @app.get("/api/voices")
    def get_voices() -> dict:
        return {"voices": voice_meta.catalog()}

    @app.get("/api/langs")
    def get_langs() -> dict:
        return {"langs": config.SUPPORTED_LANGS}

    @app.get("/api/status")
    def get_status() -> dict:
        return {
            "version": __version__,
            "uptime_s": round(time.time() - STATE["started"], 1),
            "engine": STATE["engine"].status(STATE["config"]["engine_variant"]),
            "downloader": DOWNLOADER.snapshot(),
            "config_file": str(paths.CONFIG_FILE),
        }

    @app.post("/api/model/download")
    async def start_download(body: dict | None = None) -> dict:
        variant = (body or {}).get("variant") or STATE["config"]["engine_variant"]
        if variant not in ("fp32", "int8"):
            variant = "fp32"
        return DOWNLOADER.start(variant)

    @app.get("/api/model/status")
    def model_status() -> dict:
        return DOWNLOADER.snapshot()

    @app.post("/api/engine/reload")
    async def engine_reload(body: dict | None = None) -> dict:
        variant = (body or {}).get("variant") or STATE["config"]["engine_variant"]
        asyncio.get_running_loop().create_task(_engine_reload(variant))
        return {"ok": True, "variant": variant}

    @app.get("/api/export")
    def export_config() -> JSONResponse:
        return JSONResponse(
            STATE["config"],
            headers={"Content-Disposition": 'attachment; filename="lunar-config.json"'})

    @app.get("/api/health")
    def health() -> PlainTextResponse:
        return PlainTextResponse("ok")

    async def _engine_reload(variant: str) -> None:
        engine = STATE["engine"]
        try:
            await engine.reload(variant)
            engine.warmup()
            print(f"[lunar] engine reloaded ({variant}) in {engine.load_ms:.0f} ms")
        except Exception as exc:  # noqa: BLE001
            print(f"[lunar] engine reload failed: {exc}")
        await _broadcast({"type": "status", "status": engine.status(variant)})

    # ------------------------------------------------------------- websocket --

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        STATE["clients"].add(ws)
        queue: asyncio.Queue = asyncio.Queue(maxsize=16)
        runner = asyncio.create_task(_runner(ws, queue))
        try:
            await ws.send_json({
                "type": "hello",
                "version": __version__,
                "config": STATE["config"],
                "status": STATE["engine"].status(STATE["config"]["engine_variant"]),
            })
            while True:
                raw = await ws.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                kind = data.get("type")
                if kind == "speak":
                    mode = data.get("mode", "replace")
                    if mode == "replace":
                        _drop_queue(queue)
                        if not runner.done():
                            runner.cancel()
                            try:
                                await runner
                            except (asyncio.CancelledError, Exception):
                                pass
                            runner = asyncio.create_task(_runner(ws, queue))
                    await queue.put({
                        "id": data.get("id") or uuid.uuid4().hex[:12],
                        "text": str(data.get("text", ""))[:4000],
                        "overrides": data.get("overrides") or None,
                    })
                elif kind == "stop":
                    _drop_queue(queue)
                    if not runner.done():
                        runner.cancel()
                        try:
                            await runner
                        except (asyncio.CancelledError, Exception):
                            pass
                        runner = asyncio.create_task(_runner(ws, queue))
                elif kind == "ping":
                    await ws.send_json({"type": "pong", "t": data.get("t")})
        except WebSocketDisconnect:
            pass
        finally:
            STATE["clients"].discard(ws)
            runner.cancel()
            try:
                await runner
            except (asyncio.CancelledError, Exception):
                pass

    def _drop_queue(queue: asyncio.Queue) -> None:
        while not queue.empty():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _runner(ws: WebSocket, queue: asyncio.Queue) -> None:
        while True:
            job = await queue.get()
            try:
                await _speak_job(ws, job)
            except asyncio.CancelledError:
                await _try_send(ws, {"type": "stopped", "id": job["id"]})
                raise
            except WebSocketDisconnect:
                raise
            except Exception as exc:  # noqa: BLE001
                await _try_send(ws, {"type": "error", "id": job["id"],
                                     "message": f"{type(exc).__name__}: {exc}"})

    async def _speak_job(ws: WebSocket, job: dict) -> None:
        engine = STATE["engine"]
        cfg = STATE["config"]
        text = job["text"].strip()
        if not text:
            await _try_send(ws, {"type": "error", "id": job["id"], "message": "empty text"})
            return
        overrides = None
        if job.get("overrides"):
            o = job["overrides"]
            overrides = Overrides(voice=o.get("voice"), lang=o.get("lang"),
                                  speed=o.get("speed"))
        # Make sure the session is resident before the first word.
        if not engine.stub and not engine.ready:
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(None, engine.load, cfg["engine_variant"])
            except FileNotFoundError as exc:
                await _try_send(ws, {"type": "error", "id": job["id"], "message": str(exc),
                                     "code": "model_missing"})
                return
        await _try_send(ws, {
            "type": "begin", "id": job["id"],
            "voice": overrides.voice if overrides and overrides.voice else cfg["voice"],
            "lang": overrides.lang if overrides and overrides.lang else cfg["lang"],
            "speed": overrides.speed if overrides and overrides.speed is not None else cfg["speed"],
        })
        async for chunk in engine.synth_stream(text, cfg, overrides):
            payload = {
                "type": "chunk", "id": job["id"], "seq": chunk.seq,
                "sr": chunk.sample_rate, "samples": int(len(chunk.audio)),
                "synth_ms": chunk.synth_ms, "first": chunk.first,
            }
            await ws.send_json(payload)
            await ws.send_bytes(wav_bytes(chunk.audio, chunk.sample_rate))
        await _try_send(ws, {"type": "end", "id": job["id"],
                             "stats": engine.stats.snapshot()})

    async def _broadcast(message: dict) -> None:
        for client in list(STATE["clients"]):
            await _try_send(client, message)

    async def _try_send(ws: WebSocket, message: dict) -> None:
        try:
            await ws.send_json(message)
        except Exception:  # noqa: BLE001 - a dead client must not kill jobs
            STATE["clients"].discard(ws)

    # ---------------------------------------------------------------- static --

    paths.ensure_dirs()

    @app.get("/", include_in_schema=False)
    async def index_page() -> FileResponse:
        return FileResponse(str(paths.WEB_DIR / "index.html"))

    @app.get("/config", include_in_schema=False)
    async def config_page() -> FileResponse:
        return FileResponse(str(paths.WEB_DIR / "config.html"))

    app.mount("/", StaticFiles(directory=str(paths.WEB_DIR)), name="web")
    return app
