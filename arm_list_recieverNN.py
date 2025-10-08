import threading
import queue
import time
import socket
import RobotController
# from UI.messaging.udp_definitions import *
# from parsing.ArmListParser import ArmListParser
from pythonosc.osc_message import OscMessage
from pythonosc.parsing import osc_types
from GuitarBotParser import GuitarBotParser
from RightHandParser import RightHandParser
import numpy as np
import tune as tu

# For External
# UDP_IP = "192.168.1.1"
# For Local
UDP_IP = "127.0.0.1"
UDP_PORT = 12000

message_queue = queue.SimpleQueue()
chords_queue = queue.SimpleQueue()
pluck_queue = queue.SimpleQueue()
dyn_queue = queue.SimpleQueue()  # New queue for dynamics messages
initial_point_queue = queue.SimpleQueue()
song_trajs_queue = queue.SimpleQueue()
data_queue = queue.SimpleQueue()

# Initialize dynamics parser
rh_parser = RightHandParser()

def decode_osc_message(data):
    print("Message In")
    try:
        msg = OscMessage(data)
        if msg.address in ["/Chords", "/Strum", "/Pluck", "/Dyn"]:
            return msg.address[1:], msg.params  # Remove the leading '/'
    except osc_types.ParseError:
        print("Failed to parse OSC message")
    return None, None


def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    print(f"UDP Server listening on {UDP_IP}:{UDP_PORT}")

    while True:
        data, addr = sock.recvfrom(8192) # Controls how big a single "Song" can be
        data_queue.put(data)
        if not data_queue.empty():
            message_type, message_body = decode_osc_message(data_queue.get_nowait())
            if message_type:
                message_queue.put((message_type, message_body))
                print(f"Received {message_type}: {message_body}")
                print("Message Queue Size: ", message_queue.qsize())


def process_messages():
    """Process messages from the queue and handle them."""
    while True:
        try:
            while not message_queue.empty():
                message_type, data = message_queue.get_nowait()
                print("DATA: ", data)
                if message_type == "Chords":
                    chords_queue.put(data)
                elif message_type == "Pluck":
                    pluck_queue.put(data)
                elif message_type == "Dyn":
                    dyn_queue.put(data)
                # print(f"Chords Queue Size1", chords_queue.qsize())
                # print(f"Pluck Queue Size1", pluck_queue.qsize())
        except queue.Empty:
            pass
        time.sleep(0.001)


def song_creator():
    # Instantiate the parser once with the robot's starting position.
    # The parser will now manage its own state.
    parser = GuitarBotParser(initial_point=tu.initial_point)
    last_activity_time = time.time()
    IDLE_TIMEOUT_SECONDS = 3.0

    while True:
        if chords_queue.qsize() > 0 and pluck_queue.qsize() > 0:
            try:
                chords = chords_queue.get_nowait()
                pluck = pluck_queue.get_nowait()

                while not chords_queue.empty():
                    chords.extend(chords_queue.get_nowait())
                while not pluck_queue.empty():
                    pluck.extend(pluck_queue.get_nowait())

                print("Starting Parse")

                # Call the method on the parser instance.
                # It uses its internal state for the initial_point.
                song_trajectories_array = parser.parseAllMIDI(chords, pluck)

                if song_trajectories_array.size > 0:
                    song_trajs_queue.put(song_trajectories_array)
                    print("SONG TRAJS QUEUE HAS ITEM OF SHAPE: ", song_trajectories_array.shape)

                # No need to manually update initial_point here. The parser does it internally.
                last_activity_time = time.time()
                print("Activity detected, idle timer reset.")

            except queue.Empty:
                pass
        else:
            if chords_queue.qsize() == 0 and pluck_queue.qsize() == 0:
                if time.time() - last_activity_time > IDLE_TIMEOUT_SECONDS:
                    print(f" idle for over {IDLE_TIMEOUT_SECONDS} seconds. Sending 'On' to reset state.")
                    idle_chord_message = [["On", 0]]
                    # message_queue.put(("Chords", idle_chord_message))
                    last_activity_time = time.time()

        time.sleep(0.01)


def dynamics_processor():
    """Process /Dyn messages for immediate motor testing."""
    while True:
        try:
            while not dyn_queue.empty():
                dyn_data = dyn_queue.get_nowait()
                print(f"Processing dynamics message: {dyn_data}")
                
                # Parse the dynamics message (list of MNN values)
                trajectories_list = rh_parser.parse_pluck_message(dyn_data)
                
                print(f"Dynamics Trajs Length: {len(trajectories_list)}")
                print("Executing dynamics test")
                RobotController.main(trajectories_list)
                
        except queue.Empty:
            pass
        time.sleep(0.001)


def robot_controller():
    while True:
        try:
            if not song_trajs_queue.empty():
                all_trajs = []
                while not song_trajs_queue.empty():
                    all_trajs.append(song_trajs_queue.get_nowait())

                if all_trajs:
                    song_trajectories_list = np.vstack(all_trajs)
                    print("Total Song Trajs Shape: ", song_trajectories_list.shape)
                    print("Starting Song")
                    RobotController.main(song_trajectories_list)

        except queue.Empty:
            pass
        time.sleep(0.001)

if __name__ == "__main__":
    udp_thread = threading.Thread(target=udp_listener, daemon=True)
    udp_thread.start()

    process_thread = threading.Thread(target=process_messages, daemon=True)
    process_thread.start()

    song_creation_thread = threading.Thread(target=song_creator, daemon=True)
    song_creation_thread.start()

    # Start the dynamics processor thread
    dynamics_thread = threading.Thread(target=dynamics_processor, daemon=True)
    dynamics_thread.start()

    robot_controller_thread = threading.Thread(target=robot_controller, daemon=True)
    robot_controller_thread.start()

    print("Main program running. Press Ctrl+C to stop.")
    print("Supports OSC messages: /Chords, /Pluck, /Dyn")
    print("/Dyn message format: [mnn1, mnn2, ...] where MNN 40-49→Motor 13, 50-59→Motor 14, 60+→Motor 15")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Program stopped.")
