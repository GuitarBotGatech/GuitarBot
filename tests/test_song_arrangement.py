"""Lean tests for Events JSON → planner rows."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notation.events import SongArrangement, beat_label_to_seconds


def _example_path() -> Path:
    return Path(__file__).resolve().parent.parent / "Docs" / "song-format" / "example.json"


def test_load_example():
    arrangement = SongArrangement.from_json_file(_example_path())
    assert arrangement.name == "MVP Example Song"
    assert arrangement.meta.bpm == pytest.approx(92.0)
    assert arrangement.plucks
    assert arrangement.chords


def test_event_rows_and_tempo_curve():
    arrangement = SongArrangement.from_json_file(_example_path())
    warped = arrangement.event_rows()
    raw = arrangement.event_rows(apply_meta_tempo_curve=False)
    assert warped["chords"][0] == ["Em", 0.0]
    assert warped["pluck"][0][0] == 52
    assert warped["pluck"][0][-1] > raw["pluck"][0][-1]


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
    rows = arrangement.event_rows()
    assert rows["chords"] == [["Em", 0.0], ["D", 2.0]]
    assert rows["pluck"][0][-1] == pytest.approx(4.625)


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
    rows = arrangement.event_rows(apply_meta_tempo_curve=False)["pluck"]
    assert rows[0][1] == pytest.approx(0.5)
    assert rows[1][1] == pytest.approx(0.25)
    assert rows[2][1] == pytest.approx(0.25)


def test_to_planner_rows_default_on_chord():
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
    chords, pluck = arrangement.to_planner_rows()
    assert pluck
    assert chords[0][0] == "On"


def test_roundtrip_to_dict():
    arrangement = SongArrangement.from_json_path(_example_path())
    again = SongArrangement.from_dict(arrangement.to_dict())
    assert again.name == arrangement.name
    assert len(again.plucks) == len(arrangement.plucks)
    assert len(again.chords) == len(arrangement.chords)
