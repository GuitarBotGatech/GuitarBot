import copy

import numpy as np
import pytest

import tune as tu
from GuitarBotParser import GuitarBotParser
from pluck_message_to_json import pluck_message_to_song_dict
from trajectory_harness import (
    PayloadFidelityAnalyzer,
    TremoloReadinessAnalyzer,
    OscPayload,
    _derive_lh_pick_events,
    compute_trajectory,
)


def test_payload_fidelity_analyzer_passes_for_equivalent_python_and_json_payloads(tmp_path):
    pluck_rows = [
        [52, 0.4, 3, 0, 1.0],
        [59, 0.8, 7, 1, 2.5],
        [50, 0.6, 5, 0, 2.0],
    ]

    song_dict = pluck_message_to_song_dict(
        pluck_rows,
        song_name="harness-test",
        bpm=120,
        track_name="pluck_main",
    )

    # Simulate source payloads used by the harness.
    python_payload = OscPayload(chords=[], pluck=pluck_rows, midi=[])
    json_payload = OscPayload(
        chords=[],
        pluck=[
            [event["note"], event["duration_s"], event["speed"], event["slide"], event["timestamp"]]
            for event in song_dict["song"]["tracks"][0]["events"]
        ],
        midi=[],
    )

    analyzer = PayloadFidelityAnalyzer()
    result = analyzer.analyze(
        type("Context", (), {
            "python_payload": python_payload,
            "json_payload": json_payload,
            "python_trajectory": None,
            "json_trajectory": None,
        })()
    )

    assert result["pass"] is True
    assert result["mismatch_count"] == 0
    assert result["python_slide_events"] == 1
    assert result["json_slide_events"] == 1


# ---------------------------------------------------------------------------
# Chord pluck tests
# ---------------------------------------------------------------------------

class TestChordPluckParsing:
    """parsePickMIDI: note 0-5 is a direct string index, not a MIDI pitch."""

    def _parser(self):
        return GuitarBotParser(initial_point=copy.deepcopy(tu.initial_point), graph=False)

    @pytest.mark.parametrize("string_index, expected_events", [
        (0, 1),  # string 0  → picker 0 (E)
        (2, 1),  # string 2  → picker 1 (D)
        (4, 1),  # string 4  → picker 2 (B)
        (1, 0),  # string 1  → no plucker
        (3, 0),  # string 3  → no plucker
        (5, 0),  # string 5  → no plucker
    ])
    def test_chord_pluck_routing(self, string_index, expected_events):
        positions, toggles = self._parser().parsePickMIDI([[string_index, 0.4, 3, 0, 1.0]])
        assert len(positions) == expected_events, (
            f"String {string_index}: expected {expected_events} pick event(s), got {len(positions)}"
        )
        assert len(toggles) == expected_events

    def test_chord_pluck_does_not_generate_lh_pick_event(self):
        """Chord pluck should activate the picker but leave the slider untouched."""
        payload = OscPayload(chords=[], pluck=[[0, 0.4, 3, 0, 1.0]], midi=[])
        lh_events = _derive_lh_pick_events(payload, quiet=True)
        assert lh_events == [], f"Expected no LH pick events, got: {lh_events}"

    def test_chord_pluck_picker_trajectory_has_movement(self):
        """The plucker column in the trajectory should change position on a chord pluck."""
        payload = OscPayload(chords=[], pluck=[[0, 0.4, 3, 0, 1.0]], midi=[])
        traj = compute_trajectory(payload)

        picker_col = 12  # first plucker column (string 0)
        start_idx = int(1.0 / tu.TIME_STEP)
        window = traj[start_idx: start_idx + tu.PICKER_PLUCK_MOTION_POINTS + 5, picker_col]

        initial_pos = tu.initial_point[12]
        assert not np.allclose(window, initial_pos), (
            "Expected picker to move on chord pluck, but position was unchanged."
        )

    def test_chord_pluck_slider_unchanged_compared_to_chord_only(self):
        """Adding a chord pluck on top of a chord should not alter the slider trajectory."""
        chord = [["Em", 0.0]]

        chord_only = OscPayload(chords=chord, pluck=[], midi=[])
        chord_plus_pluck = OscPayload(chords=chord, pluck=[[0, 0.4, 3, 0, 0.8]], midi=[])

        traj_base = compute_trajectory(chord_only)
        traj_pluck = compute_trajectory(chord_plus_pluck)

        # Trim to the shorter of the two
        rows = min(traj_base.shape[0], traj_pluck.shape[0])
        slider_cols = slice(0, 6)  # columns 0-5 are sliders

        np.testing.assert_array_equal(
            traj_base[:rows, slider_cols],
            traj_pluck[:rows, slider_cols],
            err_msg="Chord pluck modified slider positions unexpectedly.",
        )


def _build_context_from_payload(payload: OscPayload):
    trajectory = compute_trajectory(payload)
    return type(
        "Context",
        (),
        {
            "python_payload": payload,
            "json_payload": payload,
            "python_trajectory": trajectory,
            "json_trajectory": trajectory,
        },
    )()


def test_tremolo_readiness_flags_early_pick_start():
    payload = OscPayload(
        chords=[],
        pluck=[
            [43, 1.0, 6, 0, 4.0],
            [45, 1.0, 6, 1, 5.0],
            [43, 1.0, 6, 0, 6.0],
        ],
        midi=[],
    )

    analyzer = TremoloReadinessAnalyzer(presser_ready_pos=tu.LH_PRESSER_PRESSED_POS)
    result = analyzer.analyze(_build_context_from_payload(payload))

    assert result["pass"] is False
    assert result["python"]["checked_tremolo_events"] >= 1
    assert result["python"]["violation_count"] >= 1


def test_tremolo_readiness_passes_with_sufficient_lead_time():
    payload = OscPayload(
        chords=[],
        pluck=[
            [43, 0.25, 6, 0, 4.0],
            [43, 1.0, 6, 0, 4.5],
            [43, 0.25, 6, 0, 5.5],
        ],
        midi=[],
    )

    analyzer = TremoloReadinessAnalyzer(presser_ready_pos=tu.LH_PRESSER_PRESSED_POS)
    result = analyzer.analyze(_build_context_from_payload(payload))

    assert result["pass"] is True
    assert result["python"]["checked_tremolo_events"] >= 1
    assert result["python"]["violation_count"] == 0
