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
from LeftHandParser import LeftHandParser
from BothHandsParser import BothHandsParser
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
dyn_queue = queue.SimpleQueue()  # Queue for dynamics messages
initial_point_queue = queue.SimpleQueue()
song_trajs_queue = queue.SimpleQueue()
data_queue = queue.SimpleQueue()
fret_queue = queue.SimpleQueue()

# Initialize parsers
rh_parser = RightHandParser()  # For /Dyn messages (pluck only)
lh_parser = LeftHandParser()   # For direct LH testing (if needed)
both_hands_parser = BothHandsParser()  # For /Fret messages (coordinated fret + pluck)

def decode_osc_message(data):
    print("Message In")
    try:
        msg = OscMessage(data)
        if msg.address in ["/Chords", "/Strum", "/Pluck", "/Dyn", "/Fret"]:
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
                elif message_type == "Fret":
                    fret_queue.put(data)
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
                    # print(f" idle for over {IDLE_TIMEOUT_SECONDS} seconds. Sending 'On' to reset state.")
                    idle_chord_message = [["On", 0]]
                    # message_queue.put(("Chords", idle_chord_message))
                    last_activity_time = time.time()

        time.sleep(0.01)


def dynamics_processor():
    """
    Process /Dyn messages for immediate motor testing.
    
    Supported formats:
    1. /Dyn [40, 45]              - Multiple notes, no velocity (state toggle)
    2. /Dyn 40                    - Single note, no velocity (state toggle)
    3. /Dyn 40 60                 - Single note with velocity
    4. /Dyn [40, 45] [60, 127]    - Multiple notes with respective velocities
    """
    while True:
        try:
            while not dyn_queue.empty():
                dyn_data = dyn_queue.get_nowait()
                print(f"Processing dynamics message: {dyn_data}")
                
                midi_notes = []
                velocities = []
                use_velocity = False
                
                # Parse the message format
                if isinstance(dyn_data, list):
                    if len(dyn_data) == 0:
                        print("Warning: Empty /Dyn message, skipping")
                        continue
                    
                    # Check if first element is a list (format: [[notes], [velocities]])
                    if isinstance(dyn_data[0], list):
                        # Format: /Dyn [40, 45] [60, 127]
                        midi_notes = dyn_data[0]
                        if len(dyn_data) >= 2 and isinstance(dyn_data[1], list):
                            velocities = dyn_data[1]
                            use_velocity = True
                            
                            if len(velocities) != len(midi_notes):
                                print(f"Warning: Velocity count ({len(velocities)}) doesn't match note count ({len(midi_notes)})")
                                print("Using state toggle instead")
                                use_velocity = False
                                velocities = []
                        else:
                            # Only notes provided, no velocities
                            pass
                    
                    elif len(dyn_data) == 1:
                        # Format: /Dyn [40] or /Dyn 40 (single value in list)
                        midi_notes = [dyn_data[0]] if not isinstance(dyn_data[0], list) else dyn_data[0]
                    
                    elif len(dyn_data) == 2:
                        # Could be: /Dyn 40 60 (note + velocity)
                        # or: /Dyn [40] [60] (note list + velocity list)
                        first_elem = dyn_data[0]
                        second_elem = dyn_data[1]
                        
                        if isinstance(first_elem, list) and isinstance(second_elem, list):
                            # Format: /Dyn [40, 45] [60, 127]
                            midi_notes = first_elem
                            velocities = second_elem
                            use_velocity = True
                            
                            if len(velocities) != len(midi_notes):
                                print(f"Warning: Velocity count ({len(velocities)}) doesn't match note count ({len(midi_notes)})")
                                print("Using state toggle instead")
                                use_velocity = False
                                velocities = []
                        else:
                            # Format: /Dyn 40 60 (single note with velocity)
                            midi_notes = [first_elem]
                            velocities = [second_elem]
                            use_velocity = True
                    
                    else:
                        # Assume it's a list of notes: /Dyn [40, 45, 50]
                        midi_notes = dyn_data
                
                else:
                    # Single value: /Dyn 40
                    midi_notes = [dyn_data]
                
                if not midi_notes:
                    print("Warning: No MIDI notes found in /Dyn message")
                    continue
                
                print(f"  Parsed - Notes: {midi_notes}, Velocities: {velocities if use_velocity else 'state toggle'}")
                
                # Generate trajectories based on whether we have velocity data
                if use_velocity and velocities:
                    # Process each note with its velocity
                    all_trajectories = []
                    for note, vel in zip(midi_notes, velocities):
                        traj = rh_parser.parse_dynamics_message(
                            midi_notes=[note],
                            velocity=vel,
                            use_velocity_mapping=True
                        )
                        all_trajectories.append(traj)
                    
                    # Combine all trajectories
                    if all_trajectories:
                        # Stack them vertically (play in sequence)
                        trajectories_list = np.vstack(all_trajectories)
                    else:
                        print("Warning: No trajectories generated")
                        continue
                else:
                    # Use state toggle (no velocity)
                    trajectories_list = rh_parser.parse_dynamics_message(
                        midi_notes=midi_notes,
                        use_velocity_mapping=False
                    )
                
                print(f"Dynamics Trajs Shape: {np.array(trajectories_list).shape}")
                print("Executing dynamics test")
                RobotController.main(trajectories_list)
                
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error in dynamics_processor: {e}")
            import traceback
            traceback.print_exc()
        
        time.sleep(0.001)

