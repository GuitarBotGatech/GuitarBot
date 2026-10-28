"""Lean tests for Events JSON → planner rows."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notation.events import SongArrangement, beat_label_to_seconds


def _example() -> SongArrangement:
    path = Path(__file__).resolve().parent.parent / "Docs" / "song-format" / "example.json"
    return SongArrangement.from_dict(json.loads(path.read_text(encoding="utf-8")))


def test_load_example():
    arrangement = _example()
    assert arrangement.name == "MVP Example Song"
    assert arrangement.bpm == pytest.approx(92.0)
    assert arrangement.plucks
    assert arrangement.chords


def test_tempo_curve_delays_later_plucks():
    arrangement = _example()
    plucks, _mutes = arrangement.to_plan()
    assert arrangement.chords[0] == ["Em", 0.0]
    assert plucks[0][0] == 52
    assert plucks[0][-1] > arrangement.plucks[0][-1]


def test_beat_labels():
    assert beat_label_to_seconds("1.1", bpm=120, time_signature="4/4") == pytest.approx(0.0)
    assert beat_label_to_seconds("2.1", bpm=120, time_signature="4/4") == pytest.approx(2.0)
    assert beat_label_to_seconds("3.2.2", bpm=120, time_signature="4/4") == pytest.approx(4.625)
    assert beat_label_to_seconds("~9.3333", bpm=120, time_signature="4/4") == pytest.approx(4.66665)


def test_beat_labels_in_events():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "beats",
                "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
                "tracks": [
                    {
                        "name": "chords",
                        "type": "chord",
                        "events": [
                            {"chord": "Em", "beat": "1.1"},
                            {"chord": "D", "beat": "2.1"},
                        ],
                    },
                    {
                        "name": "pluck",
                        "type": "pluck",
                        "events": [
                            {
                                "note": 52,
                                "duration_s": 0.2,
                                "speed": 5,
                                "slide": 0,
                                "beat": "3.2.2",
                            },
                        ],
                    },
                ],
            }
        }
    )
    assert arrangement.chords == [["Em", 0.0], ["D", 2.0]]
    assert arrangement.plucks[0][-1] == pytest.approx(4.625)


def test_pluck_duration_units():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "durations",
                "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
                "tracks": [
                    {
                        "name": "pluck",
                        "type": "pluck",
                        "events": [
                            {"note": 40, "duration_s": 0.5, "speed": 5, "slide": 0, "timestamp": 0.0},
                            {"note": 41, "duration_b": 0.5, "speed": 5, "slide": 0, "timestamp": 1.0},
                            {"note": 42, "duration": 0.5, "speed": 5, "slide": 0, "timestamp": 2.0},
                        ],
                    }
                ],
            }
        }
    )
    rows = arrangement.plucks
    assert rows[0][1] == pytest.approx(0.5)
    assert rows[1][1] == pytest.approx(0.25)
    assert rows[2][1] == pytest.approx(0.25)


def test_to_plan_pluck_only():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "pluck-only",
                "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
                "tracks": [
                    {
                        "name": "pluck",
                        "type": "pluck",
                        "events": [
                            {"note": 60, "duration_s": 0.5, "speed": 5, "slide": 0, "timestamp": 0.0},
                        ],
                    }
                ],
            }
        }
    )
    plucks, mutes = arrangement.to_plan()
    assert plucks == [[60, 0.5, 5.0, 0, 0.0]]
    assert mutes == []


def test_roundtrip_to_dict():
    arrangement = _example()
    again = SongArrangement.from_dict(arrangement.to_dict())
    assert again.name == arrangement.name
    assert len(again.plucks) == len(arrangement.plucks)
    assert len(again.chords) == len(arrangement.chords)
