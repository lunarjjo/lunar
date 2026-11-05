# lunar

**An offline realtime voice console for livestreams — type a line, press Enter, it speaks.**

lunar runs entirely on your machine: one resident neural voice (Kokoro-82M,
54 voices, 24 kHz) served through a local web console. It is built for one
job — being *your* voice on stream: you type, your viewers hear it
milliseconds later. No cloud, no accounts, no network after setup.

```
type → Enter → first word in a few hundred ms (sentence-streamed)
```

- **one click** — `./run.sh` sets up everything, downloads the model once, opens the browser
- **fully offline** — after first run, zero network calls; weights live in `models/`
- **realtime** — speech streams per sentence: the first words play while the rest is still synthesizing
- **minimal live console** — a single input, Enter speaks, Esc stops, latency readout
- **deep config console** — 54 voices, speed, pauses, streaming behavior, pronunciation dictionary, engine variant, stats
- **OBS-ready** — plays through your browser audio; capture it as Desktop Audio

## Quick start

Requires Python 3.12+ (Ubuntu 24.04+ ships it as `python3`).

```bash
git clone https://github.com/lunarjjo/lunar.git
cd lunar
./run.sh
```

First run creates a private venv, installs pinned dependencies and downloads
the voice model (~340 MB). Then the console opens at
`http://127.0.0.1:8765/` — every later start is offline and takes seconds.
On Windows, double-click `run.bat`.

Air-gapped machine? Download
[`lunar-modelpack-latest.zip`](https://github.com/lunarjjo/lunar/releases/latest)
from the releases, unzip it over the repo, then start with
`LUNAR_OFFLINE=1 ./run.sh`.

## The live console

| key | action |
| --- | --- |
| `enter` | speak the line (or `ctrl+enter` if you switch modes) |
| `esc` | stop speaking immediately |
| `shift+enter` | newline — paste a paragraph and every line is spoken in order |

Per-line overrides, no menus needed:

```
/en This line is spoken with the English phonemizer.
/v am_adam Big voice energy.
/s 1.4 Faster, talk faster.
```

A live readout shows the **first-word latency** of every line so you always
know how instant you are.

## Wiring it into OBS

1. Start lunar, keep the console tab open (background is fine).
2. In OBS add an **Audio Output Capture (Desktop)** source — lunar plays through
   the browser, so desktop audio carries it.
3. Want lunar isolated from game/music audio? Route your browser into a virtual
   audio device (e.g. PulseAudio sink on Linux, VB-Cable on Windows) and capture
   that device instead.
4. Optional: add the console tab as a **Browser Source** if you want the
   waveform visible on stream.

## The config console

`http://127.0.0.1:8765/config` — every knob, live-saved:

- **voice** — searchable grid of 41 voices (US/UK English, Spanish, French,
  Hindi, Italian, Portuguese) with a per-voice audition button, speech language,
  speed, sentence and clause pauses
- **behavior** — Enter vs Ctrl+Enter, sentence streaming, fast first chunk,
  chunk length, inter-chunk gap
- **pronunciation** — a live dictionary: write `gg`, say `gee gee`; fix names,
  jargon and loanwords once and forever
- **appearance** — dark/light, font size, latency readout, history, master gain
- **engine** — fp32 vs int8 model, ORT threads, warmup, file status, one-click
  download, session stats (avg synth ms, RTF, first-word p50/p95), config
  export/import/reset

Changes broadcast instantly to every open console — tweak speed mid-sentence
and the next line already uses it.

## Languages

Speech phonemization supports Indonesian, English (US/UK), Spanish, French,
Italian, Portuguese, Hindi, German, Polish. Default is Indonesian with the
`af_heart` voice — swap to `en-us` in config or per line with `/en`.
Chinese and Japanese voice weights exist in the pack but need dedicated
pipelines and are hidden from the picker (roadmap).

## Performance

First-word latency is dominated by one ONNX inference of your first few words.
On a typical laptop CPU expect first word in roughly 100–400 ms with the full
precision model; `tools/bench.py` measures it on *your* machine:

```bash
python tools/bench.py            # current variant
python tools/bench.py --full     # fp32 vs int8 comparison
```

Numbers from the development container (weak shared CPU, your results will
likely be better): p50 first word ~1.0 s, RTF 0.55. If int8 is faster for you,
switch the variant in the engine tab — it reloads without a restart.

## Development

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest            # 56 tests, stub engine (no model needed)
LUNAR_LIVE=1 .venv/bin/python -m pytest   # + real-model suite after download
.venv/bin/python tools/e2e_check.py   # start the server first; full WS protocol check
.venv/bin/python tools/offline_pack.py    # build the release modelpack
```

The server binds `127.0.0.1` only. `LUNAR_STUB=1 python -m app` boots a
model-free stub that speaks soft chimes — handy for UI work.

## Model & licenses

lunar's voice is [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) by
hexgrad (Apache-2.0), executed through the
[kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) export (MIT) on
ONNX Runtime, with espeak-ng phonemization. Full attribution in
[NOTICE.md](NOTICE.md). This repo's own code is MIT — see [LICENSE](LICENSE).

## Roadmap

- Chinese/Japanese pipelines for the full 54-voice pack
- streaming waveform overlay for OBS browser sources
- voice blending and per-voice EQ presets
- optional local whisper echo for closed captions
