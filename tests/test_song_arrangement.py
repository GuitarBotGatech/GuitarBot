"""Tests for JSON song arrangement MVP."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import pytest

# Allow running from the GuitarBot repo root directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parsing.song_arrangement import SongArrangement, SongMeta


def _example_path() -> Path:
    return Path(__file__).resolve().parent.parent / "Docs" / "song-format" / "example.json"


def test_load_example_song_arrangement():
    arrangement = SongArrangement.from_json_file(_example_path())

    assert arrangement.name == "MVP Example Song"
    assert arrangement.meta.bpm == pytest.approx(92.0)
    assert arrangement.meta.key == "E minor"
    assert arrangement.meta.tempo_curve is not None
    assert len(arrangement.meta.tempo_curve) == 3
    assert len(arrangement.tracks) == 3


def test_render_osc_payloads_contains_expected_addresses_and_shapes():
    arrangement = SongArrangement.from_json_file(_example_path())
    payloads = arrangement.render_osc_payloads()
    raw_payloads = arrangement.render_osc_payloads(apply_meta_tempo_curve=False)

    assert set(payloads.keys()) == {"/Chords", "/Pluck", "/Midi"}
    assert payloads["/Chords"][0] == ["Em", 0.0]

    first_pluck = payloads["/Pluck"][0]
    assert first_pluck[0] == 52
    assert first_pluck[-1] != pytest.approx(raw_payloads["/Pluck"][0][-1])
    assert first_pluck[-1] > raw_payloads["/Pluck"][0][-1]

    first_midi = payloads["/Midi"][0]
    assert first_midi[0] == "/cc"
    assert first_midi[-1] == pytest.approx(0.0)


def test_meta_tempo_curve_is_applied_by_default_and_can_be_disabled():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "meta-curve",
                "meta": {
                    "key": "C",
                    "time_signature": "4/4",
                    "bpm": 120,
                    "tempo_curve": [
                        {"time": 0.0, "bpm": 120},
                        {"time": 4.0, "bpm": 60},
                    ],
                },
                "tracks": [
                    {
                        "name": "midi",
                        "type": "midi",
                        "events": [
                            {"address": "/cc", "args": [7, 64], "timestamp": 2.0},
                        ],
                    }
                ],
            }
        }
    )

    warped = arrangement.render_osc_payloads()
    raw = arrangement.render_osc_payloads(apply_meta_tempo_curve=False)

    assert warped["/Midi"][0][-1] > raw["/Midi"][0][-1]


def test_roundtrip_dict_stability():
    src = json.loads(_example_path().read_text(encoding="utf-8"))
    assert "beat" in src["song"]["tracks"][0]["events"][0]

    arrangement = SongArrangement.from_dict(src)
    output = arrangement.to_dict()
    reparsed = SongArrangement.from_dict(output)

    assert reparsed.to_dict() == output


def test_from_json_path_and_to_json_path_roundtrip(tmp_path: Path):
    arrangement = SongArrangement.from_json_path(_example_path())
    out_path = tmp_path / "roundtrip_song.json"
    arrangement.to_json_path(out_path)

    loaded = SongArrangement.from_json_path(out_path)
    assert loaded.to_dict() == arrangement.to_dict()


def test_to_json_str_is_deterministic():
    arrangement = SongArrangement.from_json_path(_example_path())
    first = arrangement.to_json_str()
    second = arrangement.to_json_str()
    assert first == second


def test_validation_error_includes_track_and_event_index():
    bad = {
        "song": {
            "name": "bad",
            "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
            "tracks": [
                {
                    "name": "pluck_main",
                    "type": "pluck",
                    "events": [
                        {"note": 52, "duration_s": 0.2, "speed": 5, "slide": 0, "timestamp": 0.0},
                        {"note": 55, "duration_s": 0.2, "speed": 5, "slide": 2, "timestamp": 1.0},
                    ],
                }
            ],
        }
    }

    with pytest.raises(ValueError) as exc:
        SongArrangement.from_dict(bad)

    message = str(exc.value)
    assert "pluck_main" in message
    assert "index 1" in message


def test_shift_time_returns_shifted_copy():
    arrangement = SongArrangement.from_json_path(_example_path())
    shifted = arrangement.shift_time(1.5)

    original_payloads = arrangement.render_osc_payloads(apply_meta_tempo_curve=False)
    shifted_payloads = shifted.render_osc_payloads(apply_meta_tempo_curve=False)

    assert original_payloads["/Chords"][0][-1] == pytest.approx(0.0)
    assert shifted_payloads["/Chords"][0][-1] == pytest.approx(1.5)


def test_copy_range_and_paste_at():
    arrangement = SongArrangement.from_json_path(_example_path())
    clip = arrangement.copy_range(0.0, 2.0)
    pasted = arrangement.paste_at(clip, 8.0)

    original_count = len(arrangement.render_osc_payloads()["/Pluck"])
    clip_count = len(clip.render_osc_payloads()["/Pluck"])
    pasted_count = len(pasted.render_osc_payloads()["/Pluck"])

    assert clip_count > 0
    assert pasted_count == original_count + clip_count
    assert pasted.render_osc_payloads()["/Pluck"][-1][-1] >= 8.0


def test_beat_label_examples_match_expected_seconds():
    meta = SongMeta(key="C", time_signature="4/4", bpm=120)

    assert meta.beat_label_to_seconds("1.1") == pytest.approx(0.0)
    assert meta.beat_label_to_seconds("2.1") == pytest.approx(2.0)
    assert meta.beat_label_to_seconds("3.2.1") == pytest.approx(4.5)
    assert meta.beat_label_to_seconds("3.2") == pytest.approx(4.5)
    assert meta.beat_label_to_seconds("3.2.2") == pytest.approx(4.625)


def test_events_can_use_beat_labels_instead_of_timestamp():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "beat-labeled",
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
                            {"note": 52, "duration_s": 0.2, "speed": 5, "slide": 0, "beat": "3.2.2"},
                        ],
                    },
                    {
                        "name": "midi",
                        "type": "midi",
                        "events": [
                            {"address": "/cc", "args": [7, 90], "interp": 0, "beat": "3.2"},
                        ],
                    },
                ],
            }
        }
    )

    payloads = arrangement.render_osc_payloads()
    assert payloads["/Chords"] == [["Em", 0.0], ["D", 2.0]]
    assert payloads["/Pluck"][0][-1] == pytest.approx(4.625)
    assert payloads["/Midi"][0][-1] == pytest.approx(4.5)


def test_reverse_range_mirrors_event_times_inside_region():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "reverse-test",
                "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
                "tracks": [
                    {
                        "name": "chords",
                        "type": "chord",
                        "events": [
                            {"chord": "A", "timestamp": 0.0},
                            {"chord": "B", "timestamp": 1.0},
                            {"chord": "C", "timestamp": 2.0},
                            {"chord": "D", "timestamp": 3.0},
                        ],
                    }
                ],
            }
        }
    )

    reversed_arr = arrangement.reverse_range(1.0, 3.0)
    times = [row[-1] for row in reversed_arr.render_osc_payloads()["/Chords"]]
    assert times == pytest.approx([0.0, 1.0, 2.0, 3.0])

    chords = [row[0] for row in reversed_arr.render_osc_payloads()["/Chords"]]
    assert chords == ["A", "D", "C", "B"]


def test_quantize_snaps_to_beat_grid():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "quantize-test",
                "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
                "tracks": [
                    {
                        "name": "midi",
                        "type": "midi",
                        "events": [
                            {"address": "/cc", "args": [7, 10], "timestamp": 0.13},
                            {"address": "/cc", "args": [7, 20], "timestamp": 0.37},
                        ],
                    }
                ],
            }
        }
    )

    quantized = arrangement.quantize(subdivisions_per_beat=4)
    times = [row[-1] for row in quantized.render_osc_payloads()["/Midi"]]
    assert times == pytest.approx([0.125, 0.375])


def test_scale_tempo_updates_meta_and_time_axis():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "tempo-scale",
                "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
                "tracks": [
                    {
                        "name": "pluck",
                        "type": "pluck",
                        "events": [
                            {"note": 52, "duration_s": 0.4, "speed": 5, "slide": 0, "timestamp": 1.0},
                        ],
                    }
                ],
            }
        }
    )

    slowed = arrangement.scale_tempo(60)
    assert slowed.meta.bpm == pytest.approx(60.0)

    event = slowed.tracks[0].events[0]
    assert event.timestamp == pytest.approx(2.0)
    assert event.duration == pytest.approx(0.8)


def test_reverse_range_with_mirror_end_policy_for_pluck():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "reverse-duration",
                "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
                "tracks": [
                    {
                        "name": "pluck",
                        "type": "pluck",
                        "events": [
                            {"note": 52, "duration_s": 0.5, "speed": 5, "slide": 0, "timestamp": 1.0},
                        ],
                    }
                ],
            }
        }
    )

    mirrored = arrangement.reverse_range(0.0, 4.0, duration_policy="mirror_end")
    t = mirrored.render_osc_payloads()["/Pluck"][0][-1]
    assert t == pytest.approx(2.5)


def test_quantize_supports_strength_and_swing():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "quantize-swing",
                "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
                "tracks": [
                    {
                        "name": "midi",
                        "type": "midi",
                        "events": [
                            {"address": "/cc", "args": [7, 10], "timestamp": 0.13},
                            {"address": "/cc", "args": [7, 20], "timestamp": 0.37},
                        ],
                    }
                ],
            }
        }
    )

    partial = arrangement.quantize(subdivisions_per_beat=4, strength=0.5, swing=0.0)
    partial_times = [row[-1] for row in partial.render_osc_payloads()["/Midi"]]
    assert partial_times[0] == pytest.approx(0.1275)
    assert partial_times[1] == pytest.approx(0.3725)

    swung = arrangement.quantize(subdivisions_per_beat=4, strength=1.0, swing=1.0)
    swung_times = [row[-1] for row in swung.render_osc_payloads()["/Midi"]]
    assert swung_times[0] == pytest.approx(0.1875)
    assert swung_times[1] == pytest.approx(0.4375)


def test_scale_tempo_curve_supports_rubato_and_duration_warp():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "rubato",
                "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
                "tracks": [
                    {
                        "name": "pluck",
                        "type": "pluck",
                        "events": [
                            {"note": 52, "duration_s": 0.4, "speed": 5, "slide": 0, "timestamp": 1.0},
                        ],
                    },
                    {
                        "name": "midi",
                        "type": "midi",
                        "events": [
                            {"address": "/cc", "args": [7, 64], "timestamp": 2.0},
                        ],
                    },
                ],
            }
        }
    )

    # 120 -> 60 BPM from t=0..4 stretches timeline progressively.
    warped = arrangement.scale_tempo_curve([(0.0, 120.0), (4.0, 60.0)])
    payloads = warped.render_osc_payloads()

    warped_pluck = payloads["/Pluck"][0]
    warped_midi = payloads["/Midi"][0]

    # Event should move later than original under slowdown curve.
    assert warped_pluck[-1] > 1.0
    assert warped_midi[-1] > 2.0

    # Pluck duration should be warped too (not kept fixed at 0.4).
    pluck_duration = warped_pluck[1]
    assert pluck_duration != pytest.approx(0.4)
    assert pluck_duration > 0


def test_scale_tempo_curve_constant_bpm_matches_uniform_scaling():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "rubato-constant",
                "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
                "tracks": [
                    {
                        "name": "pluck",
                        "type": "pluck",
                        "events": [
                            {"note": 52, "duration_s": 0.5, "speed": 5, "slide": 0, "timestamp": 2.0},
                        ],
                    },
                    {
                        "name": "midi",
                        "type": "midi",
                        "events": [
                            {"address": "/cc", "args": [7, 64], "timestamp": 1.0},
                        ],
                    },
                ],
            }
        }
    )

    # Flat 60 BPM curve from a 120 BPM base should stretch time by exactly 2x.
    warped = arrangement.scale_tempo_curve([(0.0, 60.0), (8.0, 60.0)])
    payloads = warped.render_osc_payloads(apply_meta_tempo_curve=False)

    assert payloads["/Midi"][0][-1] == pytest.approx(2.0)
    assert payloads["/Pluck"][0][-1] == pytest.approx(4.0)
    assert payloads["/Pluck"][0][1] == pytest.approx(1.0)


def test_scale_tempo_curve_linear_segment_matches_analytic_solution():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "rubato-analytic",
                "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
                "tracks": [
                    {
                        "name": "midi",
                        "type": "midi",
                        "events": [
                            {"address": "/cc", "args": [7, 64], "timestamp": 2.0},
                        ],
                    }
                ],
            }
        }
    )

    # Linear BPM ramp: 120 -> 60 over 4 s. At t=2, bpm=90.
    warped = arrangement.scale_tempo_curve([(0.0, 120.0), (4.0, 60.0)])
    got_t = warped.render_osc_payloads(apply_meta_tempo_curve=False)["/Midi"][0][-1]

    # Closed-form integral used by the implementation:
    # warped(t) = base_bpm / slope * ln((bpm0 + slope*t)/bpm0)
    slope = (60.0 - 120.0) / 4.0
    expected_t = 120.0 / slope * math.log((120.0 + slope * 2.0) / 120.0)
    assert got_t == pytest.approx(expected_t)


def test_pluck_duration_units_explicit_and_legacy_default_beats():
    arrangement = SongArrangement.from_dict(
        {
            "song": {
                "name": "duration-units",
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

    rows = arrangement.render_osc_payloads(apply_meta_tempo_curve=False)["/Pluck"]
    assert rows[0][1] == pytest.approx(0.5)
    assert rows[1][1] == pytest.approx(0.25)
    assert rows[2][1] == pytest.approx(0.25)


def test_pluck_duration_rejects_multiple_duration_fields():
    with pytest.raises(ValueError, match="only one duration field"):
        SongArrangement.from_dict(
            {
                "song": {
                    "name": "duration-ambiguous",
                    "meta": {"key": "C", "time_signature": "4/4", "bpm": 120},
                    "tracks": [
                        {
                            "name": "pluck",
                            "type": "pluck",
                            "events": [
                                {
                                    "note": 40,
                                    "duration_s": 0.3,
                                    "duration_b": 0.5,
                                    "speed": 5,
                                    "slide": 0,
                                    "timestamp": 0.0,
                                }
                            ],
                        }
                    ],
                }
            }
        )
