/* lunar live console — type, enter, speak. */
"use strict";

const $ = (id) => document.getElementById(id);
const say = $("say"), wave = $("wave"), history_ = $("history");

/* ------------------------------------------------------------------ audio */

let ctx = null, gainNode = null, analyser = null;
let cfg = null;
let nextTime = 0, playing = false;
let scheduled = [];

function ensureCtx() {
  if (ctx) return true;
  try {
    ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000, latencyHint: "interactive" });
  } catch (e) {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
  }
  gainNode = ctx.createGain();
  analyser = ctx.createAnalyser();
  analyser.fftSize = 256;
  gainNode.connect(analyser);
  analyser.connect(ctx.destination);
  return true;
}

function applyGain() { if (gainNode && cfg) gainNode.gain.value = cfg.gain; }

function resample(f32, from) {
  if (from === ctx.sampleRate) return f32;
  const ratio = ctx.sampleRate / from;
  const out = new Float32Array(Math.round(f32.length * ratio));
  for (let i = 0; i < out.length; i++) {
    const x = i / ratio, i0 = Math.floor(x), i1 = Math.min(i0 + 1, f32.length - 1);
    out[i] = f32[i0] + (f32[i1] - f32[i0]) * (x - i0);
  }
  return out;
}

function parseWav(buf) {
  const dv = new DataView(buf);
  let off = 12, sr = 24000, fmt = 1, ch = 1, bits = 16;
  while (off + 8 <= buf.byteLength) {
    const id = String.fromCharCode(dv.getUint8(off), dv.getUint8(off + 1), dv.getUint8(off + 2), dv.getUint8(off + 3));
    const size = dv.getUint32(off + 4, true);
    if (id === "fmt ") { fmt = dv.getUint16(off + 8, true); ch = dv.getUint16(off + 10, true); sr = dv.getUint32(off + 12, true); bits = dv.getUint16(off + 22, true); }
    if (id === "data") {
      const start = off + 8, n = Math.min(size, buf.byteLength - start) / 2 | 0;
      const f32 = new Float32Array(n);
      for (let i = 0; i < n; i++) f32[i] = dv.getInt16(start + i * 2, true) / 32768;
      return { pcm: f32, sr };
    }
    off += 8 + size + (size & 1);
  }
  return null;
}

function scheduleChunk(buf, first) {
  if (!ensureCtx()) return;
  const parsed = parseWav(buf);
  if (!parsed) return;
  const pcm = resample(parsed.pcm, parsed.sr);
  const src = ctx.createBufferSource();
  const audioBuf = ctx.createBuffer(1, pcm.length, ctx.sampleRate);
  audioBuf.getChannelData(0).set(pcm);
  src.buffer = audioBuf;
  src.connect(gainNode);
  const gap = cfg ? cfg.inter_chunk_gap_ms / 1000 : 0.07;
  const t = Math.max(ctx.currentTime + 0.02, first ? 0 : nextTime + gap);
  const when = first ? Math.max(ctx.currentTime + 0.02, nextTime) : t;
  src.start(when);
  nextTime = when + audioBuf.duration;
  scheduled.push(src);
  playing = true;
  wave.classList.add("on");
  src.onended = () => {
    scheduled = scheduled.filter((s) => s !== src);
    if (!scheduled.length) { playing = false; wave.classList.remove("on"); }
  };
}

function stopAudio() {
  scheduled.forEach((s) => { try { s.stop(); } catch (e) {} });
  scheduled = [];
  playing = false;
  nextTime = ctx ? ctx.currentTime : 0;
  wave.classList.remove("on");
}

/* ---------------------------------------------------------------- waveform */

const BARS = 36;
for (let i = 0; i < BARS; i++) wave.appendChild(document.createElement("span"));
const bars = [...wave.children];
const waveData = new Uint8Array(128);
function tickWave() {
  if (analyser && playing) {
    analyser.getByteTimeDomainData(waveData);
    let peak = 0;
    for (let i = 0; i < waveData.length; i++) peak = Math.max(peak, Math.abs(waveData[i] - 128));
    const h = Math.max(4, peak / 128 * 30);
    for (const b of bars) b.style.height = (Math.max(3, h * (0.55 + Math.random() * 0.7))) + "px";
  } else {
    for (const b of bars) b.style.height = "5px";
  }
  requestAnimationFrame(tickWave);
}
requestAnimationFrame(tickWave);

/* --------------------------------------------------------------- websocket */

let ws = null, backoff = 500;
let pendingBin = null, jobStart = 0, currentId = null;
let latSamples = [];

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.binaryType = "arraybuffer";
  ws.onopen = () => { backoff = 500; };
  ws.onclose = () => { setTimeout(connect, backoff); backoff = Math.min(backoff * 2, 8000); };
  ws.onmessage = (ev) => {
    if (ev.data instanceof ArrayBuffer) { onAudio(ev.data); return; }
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    onMsg(msg);
  };
}

function onMsg(msg) {
  switch (msg.type) {
    case "hello":
    case "config":
      setConfig(msg.config || (msg.type === "hello" ? msg.config : null));
      if (msg.status) setEngineStatus(msg.status);
      break;
    case "status":
      setEngineStatus(msg.status);
      break;
    case "begin":
      currentId = msg.id;
      break;
    case "chunk":
      pendingBin = msg;
      if (msg.first && jobStart) {
        const ms = performance.now() - jobStart;
        latSamples.push(ms); latSamples = latSamples.slice(-50);
        showLatency(ms);
      }
      break;
    case "end":
    case "stopped":
      pendingBin = null;
      break;
    case "error":
      toast(msg.message || "error", true);
      if (msg.code === "model_missing") showModelBar();
      break;
  }
}

