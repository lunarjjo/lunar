import json

import pytest

from app import config


@pytest.fixture()
def tmp_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config.paths, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(config.paths, "CONFIG_DIR", tmp_path)
    config.STATE = None
    return tmp_path / "config.json"


class TestDefaults:
    def test_defaults_complete(self):
        cfg = config.sanitize({})
        for key in config.DEFAULTS:
            assert key in cfg

    def test_defaults_are_sane(self):
        cfg = config.sanitize({})
        assert cfg["voice"] == "af_heart"
        assert cfg["lang"] == "id"
        assert 0.5 <= cfg["speed"] <= 2.0


class TestSanitize:
    def test_speed_clamped(self):
        assert config.sanitize({"speed": 99})["speed"] == 2.0
        assert config.sanitize({"speed": 0.1})["speed"] == 0.5

    def test_garbage_speed(self):
        assert config.sanitize({"speed": "abc"})["speed"] == config.DEFAULTS["speed"]

    def test_invalid_choice_kept_default(self):
        assert config.sanitize({"theme": "vaporwave"})["theme"] == "dark"
        assert config.sanitize({"enter_mode": "triple"})["enter_mode"] == "enter"

    def test_invalid_lang_rejected(self):
        assert config.sanitize({"lang": "xx"})["lang"] == config.DEFAULTS["lang"]

    def test_valid_voice_accepted(self):
        assert config.sanitize({"voice": "am_michael"})["voice"] == "am_michael"

    def test_unknown_keys_ignored(self):
        assert "rm -rf" not in config.sanitize({"rm -rf": "1"})

    def test_pron_dict_cleaned(self):
        out = config.sanitize({"pron_dict": {"ok": "fine", "": "x", ("y" * 90): "z"}})
        assert out["pron_dict"] == {"ok": "fine"}

    def test_pron_dict_garbage(self):
        assert config.sanitize({"pron_dict": "nope"})["pron_dict"] == {}

    def test_bool_coercion(self):
        assert config.sanitize({"streaming": "true"})["streaming"] is True
        assert config.sanitize({"streaming": 0})["streaming"] is False


class TestPersistence:
    def test_roundtrip(self, tmp_config):
        config.save({"voice": "bf_emma", "speed": 1.3, "pron_dict": {"gg": "gee gee"}})
        loaded = config.load()
        assert loaded["voice"] == "bf_emma"
        assert loaded["speed"] == 1.3
        assert loaded["pron_dict"] == {"gg": "gee gee"}

    def test_corrupt_file_falls_back(self, tmp_config):
        tmp_config.write_text("{not json", encoding="utf-8")
        assert config.load() == dict(config.DEFAULTS)

    def test_saved_file_is_valid_json(self, tmp_config):
        config.save({"speed": 1.1})
        data = json.loads(tmp_config.read_text(encoding="utf-8"))
        assert data["speed"] == 1.1
