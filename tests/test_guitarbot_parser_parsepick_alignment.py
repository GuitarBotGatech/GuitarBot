import copy

import numpy as np

import pytest

import tune as tu
from GuitarBotParser import GuitarBotParser


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


def test_lh_prep_time_capped_and_scaled_by_semitone_delta():
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    max_prep = float(tu.LH_PREP_TIME_BEFORE_PICK)

    first_note = parser._lh_prep_time_for_event(None, 52, 0.025, 0)
    same_note = parser._lh_prep_time_for_event(52, 52, 0.025, 0)
    small_delta = parser._lh_prep_time_for_event(52, 53, 0.025, 0)
    medium_delta = parser._lh_prep_time_for_event(52, 55, 0.025, 0)
    large_delta = parser._lh_prep_time_for_event(52, 61, 0.025, 0)

    assert first_note == pytest.approx(max_prep)
    assert 0.0 < same_note < max_prep
    assert same_note <= small_delta < medium_delta < large_delta <= max_prep


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


def test_lh_prep_time_adds_extra_caution_for_9th_fret_target():
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    # note 59 as D-string (picker 1) is fret 9 and should get high-fret safety padding.
    prep_d_fret9 = parser._lh_prep_time_for_event(57, 59, 0.025, 0, picker_id=1)
    # same note pitched on B-string (picker 2) is fret 0 and should also get edge padding.
    prep_b_open = parser._lh_prep_time_for_event(57, 59, 0.025, 0, picker_id=2)

    assert prep_d_fret9 == pytest.approx(prep_b_open)
    assert prep_d_fret9 >= float(tu.LH_PREP_TIME_BEFORE_PICK)
    assert prep_d_fret9 <= float(tu.LH_HIGH_FRET_MAX_PREP_TIME)


def test_lh_prep_time_from_rest_to_9th_fret_uses_high_fret_cap():
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    # First D-string 9th-fret attack should include edge bonus and remain capped.
    prep_from_rest = parser._lh_prep_time_for_event(None, 59, 0.025, 0, picker_id=1)
    expected = float(tu.LH_PREP_TIME_BEFORE_PICK) + float(tu.LH_EDGE_PREP_TIME_BONUS)
    assert prep_from_rest == pytest.approx(expected)
    assert prep_from_rest <= float(tu.LH_HIGH_FRET_MAX_PREP_TIME)


def test_lh_prep_time_from_9th_fret_to_open_uses_high_fret_cap():
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    # D-string picker 1: note 59 is fret 9, note 50 is open.
    prep_from_high_to_open = parser._lh_prep_time_for_event(59, 50, 0.025, 0, picker_id=1)
    prep_from_mid_to_open = parser._lh_prep_time_for_event(57, 50, 0.025, 0, picker_id=1)

    expected = float(tu.LH_PREP_TIME_BEFORE_PICK) + float(tu.LH_EDGE_PREP_TIME_BONUS)
    assert prep_from_high_to_open == pytest.approx(expected)
    assert prep_from_mid_to_open == pytest.approx(expected)
    assert prep_from_high_to_open <= float(tu.LH_HIGH_FRET_MAX_PREP_TIME)


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
