"""String actions and the slider targets they use."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from control.actions import Fret, Mute, Pluck, Release, Tremolo, actions_for, fret_to_encoder
from control.path_planner.model import Note, candidates
from tuning import tune as tu


def test_candidates_agree_with_string_ranges():
    # MIDI 52 is fret 7 on A and fret 2 on D. It is past the low E's ninth fret.
    assert candidates(Note(52, 0.0, 0.25)) == [(1, 7), (2, 2)]
    assert candidates(Note(52, 0.0, 0.25, forced_string=2)) == [(2, 2)]
    assert candidates(Note(52, 0.0, 0.25, forced_string=5)) == []


def test_open_string_leaves_the_slider_put():
    for string in range(6):
        assert fret_to_encoder(string, 0) == -1


def test_muted_string_is_a_mute_and_not_a_pluck():
    actions = actions_for(0, -1, pluck_time=1.0)
    assert actions == [Mute(0, 1.0 - tu.LH_PREP_TIME_BEFORE_PICK, tu.LH_PREP_TIME_BEFORE_PICK)]
    assert actions[0].presser_pos == tu.LH_PRESSER_MUTE_POS


def test_open_and_fretted_and_tremolo_actions():
    open_string = actions_for(3, 0, pluck_time=2.0)
    assert isinstance(open_string[0], Release)
    assert isinstance(open_string[1], Pluck)

    fretted = actions_for(1, 5, pluck_time=2.0, slide=True)
    assert fretted[0] == Fret(1, 2.0 - tu.LH_PREP_TIME_BEFORE_PICK, 5, tu.LH_PREP_TIME_BEFORE_PICK, True)
    assert isinstance(fretted[1], Pluck)

    tremolo = actions_for(1, 5, pluck_time=2.0, duration=1.0, speed=6)
    assert isinstance(tremolo[1], Tremolo)
    assert tremolo[1].duration == 1.0
