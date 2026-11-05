/* lunar config console — every knob of the voice, live-saved. */
"use strict";

const $ = (id) => document.getElementById(id);
let cfg = null, voices = [], langs = {};
let saveTimer = null, ws = null;

/* ------------------------------------------------------------------ saving */

function touch() {
  $("saveState").textContent = "saving…";
  $("saveState").className = "state";
  clearTimeout(saveTimer);
  saveTimer = setTimeout(saveNow, 350);
}

function saveNow() {
  fetch("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cfg) })
    .then((r) => r.json())
    .then((clean) => {
      cfg = clean;
      $("saveState").textContent = "saved " + new Date().toTimeString().slice(0, 8);
      $("saveState").className = "state saved";
      renderAll();
    })
    .catch(() => { $("saveState").textContent = "save failed"; $("saveState").className = "state"; });
}

function patch(key, value) {
  cfg[key] = value;
  touch();
}

/* ------------------------------------------------------------------- toast */

let toastTimer = null;
function toast(text, isError) {
  const el = $("toast");
  el.textContent = text;
  el.classList.toggle("error", !!isError);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2400);
}

/* -------------------------------------------------------------------- tabs */

for (const btn of $("tabs").children) {
  btn.onclick = () => {
    for (const b of $("tabs").children) b.classList.toggle("active", b === btn);
    for (const page of document.querySelectorAll(".tabpage")) page.classList.toggle("active", page.id === "tab-" + btn.dataset.tab);
  };
}

/* ------------------------------------------------------------ simple binds */

function bindRange(id, key, fmt) {
  const el = $(id), out = $(id + "Out");
  el.addEventListener("input", () => {
    const v = parseFloat(el.value);
    out.textContent = fmt ? fmt(v) : v;
    patch(key, v);
  });
}

function bindSwitch(id, key) {
  $(id).addEventListener("change", (ev) => patch(key, ev.target.checked));
}

function bindRadios(id, key) {
  for (const label of $(id).children) {
    label.onclick = () => patch(key, label.dataset.v);
  }
}

/* ------------------------------------------------------------------ voices */

function renderVoices() {
  const grid = $("voiceGrid");
  grid.innerHTML = "";
  const q = $("voiceSearch").value.toLowerCase();
  const lf = $("langFilter").value;
  let shown = 0;
  for (const v of voices) {
    if (!v.supported) continue;
    if (q && !v.name.includes(q) && !(v.note || "").toLowerCase().includes(q)) continue;
    if (lf && v.lang !== lf) continue;
    const card = document.createElement("div");
    card.className = "voice-card" + (v.name === cfg.voice ? " selected" : "");
    card.innerHTML = `<div class="vname">${v.name}</div>
      <div class="vmeta">${v.gender} · ${v.region}${v.note ? " · " + v.note : ""}</div>
      <div class="vnote">${v.lang}</div>`;
    card.onclick = () => { patch("voice", v.name); };
    const test = document.createElement("button");
    test.className = "btn small vtest";
    test.textContent = "test";
    test.onclick = (ev) => { ev.stopPropagation(); testVoice(v.name, v.lang); };
    card.appendChild(test);
    grid.appendChild(card);
    shown++;
  }
  $("voiceCount").textContent = `${shown} / ${voices.filter((v) => v.supported).length} voices`;
}

function testVoice(name, lang) {
  const sample = lang === "id"
    ? "Halo, ini suara lunar."
    : "Hello, this is the lunar voice console.";
  speakOverride(sample, { voice: name, lang });
}

let pendingBin = null;
function speakOverride(text, overrides) {
  if (!ws || ws.readyState !== 1) { toast("console connection lost", true); return; }
  ws.send(JSON.stringify({ type: "speak", text, overrides, mode: "replace", id: "t" + Date.now() }));
}

/* ------------------------------------------------------- pronunciation dict */