def fret_processor():
    """Process /Fret messages for coordinated fretting + plucking using BothHandsParser."""
    while True:
        try:
            while not fret_queue.empty():
                fret_data = fret_queue.get_nowait()
                print(f"Processing /Fret message: {fret_data}")
                
                # Parse /Fret message data
                # Expected formats:
                # [midi_note] - just note, default position & velocity
                # [midi_note, position] - note + position, default velocity
                # [midi_note, position, velocity] - note + position + velocity (not typical)
                
                midi_note = None
                presser_position = None
                pluck_velocity = None
                
                if len(fret_data) >= 1:
                    midi_note = fret_data[0]
                if len(fret_data) >= 2:
                    presser_position = fret_data[1]
                if len(fret_data) >= 3:
                    pluck_velocity = fret_data[2]
                
                if midi_note is None:
                    print("Error: No MIDI note in /Fret message, skipping")
                    continue
                
                print(f"  MIDI Note: {midi_note}, Position: {presser_position}, Velocity: {pluck_velocity}")
                
                # Generate coordinated trajectory (15 motors: LH fretting + RH plucking)
                trajectory_array = both_hands_parser.parse_fret_with_pluck(
                    midi_note=midi_note,
                    presser_position=presser_position,
                    pluck_velocity=pluck_velocity,
                    timestamp=0.0
                )
                
                if trajectory_array.size == 0:
                    print("Error: Failed to generate trajectory")
                    continue
                
                print(f"Generated trajectory shape: {trajectory_array.shape}")
                print(f"Executing coordinated fret + pluck")
                
                # Send to robot controller
                RobotController.main(trajectory_array)
                
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error in fret_processor: {e}")
            import traceback
            traceback.print_exc()
        
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

    dynamics_thread = threading.Thread(target=dynamics_processor, daemon=True)
    dynamics_thread.start()

    fretting_thread = threading.Thread(target=fret_processor, daemon=True)
    fretting_thread.start()

    robot_controller_thread = threading.Thread(target=robot_controller, daemon=True)
    robot_controller_thread.start()

    print("Main program running. Press Ctrl+C to stop.")
    print("Supports OSC messages:")
    print("  /Chords + /Pluck - Full song parsing with GuitarBotParser")
    print("")
    print("  /Dyn - Pluck only (no fretting change)")
    print("    Format options:")
    print("      /Dyn [40, 45]           - Multiple notes, state toggle")
    print("      /Dyn 40                 - Single note, state toggle")
    print("      /Dyn 40 60              - Single note with velocity 60")
    print("      /Dyn [40, 45] [60, 127] - Multiple notes with velocities")
    print("")
    print("  /Fret - Coordinated fret + pluck (15 motors)")
    print("    Format options:")
    print("      /Fret 45                - Fret note 45 with default force, auto-pluck")
    print("      /Fret 45 0.7            - Fret note 45 with 70% force, auto-pluck")
    print("      /Fret 45 0.7 100        - Fret note 45, 70% force, velocity 100")
    print("")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Program stopped.")
