import numpy as np
import time
from pythonosc.udp_client import SimpleUDPClient
UDP_IP = "127.0.0.1"
UDP_PORT = 12000
from TestMessageGenerator import *
# FORMAT
# chords_message = [[Chord, timestamp]]
# strum_message = [["DOWN"/"UP"], timestamp]
# pluck_message = [[note (midi value), duration, speed, slide_toggle, timestamp]]
# NOTES
# Duration cannot overlap with the onset of new notes.

def send_osc_message(client, address, data):
    print(f"Sending OSC message to {address}: {data}")
    client.send_message(address, data)

def main():
    # Create an OSC client
    gen = TestMessageGenerator()
    client = SimpleUDPClient(UDP_IP, UDP_PORT)
    chords_message = [['On', 1]]
    pluck_message = gen.scale()
    send_osc_message(client, "/Chords", chords_message)
    # send_osc_message(client, "/Strum", strum_message)

    send_osc_message(client, "/Pluck", pluck_message)
    time.sleep(1)


if __name__ == "__main__":
    main()