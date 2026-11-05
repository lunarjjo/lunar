# Changelog

All notable changes to lunar are documented here. The format follows
Keep a Changelog; versions are semantic.

## [0.1.0] — 2026-11-05

### Added
- One-click launchers: `run.sh` (Linux/macOS) and `run.bat` (Windows) —
  private venv, pinned deps, first-run model download, browser open.
- Realtime speech pipeline: type → Enter → sentence-streamed audio over
  WebSocket, first words playing while the rest synthesizes.
- Minimalist live console: giant input, Enter/Esc/Shift+Enter, live
  first-word latency readout, speaking waveform, clickable history.
- Deep config console (live-saved, broadcast to every open console):
  - voice tab: searchable 41-voice grid with auditions, speech language
    (Indonesian default), speed, sentence/clause pauses
  - behavior tab: Enter vs Ctrl+Enter, streaming, fast-first-chunk,
    chunk length, inter-chunk gap
  - pronunciation tab: live dictionary editor with test-speak and
    JSON import/export
  - appearance tab: dark/light, font size, latency readout, history, gain
  - engine tab: fp32/int8 variant with hot reload, ORT threads, warmup,
    file status, in-app downloader, session stats, config export/import/reset
- Per-line inline overrides: `/en`, `/id`, `/v <voice>`, `/s <speed>`.
- Multi-line paste: each line queued and spoken in order.
- In-app model downloader with progress (REST + UI banner).
- Stub mode (`LUNAR_STUB=1`) for model-free UI work and CI.
- Offline modelpack builder (`tools/offline_pack.py`), latency benchmark
  (`tools/bench.py`), WS protocol e2e checker (`tools/e2e_check.py`).
- Test suite: 56 stub-mode tests (unit + full WS protocol e2e) plus a
  real-model suite gated behind `LUNAR_LIVE=1`.
- GitHub Actions CI: pytest matrix (3.12/3.13) + smoke boot of the
  real server with health/HTML checks + launcher path verification.
- Docs: English README + Indonesian README, NOTICE with full model
  attribution, MIT license.
