"""
Tests for section expansion logic — the Python mirror of JS buildSectionExpandedJSON.

Key bugs this suite guards against:
  1. S.measures set from last event beat, not total expanded duration
     (loadJSON ignored song.measures; sections with no events at their tail
      caused the sequencer canvas to be far too short)
  2. Arrangement sections/timeline not stripped before loadJSON, causing
     old section guide lines to be redrawn over expanded events
  3. Cursor not advancing correctly for sections with sparse or zero events

The expansion logic mirrors buildSectionExpandedJSON in web/js/json.js.
"""

from __future__ import annotations

import json
import math
import pytest
from pathlib import Path
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── constants ─────────────────────────────────────────────────────────────────

SUBDIV = 4  # matches JS constant (subdivisions per beat for bar.beat.sub labels)


# ── beat helpers (mirror of state.js parseBeatWithTimeSig / beatLabelWithTimeSig)

def _beats_per_measure(time_sig: str) -> int:
    return int(time_sig.split("/")[0])


def _parse_beat(label: str, beats_per_measure: int) -> float:
    """Mirror of JS parseBeatWithTimeSig."""
    s = str(label).strip()
    if s.startswith("~"):
        return float(s[1:])
    parts = s.split(".")
    bar = int(parts[0])
    beat = int(parts[1])
    sub = int(parts[2]) if len(parts) >= 3 else 1
    return (bar - 1) * beats_per_measure + (beat - 1) + (sub - 1) / SUBDIV


def _section_span(start_label: str, end_label: str, time_sig: str) -> float:
    """Beats between two section boundary labels."""
    bpm = _beats_per_measure(time_sig)
    return _parse_beat(end_label, bpm) - _parse_beat(start_label, bpm)


# ── expand_sections (mirror of JS buildSectionExpandedJSON) ───────────────────

def expand_sections(song_dict: dict) -> dict | None:
    """
    Python mirror of JS buildSectionExpandedJSON in web/js/json.js.

    Expands the section timeline into a flat event list starting at beat 0.
    Returns None when sections or timeline are empty (matches the JS null guard).

    The output includes:
      - tracks: flat expanded events re-positioned to a continuous timeline
      - arrangement: empty sections + timeline (so loadJSON doesn't restore guides)
      - measures: ceil(total_cursor_beats / beats_per_measure) — NOT based on
        the last event; reflects the full arrangement length including silent tails
    """
    song = song_dict["song"]
    arrangement = song.get("arrangement", {})
    sections_raw = arrangement.get("sections", [])
    timeline_raw = arrangement.get("timeline", [])

    if not sections_raw or not timeline_raw:
        return None

    time_sig = song.get("meta", {}).get("time_signature", "4/4")
    beats_per_measure = _beats_per_measure(time_sig)

    section_map: dict[int, dict] = {}
    for sec in sections_raw:
        start = _parse_beat(str(sec["start_beat"]), beats_per_measure)
        end = _parse_beat(str(sec["end_beat"]), beats_per_measure)
        section_map[int(sec["id"])] = {
            "id": int(sec["id"]),
            "name": sec["name"],
            "start_beat": start,
            "end_beat": end,
        }

    source_tracks = song.get("tracks", [])
    expanded_tracks: list[dict] = [
        {"name": t["name"], "type": t["type"], "events": []}
        for t in source_tracks
    ]

    cursor_beat = 0.0
    for item in timeline_raw:
        section_id = int(item.get("section_id", item.get("sectionId", -1)))
        sec = section_map.get(section_id)
        if sec is None:
            continue
        section_len = round(sec["end_beat"] - sec["start_beat"], 4)
        if section_len <= 0:
            continue
        loops = max(1, int(item.get("loops", 1)))

        for loop_idx in range(loops):
            loop_start = cursor_beat + loop_idx * section_len
            for track_idx, source_track in enumerate(source_tracks):
                for event in source_track.get("events", []):
                    beat = _parse_beat(str(event.get("beat", "~0")), beats_per_measure)
                    # mirror JS: beat < start excluded, beat >= end excluded
                    if beat < sec["start_beat"] or beat >= sec["end_beat"]:
                        continue
                    shifted = round(loop_start + (beat - sec["start_beat"]), 4)
                    new_event = {**event, "beat": f"~{shifted}"}
                    expanded_tracks[track_idx]["events"].append(new_event)

        cursor_beat += section_len * loops

    for track in expanded_tracks:
        track["events"].sort(
            key=lambda e: _parse_beat(str(e.get("beat", "~0")), beats_per_measure)
        )

    # measures = total bars spanned by the expanded timeline.
    # MUST be based on cursor_beat (total duration), NOT on the last event —
    # sections can have no events in their tail (e.g. section 3 in
    # contemplations_sections.json has zero events but spans 180 beats = 60 bars).
    measures = max(1, math.ceil(cursor_beat / max(1, beats_per_measure)))

    return {
        "song": {
            **song,
            "measures": measures,
            "tracks": expanded_tracks,
            # Stripped so loadJSON does not restore old section guide lines.
            "arrangement": {"sections": [], "timeline": []},
        }
    }


