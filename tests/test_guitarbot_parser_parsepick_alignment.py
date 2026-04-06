import copy

import pytest

import tune as tu
from GuitarBotParser import GuitarBotParser


def test_parse_pick_midi_keeps_slide_toggles_aligned_when_event_skipped():
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    picks = [
        [59, 0.4, 4, 0, 1.0],   # assigned
        [60, 0.4, 4, 0, 1.1],   # too close on same picker, should be skipped
        [61, 0.4, 4, 1, 2.0],   # assigned and slide enabled
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

    # note 59 can be voiced as open B (picker 2) or D-string 9th fret (picker 1).
    # Override string_index=1 must force picker 1 so note 68 can still play on picker 2.
    picks = [
        [59, 0.25, 6, 0, 1, 27.0],
        [68, 0.25, 6, 0, 27.0],
    ]

    pick_motor_positions, _slide_toggles = parser.parsePickMIDI(picks)
    assert len(pick_motor_positions) == 2

    assigned = sorted((int(event[0][0]), int(event[0][1])) for event in pick_motor_positions)
    assert assigned == [(1, 59), (2, 68)]


def test_lh_prep_time_adds_extra_caution_for_9th_fret_target():
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    # note 59 as D-string (picker 1) is fret 9 and should get high-fret safety padding.
    prep_d_fret9 = parser._lh_prep_time_for_event(57, 59, 0.025, 0, picker_id=1)
    # same note pitched on B-string (picker 2) is fret 0 and should not get high-fret padding.
    prep_b_open = parser._lh_prep_time_for_event(57, 59, 0.025, 0, picker_id=2)

    assert prep_d_fret9 > prep_b_open
    assert prep_d_fret9 >= float(tu.LH_PREP_TIME_BEFORE_PICK)
    assert prep_d_fret9 <= float(tu.LH_HIGH_FRET_MAX_PREP_TIME)


def test_lh_prep_time_from_rest_to_9th_fret_uses_high_fret_cap():
    parser = GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    # First D-string 9th-fret attack should use the high-fret safety cap.
    prep_from_rest = parser._lh_prep_time_for_event(None, 59, 0.025, 0, picker_id=1)
    assert prep_from_rest == pytest.approx(float(tu.LH_HIGH_FRET_MAX_PREP_TIME))
