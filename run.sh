#!/usr/bin/env bash
# lunar — one-click launcher (Linux / macOS)
# Sets up a private venv, installs pinned deps, downloads the voice model on
# first run, then starts the console and opens your browser.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${LUNAR_PORT:-8765}"
VARIANT="${LUNAR_VARIANT:-fp32}"

say() { printf '\033[1;35m[lunar]\033[0m %s\n' "$*"; }

# ---------------------------------------------------------------- python ----
PY=""
PY_ANY=""
for cand in python3.13 python3.12 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    if "$cand" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      PY_ANY="${PY_ANY:-$cand}"
      # venv creation needs ensurepip on board
      if "$cand" -c 'import ensurepip' 2>/dev/null; then
        PY="$cand"; break
      fi
    fi
  fi
done
if [ -z "$PY" ]; then
  if [ -n "$PY_ANY" ]; then
    echo "lunar found Python ($PY_ANY) but without venv support."
    echo "  fix: sudo apt install python3-venv (or python$($PY_ANY -c 'import sys; print(f\"{sys.version_info.major}.{sys.version_info.minor}\")')-venv)"
  else
    echo "lunar needs Python 3.11+ (found: $(python3 --version 2>&1 || echo none))."
    echo "  Ubuntu 24.04+ ships it as python3; on older systems: sudo apt install python3.12 python3.12-venv"
  fi
  exit 1
fi

# ------------------------------------------------------------------- venv ----
if [ ! -x .venv/bin/python ]; then
  say "creating private python environment (.venv)…"
  if ! "$PY" -m venv .venv; then
    echo "venv creation failed — try: sudo apt install python3-venv"
    exit 1
  fi
fi
VPY=.venv/bin/python

# ------------------------------------------------------------------- deps ----
STAMP=".venv/.deps-stamp"
HASH="$(cksum requirements.txt 2>/dev/null | cut -d' ' -f1,2 || echo none)"
if [ "${LUNAR_OFFLINE:-0}" != "1" ] && [ "$(cat "$STAMP" 2>/dev/null || echo missing)" != "$HASH" ]; then
  say "installing dependencies (first run only, pinned versions)…"
  if ! "$VPY" -m pip install --quiet -r requirements.txt; then
    if [ ! -f "$STAMP" ]; then
      say "pip install failed — no network? retry later or set LUNAR_OFFLINE=1 if deps exist."
      exit 1
    fi
    say "pip refresh failed — continuing with the already-installed environment."
  else
    echo "$HASH" > "$STAMP"
  fi
fi

# ------------------------------------------------------------------ model ----
if [ "${LUNAR_OFFLINE:-0}" != "1" ]; then
  MODEL_OK=0
  [ -f "models/kokoro-v1.0.onnx" ] && MODEL_OK=1
  [ -f "models/kokoro-v1.0.int8.onnx" ] && MODEL_OK=1
  if [ "$MODEL_OK" = "0" ] || [ ! -f "voices/voices-v1.0.bin" ]; then
    say "downloading the voice model (first run only, ~340 MB — after this lunar is fully offline)…"
    "$VPY" -m app.download "$VARIANT" || { say "model download failed — check your connection and rerun."; exit 1; }
  fi
fi

# ----------------------------------------------------------------- launch ----
if command -v uname >/dev/null && uname | grep -qi darwin; then OPEN=open; else OPEN=xdg-open; fi
( sleep 1.5; command -v "$OPEN" >/dev/null 2>&1 && "$OPEN" "http://127.0.0.1:${PORT}/" >/dev/null 2>&1) &
say "live console: http://127.0.0.1:${PORT}/  (config: /config)"
say "ctrl-c stops lunar"
exec "$VPY" -m app --port "$PORT"
