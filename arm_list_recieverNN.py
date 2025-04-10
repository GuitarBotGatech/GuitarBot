import threading
import queue
import time
import socket
import RobotController
from UI.messaging.udp_definitions import *
from parsing.ArmListParser import ArmListParser
from pythonosc.osc_message import OscMessage
from pythonosc.parsing import osc_types

# For External
# UDP_IP = "192.168.1.1"
# For Local
UDP_IP = "127.0.0.1"
UDP_PORT = 12000
# initial_point = [0,0,0,0,0,0,-10,-10,-10,-10,-10,-10, -115, 9, 7,7]
# 6 sliders, 6 pressers, 1 strummer-slider, 1 strummer-plucker, Two pluckers for now, convert to encoder_ticks
message_queue = queue.SimpleQueue()
# chords = strum = pluck = None

def decode_osc_message(data):
    print("Message In")
    try:
        msg = OscMessage(data)
        if msg.address in ["/Chords", "/Strum", "/Pluck"]:
            return msg.address[1:], msg.params  # Remove the leading '/'
    except osc_types.ParseError:
        print("Failed to parse OSC message")
    return None, None

def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"UDP Server listening on {UDP_IP}:{UDP_PORT}")

    while True:
        data, addr = sock.recvfrom(1024)
        message_type, message_body = decode_osc_message(data)
        if message_type:
            message_queue.put((message_type, message_body))
            print(f"Received {message_type}: {message_body}")
            print(f"QUEUE SIZE",message_queue.qsize())

def process_messages():
    """Process messages from the queue and handle them."""
    chords = strum = pluck = None
    initial_point = [0, 0, 0, 0, 0, 0, -10, -10, -10, -10, -10, -10, -23965, 1960, 817, 762, 1525]

    while True:
        try:
            while not message_queue.empty():
                message_type, data = message_queue.get_nowait()
                if message_type == "Chords":
                    chords = data
                elif message_type == "Strum":
                    strum = data
                elif message_type == "Pluck":
                    pluck = data

                if chords and strum and pluck:
                    print("Starting Song")
                    song_trajectories_dict = ArmListParser.parseAllMIDI(chords, strum, pluck, initial_point)
                    song_trajectories_list = [value for value in song_trajectories_dict.values()]
                    RobotController.main(song_trajectories_list)
                    initial_point = song_trajectories_list[-1]
                    chords = strum = pluck = None
        except queue.Empty:
            pass
        time.sleep(0.001)

if __name__ == "__main__":
    # Start the UDP listener in a separate thread
    udp_thread = threading.Thread(target=udp_listener, daemon=True)
    udp_thread.start()

    # Start the message processing thread
    process_thread = threading.Thread(target=process_messages, daemon=True)
    process_thread.start()

    print("Main program running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Program stopped.")