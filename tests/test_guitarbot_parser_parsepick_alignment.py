import copy

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
