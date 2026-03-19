from pluck_message_to_json import pluck_message_to_song_dict
from trajectory_harness import PayloadFidelityAnalyzer, OscPayload


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
