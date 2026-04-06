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
