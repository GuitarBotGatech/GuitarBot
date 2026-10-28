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


def _example() -> SongArrangement:
    return SongArrangement.from_dict(json.loads(EXAMPLE.read_text(encoding="utf-8")))


def test_from_json_loads_example_with_plucks():
    assert _example().plucks


def test_to_plan_from_example():
    plucks, _mutes = _example().to_plan()
    assert plucks


def test_to_plan_without_chords_returns_plucks_unchanged():
    payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    payload["song"]["meta"].pop("tempo_curve", None)
    payload["song"]["tracks"] = [
        t for t in payload["song"]["tracks"] if t.get("type") != "chord"
    ]
    doc = SongArrangement.from_dict(payload)
    plucks, mutes = doc.to_plan()
    assert plucks == doc.plucks
    assert mutes == []


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
    assert doc.plucks[0][2] == cfg["pluck"]["speed"]
    assert doc.plucks[0][3] == cfg["pluck"]["slide"]

    with_speed = copy.deepcopy(payload)
    with_speed["song"]["tracks"][0]["events"][0]["speed"] = 9
    with_speed["song"]["tracks"][0]["events"][0]["slide"] = 1
    doc2 = SongArrangement.from_dict(with_speed)
    assert doc2.plucks[0][2] == 9
    assert doc2.plucks[0][3] == 1