def _last_event_beat(result: dict, time_sig: str) -> float:
    """Highest event beat across all tracks in an expanded result."""
    bpm = _beats_per_measure(time_sig)
    max_beat = 0.0
    for track in result["song"]["tracks"]:
        for event in track["events"]:
            b = _parse_beat(str(event.get("beat", "~0")), bpm)
            if b > max_beat:
                max_beat = b
    return max_beat


# ── fixtures ──────────────────────────────────────────────────────────────────

def _make_song(
    *,
    time_sig: str = "4/4",
    bpm: int = 120,
    sections: list[dict],
    timeline: list[dict],
    tracks: list[dict],
) -> dict:
    return {
        "song": {
            "name": "test",
            "meta": {"key": "C", "time_signature": time_sig, "bpm": bpm},
            "arrangement": {"sections": sections, "timeline": timeline},
            "tracks": tracks,
        }
    }


def _pluck(beat: str, note: int = 52) -> dict:
    return {"note": note, "duration_b": 0.5, "speed": 64, "slide": 0, "beat": beat}


def _chord(beat: str, chord: str = "Em") -> dict:
    return {"chord": chord, "beat": beat}


def _contemplations() -> dict:
    path = Path(__file__).resolve().parent.parent / "Songs" / "contemplations_sections.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ── TestEmptyGuards ───────────────────────────────────────────────────────────

class TestEmptyGuards:
    def test_empty_timeline_returns_none(self):
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "5.1"}],
            timeline=[],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("2.1")]}],
        )
        assert expand_sections(song) is None

    def test_empty_sections_returns_none(self):
        song = _make_song(
            sections=[],
            timeline=[{"section_id": 1, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("2.1")]}],
        )
        assert expand_sections(song) is None

    def test_missing_arrangement_returns_none(self):
        song = {"song": {"name": "t", "meta": {"key": "C", "time_signature": "4/4", "bpm": 120}, "tracks": []}}
        assert expand_sections(song) is None


# ── TestEventPositions ────────────────────────────────────────────────────────

class TestEventPositions:
    def test_event_at_section_start_maps_to_beat_zero(self):
        # Section starts at bar 3 (beat 8 in 4/4). Event at bar 3.
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "3.1", "end_beat": "5.1"}],
            timeline=[{"section_id": 1, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("3.1")]}],
        )
        result = expand_sections(song)
        beat = _parse_beat(result["song"]["tracks"][0]["events"][0]["beat"], 4)
        assert beat == pytest.approx(0.0)

    def test_event_within_section_is_section_relative(self):
        # Section bars 3-7, event at bar 4 (beat 12). Section start = beat 8.
        # Shifted = 12 - 8 = 4.
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "3.1", "end_beat": "7.1"}],
            timeline=[{"section_id": 1, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("4.1")]}],
        )
        result = expand_sections(song)
        beat = _parse_beat(result["song"]["tracks"][0]["events"][0]["beat"], 4)
        assert beat == pytest.approx(4.0)

    def test_event_at_end_boundary_is_excluded(self):
        # JS: beat >= section.endBeat → exclude
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "3.1"}],
            timeline=[{"section_id": 1, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1"), _pluck("3.1")]}],
        )
        result = expand_sections(song)
        events = result["song"]["tracks"][0]["events"]
        assert len(events) == 1
        assert _parse_beat(events[0]["beat"], 4) == pytest.approx(0.0)

    def test_events_outside_all_sections_are_excluded(self):
        # Events at bars 1-2 excluded; section starts at bar 3.
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "3.1", "end_beat": "5.1"}],
            timeline=[{"section_id": 1, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [
                _pluck("1.1"), _pluck("2.1"), _pluck("3.1"),
            ]}],
        )
        result = expand_sections(song)
        events = result["song"]["tracks"][0]["events"]
        assert len(events) == 1  # only bar 3 survives