function renderPron() {
  const tbody = $("pronTable").querySelector("tbody");
  tbody.innerHTML = "";
  const entries = Object.entries(cfg.pron_dict || {});
  if (!entries.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="3" class="faint small">no entries — add a word and how it should sound</td>`;
    tbody.appendChild(tr);
  }
  for (const [k, v] of entries) tbody.appendChild(pronRow(k, v));
}

function pronRow(k, v) {
  const tr = document.createElement("tr");
  const td1 = document.createElement("td");
  const td2 = document.createElement("td");
  const td3 = document.createElement("td");
  td3.style.textAlign = "right";
  const i1 = document.createElement("input");
  i1.className = "field"; i1.value = k; i1.placeholder = "word";
  const i2 = document.createElement("input");
  i2.className = "field"; i2.value = v; i2.placeholder = "say it like";
  i1.oninput = () => { renamePron(k, i1.value, v, i1, i2); };
  i2.oninput = () => { cfg.pron_dict[k] = i2.value; touch(); };
  const del = document.createElement("button");
  del.className = "btn small danger"; del.textContent = "remove";
  del.onclick = () => { delete cfg.pron_dict[k]; touch(); renderPron(); };
  td1.appendChild(i1); td2.appendChild(i2); td3.appendChild(del);
  tr.append(td1, td2, td3);
  return tr;
}

function renamePron(oldKey, newKey, val, i1, i2) {
  newKey = newKey.trim();
  if (newKey && newKey !== oldKey) {
    delete cfg.pron_dict[oldKey];
    cfg.pron_dict[newKey] = i2.value;
    // keep this row bound to the new key without re-render jump
    i1.oninput = () => renamePron(newKey, i1.value, i2.value, i1, i2);
    i2.oninput = () => { cfg.pron_dict[newKey] = i2.value; touch(); };
  } else if (!newKey) {
    delete cfg.pron_dict[oldKey];
  }
  touch();
}

$("pronAdd").onclick = () => {
  cfg.pron_dict[""] = "";
  renderPron();
  const first = $("pronTable").querySelector("tbody input");
  if (first) first.focus();
};
$("pronExample").onclick = () => {
  Object.assign(cfg.pron_dict, {
    gg: "gee gee",
    noob: "noob",
    gaming: "gey-ming",
    oke: "okay",
    seru: "se-roo",
  });
  touch(); renderPron(); toast("example set inserted");
};
$("pronExport").onclick = () => {
  downloadJson(cfg.pron_dict, "lunar-pron.json");
};
$("pronImport").onchange = (ev) => {
  fileToJson(ev.target.files[0], (data) => {
    if (data && typeof data === "object" && !Array.isArray(data)) {
      cfg.pron_dict = data;
      touch(); renderPron(); toast("dictionary imported");
    } else toast("not a dictionary file", true);
  });
  ev.target.value = "";
};
$("pronTest").onclick = () => speakOverride($("pronTestText").value || "Halo, ini tes pelafalan.", null);

/* -------------------------------------------------------------- file utils */

function downloadJson(obj, name) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}
function fileToJson(file, cb) {
  if (!file) return;
  const fr = new FileReader();
  fr.onload = () => { try { cb(JSON.parse(fr.result)); } catch (e) { toast("invalid json", true); } };
  fr.readAsText(file);
}

/* ---------------------------------------------------------------- engine tab */

function renderEngine(st) {
  if (!st) return;
  $("dlText").textContent = st.downloader && st.downloader.running
    ? `${st.downloader.step} — ${(st.downloader.received / 1048576).toFixed(1)} / ${(st.downloader.total / 1048576).toFixed(1)} MB`
    : (st.downloader && st.downloader.error ? "download failed: " + st.downloader.error : "");
  $("dlProg").classList.toggle("hidden", !(st.downloader && st.downloader.running));
  $("dlBar").style.width = st.downloader ? (st.downloader.percent || 0) + "%" : "0%";

  const files = st.downloader ? st.downloader.files : {};
  $("files").innerHTML = "";
  for (const [name, ok] of Object.entries(files)) {
    const row = document.createElement("div");
    row.className = "row between small";
    row.innerHTML = `<span>${name}</span><span class="${ok ? "muted" : "faint"}">${ok ? "present" : "missing"}</span>`;
    $("files").appendChild(row);
  }

  const stats = st.engine ? st.engine.stats : null;
  if (stats) {
    $("stats").innerHTML = "";
    const fields = [
      ["requests", stats.requests],
      ["chunks", stats.chunks],
      ["avg synth", stats.avg_synth_ms != null ? stats.avg_synth_ms + " ms" : "—"],
      ["rtf", stats.avg_rtf != null ? stats.avg_rtf : "—"],
      ["first word p50", stats.first_chunk_p50_ms != null ? stats.first_chunk_p50_ms + " ms" : "—"],
      ["first word p95", stats.first_chunk_p95_ms != null ? stats.first_chunk_p95_ms + " ms" : "—"],
    ];
    for (const [k, v] of fields) {
      const d = document.createElement("div");
      d.className = "stat";
      d.innerHTML = `<div class="k">${k}</div><div class="v">${v}</div>`;
      $("stats").appendChild(d);
    }
  }
  if (st.config_file) $("paths").textContent = "config lives at " + st.config_file;
}

$("dlNow").onclick = () => {
  fetch("/api/model/download", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ variant: cfg.engine_variant }) })
    .then((r) => r.json()).then(() => { toast("download started"); pollStatus(); });
};
$("reloadEngine").onclick = () => {
  fetch("/api/engine/reload", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ variant: cfg.engine_variant }) })
    .then((r) => r.json()).then(() => toast("engine reloading"));
};
$("cfgExport").onclick = () => downloadJson(cfg, "lunar-config.json");
$("cfgImport").onchange = (ev) => {
  fileToJson(ev.target.files[0], (data) => {
    if (data && typeof data === "object") {
      cfg = Object.assign({}, cfg, data);
      touch(); toast("config imported");
    } else toast("invalid config", true);
  });
  ev.target.value = "";
};
$("cfgReset").onclick = () => {
  if (!confirm("reset every setting to defaults?")) return;
  fetch("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reset: true }) })
    .then((r) => r.json()).then((clean) => { cfg = clean; renderAll(); toast("defaults restored"); });
};

/* ------------------------------------------------------------------ render */

function renderAll() {
  document.documentElement.dataset.theme = cfg.theme;
  document.documentElement.style.setProperty("--font-size", cfg.font_size + "px");

  // voice tab
  $("lang").innerHTML = "";
  for (const [code, label] of Object.entries(langs)) {
    const opt = document.createElement("option");
    opt.value = code; opt.textContent = `${label} (${code})`;
    $("lang").appendChild(opt);
  }
  $("lang").value = cfg.lang;

  for (const id of ["speed", "sentence_pause", "clause_pause", "max_chunk_chars", "inter_chunk_gap_ms", "font_size", "history_limit", "gain"]) {
    const el = $(id), out = $(id + "Out");
    if (el && out) { el.value = cfg[id]; out.textContent = cfg[id]; }
  }
  for (const id of ["streaming", "first_chunk_fast", "show_latency", "warmup_on_start", "pron_dict_enabled"]) $(id).checked = cfg[id];
  for (const [id, key] of [["enter_mode", "enter_mode"], ["theme", "theme"], ["engine_variant", "engine_variant"]]) {
    for (const label of $(id).children) label.classList.toggle("on", label.dataset.v === cfg[key]);
  }
  $("ort_threads").value = cfg.ort_threads;
  renderVoices();
  renderPron();
}

function pollStatus() {
  fetch("/api/status").then((r) => r.json()).then(renderEngine).catch(() => {});
}
setInterval(pollStatus, 2000);

/* ---------------------------------------------------------------- connect */

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.binaryType = "arraybuffer";
  ws.onmessage = (ev) => {
    if (ev.data instanceof ArrayBuffer) {
      if (pendingBin) playTestChunk(ev.data, pendingBin);
      pendingBin = null;
      return;
    }
    let msg;
    try { msg = JSON.parse(ev.data); } catch (e) { return; }
    if (msg.type === "chunk") pendingBin = msg;
    if (msg.type === "hello" || msg.type === "config") { if (msg.config) { cfg = msg.config; renderAll(); } }
  };
  ws.onclose = () => setTimeout(connect, 1000);
}

/* test playback on this page too */
let tctx = null, tnext = 0, tscheduled = [];
function playTestChunk(buf, meta) {
  if (!tctx) {
    try { tctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 }); }
    catch (e) { tctx = new (window.AudioContext || window.webkitAudioContext)(); }
  }
  if (tctx.state === "suspended") tctx.resume();
  const dv = new DataView(buf);
  let off = 12, sr = 24000;
  while (off + 8 <= buf.byteLength) {
    const id = String.fromCharCode(dv.getUint8(off), dv.getUint8(off + 1), dv.getUint8(off + 2), dv.getUint8(off + 3));
    const size = dv.getUint32(off + 4, true);
    if (id === "fmt ") sr = dv.getUint32(off + 12, true);
    if (id === "data") {
      const start = off + 8, n = Math.min(size, buf.byteLength - start) / 2 | 0;
      let f32 = new Float32Array(n);
      for (let i = 0; i < n; i++) f32[i] = dv.getInt16(start + i * 2, true) / 32768;
      if (sr !== tctx.sampleRate) {
        const ratio = tctx.sampleRate / sr;
        const out = new Float32Array(Math.round(n * ratio));
        for (let i = 0; i < out.length; i++) {
          const x = i / ratio, i0 = Math.floor(x), i1 = Math.min(i0 + 1, n - 1);
          out[i] = f32[i0] + (f32[i1] - f32[i0]) * (x - i0);
        }
        f32 = out;
      }
      const src = tctx.createBufferSource();
      const ab = tctx.createBuffer(1, f32.length, tctx.sampleRate);
      ab.getChannelData(0).set(f32);
      src.buffer = ab;
      src.connect(tctx.destination);
      const when = Math.max(tctx.currentTime + 0.02, tnext);
      src.start(when);
      tnext = when + ab.duration;
      tscheduled.push(src);
      src.onended = () => { tscheduled = tscheduled.filter((s) => s !== src); };
      return;
    }
    off += 8 + size + (size & 1);
  }
}

/* ------------------------------------------------------------------ events */

$("voiceSearch").addEventListener("input", renderVoices);
$("langFilter").addEventListener("change", renderVoices);
$("lang").addEventListener("change", (ev) => patch("lang", ev.target.value));
$("ort_threads").addEventListener("change", (ev) => patch("ort_threads", parseInt(ev.target.value || "0", 10) || 0));

bindRange("speed", "speed", (v) => v.toFixed(2) + "x");
bindRange("sentence_pause", "sentence_pause", (v) => v.toFixed(2) + "s");
bindRange("clause_pause", "clause_pause", (v) => v.toFixed(2) + "s");
bindRange("max_chunk_chars", "max_chunk_chars", (v) => v + "ch");
bindRange("inter_chunk_gap_ms", "inter_chunk_gap_ms", (v) => v + "ms");
bindRange("font_size", "font_size", (v) => v + "px");
bindRange("history_limit", "history_limit", (v) => v + "");
bindRange("gain", "gain", (v) => v.toFixed(2) + "x");
bindSwitch("streaming", "streaming");
bindSwitch("first_chunk_fast", "first_chunk_fast");
bindSwitch("show_latency", "show_latency");
bindSwitch("warmup_on_start", "warmup_on_start");
bindSwitch("pron_dict_enabled", "pron_dict_enabled");
bindRadios("enter_mode", "enter_mode");
bindRadios("theme", "theme");
bindRadios("engine_variant", "engine_variant");

/* boot */
(async function boot() {
  const [cfgRes, voicesRes, langsRes, stRes] = await Promise.all([
    fetch("/api/config"), fetch("/api/voices"), fetch("/api/langs"), fetch("/api/status"),
  ]);
  cfg = await cfgRes.json();
  const v = await voicesRes.json();
  voices = v.voices || [];
  const l = await langsRes.json();
  langs = l.langs || {};

  const langFilter = $("langFilter");
  const seen = new Set();
  for (const voice of voices) {
    if (voice.supported && !seen.has(voice.lang)) {
      seen.add(voice.lang);
      const opt = document.createElement("option");
      opt.value = voice.lang;
      opt.textContent = (langs[voice.lang] || voice.lang) + " voices";
      langFilter.appendChild(opt);
    }
  }
  renderAll();
  renderEngine(await stRes.json());
  connect();
})();
