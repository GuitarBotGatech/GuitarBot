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
    d_mm = abs(qf - q0) * float(tu.MM_TO_ENCODER_CONVERSION_FACTOR) / 2048.0
    n = max(40, int(np.ceil(min_slide_time_s(d_mm) / float(tu.TIME_STEP))) + 5)
    pos = trapezoid_positions(q0, qf, n)
    assert len(pos) == n
    assert int(pos[0]) == q0
    assert int(pos[-1]) == qf
    # Mostly monotonic toward target; no single-step snap larger than half travel
    diffs = np.diff(pos.astype(float))
    assert np.all(diffs >= -2.0)  # allow 1-count encoder rounding wobble
    assert float(np.max(np.abs(diffs))) < abs(qf - q0) * 0.5


def test_trapezoid_short_window_does_not_snap():
    """Insufficient time must not jump to qf on the last sample."""
    q0, qf = 0, 20000
    pos = trapezoid_positions(q0, qf, 10)  # 50ms — far too short
    assert int(pos[0]) == q0
    assert abs(int(pos[-1]) - q0) < abs(qf - q0)
    assert float(np.max(np.abs(np.diff(pos.astype(float))))) < 10000


def test_trapezoid_long_stretch_stays_continuous():
    """Spare gap-fill time must stretch the profile, not finish early + snap."""
    q0, qf = 0, 16519
    n = 4100  # ~20.5s at 5ms — Contemplations-style first-move window
    pos = trapezoid_positions(q0, qf, n)
    diffs = np.abs(np.diff(pos.astype(float)))
    assert int(pos[0]) == q0
    assert int(pos[-1]) == qf
    assert float(np.max(diffs)) < 10000
    # Should be near the midpoint around halfway through the window
    mid = pos[n // 2]
    assert abs(int(mid) - (q0 + qf) // 2) < abs(qf - q0) * 0.25


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


def test_experimental_late_starts_after_prev_note_ends(experimental_on):
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    parser.use_path_planner = False
    # String 0 (low E open=40): open at t=2.0, then fret 3 at t=5.0 after a rest.
    # Must not leave before first note ends (t=3.0); with spare rest, late-start
    # so prep ≈ physics min (hold through the rest).
    picks = [
        [40, 1.0, 6, 0, 0, 2.0],
        [43, 0.25, 6, 0, 0, 5.0],
    ]
    pick_pos, slides = parser.parsePickMIDI(picks)
    assert len(pick_pos) == 2
    _, lh_events = parser.interpPick(pick_pos, slides, copy.deepcopy(tu.initial_point))
    motor0 = [e for e in lh_events if e[0] == 0]
    assert len(motor0) >= 2
    t_min = parser._lh_prep_time_for_event(40, 43, 0.25, 0, picker_id=0)
    second = motor0[1]
    t_start, prep = float(second[3]), float(second[4])
    assert t_start >= 3.0 - 1e-9  # finished the previous note
    assert t_start == pytest.approx(5.0 - t_min)
    assert prep == pytest.approx(t_min)


def test_experimental_skip_omits_pluck(experimental_on):
    """Impossible LH travel must not strum mid-slide / at the wrong fret."""
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    parser.use_path_planner = False
    # Fret 1 at t=2, then huge jump to fret 8 only 0.05s after note end.
    picks = [
        [41, 1.0, 6, 0, 0, 2.0],
        [48, 0.25, 6, 0, 0, 3.05],
    ]
    pick_pos, slides = parser.parsePickMIDI(picks)
    assert len(pick_pos) == 2
    rh, lh_events = parser.interpPick(pick_pos, slides, copy.deepcopy(tu.initial_point))
    motor0_lh = [e for e in lh_events if e[0] == 0]
    # Only the first fretted move should be scheduled.
    assert len(motor0_lh) == 1
    # Second event's pluck time must not move the RH picker off its hold after first.
    t_second = 3.05
    idx = int(t_second / float(tu.TIME_STEP))
    # Compare RH column for string 0 around second pluck vs just before: no new motion burst.
    phys0 = tu.picker_physical_index(0)
    pre = rh[max(0, idx - 1), phys0]
    # Pluck motion would change several samples; require flat neighborhood if skipped.
    window = rh[idx : idx + int(tu.PICKER_PLUCK_MOTION_POINTS), phys0]
    assert np.allclose(window, pre), "skipped note must not pluck"


def test_experimental_same_fret_repluck_minimal(experimental_on):
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    t_min = parser._lh_prep_time_for_event(44, 44, 0.025, 0, picker_id=0)
    assert t_min == pytest.approx(float(tu.LH_PREP_TIME_MIN))


def test_experimental_no_lh_discontinuity_when_chord_overlaps_slide(experimental_on):
    """Regression: mid-slide chord must continue from array pose, not end-pose cache."""
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    parser.use_path_planner = False

    # Pluck at 4.0 with large fret travel → late-start slide spans ~t_min before 4.0
    picks = [[48, 0.25, 6, 0, 0, 4.0]]
    pick_pos, slides = parser.parsePickMIDI(picks)
    assert pick_pos
    _, lh_pick_events = parser.interpPick(pick_pos, slides, copy.deepcopy(tu.initial_point))
    assert lh_pick_events
    t_start = float(lh_pick_events[0][3])
    prep = float(lh_pick_events[0][4])
    assert prep > 0.2
    chord_t = t_start + 0.5 * prep
    chord_positions = list(tu.initial_point[:12])
    chord_positions[0] = int(-28284)
    for i in range(6, 12):
        chord_positions[i] = int(tu.LH_PRESSER_UNPRESSED_POS)
    lh_chords = [[chord_positions, chord_t]]

    traj = parser.lh_interpolate(lh_chords, lh_pick_events, copy.deepcopy(tu.initial_point))
    diffs = np.abs(np.diff(traj[:, :6], axis=0))
    max_jump = float(np.nanmax(diffs)) if diffs.size else 0.0
    assert max_jump < 10000, f"LH discontinuity jump {max_jump} >= DISCONTINUITY_THRESHOLD"
