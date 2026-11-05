"""End-to-end server tests over HTTP + WebSocket using the stub engine.

Exercises the exact protocol the browser consoles speak: hello, config
broadcast, speak -> begin -> (chunk json + binary wav)* -> end, stop, errors.
"""
import json
import struct

import pytest
from fastapi.testclient import TestClient

from app.server import create_app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from app import config as config_mod
    monkeypatch.setattr(config_mod.paths, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(config_mod.paths, "CONFIG_DIR", tmp_path)
    app = create_app(stub=True)
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").text == "ok"


def test_config_roundtrip(client):
    before = client.get("/api/config").json()
    assert before["voice"] == "af_heart"
    after = client.post("/api/config", json={"speed": 1.4, "voice": "bf_emma"}).json()
    assert after["speed"] == 1.4 and after["voice"] == "bf_emma"
    again = client.get("/api/config").json()
    assert again["speed"] == 1.4


def test_config_sanitized(client):
    out = client.post("/api/config", json={"speed": 99, "theme": "neon"}).json()
    assert out["speed"] == 2.0
    assert out["theme"] == "dark"


def test_config_reset(client):
    client.post("/api/config", json={"voice": "bf_emma", "speed": 1.8})
    out = client.post("/api/config", json={"reset": True}).json()
    assert out["voice"] == "af_heart"
    assert out["speed"] == 1.0


def test_voices_catalog(client):
    data = client.get("/api/voices").json()
    names = [v["name"] for v in data["voices"]]
    assert "af_heart" in names and "am_michael" in names
    zh = [v for v in data["voices"] if v["name"].startswith("z")][0]
    assert zh["supported"] is False


def test_status_shape(client):
    st = client.get("/api/status").json()
    assert st["engine"]["stub"] is True
    assert "version" in st and "downloader" in st


def test_index_served(client):
    html = client.get("/").text
    assert "lunar" in html and "say" in html


def test_config_page_served(client):
    html = client.get("/config").text
    assert "voice" in html and "pronunciation" in html


def test_static_assets(client):
    assert client.get("/assets/live.js").status_code == 200
    assert client.get("/assets/style.css").status_code == 200
    assert client.get("/assets/config.js").status_code == 200


def _read_chunk(ws):
    """Receive one protocol event: json or binary wav."""
    msg = ws.receive()
    if "bytes" in msg and msg["bytes"] is not None:
        return {"binary": msg["bytes"]}
    return {"json": json.loads(msg["text"])}


class TestSpeechProtocol:
    def test_speak_full_flow(self, client):
        with client.websocket_connect("/ws") as ws:
            hello = json.loads(ws.receive_text())
            assert hello["type"] == "hello"
            assert hello["config"]["voice"] == "af_heart"

            ws.send_text(json.dumps({"type": "speak", "text": "Halo guys, tes satu dua.", "id": "j1"}))
            begin = json.loads(ws.receive_text())
            assert begin["type"] == "begin" and begin["id"] == "j1"

            n_binary = 0
            while True:
                msg = ws.receive()
                if "bytes" in msg and msg["bytes"] is not None:
                    blob = msg["bytes"]
                    assert blob[:4] == b"RIFF"
                    assert struct.unpack("<I", blob[4:8])[0] == len(blob) - 8
                    n_binary += 1
                    continue
                data = json.loads(msg["text"])
                if data["type"] == "chunk":
                    assert data["id"] == "j1"
                    assert data["sr"] == 24000
                    continue
                assert data["type"] == "end"
                assert data["id"] == "j1"
                break
            assert n_binary >= 2  # fast first chunk splits this line

    def test_error_on_empty(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()  # hello
            ws.send_text(json.dumps({"type": "speak", "text": "   ", "id": "j2"}))
            data = json.loads(ws.receive_text())
            assert data["type"] == "error" and data["id"] == "j2"

    def test_stop_interrupts(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
            ws.send_text(json.dumps({"type": "speak", "text": "satu. dua. tiga. empat.", "id": "j3"}))
            # read until first chunk arrives, then stop
            got_chunk = False
            while True:
                msg = ws.receive()
                if "bytes" in msg and msg["bytes"] is not None:
                    ws.send_text(json.dumps({"type": "stop"}))
                    got_chunk = True
                    continue
                data = json.loads(msg["text"])
                if data["type"] in ("begin", "chunk"):
                    continue
                assert data["type"] in ("stopped", "end")
                assert got_chunk
                break

    def test_config_broadcast_reaches_socket(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()  # hello
            # a REST config change broadcasts to connected consoles
            client.post("/api/config", json={"voice": "am_adam"})
            data = json.loads(ws.receive_text())
            assert data["type"] == "config"
            assert data["config"]["voice"] == "am_adam"

    def test_ping(self, client):
        with client.websocket_connect("/ws") as ws:
            ws.receive_text()
            ws.send_text(json.dumps({"type": "ping", "t": 42}))
            data = json.loads(ws.receive_text())
            assert data == {"type": "pong", "t": 42}