function onAudio(buf) {
  const meta = pendingBin;
  pendingBin = null;
  if (!meta || !ctx) { if (meta) scheduleChunk(buf, false); return; }
  scheduleChunk(buf, meta.first);
}

function speak(text, mode) {
  if (!ws || ws.readyState !== 1) { toast("not connected", true); return; }
  if (ctx && ctx.state === "suspended") ctx.resume();
  jobStart = performance.now();
  ws.send(JSON.stringify({ type: "speak", text, mode: mode || "replace", id: "c" + Date.now().toString(36) }));
}

function stop() {
  stopAudio();
  if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: "stop" }));
}

/* ------------------------------------------------------------------- ui */

function setConfig(c) {
  if (!c) return;
  cfg = c;
  document.documentElement.dataset.theme = c.theme;
  document.documentElement.style.setProperty("--font-size", c.font_size + "px");
  applyGain();
  $("voicename").textContent = c.voice;
  $("enterkey").textContent = c.enter_mode === "ctrl_enter" ? "ctrl+enter" : "enter";
  $("lat").classList.toggle("hidden", !c.show_latency);
}

function setEngineStatus(st) {
  const el = $("engine"), dot = el.querySelector(".dot"), txt = $("enginetext");
  const bar = $("modelbar");
  if (st.stub) { dot.className = "dot warn"; txt.textContent = "stub mode"; bar.classList.add("hidden"); return; }
  if (!st.model_present) { dot.className = "dot err"; txt.textContent = "model missing"; showModelBar(); return; }
  if (st.loaded) { dot.className = "dot ok"; txt.textContent = `ready · ${st.variant} · ${st.load_ms ? Math.round(st.load_ms) + "ms" : ""}`; }
  else { dot.className = "dot warn"; txt.textContent = "loading model…"; }
}

function showLatency(ms) {
  if (!cfg || !cfg.show_latency) return;
  const avg = latSamples.reduce((a, b) => a + b, 0) / latSamples.length;
  $("lat").textContent = `first word ${Math.round(ms)}ms · avg ${Math.round(avg)}ms`;
}

/* history */
const histLines = [];
function pushHistory(text) {
  const at = new Date().toTimeString().slice(0, 8);
  histLines.unshift({ at, text });
  const limit = cfg ? cfg.history_limit : 30;
  if (histLines.length > limit) histLines.length = limit;
  renderHistory();
}
function renderHistory() {
  history_.innerHTML = "";
  for (const line of histLines) {
    const div = document.createElement("div");
    div.className = "line";
    const t = document.createElement("span"); t.className = "t"; t.textContent = line.at;
    const x = document.createElement("span"); x.className = "txt"; x.textContent = line.text;
    div.append(t, x);
    div.onclick = () => { say.value = line.text; say.focus(); };
    history_.appendChild(div);
  }
}

/* toast */
let toastTimer = null;
function toast(text, isError) {
  const el = $("toast");
  el.textContent = text;
  el.classList.toggle("error", !!isError);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2600);
}

/* model download bar */
let dlPoll = null;
function showModelBar() {
  $("modelbar").classList.remove("hidden");
}
function startDownload() {
  fetch("/api/model/download", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
    .then((r) => r.json()).then((st) => { showModelBar(); pollDownload(); toast("download started"); });
}
function pollDownload() {
  if (dlPoll) return;
  dlPoll = setInterval(() => {
    fetch("/api/model/status").then((r) => r.json()).then((st) => {
      $("dlbar").style.width = (st.percent || 0) + "%";
      $("dltext").textContent = st.running
        ? `${st.step} — ${(st.received / 1048576).toFixed(1)} / ${(st.total / 1048576).toFixed(1)} MB`
        : (st.error ? "failed: " + st.error : "ready");
      if (!st.running) {
        clearInterval(dlPoll); dlPoll = null;
        if (!st.error) { $("modelbar").classList.add("hidden"); toast("model ready — lunar is offline now"); }
      }
    }).catch(() => {});
  }, 800);
}
$("dlbtn").onclick = startDownload;

/* ------------------------------------------------------------ input glue */

say.addEventListener("keydown", (ev) => {
  if (ev.key === "Escape") { stop(); return; }
  const mod = ev.ctrlKey || ev.metaKey;
  const wantEnter = cfg && cfg.enter_mode === "ctrl_enter" ? mod && ev.key === "Enter" : ev.key === "Enter" && !ev.shiftKey && !mod;
  if (wantEnter) {
    ev.preventDefault();
    const text = say.value.trim();
    if (!text) return;
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
    lines.forEach((line, i) => speak(line, i === 0 ? "replace" : "queue"));
    pushHistory(lines.length > 1 ? lines.join(" / ") : lines[0]);
    say.value = "";
  }
});

/* periodic status refresh keeps latency stats + engine state honest */
setInterval(() => {
  fetch("/api/status").then((r) => r.json()).then((st) => setEngineStatus(st.engine)).catch(() => {});
}, 5000);

connect();
fetch("/api/config").then((r) => r.json()).then(setConfig).catch(() => {});
