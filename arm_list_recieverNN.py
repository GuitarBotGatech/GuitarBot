import threading
import queue
import time
import socket
import RobotController
import numpy as np

from GuitarBot.RobotControllerAmit import chords_dir
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
initial_point_queue = queue.SimpleQueue()
song_trajs_queue = queue.SimpleQueue()
data_queue = queue.SimpleQueue()
chords_queue = queue.SimpleQueue()
strum_queue = queue.SimpleQueue()
pluck_queue = queue.SimpleQueue()

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
        data_queue.put(data)
        if not data_queue.empty():
            message_type, message_body = decode_osc_message(data_queue.get_nowait())
            if message_type:
                message_queue.put((message_type, message_body))
                print(f"Received {message_type}: {message_body}")
                print("Message Queue Size: ", message_queue.qsize())

def process_messages():
    """Process messages from the queue and handle them."""
    chords = strum = pluck = None
    while True:
        try:
            while not message_queue.empty():
                message_type, data = message_queue.get_nowait()
                print("DATA: ", data)
                if message_type == "Chords":
                    chords_queue.put(data)
                elif message_type == "Strum":
                    strum_queue.put(data)
                elif message_type == "Pluck":
                    pluck_queue.put(data)
                print(f"Chords Queue Size1", chords_queue.qsize())
                print(f"Strum Queue Size1", strum_queue.qsize())
                print(f"Pluck Queue Size1", pluck_queue.qsize())
        except queue.Empty:
            pass
        time.sleep(0.001)

def song_creator():
    initial_point = [0, 0, 0, 0, 0, 0, -10, -10, -10, -10, -10, -10, -23965, 1960, 817, 762, 1525]
    while True:
        try:
            while chords_queue.qsize() > 0 and strum_queue.qsize() > 0 and pluck_queue.qsize() > 0:
                print("HERE")
                # Collect all chords, strums, and plucks together
                chords = chords_queue.get_nowait()
                strum = strum_queue.get_nowait()
                pluck = []
                # for i in range(chords_queue.qsize()):
                #     chords.extend(chords_queue.get_nowait())
                # for i in range(strum_queue.qsize()):
                #     strum.extend(strum_queue.get_nowait())
                if pluck_queue.qsize() > 1:
                    prev_timestamp = 1
                    prev_duration = 0
                    for i in range(pluck_queue.qsize()):
                        data = pluck_queue.get_nowait()[0]
                        print("HERE DATA: ", data)
                        note = data[0]
                        duration = data[1]
                        speed = data[2]
                        timestamp = prev_timestamp + prev_duration
                        new_data = [note, duration, speed, timestamp]
                        pluck.append(new_data)
                        prev_timestamp = timestamp
                        prev_duration = duration
                print("ALL CHORDS: ", chords)
                print("ALL STRUMS: ", strum)
                print("ALL PLUCKS: ", pluck)
                print("Starting Parse")
                song_trajectories_dict = ArmListParser.parseAllMIDI(chords, strum, pluck, initial_point)
                song_trajectories_list = [value for value in song_trajectories_dict.values()]
                song_trajs_queue.put(song_trajectories_list)
                print("SONG TRAJS QUEUE LENGTH: ", song_trajs_queue.qsize())
                initial_point = song_trajectories_list[-1]
                initial_point_queue.put(initial_point)
                chords = strum = pluck = None
        except queue.Empty:
            pass
        time.sleep(0.001)

def robot_controller():
    while True:
        try:
            song_trajectories_list = []
            # While theres song lists in the queue
            while not song_trajs_queue.empty():
                # If they're more than one song list in the queue
                if song_trajs_queue.qsize() > 1:
                   for i in range(song_trajs_queue.qsize()): # Combine all the song lists into one
                       song_trajectories_list.append(song_trajs_queue.get_nowait())
                   song_trajectories_list = np.vstack(song_trajectories_list)
                else:
                    song_trajectories_list = song_trajs_queue.get_nowait()
                print("Song Trajs Length: ", len(song_trajectories_list))
                print("Starting Song")
                RobotController.main(song_trajectories_list)

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

    song_creation_thread = threading.Thread(target=song_creator, daemon=True)
    song_creation_thread.start()

    robot_controller_thread = threading.Thread(target=robot_controller, daemon=True)
    robot_controller_thread.start()

    print("Main program running. Press Ctrl+C to stop.")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Program stopped.")