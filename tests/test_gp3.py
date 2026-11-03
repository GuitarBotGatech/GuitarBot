"""Guitar Pro 3 tabs → SongArrangement pluck events."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notation.events import SongArrangement
from notation.gp3 import playback_measure_indices

ROOT = Path(__file__).resolve().parent.parent
SANDMAN = ROOT / "notation" / "Songs" / "enter-sandman-6-11600.gp3"


def _header(*, open_=False, close=-1, alt=0):
    return SimpleNamespace(isRepeatOpen=open_, repeatClose=close, repeatAlternative=alt)


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
