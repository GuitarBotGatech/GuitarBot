"""Flask play/reset API, verified without OpenCR."""

from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from control.playback import NUM_MOTORS, PlaybackSession
from web.server import create_app

ROOT = Path(__file__).resolve().parent.parent
SMOKE = ROOT / "Docs" / "song-format" / "smoke_on_the_water.json"


def _smoke() -> dict:
    return json.loads(SMOKE.read_text(encoding="utf-8"))


def _client(monkeypatch, *, dry_run: bool, record_audio: bool = False, send_impl=None):
    if send_impl is None:
        monkeypatch.setattr("control.playback.send_trajectory", lambda traj, **kwargs: None)
    else:
        monkeypatch.setattr("control.playback.send_trajectory", send_impl)
    session = PlaybackSession()
    app = create_app(dry_run=dry_run, record_audio=record_audio, session=session)
    app.config["TESTING"] = True
    return app.test_client(), session


def test_health():
    session = PlaybackSession()
    app = create_app(dry_run=True, session=session)
    resp = app.test_client().get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["dry_run"] is True
    assert body["playing"] is False


def test_play_dry_run_returns_shape_and_does_not_send(monkeypatch):
    called = []
    monkeypatch.setattr("control.playback.send_trajectory", lambda traj, **kwargs: called.append(traj))
    session = PlaybackSession()
    client = create_app(dry_run=True, session=session).test_client()
    resp = client.post("/play", json=_smoke())
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["dry_run"] is True
    assert body["shape"][1] == NUM_MOTORS
    assert body["shape"][0] > 0
    assert body["duration_s"] > 0
    assert called == []


def test_play_without_dry_run_sends_trajectory(monkeypatch):
    sent = threading.Event()

    def fake_send(traj, **kwargs):
        sent.set()

    client, _session = _client(monkeypatch, dry_run=False, send_impl=fake_send)
    resp = client.post("/play", json=_smoke())
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True
    assert sent.wait(timeout=5)


def test_play_records_audio_when_enabled(monkeypatch):
    seen = {}
    done = threading.Event()

    def fake_send(traj, **kwargs):
        seen.update(kwargs)
        done.set()

    client, _session = _client(
        monkeypatch,
        dry_run=False,
        record_audio=True,
        send_impl=fake_send,
    )
    song = _smoke()
    resp = client.post("/play", json=song)
    assert resp.status_code == 200
    assert done.wait(timeout=5)
    assert seen.get("telemetry_label") == "play"
    assert seen.get("record_audio") is True
    assert seen.get("song") == song


def test_reset_does_not_record_audio(monkeypatch):
    seen = {}
    done = threading.Event()

    def fake_send(traj, **kwargs):
        seen.update(kwargs)
        done.set()

    client, _session = _client(
        monkeypatch,
        dry_run=False,
        record_audio=True,
        send_impl=fake_send,
    )
    resp = client.post("/reset")
    assert resp.status_code == 200
    assert done.wait(timeout=5)
    assert seen.get("telemetry_label") == "reset"
    assert seen.get("record_audio") is False
    assert seen.get("song") is None


def test_reset_dry_run(monkeypatch):
    client, _session = _client(monkeypatch, dry_run=True)
    resp = client.post("/reset")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert body["shape"][1] == NUM_MOTORS
    assert body["shape"][0] > 0


def test_bad_json_returns_400(monkeypatch):
    client, _session = _client(monkeypatch, dry_run=True)
    resp = client.post("/play", data="not-json", content_type="application/json")
    assert resp.status_code == 400
    assert resp.get_json()["ok"] is False


def test_play_busy_returns_409(monkeypatch):
    client, session = _client(monkeypatch, dry_run=True)
    assert session.try_acquire()
    try:
        resp = client.post("/play", json=_smoke())
        assert resp.status_code == 409
        assert resp.get_json()["ok"] is False
    finally:
        session.release()


def test_serves_sequencer_html(monkeypatch):
    client, _session = _client(monkeypatch, dry_run=True)
    resp = client.get("/sequencer.html")
    assert resp.status_code == 200
    assert b"GuitarBot" in resp.data or b"sequencer" in resp.data.lower()
