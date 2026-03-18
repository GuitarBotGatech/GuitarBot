import pytest

from pluck_message_to_json import pluck_message_to_song_dict


def test_converts_five_field_rows_and_sorts_by_timestamp():
    pluck_message = [
        [52, 0.2, 5, 0, 1.0],
        [50, 0.1, 4, 1, 0.5],
    ]

    song = pluck_message_to_song_dict(pluck_message, song_name="demo", bpm=96)

    assert song["song"]["name"] == "demo"
    assert song["song"]["meta"]["bpm"] == pytest.approx(96.0)
    track = song["song"]["tracks"][0]
    assert track["name"] == "pluck_main"
    assert track["type"] == "pluck"
    assert [event["timestamp"] for event in track["events"]] == [0.5, 1.0]


def test_converts_six_field_rows_with_string_index():
    pluck_message = [
        [52, 0.2, 5, 0, 2, 1.0],
    ]

    song = pluck_message_to_song_dict(pluck_message)
    event = song["song"]["tracks"][0]["events"][0]

    assert event["string_index"] == 2
    assert event["timestamp"] == pytest.approx(1.0)


def test_rejects_invalid_slide_value():
    with pytest.raises(ValueError, match="slide must be 0 or 1"):
        pluck_message_to_song_dict([[52, 0.2, 5, 2, 1.0]])
