"""Chord track → pinned plucks before the planner."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import copy

import numpy as np

from control.actions import Mute
from control.plan import GuitarBotParser
from notation import chords
from notation.chords import chord_name, plan_parts
from tuning import tune as tu

OPEN = [low for low, _high in tu.STRING_MIDI_RANGES]


def _fixed_voicing(monkeypatch, frets):
    monkeypatch.setattr(chords, "find_lowest_cost_chord", lambda *_args: list(frets))


def test_chord_name_matches_library_spelling():
    assert chord_name("Em") == ("En", "MINOR")
    assert chord_name("F#m7") == ("F#", "MINOR7")
    assert chord_name("Csus2") == ("Cn", "SUS2")
    assert chord_name("G") == ("Gn", "MAJOR")
    assert chord_name("Fm") == ("Fn", "MINOR")


def test_flat_chords_use_the_library_spelling():
    assert chord_name("Bb") == ("Bf", "MAJOR")
    assert chord_name("Bbm7") == ("Bf", "MINOR7")
    assert chord_name("Eb") == ("Ef", "MAJOR")
    assert chord_name("Ab") == chord_name("Af")
    assert chord_name("Db") == ("Df", "MAJOR")
    assert chord_name("Gb") == ("Gf", "MAJOR")


def test_flat_chord_resolves_from_the_library():
    strings = [[s, 0.4, 3, 0, 1.0] for s in range(6)]
    assert plan_parts([["Bb", 0.0]], strings)[0] == plan_parts([["Bf", 0.0]], strings)[0]
    assert plan_parts([["Bb", 0.0]], strings)[0] != plan_parts([["B", 0.0]], strings)[0]


def test_string_pluck_takes_the_active_chords_fret_and_is_pinned(monkeypatch):
    _fixed_voicing(monkeypatch, [0, 2, 2, 0, 0, 0])
    rows = plan_parts([["Em", 0.0]], [[1, 0.4, 3, 0, 1.0], [3, 0.4, 3, 1, 1.5]])[0]
    assert rows == [
        [OPEN[1] + 2, 0.4, 3, 0, 1, 1.0],
        [OPEN[3], 0.4, 3, 1, 3, 1.5],
    ]


def test_string_pluck_before_first_chord_plays_open(monkeypatch):
    _fixed_voicing(monkeypatch, [3, 3, 3, 3, 3, 3])
    rows = plan_parts([["G", 2.0]], [[4, 0.4, 3, 0, 1.0], [4, 0.4, 3, 0, 2.0]])[0]
    assert rows == [
        [OPEN[4], 0.4, 3, 0, 4, 1.0],
        [OPEN[4] + 3, 0.4, 3, 0, 4, 2.0],
    ]


def test_muted_string_is_not_plucked(monkeypatch):
    _fixed_voicing(monkeypatch, [-1, 3, 2, 0, 1, 0])
    plucks, mutes = plan_parts([["C", 0.0]], [[0, 0.4, 3, 0, 1.0]])
    assert plucks == []
    assert mutes == [Mute(0, 0.0, tu.LH_PREP_TIME_BEFORE_PICK)]


def test_chord_mute_damps_the_presser_and_leaves_the_slider(monkeypatch):
    _fixed_voicing(monkeypatch, [-1, 0, 0, 0, 0, 0])
    plucks, mutes = plan_parts([["C", 1.0]], [[1, 0.4, 3, 0, 1.0]])
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    traj = parser.parseAll(plucks, mutes)

    at_chord = int(1.0 / tu.TIME_STEP)
    assert int(traj[at_chord, 6]) == tu.LH_PRESSER_MUTE_POS
    assert int(traj[at_chord, 0]) == tu.initial_point[0]


def test_mute_yields_to_a_note_on_the_same_string(monkeypatch):
    _fixed_voicing(monkeypatch, [-1, 0, 0, 0, 0, 0])
    plucks, mutes = plan_parts([["C", 1.0]], [[OPEN[0], 0.4, 3, 0, 1.0]])
    assert mutes
    quiet = dict(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    with_mute = GuitarBotParser(**quiet).parseAll(plucks, mutes)
    without = GuitarBotParser(**quiet).parseAll(plucks)
    np.testing.assert_array_equal(with_mute, without)


def test_pitched_plucks_pass_through(monkeypatch):
    _fixed_voicing(monkeypatch, [0, 2, 2, 0, 0, 0])
    pitched = [[52, 0.5, 5, 0, 1.0], [55, 0.5, 5, 0, 2, 1.5]]
    assert plan_parts([["Em", 0.0]], pitched)[0] == pitched


def test_library_voicing_resolves_every_string():
    rows = plan_parts([["Em", 0.0]], [[s, 0.4, 3, 0, 1.0] for s in range(6)])[0]
    assert [row[4] for row in rows] == list(range(6))
    for row in rows:
        low, high = tu.STRING_MIDI_RANGES[row[4]]
        assert low <= row[0] <= high