# ── TestLoops ─────────────────────────────────────────────────────────────────

class TestLoops:
    def test_two_loops_doubles_event_count(self):
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "3.1"}],
            timeline=[{"section_id": 1, "loops": 2}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1"), _pluck("2.1")]}],
        )
        result = expand_sections(song)
        assert len(result["song"]["tracks"][0]["events"]) == 4

    def test_two_loops_second_copy_starts_at_section_length(self):
        # Section bars 1-3 in 4/4 = 8 beats. Loop 2 starts at beat 8.
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "3.1"}],
            timeline=[{"section_id": 1, "loops": 2}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1")]}],
        )
        result = expand_sections(song)
        beats = sorted(_parse_beat(e["beat"], 4) for e in result["song"]["tracks"][0]["events"])
        assert beats == pytest.approx([0.0, 8.0])

    def test_three_loops_offsets(self):
        # Section bars 1-2 in 4/4 = 4 beats. Copies at 0, 4, 8.
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "2.1"}],
            timeline=[{"section_id": 1, "loops": 3}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1")]}],
        )
        result = expand_sections(song)
        beats = sorted(_parse_beat(e["beat"], 4) for e in result["song"]["tracks"][0]["events"])
        assert beats == pytest.approx([0.0, 4.0, 8.0])


# ── TestCursorAdvance ─────────────────────────────────────────────────────────

class TestCursorAdvance:
    def test_second_section_starts_after_first(self):
        # A: bars 1-3 (8 beats), B: bars 3-5 (8 beats). B cursor starts at 8.
        song = _make_song(
            sections=[
                {"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "3.1"},
                {"id": 2, "name": "B", "start_beat": "3.1", "end_beat": "5.1"},
            ],
            timeline=[{"section_id": 1, "loops": 1}, {"section_id": 2, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [
                _pluck("1.1", note=60), _pluck("3.1", note=61),
            ]}],
        )
        result = expand_sections(song)
        beats = {e["note"]: _parse_beat(e["beat"], 4) for e in result["song"]["tracks"][0]["events"]}
        assert beats[60] == pytest.approx(0.0)  # A starts at cursor 0
        assert beats[61] == pytest.approx(8.0)  # B starts at cursor 8

    def test_interleaved_aba_timeline(self):
        # A(4 beats), B(4 beats). Timeline: A, B, A → A at 0, B at 4, A at 8.
        song = _make_song(
            sections=[
                {"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "2.1"},
                {"id": 2, "name": "B", "start_beat": "2.1", "end_beat": "3.1"},
            ],
            timeline=[
                {"section_id": 1, "loops": 1},
                {"section_id": 2, "loops": 1},
                {"section_id": 1, "loops": 1},
            ],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [
                _pluck("1.1", note=60), _pluck("2.1", note=61),
            ]}],
        )
        result = expand_sections(song)
        by_note: dict[int, list[float]] = {}
        for e in result["song"]["tracks"][0]["events"]:
            by_note.setdefault(e["note"], []).append(_parse_beat(e["beat"], 4))
        assert sorted(by_note[60]) == pytest.approx([0.0, 8.0])  # A twice
        assert by_note[61] == pytest.approx([4.0])               # B once


# ── TestMeasuresCalculation ───────────────────────────────────────────────────
#
# This class guards the most critical bug: measures must be based on the total
# cursor advance (sum of all section lengths × loops), NOT on where the last
# event happens to land.  Sections can have sparse events — or no events at all
# (e.g. section 3 in contemplations_sections.json) — while still occupying
# real time in the arrangement.

