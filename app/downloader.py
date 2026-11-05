"""First-run model downloader with progress reporting.

Downloads the Kokoro v1.0 ONNX weights and the voice pack from GitHub Releases
(Hugging Face as fallback mirror). After this one download lunar never touches
the network again.
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable
from urllib.request import Request, urlopen

from . import paths

SOURCES = {
    "fp32": [
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx",
        "https://huggingface.co/thewh1teagle/kokoro-onnx/resolve/main/kokoro-v1.0.onnx",
    ],
    "int8": [
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.int8.onnx",
        "https://huggingface.co/thewh1teagle/kokoro-onnx/resolve/main/kokoro-v1.0.int8.onnx",
    ],
    "voices": [
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin",
        "https://huggingface.co/thewh1teagle/kokoro-onnx/resolve/main/voices-v1.0.bin",
    ],
}

EXPECTED_SIZES = {
    "fp32": 325_505_369,
    "int8": 114_119_327,
    "voices": 28_214_398,
}

TARGETS = {
    "fp32": lambda: paths.model_path("fp32"),
    "int8": lambda: paths.model_path("int8"),
    "voices": lambda: paths.VOICES_FILE,
}


@dataclass
class Progress:
    running: bool = False
    step: str = ""
    received: int = 0
    total: int = 0
    error: str | None = None
    done: list[str] = field(default_factory=list)

    def snapshot(self) -> dict:
        pct = round(100 * self.received / self.total, 1) if self.total else 0.0
        return {
            "running": self.running, "step": self.step,
            "received": self.received, "total": self.total,
            "percent": pct, "error": self.error, "done": list(self.done),
        }


def _download(key: str, progress: Progress, cb: Callable[[], None] | None = None) -> None:
    target = TARGETS[key]()
    if target.exists() and (not EXPECTED_SIZES[key] or target.stat().st_size == EXPECTED_SIZES[key]):
        progress.done.append(key)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    errors = []
    for url in SOURCES[key]:
        try:
            progress.step = f"{key}: {url.split('/')[2]}"
            progress.received, progress.total = 0, 0
            req = Request(url, headers={"User-Agent": "lunar-setup/0.1"})
            with urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:
                progress.total = int(resp.headers.get("Content-Length") or EXPECTED_SIZES[key] or 0)
                while True:
                    block = resp.read(1 << 20)
                    if not block:
                        break
                    out.write(block)
                    progress.received += len(block)
                    if cb:
                        cb()
            if tmp.stat().st_size < 1 << 20:
                raise IOError(f"downloaded file too small: {tmp.stat().st_size} bytes")
            tmp.replace(target)
            progress.done.append(key)
            return
        except Exception as exc:  # noqa: BLE001 - report and try next mirror
            errors.append(f"{url}: {exc}")
            progress.error = "; ".join(errors)[-400:]
            time.sleep(1.0)
    raise IOError(f"all mirrors failed for {key}: {'; '.join(errors)}")


def download_all(variant: str = "fp32", progress: Progress | None = None,
                 cb: Callable[[], None] | None = None) -> None:
    """Blocking download of the chosen variant + voices. Idempotent."""
    progress = progress or Progress()
    progress.running = True
    try:
        _download("voices", progress, cb)
        _download(variant, progress, cb)
        progress.step = "complete"
    finally:
        progress.running = False


class BackgroundDownloader:
    """Runs download_all in a thread; snapshot() powers the UI progress bar."""

    def __init__(self, variant: str = "fp32"):
        self.progress = Progress()
        self.variant = variant
        self._thread: threading.Thread | None = None

    def start(self, variant: str | None = None) -> dict:
        if variant:
            self.variant = variant
        if self._thread and self._thread.is_alive():
            return self.progress.snapshot()
        for key in ("voices", self.variant):
            if key not in self.progress.done:
                self.progress = Progress()
                break
        self.progress.running = True
        self._thread = threading.Thread(
            target=self._run, name="lunar-downloader", daemon=True)
        self._thread.start()
        return self.progress.snapshot()

    def _run(self) -> None:
        try:
            download_all(self.variant, self.progress)
        except Exception as exc:  # noqa: BLE001
            self.progress.error = str(exc)[:400]
            self.progress.running = False
            self.progress.step = "failed"

    def snapshot(self) -> dict:
        snap = self.progress.snapshot()
        snap["files"] = {
            "fp32": paths.model_path("fp32").exists(),
            "int8": paths.model_path("int8").exists(),
            "voices": paths.VOICES_FILE.exists(),
        }
        snap["variant"] = self.variant
        return snap


def cli(variant: str = "fp32") -> int:
    """Terminal entry: python -m app.download [fp32|int8]"""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] in ("fp32", "int8"):
        variant = sys.argv[1]
    progress = Progress()
    print(f"lunar setup — downloading model ({variant}) + voice pack")
    print(f"  fp32  ~311 MB   int8 ~109 MB   voices ~27 MB\n")
    last = -1.0

    def tick() -> None:
        nonlocal last
        if time.time() - last < 0.2:
            return
        last = time.time()
        pct = 100 * progress.received / progress.total if progress.total else 0
        sys.stdout.write(
            f"\r  {progress.step[:44]:44} {progress.received/1048576:7.1f} MB  {pct:5.1f}%")
        sys.stdout.flush()

    try:
        download_all(variant, progress, cb=tick)
    except Exception as exc:  # noqa: BLE001
        print(f"\n  failed: {exc}")
        return 1
    print("\n  done — lunar is now fully offline.")
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
