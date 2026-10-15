"""Tests for experimental LH gap-fill physics and planner hard-reject."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from control.path_planner.astar import plan
from control.path_planner.model import Note, StringState, is_physically_feasible
from control.plan import GuitarBotParser
from control.slider_motion import (
    distance_mm,
    min_finger_move_time_s,
    min_slide_time_s,
    move_feasible,
    phase_point_counts,
    trapezoid_positions,
)
from tuning import tune as tu


@pytest.fixture
def experimental_on(monkeypatch):
    monkeypatch.setattr(tu, "USE_EXPERIMENTAL_TRAJ", True)


@pytest.fixture
def experimental_off(monkeypatch):
    monkeypatch.setattr(tu, "USE_EXPERIMENTAL_TRAJ", False)


def test_min_slide_time_zero_and_scales_with_distance():
    assert min_slide_time_s(0.0) == 0.0
    short = min_slide_time_s(10.0)
    long = min_slide_time_s(200.0)
    assert short > 0.0
    assert long > short


def test_min_finger_move_includes_press_phases_for_travel():
    t0 = min_finger_move_time_s(0.0)
    assert t0 == pytest.approx(float(tu.LH_PREP_TIME_MIN))
    t_big = min_finger_move_time_s(200.0)
    # Must be strictly larger than slide-only time (unpress + press pads).
    assert t_big > min_slide_time_s(200.0)
    assert t_big >= 2.0 * float(tu.PRESSER_INTERPOLATION_POINTS) * float(tu.TIME_STEP)


def test_move_feasible_rejects_short_gap_for_long_travel():
    d = distance_mm(1, 8)
    t_need = min_finger_move_time_s(d)
    assert move_feasible(t_need, d)
    assert not move_feasible(t_need * 0.5, d)


def test_trapezoid_reaches_target_and_respects_point_count():
    q0, qf = 0, 5000
    n = 40
    pos = trapezoid_positions(q0, qf, n)
    assert len(pos) == n
    assert int(pos[0]) == q0
    assert int(pos[-1]) == qf
    # Monotonic toward target
    assert np.all(np.diff(pos.astype(float)) >= -1e-6)


def test_phase_point_counts_reserve_press_budget_when_possible():
    prep = 2.0 * float(tu.PRESSER_INTERPOLATION_POINTS) * float(tu.TIME_STEP) + 0.5
    p1, p2, p3 = phase_point_counts(prep)
    assert p1 == int(tu.PRESSER_INTERPOLATION_POINTS)
    assert p3 == int(tu.PRESSER_INTERPOLATION_POINTS)
    assert p2 >= 1
    assert p1 + p2 + p3 == max(3, int(round(prep / float(tu.TIME_STEP))))


def test_planner_hard_rejects_impossible_jump(experimental_on):
    # String 0 (low E): open=40. Fret 1 note=41, fret 8 note=48.
    # Hold fret 8 until t=1.0, then demand fret 1 at t=1.05 — too little gap.
    notes = [
        Note(pitch=48, t=0.0, dur=1.0),
        Note(pitch=41, t=1.05, dur=0.25),
    ]
    assignments = plan(notes, initial_frets=[8, 0, 0, 0, 0, 0])
    # First note assigned; second impossible on string 0 and may be skipped entirely
    # or assigned elsewhere if another string can play pitch 41 with frets free.
    by_idx = {a.note_idx: a for a in assignments}
    assert 0 in by_idx
    if 1 in by_idx:
        # If assigned, must be physically feasible from that string's prior state.
        a = by_idx[1]
        # Reconstruct prior state on that string: only note 0 touched string 0.
        if a.string == 0:
            prev = StringState(fret=8, last_pluck_t=0.0, last_note_end_t=1.0)
            assert is_physically_feasible(prev, notes[1], a.fret)


def test_planner_accepts_long_gap_jump(experimental_on):
    notes = [
        Note(pitch=48, t=0.0, dur=0.5),   # fret 8 on string 0
        Note(pitch=41, t=3.0, dur=0.25),  # fret 1 — plenty of time
    ]
    assignments = plan(notes, initial_frets=[0, 0, 0, 0, 0, 0])
    by_idx = {a.note_idx: a for a in assignments}
    assert 0 in by_idx and 1 in by_idx
    assert by_idx[1].string == 0
    assert by_idx[1].fret == 1


def test_is_physically_feasible_matches_move_feasible(experimental_on):
    prev = StringState(fret=8, last_pluck_t=0.0, last_note_end_t=1.0)
    note_ok = Note(pitch=41, t=3.0, dur=0.25)
    note_bad = Note(pitch=41, t=1.1, dur=0.25)
    assert is_physically_feasible(prev, note_ok, 1)
    assert not is_physically_feasible(prev, note_bad, 1)


def test_default_mode_prep_is_uniform(experimental_off):
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    max_prep = float(tu.LH_PREP_TIME_BEFORE_PICK)
    assert parser._lh_prep_time_for_event(None, 52, 0.025, 0) == pytest.approx(max_prep)
    assert parser._lh_prep_time_for_event(52, 60, 0.025, 0, picker_id=2) == pytest.approx(max_prep)


def test_experimental_prep_is_physics_min(experimental_on):
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    # Same note → min prep floor
    same = parser._lh_prep_time_for_event(52, 52, 0.025, 0, picker_id=2)
    assert same == pytest.approx(float(tu.LH_PREP_TIME_MIN))
    # Large fret jump on D string (picker 2): 50 open … 58 ~ fret 8
    big = parser._lh_prep_time_for_event(50, 58, 0.025, 0, picker_id=2)
    assert big == pytest.approx(min_finger_move_time_s(distance_mm(0, 8)))


def test_experimental_gap_fill_lh_event_starts_after_prev_end(experimental_on):
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    parser.use_path_planner = False
    # String 0 (low E open=40): open at t=2.0 (enough time from rest), then fret 3
    # after the first note ends — gap-fill should start at note-end, not pluck-0.45.
    picks = [
        [40, 1.0, 6, 0, 0, 2.0],
        [43, 0.25, 6, 0, 0, 5.0],
    ]
    pick_pos, slides = parser.parsePickMIDI(picks)
    assert len(pick_pos) == 2
    _, lh_events = parser.interpPick(pick_pos, slides, copy.deepcopy(tu.initial_point))
    motor0 = [e for e in lh_events if e[0] == 0]
    assert len(motor0) >= 2
    # First note ends at 2.0 + 1.0 = 3.0; second pluck at 5.0 → start=3.0, prep=2.0
    second = motor0[1]
    t_start, prep = float(second[3]), float(second[4])
    assert t_start == pytest.approx(3.0)
    assert prep == pytest.approx(2.0)


def test_experimental_same_fret_repluck_minimal(experimental_on):
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    t_min = parser._lh_prep_time_for_event(44, 44, 0.025, 0, picker_id=0)
    assert t_min == pytest.approx(float(tu.LH_PREP_TIME_MIN))
