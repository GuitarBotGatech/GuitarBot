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

        /cc ff 3.0  30  t=1.0s   →  CC #3 =  30 fires at t0 + 1.0 s
        /cc ff 3.0 120  t=3.0s   →  CC #3 = 120 fires at t0 + 3.0 s

    ('ff' = two OSC floats: arg0=CC number, arg1=value)
    The last float in each group is always the timestamp in seconds.

    If sent alongside /Pluck the receiver will synchronise both to the
    same t0.  Sent alone, the sequence plays immediately.
    """
    client = SimpleUDPClient(UDP_IP, UDP_PORT)

    midi_payload = [
        "/cc", 7.0,  30.0, 1.0,   # CC #3 =  30 at t = 1.0 s
        "/cc", 7.0, 120.0, 3.0,   # CC #3 = 120 at t = 3.0 s
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
    midi_message = [
        "/cc", 7.0,  30.0, 1.0,   # CC #3 =  30 at t = 1.0 s
        "/cc", 7.0, 40.0, 2.0,
        "/cc", 7.0, 60.0, 3.0,   # CC #3 = 120 at t = 3.0 s
    ]
    pluck_message = gen.scale()
    client.send_message("/Pluck", pluck_message)
    client.send_message("/Midi", midi_message)
    # client.send_message("/Chords", chord_message)
    # client.send_message("/RLFret", [0, 6, 650])
    # client.send_message("/Config", ["graph", True])


if __name__ == "__main__":
    main()