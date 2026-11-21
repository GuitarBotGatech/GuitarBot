"""AudioBox recorder, verified without PipeWire or the interface."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime

from tuning.record_audio import capture_audio, capture_performance, find_source, new_session_dir, write_spectrogram


def test_find_source_matches_audiobox(monkeypatch):
    payload = json.dumps(
        [
            {
                "type": "PipeWire:Interface:Node",
                "info": {
                    "props": {
                        "media.class": "Audio/Sink",
                        "node.name": "alsa_output.audiobox",
                    }
                },
            },
            {
                "type": "PipeWire:Interface:Node",
                "info": {
                    "props": {
                        "media.class": "Audio/Source",
                        "node.name": "alsa_input.built-in",
                        "node.description": "Built-in Audio",
                    }
                },
            },
            {
                "type": "PipeWire:Interface:Node",
                "info": {
                    "props": {
                        "media.class": "Audio/Source",
                        "node.name": "alsa_input.usb-PreSonus_AudioBox",
                        "node.description": "AudioBox USB 96 Analog Stereo",
                    }
                },
            },
        ]
    )
    monkeypatch.setattr("tuning.record_audio.subprocess.check_output", lambda *args, **kwargs: payload)
    assert find_source() == "alsa_input.usb-PreSonus_AudioBox"


def test_capture_audio_starts_and_stops(tmp_path, monkeypatch):
    monkeypatch.setattr("tuning.record_audio.find_source", lambda match="audiobox": "alsa_input.audiobox")
    started: dict = {}

    class FakeProc:
        def __init__(self, cmd, **kwargs):
            self.stderr = None
            started["cmd"] = cmd
            Path(cmd[-1]).write_bytes(b"RIFF" + b"\x00" * 40)

        def terminate(self):
            started["stopped"] = True

        def wait(self, timeout=None):
            return 0

        def kill(self):
            started["killed"] = True

    monkeypatch.setattr("tuning.record_audio.subprocess.Popen", FakeProc)
    with capture_audio(label="play", log_dir=tmp_path) as recorder:
        assert recorder.wav_path is not None
        assert recorder.wav_path.parent == tmp_path
        assert recorder.wav_path.name.endswith("_play.wav")
    assert started["stopped"] is True
    assert started["cmd"][:6] == [
        "pw-record",
        "--target",
        "alsa_input.audiobox",
        "--rate",
        "48000",
        "--channels",
    ]


def test_missing_device_does_not_start_recorder(tmp_path, monkeypatch):
    monkeypatch.setattr("tuning.record_audio.find_source", lambda match="audiobox": None)

    def fail(*args, **kwargs):
        raise AssertionError("pw-record should not start")

    monkeypatch.setattr("tuning.record_audio.subprocess.Popen", fail)
    with capture_audio(label="play", log_dir=tmp_path) as recorder:
        assert recorder.wav_path is None


def test_session_dir_is_human_readable_and_unique(tmp_path):
    when = datetime(2026, 11, 20, 22, 10, 5)
    first = new_session_dir(tmp_path, when)
    second = new_session_dir(tmp_path, when)
    assert first.name == "2026-11-20_22-10-05"
    assert second.name == "2026-11-20_22-10-05_2"


def _tone_wav(path: Path) -> None:
    import math
    import struct
    import wave

    rate = 48000
    count = rate // 4
    frames = bytearray()
    for i in range(count):
        sample = int(0.4 * math.sin(2 * math.pi * 220 * i / rate) * 32767)
        frames += struct.pack("<hh", sample, 0)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames)


def test_write_spectrogram(tmp_path):
    wav_path = tmp_path / "audio.wav"
    png_path = tmp_path / "spectrogram.png"
    _tone_wav(wav_path)
    write_spectrogram(wav_path, png_path)
    assert png_path.is_file()
    assert png_path.stat().st_size > 1000


def test_performance_log_writes_song_telemetry_audio_and_spectrogram(tmp_path, monkeypatch):
    monkeypatch.setattr("tuning.record_audio.find_source", lambda match="audiobox": "alsa_input.audiobox")

    class FakeProc:
        def __init__(self, cmd, **kwargs):
            self.stderr = None
            _tone_wav(Path(cmd[-1]))

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

        def kill(self):
            return None

    class FakeTelemetry:
        def __init__(self, **kwargs):
            self.log_dir = Path(kwargs["log_dir"])

        def start(self):
            return None

        def stop(self, drain_s=0.5):
            path = self.log_dir / "telemetry.csv"
            path.write_text("t_unix,m1\n0,1\n", encoding="utf-8")
            return path

    monkeypatch.setattr("tuning.record_audio.subprocess.Popen", FakeProc)
    monkeypatch.setattr("tuning.record_audio.TelemetryRecorder", FakeTelemetry)
    song = {"song": {"name": "Smoke"}}
    with capture_performance(song=song, log_root=tmp_path) as recording:
        folder = recording.directory
    assert folder is not None
    assert folder.parent == tmp_path
    assert len(folder.name) == len("2026-11-20_22-10-05")
    saved = json.loads((folder / "song.json").read_text(encoding="utf-8"))
    assert saved == song
    assert (folder / "telemetry.csv").is_file()
    assert (folder / "audio.wav").is_file()
    assert (folder / "spectrogram.png").stat().st_size > 1000


def test_recorder_failure_does_not_raise(tmp_path, monkeypatch):
    monkeypatch.setattr("tuning.record_audio.find_source", lambda match="audiobox": "alsa_input.audiobox")

    def fail(*args, **kwargs):
        raise OSError("pw-record missing")

    monkeypatch.setattr("tuning.record_audio.subprocess.Popen", fail)
    with capture_audio(label="play", log_dir=tmp_path) as recorder:
        assert recorder.wav_path is None
