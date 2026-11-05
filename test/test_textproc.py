import pytest

from app.textproc import (
    apply_pron_dict,
    parse_overrides,
    split_for_stream,
)


class TestOverrides:
    def test_voice(self):
        text, ov = parse_overrides("/v am_adam hello there")
        assert text == "hello there"
        assert ov.voice == "am_adam"

    def test_lang_alias(self):
        text, ov = parse_overrides("/en Halo semuanya")
        assert ov.lang == "en-us"
        assert text == "Halo semuanya"

    def test_speed_clamped(self):
        text, ov = parse_overrides("/s 9.0 terlalu cepat")
        assert ov.speed == 2.0

    def test_combined(self):
        text, ov = parse_overrides("/v bf_emma /id /s 1.2 satu dua")
        assert (text, ov.voice, ov.lang, ov.speed) == ("satu dua", "bf_emma", "id", 1.2)

    def test_no_override(self):
        text, ov = parse_overrides("plain message")
        assert text == "plain message"
        assert ov.voice is None and ov.lang is None and ov.speed is None


class TestPronDict:
    def test_simple(self):
        out = apply_pron_dict("gg we gaming", {"gg": "gee gee"})
        assert out == "gee gee we gaming"

    def test_case_insensitive(self):
        assert apply_pron_dict("GG!", {"gg": "gee gee"}) == "gee gee!"

    def test_word_boundary(self):
        out = apply_pron_dict("begging", {"egg": "ay-gee"})
        assert out == "begging"  # 'egg' inside 'begging' must not match

    def test_empty(self):
        assert apply_pron_dict("same", {}) == "same"


class TestSplit:
    def test_single_sentence(self):
        assert split_for_stream("One sentence only.") == ["One sentence only."]

    def test_sentences(self):
        parts = split_for_stream("First one. Second one! Third?")
        assert len(parts) == 3

    def test_first_chunk_fast(self):
        parts = split_for_stream("Halo guys, selamat datang di stream malam ini.")
        assert parts[0] == "Halo guys,"
        assert parts[1].startswith("selamat")

    def test_first_chunk_fast_off(self):
        parts = split_for_stream("Halo guys, selamat datang.", first_chunk_fast=False)
        assert len(parts) == 1

    def test_max_chars(self):
        text = " ".join(f"word{i}" for i in range(80))
        parts = split_for_stream(text, first_chunk_fast=False, max_chars=100)
        assert all(len(p) <= 160 for p in parts)
        assert len(parts) >= 2

    def test_emoji_only_dropped(self):
        assert split_for_stream("\U0001f600\U0001f600\U0001f600") == []

    def test_empty(self):
        assert split_for_stream("   ") == []

    def test_tiny_fragments_merged(self):
        parts = split_for_stream("Hi. Ok. Real sentence follows here now.")
        assert parts[0] == "Hi. Ok."

    def test_newlines_treated_as_space(self):
        parts = split_for_stream("line one\nline two")
        assert parts == ["line one line two"]
