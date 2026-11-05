#!/usr/bin/env python3
"""Build the offline model pack (release asset).

Bundles both model variants + the voice pack into one zip so lunar can be
installed with zero network at all::

    python tools/offline_pack.py            # dist/lunar-modelpack-<ver>.zip
    python tools/offline_pack.py --check    # verify an extracted tree
"""
from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import __version__, paths  # noqa: E402

FILES = [
    ("models/kokoro-v1.0.onnx", "fp32 weights"),
    ("models/kokoro-v1.0.int8.onnx", "int8 weights (optional fast mode)"),
    ("voices/voices-v1.0.bin", "54-voice style pack"),
]


def build() -> Path:
    paths.ensure_dirs()
    dist = Path("dist")
    dist.mkdir(exist_ok=True)
    out = dist / f"lunar-modelpack-{__version__}.zip"
    missing = [rel for rel, _ in FILES if not (paths.ROOT / rel).exists()]
    if missing:
        print("missing files (run the downloader first):")
        for rel in missing:
            print(f"  {rel}")
        raise SystemExit(1)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as zf:  # weights are incompressible
        for rel, label in FILES:
            src = paths.ROOT / rel
            print(f"  + {rel:28} {src.stat().st_size / 1048576:7.1f} MB  ({label})")
            zf.write(src, rel)
    print(f"\nwrote {out} ({out.stat().st_size / 1048576:.1f} MB)")
    print("install: unzip over the repo root — then run ./run.sh with LUNAR_OFFLINE=1")
    return out


def check(root: Path) -> int:
    ok = True
    for rel, _ in FILES:
        present = (root / rel).exists()
        print(f"  {'ok ' if present else 'MISSING '} {rel}")
        ok = ok and present
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", metavar="DIR", help="verify files in an extracted tree")
    args = parser.parse_args()
    if args.check:
        return check(Path(args.check))
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
