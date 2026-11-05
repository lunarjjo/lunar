"""Text pipeline: inline overrides, pronunciation dictionary, stream chunking.

The chunker is what makes lunar feel instant: instead of waiting for the whole
message to synthesize, the text is cut at sentence (and early clause) boundaries
so the first words hit the speaker while the rest is still being generated.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ---------------------------------------------------------------- overrides --

_OVERRIDE = re.compile(r"^\s*/(v|s|sp|lang|l)\s+(\S+)\s+", re.IGNORECASE)
_LANG_CODE = re.compile(r"^\s*/([a-z]{2}(?:-[a-z]{2})?)\s+", re.IGNORECASE)
_LANG_ALIASES = {
    "en": "en-us", "us": "en-us", "gb": "en-gb", "uk": "en-gb",
    "id": "id", "es": "es", "fr": "fr-fr", "it": "it", "pt": "pt-br",
    "br": "pt-br", "hi": "hi", "de": "de", "pl": "pl",
    "en-us": "en-us", "en-gb": "en-gb", "fr-fr": "fr-fr", "pt-br": "pt-br",
}


@dataclass
class Overrides:
    voice: str | None = None
    lang: str | None = None
    speed: float | None = None


def parse_overrides(text: str) -> tuple[str, Overrides]:
    """Strip leading ``/v NAME``, ``/lang CODE``, ``/s 1.2``, ``/en`` tokens."""
    ov = Overrides()
    remaining = text
    for _ in range(5):  # allow several flags in a row
        m = _OVERRIDE.match(remaining)
        if m:
            flag, value = m.group(1).lower(), m.group(2)
            if flag == "v":
                ov.voice = value[:32]
            elif flag in ("lang", "l"):
                ov.lang = _LANG_ALIASES.get(value.lower(), value.lower()[:8])
            else:
                try:
                    ov.speed = min(max(float(value), 0.5), 2.0)
                except ValueError:
                    pass
            remaining = remaining[m.end():]
            continue
        m = _LANG_CODE.match(remaining)
        if m and m.group(1).lower() in _LANG_ALIASES:
            ov.lang = _LANG_ALIASES[m.group(1).lower()]
            remaining = remaining[m.end():]
            continue
        break
    return remaining.strip(), ov


# ------------------------------------------------------ pronunciation dict --

_WORD = re.compile(r"[A-Za-z0-9']+")


def apply_pron_dict(text: str, pron: dict[str, str]) -> str:
    """Replace whole words (case-insensitive) with their "say it like" spelling."""
    if not pron:
        return text
    table = {k.lower(): v for k, v in pron.items()}
    out = []
    last = 0
    for m in _WORD.finditer(text):
        sub = table.get(m.group(0).lower())
        if sub is not None:
            out.append(text[last:m.start()])
            out.append(sub)
            last = m.end()
    out.append(text[last:])
    return "".join(out)


# ------------------------------------------------------------- chunking -----

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+")
_CLAUSE_SPLIT = re.compile(r"(?<=[,;:])\s+")
_HAS_SPEAKABLE = re.compile(r"[^\W\d_]+|\d")  # letters or digits


def _merge_tiny(parts: list[str], floor: int = 4) -> list[str]:
    merged: list[str] = []
    for part in parts:
        if merged and (len(part.strip()) < floor or len(merged[-1].strip()) < floor):
            merged[-1] = merged[-1].rstrip() + " " + part.lstrip()
        else:
            merged.append(part)
    return [p for p in (m.strip() for m in merged) if p]


def _split_long(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    clauses = _merge_tiny(_CLAUSE_SPLIT.split(sentence))
    out: list[str] = []
    buf = ""
    for clause in clauses:
        candidate = f"{buf} {clause}".strip() if buf else clause
        if len(candidate) > max_chars and buf:
            out.append(buf)
            buf = clause
        else:
            buf = candidate
    if buf:
        out.append(buf)
    # any remaining oversized chunk gets hard-split at word boundaries
    final: list[str] = []
    for chunk in out:
        while len(chunk) > max_chars * 1.6:
            cut = chunk.rfind(" ", 0, max_chars)
            if cut <= 0:
                cut = max_chars
            final.append(chunk[:cut].rstrip())
            chunk = chunk[cut:].lstrip()
        final.append(chunk)
    return [f for f in final if f]


def split_for_stream(
    text: str,
    first_chunk_fast: bool = True,
    max_chars: int = 160,
) -> list[str]:
    """Cut text into speakable chunks ordered for lowest first-audio latency."""
    text = " ".join(text.split()).strip()
    if not text:
        return []
    sentences = _merge_tiny([s for s in _SENTENCE_SPLIT.split(text) if s.strip()])
    chunks: list[str] = []
    for sentence in sentences:
        chunks.extend(_split_long(sentence, max_chars))
    # Fast start: if the first chunk has an early comma, cut there so playback
    # begins after the first few words instead of the whole first sentence.
    if first_chunk_fast and chunks:
        m = _CLAUSE_SPLIT.search(chunks[0])
        if m and 4 <= m.start() <= 64 and len(chunks[0]) > m.end() + 4:
            head, tail = chunks[0][: m.start()], chunks[0][m.end():]
            chunks = [head, *([tail] if tail else []), *chunks[1:]]
    return [c for c in chunks if _HAS_SPEAKABLE.search(c)]


def chunk_text_plain(text: str, max_chars: int = 160) -> list[str]:
    """Splitting used when streaming is disabled (single call is still batched)."""
    return split_for_stream(text, first_chunk_fast=False, max_chars=max_chars)
