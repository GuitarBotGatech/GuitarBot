"""Tests for GuitarBot sequence_player."""

from __future__ import annotations

import sys
import os
import threading
import time

import pytest

# Allow running from the GuitarBot repo root directly.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sequence_player import SequencePlayer, TimedMessage
from midification.mapper import OSCMIDIMapper
from midification.midi_output import MIDIOutput
from midification.config import BridgeConfig, MappingRule


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mapper():
    return OSCMIDIMapper([
        MappingRule(osc_address="/cc",   midi_type="control_change", channel=0),
        MappingRule(osc_address="/note", midi_type="note_on",        channel=0),
    ])


@pytest.fixture
def dry_midi():
    m = MIDIOutput(dry_run=True)
    m.open()
    return m


@pytest.fixture
def player(mapper, dry_midi):
    return SequencePlayer(mapper=mapper, midi_output=dry_midi, robot_delay=0.0)


# ─────────────────────────────────────────────────────────────────────────────
# TimedMessage
# ─────────────────────────────────────────────────────────────────────────────


class TestTimedMessage:
    def test_from_osc_args_basic(self):
        msg = TimedMessage.from_osc_args("/cc", (7, 100, 2.5))
        assert msg.address == "/cc"
        assert msg.args == (7, 100)
        assert msg.timestamp == pytest.approx(2.5)

    def test_from_osc_args_cc_integer_value_is_not_interp_flag(self):
        msg = TimedMessage.from_osc_args("/cc", (7, 100, 2.5))
        assert msg.args == (7, 100)
        assert msg.interpolate is False

    def test_from_osc_args_explicit_interp_flag_still_supported(self):
        msg = TimedMessage.from_osc_args("/cc", (7, 100, 1, 2.5))
        assert msg.args == (7, 100)
        assert msg.interpolate is True
        assert msg.timestamp == pytest.approx(2.5)

    def test_from_osc_args_single_arg_is_timestamp(self):
        msg = TimedMessage.from_osc_args("/note", (5.0,))
        assert msg.args == ()
        assert msg.timestamp == pytest.approx(5.0)

    def test_from_osc_args_empty_raises(self):
        with pytest.raises(ValueError, match="no arguments"):
            TimedMessage.from_osc_args("/cc", ())

    def test_from_osc_args_non_numeric_timestamp_raises(self):
        with pytest.raises(ValueError, match="must be numeric"):
            TimedMessage.from_osc_args("/cc", (7, 100, "bad"))

    def test_ordering_by_timestamp(self):
        a = TimedMessage(0.5, "/cc", (7, 64))
        b = TimedMessage(1.0, "/cc", (7, 100))
        c = TimedMessage(0.2, "/note", (60, 100))
        assert sorted([a, b, c]) == [c, a, b]

    def test_repr(self):
        msg = TimedMessage(1.234, "/cc", (7, 100))
        assert "1.234" in repr(msg)
        assert "/cc" in repr(msg)


# ─────────────────────────────────────────────────────────────────────────────
# SequencePlayer construction
# ─────────────────────────────────────────────────────────────────────────────


class TestSequencePlayerConstruction:
    def test_from_config(self):
        config = BridgeConfig.from_dict({
            "mappings": [{"osc_address": "/cc", "midi_type": "control_change"}]
        })
        p = SequencePlayer.from_config(config, robot_delay=0.05, dry_run=True)
        assert isinstance(p, SequencePlayer)
        assert p.robot_delay == pytest.approx(0.05)

    def test_negative_robot_delay_raises(self, mapper, dry_midi):
        with pytest.raises(ValueError, match="robot_delay"):
            SequencePlayer(mapper=mapper, midi_output=dry_midi, robot_delay=-0.1)

    def test_repr_idle(self, player):
        assert "idle" in repr(player)
        assert "robot_delay" in repr(player)


# ─────────────────────────────────────────────────────────────────────────────
# Sequence loading
# ─────────────────────────────────────────────────────────────────────────────


