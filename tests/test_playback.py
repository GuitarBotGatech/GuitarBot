"""Playback plans trajectories from arrangement JSON without OSC or Tone Master."""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from playback import NUM_MOTORS, PlaybackSession, play_arrangement, reset

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "Docs" / "song-format" / "example.json"
SMOKE = ROOT / "Docs" / "song-format" / "smoke_on_the_water.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_play_example_json_returns_18_column_trajectory():
    traj = play_arrangement(_load(EXAMPLE), send=False, session=PlaybackSession())
    assert traj.ndim == 2
    assert traj.shape[1] == NUM_MOTORS
    assert traj.shape[0] > 0


def test_play_smoke_on_the_water_pluck_only():
    traj = play_arrangement(_load(SMOKE), send=False, session=PlaybackSession())
    assert traj.ndim == 2
    assert traj.shape[1] == NUM_MOTORS
    assert traj.shape[0] > 0


def test_midi_track_does_not_change_trajectory():
    payload = _load(EXAMPLE)
    with_midi = play_arrangement(payload, send=False, session=PlaybackSession())

    stripped = copy.deepcopy(payload)
    stripped["song"]["tracks"] = [
        track for track in stripped["song"]["tracks"] if track.get("type") != "midi"
    ]
    without_midi = play_arrangement(stripped, send=False, session=PlaybackSession())

    np.testing.assert_allclose(with_midi, without_midi)


def test_play_arrangement_send_false_does_not_call_robot(monkeypatch):
    called = []
    monkeypatch.setattr("playback.send_trajectory", lambda traj: called.append(traj))
    play_arrangement(_load(SMOKE), send=False, session=PlaybackSession())
    assert called == []


def test_play_arrangement_send_true_calls_robot(monkeypatch):
    called = []
    monkeypatch.setattr("playback.send_trajectory", lambda traj: called.append(traj.shape))
    traj = play_arrangement(_load(SMOKE), send=True, session=PlaybackSession())
    assert called == [traj.shape]


def test_reset_returns_home_trajectory_and_restores_parser_state(monkeypatch):
    monkeypatch.setattr("playback.send_trajectory", lambda traj: None)
    session = PlaybackSession()
    play_arrangement(_load(SMOKE), send=False, session=session)

    traj = reset(send=False, session=session)
    assert traj.ndim == 2
    assert traj.shape[1] == NUM_MOTORS
    assert traj.shape[0] > 0
    np.testing.assert_allclose(session.last_position, session.parser.initial_point)
    assert session.parser.current_fret_positions == [0, 0, 0, 0, 0, 0]


def test_missing_plucks_raise():
    payload = {
        "song": {
            "name": "empty",
            "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
            "tracks": [{"name": "chords", "type": "chord", "events": [{"chord": "C", "beat": "1.1"}]}],
        }
    }
    with pytest.raises(ValueError, match="no pluck"):
        play_arrangement(payload, send=False, session=PlaybackSession())
