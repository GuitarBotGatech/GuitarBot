"""
effects_sequence_example.py
───────────────────────────
Shows how to synchronise a timed MIDI effect sequence with a GuitarBot song.

The GuitarBot robot has a physical latency between when a motor command is
sent and when the striker actually hits the string.  Similarly, a MIDI
effects pedal has a latency between receiving a CC and audibly changing the
sound.  ``robot_delay`` compensates for both by pre-firing each MIDI message
early.

Song concept
────────────
A "song" consists of:
  • A list of /Pluck or /Chords OSC messages sent to the GuitarBot controller
  • A parallel list of timestamped MIDI messages (pedal CC, program change,
    etc.) that must line up with the robot's note events

Both share the same ``t0`` clock so they are naturally synchronised.

Run
───
    python effects_sequence_example.py
"""

from __future__ import annotations

import logging
import sys
import time

from pythonosc.udp_client import SimpleUDPClient

# Import from the GuitarBot repo's own sequence_player module.
from sequence_player import SequencePlayer
from osc2midi.config import BridgeConfig

# Add GuitarBot root to sys.path if running from a subdirectory.
sys.path.insert(0, __file__.rsplit("/", 1)[0])

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    datefmt="%H:%M:%S",
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

# GuitarBot controller address (matches OSC_Message_Receiver.py defaults)
GUITARBOT_IP   = "127.0.0.1"
GUITARBOT_PORT = 12000

# How many seconds early to fire MIDI relative to the desired musical moment.
# Tune this to match your specific robot + effects-pedal latency:
#   • Typical robot striker latency:  30–80 ms
#   • Typical MIDI pedal latency:      5–20 ms
# Start at 50 ms and adjust by ear.
ROBOT_DELAY_S = 0.05

# ─────────────────────────────────────────────────────────────────────────────
# osc2midi config: maps OSC address strings → MIDI messages
# ─────────────────────────────────────────────────────────────────────────────

config = BridgeConfig.from_dict(
    {
        "midi": {
            # Set this to your effects pedal's MIDI port name.
            # Run `osc2midi list-ports` to see available ports.
            # Set dry_run=True below to test without a real MIDI device.
            "port_name": None,   # None = first available port
            "virtual": False,
        },
        "mappings": [
            # Control-change (expression pedal, reverb depth, etc.)
            {"osc_address": "/cc",      "midi_type": "control_change",  "channel": 0},
            # Program change (switch pedal presets)
            {"osc_address": "/program", "midi_type": "program_change",  "channel": 0},
            # Note on (trigger looper / sample pad)
            {"osc_address": "/note",    "midi_type": "note_on",         "channel": 0},
        ],
    }
)

# ─────────────────────────────────────────────────────────────────────────────
# Timed MIDI effect sequence
#
# Format: (osc_address, (arg0, arg1, …, timestamp_seconds))
#
# The *last* element of each tuple is always the timestamp (seconds from
# song start) at which this MIDI event should sound.
# ─────────────────────────────────────────────────────────────────────────────

MIDI_SEQUENCE = [
    # t=0.0 s – switch to clean preset at song start
    ("/program", (0,  0.00)),

    # t=2.0 s – gradually increase reverb depth (CC #91) during the phrase
    ("/cc", (91,  20,  2.00)),
    ("/cc", (91,  40,  2.50)),
    ("/cc", (91,  70,  3.00)),
    ("/cc", (91, 100,  3.50)),

    # t=5.0 s – switch to overdrive preset before the riff
    ("/program", (1,  5.00)),
    ("/cc", (11, 127,  5.00)),   # boost expression (CC #11)

    # t=9.0 s – back to clean coming out of the riff
    ("/cc", (11,  80,  9.00)),
    ("/program", (0,  9.00)),

    # t=12.0 s – fade reverb back out
    ("/cc", (91,  60, 12.00)),
    ("/cc", (91,  30, 12.50)),
    ("/cc", (91,   0, 13.00)),
]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def build_pluck_message() -> list:
    """
    Return a /Pluck payload for the GuitarBot controller.

    Replace the body of this function with real song data, e.g.:

        from MusicGeneration.MidiFileParser import midi_to_mido, mido_to_pluck_messages
        midi = midi_to_mido("my_song.mid")
        return mido_to_pluck_messages(midi, length=13.0, target_bpm=60)
    """
    return []  # TODO: populate with real song data


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    gb_client = SimpleUDPClient(GUITARBOT_IP, GUITARBOT_PORT)

    player = SequencePlayer.from_config(
        config,
        robot_delay=ROBOT_DELAY_S,
        dry_run=False,   # set True to test without a MIDI device
    )
    player.load_raw(MIDI_SEQUENCE)

    with player:
        # Capture t0 *before* sending anything so both clocks align.
        t0 = time.monotonic()

        # Send GuitarBot pluck song and MIDI sequence from the same t0.
        gb_client.send_message("/Pluck", build_pluck_message())
        player.play(start_time=t0)   # blocks until all MIDI events sent

    print("Song complete.")


if __name__ == "__main__":
    main()