class TestLoadSequence:
    def test_load_raw_parses_and_sorts(self, player):
        player.load_raw([
            ("/cc",   (7, 100, 2.5)),
            ("/cc",   (7,  64, 0.0)),
            ("/note", (60, 100, 1.0)),
        ])
        seq = player.sequence
        assert len(seq) == 3
        assert [m.timestamp for m in seq] == [0.0, 1.0, 2.5]

    def test_load_replaces_previous(self, player):
        player.load_raw([("/cc", (7, 100, 0.0))])
        player.load_raw([("/note", (60, 80, 1.0)), ("/note", (62, 80, 2.0))])
        assert len(player.sequence) == 2

    def test_sequence_property_is_copy(self, player):
        player.load_raw([("/cc", (7, 100, 0.0))])
        seq = player.sequence
        seq.clear()
        assert len(player.sequence) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Playback
# ─────────────────────────────────────────────────────────────────────────────


class TestPlayback:
    def test_play_empty_sequence_is_noop(self, player, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="sequence_player"):
            player.play()
        assert "empty" in caplog.text

    def test_play_sends_midi_messages(self, player):
        sent = []
        player._midi.send = lambda msg: sent.append(msg)
        player.load_raw([
            ("/cc", (7,  64, 0.0)),
            ("/cc", (7, 100, 0.001)),
        ])
        player.play()
        assert len(sent) == 2
        assert sent[0].value == 64
        assert sent[1].value == 100

    def test_play_respects_ordering(self, player):
        received_values = []
        player._midi.send = lambda msg: received_values.append(msg.value)
        player.load_raw([
            ("/cc", (7, 10, 0.0)),
            ("/cc", (7, 20, 0.001)),
            ("/cc", (7, 30, 0.002)),
        ])
        player.play()
        assert received_values == [10, 20, 30]

    def test_play_async_returns_thread(self, player):
        player.load_raw([("/cc", (7, 100, 0.0))])
        t = player.play_async()
        assert isinstance(t, threading.Thread)
        t.join(timeout=2.0)
        assert not player.is_playing

    def test_play_async_raises_if_already_playing(self, player):
        player.load_raw([("/cc", (7, 100, 60.0))])
        player.play_async()
        try:
            with pytest.raises(RuntimeError, match="already playing"):
                player.play_async()
        finally:
            player.stop()

    def test_stop_cancels_playback(self, player):
        player.load_raw([
            ("/cc", (7, 100,  0.0)),
            ("/cc", (7,  64, 60.0)),   # far future – should never fire
        ])
        sent = []
        player._midi.send = lambda msg: sent.append(msg)
        player.play_async()
        time.sleep(0.05)
        player.stop()
        assert not player.is_playing
        assert len(sent) <= 1

    def test_play_with_explicit_start_time(self, player):
        sent = []
        player._midi.send = lambda msg: sent.append(msg)
        player.load_raw([("/cc", (7, 99, 0.0))])
        past = time.monotonic() - 10.0
        player.play(start_time=past)
        assert len(sent) == 1


# ─────────────────────────────────────────────────────────────────────────────
# Robot delay accounting
# ─────────────────────────────────────────────────────────────────────────────


class TestRobotDelay:
    def test_robot_delay_shifts_fire_time(self):
        """Message fires ~robot_delay seconds before t0+timestamp."""
        robot_delay = 0.10
        fire_times = []

        mapper = OSCMIDIMapper([
            MappingRule(osc_address="/cc", midi_type="control_change", channel=0)
        ])
        midi = MIDIOutput(dry_run=True)
        midi.open()
        midi.send = lambda msg: fire_times.append(time.monotonic())

        player = SequencePlayer(mapper=mapper, midi_output=midi, robot_delay=robot_delay)
        player.load_raw([("/cc", (7, 100, 0.20))])   # desired fire at t0 + 0.20 s

        t0 = time.monotonic()
        player.play(start_time=t0)

        # Expected fire at t0 + 0.20 - 0.10 = t0 + 0.10 s
        assert len(fire_times) == 1
        elapsed = fire_times[0] - t0
        assert 0.07 <= elapsed <= 0.13, f"Expected ~0.10 s, got {elapsed:.3f} s"
