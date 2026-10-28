import numpy as np

from tuning import tune as tu
from notation.Songs.legacy.pluck_message_to_json import pluck_message_to_song_dict
from control.debug.trajectory_harness import (
    PayloadFidelityAnalyzer,
    TremoloReadinessAnalyzer,
    PlannerPayload,
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
    python_payload = PlannerPayload(pluck=pluck_rows)
    json_payload = PlannerPayload(
        pluck=[
            [event["note"], event["duration_s"], event["speed"], event["slide"], event["timestamp"]]
            for event in song_dict["song"]["tracks"][0]["events"]
        ],
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


def test_open_string_pluck_moves_picker_without_moving_slider():
    """A resolved open-string pluck fires its picker and leaves the slider where it is."""
    payload = PlannerPayload(pluck=[[tu.STRING_MIDI_RANGES[0][0], 0.4, 3, 0, 0, 1.0]])
    traj = compute_trajectory(payload)

    start_idx = int(1.0 / tu.TIME_STEP)
    window = traj[start_idx: start_idx + tu.PICKER_PLUCK_MOTION_POINTS + 5, 12]
    assert not np.allclose(window, tu.initial_point[12])
    np.testing.assert_array_equal(traj[:, 0], tu.initial_point[0])

    lh_events = _derive_lh_pick_events(payload, quiet=True)
    assert [(event[0], event[1]) for event in lh_events] == [(0, -1)]


def _build_context_from_payload(payload: PlannerPayload):
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
    payload = PlannerPayload(
        pluck=[
            [43, 1.0, 6, 0, 4.0],
            [45, 1.0, 6, 1, 5.0],
            [43, 1.0, 6, 0, 6.0],
        ],
    )

    analyzer = TremoloReadinessAnalyzer(presser_ready_pos=tu.LH_PRESSER_PRESSED_POS + 200)
    result = analyzer.analyze(_build_context_from_payload(payload))

    assert result["pass"] is False
    assert result["python"]["checked_tremolo_events"] >= 1
    assert result["python"]["violation_count"] >= 1


def test_tremolo_readiness_passes_with_sufficient_lead_time():
    payload = PlannerPayload(
        pluck=[
            [43, 0.25, 6, 0, 4.0],
            [43, 1.0, 6, 0, 4.5],
            [43, 0.25, 6, 0, 5.5],
        ],
    )

    analyzer = TremoloReadinessAnalyzer(presser_ready_pos=tu.LH_PRESSER_PRESSED_POS)
    result = analyzer.analyze(_build_context_from_payload(payload))

    assert result["pass"] is True
    assert result["python"]["checked_tremolo_events"] >= 1
    assert result["python"]["violation_count"] == 0