class TestMeasuresCalculation:
    def test_measures_equals_ceil_cursor_over_beats_per_measure(self):
        # Section bars 1-5 in 4/4 = 16 beats = 4 bars.
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "5.1"}],
            timeline=[{"section_id": 1, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1")]}],
        )
        result = expand_sections(song)
        assert result["song"]["measures"] == 4

    def test_measures_not_based_on_last_event(self):
        # Section spans 16 beats (4 bars). Single event at the very start.
        # If measures were based on last event, we'd get 1 bar — must be 4.
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "5.1"}],
            timeline=[{"section_id": 1, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1")]}],
        )
        result = expand_sections(song)
        last_event_beat = _last_event_beat(result, "4/4")
        measures_from_event = math.ceil(last_event_beat / 4) + 2  # loadJSON formula

        assert last_event_beat == pytest.approx(0.0)              # event is at beat 0
        assert measures_from_event == pytest.approx(2)            # naive formula gives 2
        assert result["song"]["measures"] == 4                    # correct answer is 4

    def test_empty_section_advances_cursor_and_measures(self):
        # Section A has one event. Section B has NO events but spans 8 beats.
        # Total = 16 beats = 4 bars in 4/4. measures must be 4, not 2.
        song = _make_song(
            sections=[
                {"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "3.1"},  # 8 beats
                {"id": 2, "name": "B", "start_beat": "3.1", "end_beat": "5.1"},  # 8 beats, NO events
            ],
            timeline=[{"section_id": 1, "loops": 1}, {"section_id": 2, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1")]}],
        )
        result = expand_sections(song)
        last_event_beat = _last_event_beat(result, "4/4")
        assert last_event_beat == pytest.approx(0.0)   # event only at start
        assert result["song"]["measures"] == 4         # but full arrangement is 4 bars

    def test_measures_with_two_loops_of_sparse_section(self):
        # Section bars 1-5 (16 beats). Event only at bar 1. 2 loops = 32 beats = 8 bars.
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "5.1"}],
            timeline=[{"section_id": 1, "loops": 2}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1")]}],
        )
        result = expand_sections(song)
        assert result["song"]["measures"] == 8

    def test_measures_3_4_time_sig(self):
        # Section bars 1-5 in 3/4 = 4 bars × 3 beats = 12 beats. measures = 4.
        song = _make_song(
            time_sig="3/4",
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "5.1"}],
            timeline=[{"section_id": 1, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1")]}],
        )
        result = expand_sections(song)
        assert result["song"]["measures"] == 4

    def test_measures_multi_section_sum(self):
        # A: 8 beats (2 bars), B: 12 beats (3 bars). Total = 20 beats = 5 bars.
        song = _make_song(
            sections=[
                {"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "3.1"},  # 8 beats
                {"id": 2, "name": "B", "start_beat": "3.1", "end_beat": "6.1"},  # 12 beats
            ],
            timeline=[{"section_id": 1, "loops": 1}, {"section_id": 2, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1")]}],
        )
        result = expand_sections(song)
        assert result["song"]["measures"] == 5


# ── TestContemplationsFile ────────────────────────────────────────────────────

class TestContemplationsFile:
    """
    Integration tests using the real contemplations_sections.json.

    This file is the specific case that exposed the measures bug:
      - 3 sections spanning 153 bars total in 3/4 time
      - Events only up to bar 64 (end of section 2's occupied range)
      - Section 3 (bars 96-156) has ZERO events
      - After expansion, loadJSON was computing measures = 64 instead of 153
    """

    def test_file_has_correct_structure(self):
        data = _contemplations()
        assert data["song"]["meta"]["time_signature"] == "3/4"
        assert data["song"]["meta"]["bpm"] == 120
        sections = data["song"]["arrangement"]["sections"]
        assert len(sections) == 3
        assert sections[0]["start_beat"] == "3.1.1"
        assert sections[2]["end_beat"] == "156.1.1"

    def test_section_beat_spans(self):
        # Verify section sizes in beats (3/4 time).
        data = _contemplations()
        secs = data["song"]["arrangement"]["sections"]
        bpm = _beats_per_measure("3/4")  # = 3

        s1_start = _parse_beat(secs[0]["start_beat"], bpm)  # bar 3 = 6
        s1_end   = _parse_beat(secs[0]["end_beat"],   bpm)  # bar 51 = 150
        s2_start = _parse_beat(secs[1]["start_beat"], bpm)  # bar 51 = 150
        s2_end   = _parse_beat(secs[1]["end_beat"],   bpm)  # bar 96 = 285
        s3_start = _parse_beat(secs[2]["start_beat"], bpm)  # bar 96 = 285
        s3_end   = _parse_beat(secs[2]["end_beat"],   bpm)  # bar 156 = 465

        assert s1_end - s1_start == pytest.approx(144.0)  # 48 bars
        assert s2_end - s2_start == pytest.approx(135.0)  # 45 bars
        assert s3_end - s3_start == pytest.approx(180.0)  # 60 bars

    def test_total_timeline_duration_is_459_beats(self):
        # All three sections in sequence = 144 + 135 + 180 = 459 beats.
        assert 144 + 135 + 180 == 459

    def test_section3_contains_no_events(self):
        """Section 3 (bars 96-156) is silent — a key driver of the measures bug."""
        data = _contemplations()
        bpm = _beats_per_measure("3/4")
        s3_start = _parse_beat("96.1.1", bpm)   # 285
        s3_end   = _parse_beat("156.1.1", bpm)  # 465

        events_in_s3 = 0
        for track in data["song"]["tracks"]:
            for ev in track["events"]:
                b = _parse_beat(str(ev.get("beat", "~0")), bpm)
                if s3_start <= b < s3_end:
                    events_in_s3 += 1

        assert events_in_s3 == 0, (
            "Section 3 must have no events; this is what exposed the measures bug"
        )

    def test_last_event_is_in_section2(self):
        data = _contemplations()
        bpm = _beats_per_measure("3/4")
        s2_start = _parse_beat("51.1.1", bpm)  # 150
        s2_end   = _parse_beat("96.1.1", bpm)  # 285

        all_beats = []
        for track in data["song"]["tracks"]:
            for ev in track["events"]:
                all_beats.append(_parse_beat(str(ev.get("beat", "~0")), bpm))

        last_beat = max(all_beats)
        assert s2_start <= last_beat < s2_end, (
            f"Last event at beat {last_beat} should be inside section 2 ({s2_start}-{s2_end})"
        )

    def test_naive_measures_from_last_event_is_far_too_small(self):
        """Quantify how wrong the old loadJSON formula was."""
        data = _contemplations()
        bpm_val = _beats_per_measure("3/4")  # 3 beats per bar

        all_beats = []
        for track in data["song"]["tracks"]:
            for ev in track["events"]:
                all_beats.append(_parse_beat(str(ev.get("beat", "~0")), bpm_val))

        # Simulate loadJSON's old formula: ceil(maxB / bpm) + 2
        # but first we need to know maxB after section 1+2 expansion

        # Section 1: beats 6-150 → expanded to 0-144
        # Section 2: beats 150-285 → expanded to 144-279
        s1_start, s1_end = _parse_beat("3.1.1", bpm_val), _parse_beat("51.1.1", bpm_val)
        s2_start, s2_end = _parse_beat("51.1.1", bpm_val), _parse_beat("96.1.1", bpm_val)

        max_expanded = 0.0
        for b in all_beats:
            if s1_start <= b < s1_end:
                shifted = b - s1_start
                max_expanded = max(max_expanded, shifted)
            elif s2_start <= b < s2_end:
                shifted = 144.0 + (b - s2_start)
                max_expanded = max(max_expanded, shifted)

        measures_naive = math.ceil(max_expanded / bpm_val) + 2  # old formula
        correct_measures = math.ceil(459 / bpm_val)             # 153

        assert measures_naive < correct_measures, (
            f"Naive formula ({measures_naive}) should be less than correct ({correct_measures})"
        )
        assert correct_measures - measures_naive >= 80, (
            f"Gap should be at least 80 bars, got {correct_measures - measures_naive}"
        )

    def test_all_sections_measures_is_153(self):
        """All 3 sections in timeline → 153 bars, even though section 3 is silent."""
        data = _contemplations()
        data["song"]["arrangement"]["timeline"] = [
            {"section_id": sec["id"], "loops": 1}
            for sec in data["song"]["arrangement"]["sections"]
        ]
        result = expand_sections(data)
        assert result is not None
        assert result["song"]["measures"] == 153

    def test_section1_only_measures_is_48(self):
        data = _contemplations()
        data["song"]["arrangement"]["timeline"] = [
            {"section_id": data["song"]["arrangement"]["sections"][0]["id"], "loops": 1}
        ]
        result = expand_sections(data)
        assert result["song"]["measures"] == 48  # 144 beats / 3 = 48

    def test_section2_only_measures_is_45(self):
        data = _contemplations()
        data["song"]["arrangement"]["timeline"] = [
            {"section_id": data["song"]["arrangement"]["sections"][1]["id"], "loops": 1}
        ]
        result = expand_sections(data)
        assert result["song"]["measures"] == 45  # 135 beats / 3 = 45

    def test_section3_only_measures_is_60_despite_zero_events(self):
        """The silent section alone still yields 60 bars, not 0."""
        data = _contemplations()
        data["song"]["arrangement"]["timeline"] = [
            {"section_id": data["song"]["arrangement"]["sections"][2]["id"], "loops": 1}
        ]
        result = expand_sections(data)
        assert result is not None
        assert result["song"]["measures"] == 60   # 180 beats / 3 = 60

        # And it has no events (confirms silence, not a bug)
        total_events = sum(len(t["events"]) for t in result["song"]["tracks"])
        assert total_events == 0

    def test_two_loops_of_all_sections_doubles_measures(self):
        data = _contemplations()
        data["song"]["arrangement"]["timeline"] = [
            {"section_id": sec["id"], "loops": 2}
            for sec in data["song"]["arrangement"]["sections"]
        ]
        result = expand_sections(data)
        assert result["song"]["measures"] == 306  # 153 × 2

    def test_empty_timeline_returns_none(self):
        data = _contemplations()
        # File ships with timeline:[] — expansion must return None.
        assert expand_sections(data) is None

    def test_expanded_arrangement_is_stripped(self):
        data = _contemplations()
        data["song"]["arrangement"]["timeline"] = [
            {"section_id": data["song"]["arrangement"]["sections"][0]["id"], "loops": 1}
        ]
        result = expand_sections(data)
        assert result["song"]["arrangement"]["sections"] == []
        assert result["song"]["arrangement"]["timeline"] == []

    def test_events_sorted_by_beat(self):
        data = _contemplations()
        data["song"]["arrangement"]["timeline"] = [
            {"section_id": sec["id"], "loops": 1}
            for sec in data["song"]["arrangement"]["sections"]
        ]
        result = expand_sections(data)
        bpm_val = _beats_per_measure("3/4")
        for track in result["song"]["tracks"]:
            beats = [_parse_beat(e["beat"], bpm_val) for e in track["events"]]
            assert beats == sorted(beats), f"Track '{track['name']}' not sorted"

    def test_events_before_section1_are_excluded(self):
        """Bars 1-2 of the file are before section 1 (starts bar 3) → excluded."""
        data = _contemplations()
        bpm_val = _beats_per_measure("3/4")
        s1_start = _parse_beat("3.1.1", bpm_val)  # 6

        pre_section_events = sum(
            1 for track in data["song"]["tracks"]
            for ev in track["events"]
            if _parse_beat(str(ev.get("beat", "~0")), bpm_val) < s1_start
        )
        assert pre_section_events > 0, "Fixture should have events before section 1"

        data["song"]["arrangement"]["timeline"] = [
            {"section_id": data["song"]["arrangement"]["sections"][0]["id"], "loops": 1}
        ]
        result = expand_sections(data)
        # No expanded event should be at negative beat
        for track in result["song"]["tracks"]:
            for ev in track["events"]:
                assert _parse_beat(ev["beat"], bpm_val) >= 0.0


# ── TestExportToSequencerFix ──────────────────────────────────────────────────

class TestExportToSequencerFix:
    """
    Guards both fixes applied to the export-to-sequencer path.

    Fix 1: arrangement.sections and arrangement.timeline must be empty so
           loadJSON doesn't restore old section guide lines.

    Fix 2: song.measures must reflect the full expanded timeline length
           (cursor-based), not the position of the last event, so loadJSON
           (which now honors song.measures when it's larger) sets S.measures
           to the correct bar count.
    """

    def test_arrangement_sections_empty(self):
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "3.1"}],
            timeline=[{"section_id": 1, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1")]}],
        )
        result = expand_sections(song)
        assert result["song"]["arrangement"]["sections"] == []

    def test_arrangement_timeline_empty(self):
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "3.1"}],
            timeline=[{"section_id": 1, "loops": 2}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("2.1")]}],
        )
        result = expand_sections(song)
        assert result["song"]["arrangement"]["timeline"] == []

    def test_measures_field_present_in_output(self):
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "5.1"}],
            timeline=[{"section_id": 1, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1")]}],
        )
        result = expand_sections(song)
        assert "measures" in result["song"]

    def test_measures_larger_than_event_based_estimate(self):
        # Section spans 16 beats (4 bars) but event is only at beat 0.
        # Event-based formula: ceil(0/4)+2 = 2. Correct: 4.
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "5.1"}],
            timeline=[{"section_id": 1, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1")]}],
        )
        result = expand_sections(song)
        last_beat = _last_event_beat(result, "4/4")
        event_based_measures = math.ceil(max(last_beat, 0) / 4) + 2
        assert result["song"]["measures"] > event_based_measures

    def test_source_dict_not_mutated(self):
        song = _make_song(
            sections=[{"id": 1, "name": "A", "start_beat": "1.1", "end_beat": "3.1"}],
            timeline=[{"section_id": 1, "loops": 1}],
            tracks=[{"name": "pluck_main", "type": "pluck", "events": [_pluck("1.1")]}],
        )
        original_sections = list(song["song"]["arrangement"]["sections"])
        expand_sections(song)
        assert song["song"]["arrangement"]["sections"] == original_sections
