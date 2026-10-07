"""Events conversion: UI JSON → SongArrangement → planner rows."""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notation.events import SongArrangement, load_config

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "Docs" / "song-format" / "example.json"


def test_from_json_loads_example_with_plucks():
    doc = SongArrangement.from_json_path(EXAMPLE)
    assert doc.plucks


def test_to_planner_rows_from_example():
    chords, pluck = SongArrangement.from_json_path(EXAMPLE).to_planner_rows()
    assert pluck
    assert chords


def test_to_planner_rows_defaults_on_chord_when_missing():
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["song"]["tracks"] = [
        t for t in payload["song"]["tracks"] if t.get("type") != "chord"
    ]
    chords, pluck = SongArrangement.from_dict(payload).to_planner_rows()
    assert pluck
    assert chords
    assert chords[0][0] == "On"


def test_legacy_midi_tracks_are_skipped_on_load():
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["song"]["tracks"].append(
        {
            "name": "midi_fx",
            "type": "midi",
            "events": [{"address": "/cc", "args": [7, 30], "timestamp": 0.0}],
        }
    )
    doc = SongArrangement.from_dict(payload)
    assert doc.plucks
    assert doc.chords


def test_from_dict_fills_missing_pluck_speed_slide():
    payload = {
        "song": {
            "name": "defaults",
            "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
            "tracks": [
                {
                    "name": "p",
                    "type": "pluck",
                    "events": [
                        {"note": 60, "duration_s": 0.5, "timestamp": 0.0},
                    ],
                }
            ],
        }
    }
    cfg = load_config()
    doc = SongArrangement.from_dict(payload)
    assert doc.plucks[0].speed == cfg["pluck"]["speed"]
    assert doc.plucks[0].slide == cfg["pluck"]["slide"]

    with_speed = copy.deepcopy(payload)
    with_speed["song"]["tracks"][0]["events"][0]["speed"] = 9
    with_speed["song"]["tracks"][0]["events"][0]["slide"] = 1
    doc2 = SongArrangement.from_dict(with_speed)
    assert doc2.plucks[0].speed == 9
    assert doc2.plucks[0].slide == 1
