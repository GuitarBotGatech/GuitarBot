import numpy as np
import time
from pythonosc.udp_client import SimpleUDPClient
UDP_IP = "127.0.0.1"
UDP_PORT = 12000
from MusicGeneration import RandomNoteGenerator
from MusicGeneration.MidiFileParser import *
from MusicGeneration.TestMessageGenerator import *
import copy


def send_osc_message(client, address, data):
    print(f"Sending OSC message to {address}: {data}")
    client.send_message(address, data)


def send_cc_example():
    """
    Minimal example: send two timed CC messages via /Midi.

    Wire format – flat OSC list, alternating address strings and args:

        /cc  <ctrl>  <value>  [<interp_flag>]  <timestamp_s>

    * ctrl, value, timestamp  → OSC floats  (type tag 'f')
    * interp_flag (optional)  → OSC integer (type tag 'i')
      0 = jump to value immediately (default if omitted)
      1 = linearly interpolate to the NEXT message with the same controller,
          inserting steps every MIDI_INTERPOLATION_INTERVAL_S (tune.py, default 5 ms)

    The last float in each group is always the timestamp in seconds.
    If sent alongside /Pluck the receiver will synchronise both to the
    same t0.  Sent alone, the sequence plays immediately.

    Examples
    --------
    No interpolation (jump):
        ["/cc", 7.0, 30.0, 0.0,   "/cc", 7.0, 120.0, 3.0]
          addr  ctrl  val  time     addr  ctrl   val   time

    With interpolation from 30 → 120 over 3 s (steps every 5 ms):
        ["/cc", 7.0, 30.0, 1, 0.0,   "/cc", 7.0, 120.0, 0, 3.0]
          addr  ctrl  val  ^flag time   addr  ctrl   val   ^flag time
    """
    client = SimpleUDPClient(UDP_IP, UDP_PORT)

    # Interpolated: CC #7 sweeps from 30 → 120 over 3 seconds (5 ms steps)
    midi_payload = [
        "/cc", 7.0,  30.0, 1, 0.0,   # CC #7 =  30 at t = 0.0 s, interp ON
        "/cc", 7.0, 120.0, 0, 3.0,   # CC #7 = 120 at t = 3.0 s (step target)
    ]
    print(f"Sending /Midi: {midi_payload}")
    client.send_message("/Midi", midi_payload)


def main():
    # Create an OSC client
    client = SimpleUDPClient(UDP_IP, UDP_PORT)
    gen = TestMessageGenerator()

    # hbd = midi_to_mido("/home/guitarbot/Documents/Midi/Happy Birthday MIDI.mid")
    # hbd = transpose(hbd, semitones= -24)
    # pluck_message = mido_to_pluck_messages(hbd, length=60.0, target_bpm=30)
    # client.send_message("/Pluck", pluck_message)
    # Interpolated volume sweep: CC #7 ramps 20 → 100 over 5 s, then drops to 40
    midi_message = [
        "/cc", 7.0,  20.0, 1, 0.0,   # CC #7 =  20 at t = 0.0 s, interp ON → next
        "/cc", 7.0, 100.0, 0, 5.0,   # CC #7 = 100 at t = 5.0 s (target, no interp)
        "/cc", 7.0,  40.0, 0, 6.0,   # CC #7 =  40 at t = 6.0 s (jump, no interp)
    ]
    pluck_message = gen.scale()
    client.send_message("/Midi", midi_message)
    client.send_message("/Pluck", pluck_message)
    # client.send_message("/Chords", chord_message)
    # client.send_message("/RLFret", [0, 6, 650])
    # client.send_message("/Config", ["graph", True])


if __name__ == "__main__":
    main()