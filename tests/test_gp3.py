"""Guitar Pro 3 tabs → SongArrangement pluck events."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notation.events import SongArrangement
from notation.gp3 import _lower_into_range, compile_gp3, playback_measure_indices
from tuning import tune as tu

ROOT = Path(__file__).resolve().parent.parent
SANDMAN = ROOT / "notation" / "Songs" / "enter-sandman-6-11600.gp3"
TOCCATA = ROOT / "notation" / "Songs" / "toccata-and-fugue-v2-1291.gp3"


def _header(*, open_=False, close=-1, alt=0):
    return SimpleNamespace(isRepeatOpen=open_, repeatClose=close, repeatAlternative=alt)


def test_hand_scale_stretches_a_fret_change_to_the_prep_window():
    from notation.gp3 import _Pluck, _hand_scale

    held = [
        _Pluck(midi=40, timestamp=0.0, duration_s=0.05, slide=0, preferred=0, string_index=0),
        _Pluck(midi=40, timestamp=0.05, duration_s=0.05, slide=0, preferred=0, string_index=0),
    ]
    assert _hand_scale(held) == 1.0

    changed = [
        _Pluck(midi=40, timestamp=0.0, duration_s=0.05, slide=0, preferred=0, string_index=0),
        _Pluck(midi=43, timestamp=0.1, duration_s=0.05, slide=0, preferred=0, string_index=0),
    ]
    assert _hand_scale(changed) == pytest.approx((tu.LH_PREP_TIME_BEFORE_PICK + 1e-4) / 0.1)


def test_high_notes_drop_by_octaves_until_a_string_can_play_them():
    top = max(high for _low, high in tu.STRING_MIDI_RANGES)
    assert _lower_into_range(top) == top
    assert _lower_into_range(top + 1) == top + 1 - 12
    assert _lower_into_range(81) == 69
    assert _lower_into_range(86) == 62
    assert _lower_into_range(40) == 40


def test_playback_without_repeats_is_the_written_order():
    headers = [_header(), _header(), _header()]
    assert playback_measure_indices(headers) == [0, 1, 2]


def test_repeat_close_plays_the_group_that_many_times():
    headers = [_header(open_=True), _header(), _header(close=3)]
    assert playback_measure_indices(headers) == [0, 1, 2, 0, 1, 2, 0, 1, 2]


def test_alternate_endings_play_on_their_pass():
    headers = [_header(open_=True), _header(close=2, alt=1), _header(alt=2)]
    assert playback_measure_indices(headers) == [0, 1, 0, 2]


def test_sandman_compiles_james_riff_into_plucks():
    pytest.importorskip("guitarpro")
    arrangement = SongArrangement.from_gp3(SANDMAN)
    assert arrangement.name == "Enter Sandman (James)"
    assert arrangement.time_signature == "4/4"
    assert arrangement.chords == []

    # Eighth-note pickup on the open low E, tied into the downbeat, then the riff.
    # Times are in beats so they stay put when the song slows to fit the hand.
    pickup, fifth, fourth = arrangement.plucks[:3]
    beat = lambda seconds: seconds * arrangement.bpm / 60.0
    assert pickup[0] == 40
    assert pickup[4] == 0
    assert beat(pickup[5]) == pytest.approx(0.5)
    assert beat(pickup[1]) == pytest.approx(1.0)
    assert fifth[0] == 52
    assert fifth[4] == 1
    assert beat(fifth[5]) == pytest.approx(1.5)
    assert fourth[0] == 55
    assert fourth[4] == 2
    assert beat(fourth[5]) == pytest.approx(2.0)

    plucks, mutes = arrangement.to_plan()
    assert mutes == []
    assert plucks[0][0] == 40
    assert plucks[0][4] == 0
    assert len(plucks) == len(arrangement.plucks)


def test_sandman_track_can_be_selected_by_name():
    pytest.importorskip("guitarpro")
    james = SongArrangement.from_gp3(SANDMAN, track="James")
    by_index = SongArrangement.from_gp3(SANDMAN, track=1)
    assert [row[0] for row in james.plucks] == [row[0] for row in by_index.plucks]
    with pytest.raises(ValueError, match="drums"):
        SongArrangement.from_gp3(SANDMAN, track="Lars")


def test_toccata_high_ornament_drops_an_octave_onto_a_string():
    pytest.importorskip("guitarpro")
    arrangement = SongArrangement.from_gp3(TOCCATA)
    top = max(high for _low, high in tu.STRING_MIDI_RANGES)
    assert arrangement.plucks
    assert all(row[0] <= top for row in arrangement.plucks)
    # Written tempo is 50. The 64th-note ornaments need the hand's prep window,
    # so the compiled song is slower and keeps every note a string can sound.
    compiled = compile_gp3(TOCCATA)
    assert compiled.skipped == 0
    assert compiled.song["song"]["meta"]["bpm"] < 50
    assert any(row[0] == 67 for row in arrangement.plucks)
    for row in arrangement.plucks:
        low, high = tu.STRING_MIDI_RANGES[row[4]]
        assert low <= row[0] <= high
