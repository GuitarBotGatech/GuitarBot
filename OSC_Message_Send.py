import numpy as np
import time
from pythonosc.udp_client import SimpleUDPClient
UDP_IP = "127.0.0.1"
UDP_PORT = 12000
from MusicGeneration import RandomNoteGenerator
from MusicGeneration.MidiFileParser import midi_to_pluck_messages, get_pluck_segment, transpose
import copy

def send_osc_message(client, address, data):
    print(f"Sending OSC message to {address}: {data}")
    client.send_message(address, data)

def main():
    # Create an OSC client
    client = SimpleUDPClient(UDP_IP, UDP_PORT)

    pluck_message = midi_to_pluck_messages("/home/guitarbot/Documents/Midi/Happy Birthday MIDI.mid", length=20.0, target_bpm=88)
    #
    client.send_message("/Pluck", pluck_message)
    # client.send_message("/Chords", chord_message)
    # time.sleep(30)
    # client.send_message("/RLFret", [0, 6, 650])
    # client.send_message("/Reset", [])


if __name__ == "__main__":
    main()