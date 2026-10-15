import copy

import numpy as np

import pytest

from tuning import tune as tu
from control.plan import GuitarBotParser


def test_parse_pick_midi_keeps_slide_toggles_aligned_when_event_skipped():
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    picks = [
        [72, 0.4, 4, 0, 1.0],   # assigned (high E string)
        [73, 0.4, 4, 0, 1.1],   # too close on same picker, should be skipped
        [71, 0.4, 4, 1, 2.0],   # assigned and slide enabled
    ]

    pick_motor_positions, slide_toggles = parser.parsePickMIDI(picks)

    assert len(pick_motor_positions) == 2
    assert slide_toggles == [0, 1]


def test_lh_prep_time_default_mode_is_uniform():
    """Default (non-experimental) mode always uses LH_PREP_TIME_BEFORE_PICK."""
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    assert not tu.USE_EXPERIMENTAL_TRAJ

    max_prep = float(tu.LH_PREP_TIME_BEFORE_PICK)
    assert parser._lh_prep_time_for_event(None, 52, 0.025, 0) == pytest.approx(max_prep)
    assert parser._lh_prep_time_for_event(52, 52, 0.025, 0) == pytest.approx(max_prep)
    assert parser._lh_prep_time_for_event(52, 61, 0.025, 0, picker_id=2) == pytest.approx(max_prep)


def test_parse_pick_midi_honors_zero_based_string_override_for_ambiguous_note():
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)
    parser.use_path_planner = False

    # note 59 is playable on multiple strings; override string_index=2 (0-based)
    # must force picker 2 so a later note can still be auto-assigned independently.
    picks = [
        [59, 0.25, 6, 0, 2, 27.0],
        [68, 0.25, 6, 0, 27.0],
    ]

    pick_motor_positions, _slide_toggles = parser.parsePickMIDI(picks)
    assert len(pick_motor_positions) == 2

    assigned = sorted((int(event[0][0]), int(event[0][1])) for event in pick_motor_positions)
    assert assigned == [(2, 59), (4, 68)]


def test_parse_pick_midi_honors_override_even_when_picker_is_busy():
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    # Regression: when a run of E2 notes is followed by F#2 forced to string 0,
    # prep-time conflict previously caused a fallback to picker 1 (A string).
    picks = [
        [40, 0.25, 6, 0, 1.0],
        [40, 0.25, 6, 0, 1.5],
        [40, 0.25, 6, 0, 2.0],
        [40, 0.25, 6, 0, 2.5],
        [49, 0.25, 6, 0, 0, 3.0],
        [49, 0.25, 6, 0, 0, 3.5],
        [49, 0.25, 6, 0, 0, 4.0],
        [49, 0.25, 6, 0, 0, 4.5],
    ]

    pick_motor_positions, _slide_toggles = parser.parsePickMIDI(picks)
    assigned = [(int(event[0][0]), int(event[0][1]), float(event[1])) for event in pick_motor_positions]

    forced_note_assignments = [(picker, note, ts) for picker, note, ts in assigned if note == 49]
    assert forced_note_assignments
    assert all(picker == 0 for picker, _note, _ts in forced_note_assignments)


def test_parse_pick_midi_keeps_plucker_motion_synced_across_segments():
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    # Segment 1 ends with picker 0 at down-pluck destination.
    parser.parseAllMIDI([], [[44, 0.125, 6, 0, 1.0]])

    # Segment 2 starts with the same note; first pluck should still move (up-stroke),
    # not be a no-op due to picker state reset.
    segment_two = [
        [44, 0.125, 6, 0, 2.0],
        [45, 0.125, 6, 1, 2.125],
        [44, 0.125, 6, 1, 2.25],
    ]
    traj = parser.parseAllMIDI([], segment_two)

    picker_col = 12
    start_idx = int(2.0 / tu.TIME_STEP)
    end_idx = start_idx + tu.PICKER_PLUCK_MOTION_POINTS + 6
    window = traj[start_idx:end_idx, picker_col]

    assert float(np.max(window) - np.min(window)) > 0.0


@pytest.mark.parametrize("tremolo_duration", [0.6, 1.6, 2.0])
def test_tremolo_then_pluck_on_same_picker_still_moves(tremolo_duration):
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    second_timestamp = 1.0 + tremolo_duration + 0.2
    picks = [
        [44, tremolo_duration, 6, 0, 1.0],
        [44, 0.125, 6, 0, second_timestamp],
    ]

    traj = parser.parseAllMIDI([], picks)

    picker_col = 12
    start_idx = int(second_timestamp / tu.TIME_STEP)
    end_idx = start_idx + tu.PICKER_PLUCK_MOTION_POINTS + 6
    window = traj[start_idx:end_idx, picker_col]

    assert float(np.max(window) - np.min(window)) > 0.0


def test_tremolo_end_state_is_respected_across_segments():
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    # First segment is a tremolo with duration that previously could leave stale picker state.
    parser.parseAllMIDI([], [[44, 1.6, 6, 0, 1.0]])

    # Second segment starts with the same string; it should still produce motion.
    traj = parser.parseAllMIDI([], [[44, 0.125, 6, 0, 2.8]])

    picker_col = 12
    start_idx = int(2.8 / tu.TIME_STEP)
    end_idx = start_idx + tu.PICKER_PLUCK_MOTION_POINTS + 6
    window = traj[start_idx:end_idx, picker_col]

    assert float(np.max(window) - np.min(window)) > 0.0
