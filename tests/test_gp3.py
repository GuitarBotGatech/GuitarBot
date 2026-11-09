"""Guitar Pro tabs → SongArrangement pluck events."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notation.events import SongArrangement
from notation.gp3 import playback_measure_indices
from tuning import tune as tu

ROOT = Path(__file__).resolve().parent.parent
SANDMAN = ROOT / "notation" / "Songs" / "enter-sandman-6-11600.gp3"
ALL_OF_ME = ROOT / "notation" / "Songs" / "Django Reinhardt - All Of Me.gp5"


def _header(*, open_=False, close=-1, alt=0):
    return SimpleNamespace(isRepeatOpen=open_, repeatClose=close, repeatAlternative=alt)


def test_playback_without_repeats_is_the_written_order():
    headers = [_header(), _header(), _header()]
    assert playback_measure_indices(headers) == [0, 1, 2]


def test_repeat_close_is_how_many_times_playback_jumps_back():
    # A plain repeat sign is 1: the group plays, jumps once, and plays again.
    headers = [_header(open_=True), _header(), _header(close=1)]
    assert playback_measure_indices(headers) == [0, 1, 2, 0, 1, 2]
    twice_more = [_header(open_=True), _header(), _header(close=2)]
    assert playback_measure_indices(twice_more) == [0, 1, 2, 0, 1, 2, 0, 1, 2]


def test_alternate_endings_play_on_their_pass():
    # First ending closes the repeat. Second ending follows the last pass.
    headers = [_header(open_=True), _header(close=1, alt=1), _header(alt=2)]
    assert playback_measure_indices(headers) == [0, 1, 0, 2]


def test_repeat_on_a_skipped_ending_still_jumps_until_it_is_spent():
    headers = [_header(open_=True), _header(close=2, alt=1), _header(alt=2)]
    assert playback_measure_indices(headers) == [0, 1, 0, 0, 2]


def test_sandman_compiles_james_riff_into_plucks():
    pytest.importorskip("guitarpro")
    arrangement = SongArrangement.from_gp3(SANDMAN)
    assert arrangement.name == "Enter Sandman (James)"
    assert arrangement.bpm == pytest.approx(125)
    assert arrangement.time_signature == "4/4"
    assert arrangement.chords == []

    # Eighth-note pickup on the open low E, tied into the downbeat, then the riff.
    pickup, fifth, fourth = arrangement.plucks[:3]
    assert pickup[0] == 40
    assert pickup[1] == pytest.approx(0.48)
    assert pickup[4] == 0
    assert pickup[5] == pytest.approx(0.24)
    assert fifth == pytest.approx([52, 0.24, pickup[2], 0, 1, 0.72])
    assert fourth[0] == 55
    assert fourth[4] == 2
    assert fourth[5] == pytest.approx(0.96)

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


def test_all_of_me_unfolds_the_volta_and_swings_eighths():
    guitarpro = pytest.importorskip("guitarpro")
    song = guitarpro.parse(str(ALL_OF_ME))
    order = [index + 1 for index in playback_measure_indices(song.measureHeaders)]
    # |: bars 1–16, with bar 9 only on the first pass :| then the second ending.
    assert order[:32] == list(range(1, 17)) + [1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17]
    assert order.count(9) == 1
    assert order.count(17) == 1

    arrangement = SongArrangement.from_gp3(ALL_OF_ME)
    assert arrangement.name == "All Of Me (Nylon Guitar)"
    assert arrangement.bpm == pytest.approx(170)
    assert arrangement.time_signature == "4/4"
    assert arrangement.key == "C"
    assert arrangement.plucks[0][0] == 72
    assert arrangement.plucks[0][-1] == pytest.approx(0)

    # Written off-beat eighth (1.5 beats) sounds at 1 and 2/3 under eighth swing.
    beat = 60.0 / 170.0
    offbeat = beat + beat * 2.0 / 3.0
    assert any(abs(row[-1] - offbeat) < 1e-4 for row in arrangement.plucks)
    straight = beat * 1.5
    assert not any(abs(row[-1] - straight) < 1e-4 for row in arrangement.plucks)

    # Every kept attack is a pluck or a tremolo the hand can actually prepare.
    prep = float(tu.LH_PREP_TIME_BEFORE_PICK)
    frets = [0] * len(tu.STRING_MIDI_RANGES)
    free_at = [-prep] * len(tu.STRING_MIDI_RANGES)
    seen = set()
    for row in arrangement.plucks:
        midi, duration, _speed, slide, string, timestamp = row
        assert slide == 0
        low, high = tu.STRING_MIDI_RANGES[string]
        fret = midi - low
        assert 0 <= fret <= high - low
        key = (round(timestamp, 4), string)
        assert key not in seen
        seen.add(key)
        if frets[string] != fret:
            assert timestamp - free_at[string] + 1e-6 >= prep
        else:
            assert timestamp + 1e-6 >= free_at[string]
        frets[string] = fret
        free_at[string] = timestamp + duration if duration >= tu.TREMOLO_DURATION_THRESHOLD else timestamp
    assert len(arrangement.plucks) > 700
