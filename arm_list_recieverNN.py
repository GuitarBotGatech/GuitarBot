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
import traceback

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
rlfret_queue = queue.SimpleQueue()  # Queue for RL low-level fret commands
reset_queue = queue.SimpleQueue()
config_queue = queue.SimpleQueue()

# Mutual-exclusion lock for RobotController.main().
# RobotController.main() sends a blocking UDP trajectory to the Arduino.
# Calling it from multiple threads simultaneously corrupts the packet stream
# and can cause violent motor behaviour (e.g. Reset interrupting an RLFret).
# Every call to RobotController.main() MUST be preceded by acquiring this lock.
robot_lock = threading.Lock()

# Initialize parsers
rh_parser = RightHandParser()  # For /Dyn messages (pluck only)
lh_parser = LeftHandParser()   # For direct LH testing (if needed)
both_hands_parser = BothHandsParser()  # For /Fret messages (coordinated fret + pluck)

# Track the actual robot position (last trajectory endpoint sent to RobotController)
last_robot_position = tu.initial_point.copy()  # Start at initial position

# Runtime configuration flags (can be updated via /Config messages)
unpress_after_flag = True      # Default: release presser after pluck
force_adjustment_only_flag = False  # Default: normal fretting behavior
direct_press_flag = True       # Default: presser current→target direct (no -650 waypoint)

def decode_osc_message(data):
    print("Message In")
    try:
        msg = OscMessage(data)
        if msg.address in ["/Chords", "/Strum", "/Pluck", "/Dyn", "/Fret", "/RLFret", "/Reset", "/Config"]:
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
                elif message_type == "RLFret":
                    rlfret_queue.put(data)
                elif message_type == "Reset":
                    reset_queue.put(data)
                elif message_type == "Config":
                    config_queue.put(data)
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
                    #print(f" idle for over {IDLE_TIMEOUT_SECONDS} seconds. Sending 'On' to reset state.")
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
                with robot_lock:
                    RobotController.main(trajectories_list)
                
                # Update last robot position
                global last_robot_position
                if len(trajectories_list) > 0:
                    last_robot_position = np.array(trajectories_list)[-1, :].copy()
                    print(f"Updated last_robot_position after /Dyn")
                
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error in dynamics_processor: {e}")
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
                # [midi_note] - just note, default force & velocity
                # [midi_note, force] - note + force, default velocity
                # [midi_note, force, velocity] - note + force + velocity (not typical)
                
                midi_note = None
                presser_force = None
                pluck_velocity = None
                
                if len(fret_data) >= 1:
                    midi_note = fret_data[0]
                if len(fret_data) >= 2:
                    presser_force = fret_data[1]
                if len(fret_data) >= 3:
                    pluck_velocity = fret_data[2]
                
                if midi_note is None:
                    print("Error: No MIDI note in /Fret message, skipping")
                    continue
                
                print(f"  MIDI Note: {midi_note}, Force: {presser_force}, Velocity: {pluck_velocity}")
                
                # Generate coordinated trajectory (15 motors: LH fretting + RH plucking)
                trajectory_array = both_hands_parser.parse_fret_with_pluck(
                    midi_note=midi_note,
                    presser_force=presser_force,
                    pluck_velocity=pluck_velocity,
                    timestamp=0.0,
                    force_adjustment_only=force_adjustment_only_flag,
                    unpress_after=unpress_after_flag
                )
                
                if trajectory_array.size == 0:
                    print("Error: Failed to generate trajectory")
                    continue
                
                print(f"Generated trajectory shape: {trajectory_array.shape}")
                print(f"Executing coordinated fret + pluck")
                
                # Send to robot controller
                with robot_lock:
                    RobotController.main(trajectory_array)
                
                # Update last robot position
                global last_robot_position
                last_robot_position = trajectory_array[-1, :].copy()
                print(f"Updated last_robot_position after /Fret")
                
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error in fret_processor: {e}")
            traceback.print_exc()
        
        time.sleep(0.001)


def rlfret_processor():
    """
    Process /RLFret messages for RL low-level control.
    
    This is the primary interface for RL agents to control the robot.
    Uses fractional frets and raw torque for fine-grained control.
    
    OSC Format: /RLFret <string_idx> <fret_position> <torque> [pluck_velocity]
    
    Parameters:
        string_idx: String index (0, 2, or 4 - must have plucker)
        fret_position: Fractional fret position (0.0 - 9.0)
        torque: Fretting torque (0 - 1000, where 1000 = 100% motor rating)
        pluck_velocity: Optional pluck velocity (0-127), defaults to state toggle
    
    Examples:
        /RLFret 0 4.0 100      - String 0, fret 4 (harmonic), light touch
        /RLFret 2 5.5 400      - String 2, between frets 5-6, normal press
        /RLFret 4 7.0 150 80   - String 4, fret 7 (harmonic), light touch, velocity 80
    """
    while True:
        try:
            while not rlfret_queue.empty():
                rlfret_data = rlfret_queue.get_nowait()
                print(f"Processing /RLFret message: {rlfret_data}")
                
                # Parse /RLFret message data
                # Expected formats:
                # [string_idx, fret_position, torque] - basic
                # [string_idx, fret_position, torque, pluck_velocity] - with velocity
                
                if len(rlfret_data) < 3:
                    print("Error: /RLFret requires at least [string_idx, fret_position, torque]")
                    continue
                
                string_idx = int(rlfret_data[0])
                fret_position = float(rlfret_data[1])
                torque = float(rlfret_data[2])
                pluck_velocity = None
                
                if len(rlfret_data) >= 4:
                    pluck_velocity = int(rlfret_data[3])
                
                # Validate string has a plucker
                PLAYABLE_STRINGS = [0, 2, 4]
                if string_idx not in PLAYABLE_STRINGS:
                    print(f"Error: String {string_idx} has no plucker. Use strings {PLAYABLE_STRINGS}")
                    continue
                
                # Clamp values to valid ranges
                fret_position = max(0.0, min(9.0, fret_position))
                torque = max(0.0, min(1000.0, torque))
                
                print(f"  String: {string_idx}, Fret: {fret_position:.2f}, Torque: {torque:.0f}, Velocity: {pluck_velocity}")
                
                # Generate coordinated trajectory using BothHandsParser
                trajectory_array = both_hands_parser.parse_rlfret_with_pluck(
                    string_idx=string_idx,
                    fret_position=fret_position,
                    torque=torque,
                    pluck_velocity=pluck_velocity,
                    timestamp=0.0,
                    unpress_after=unpress_after_flag,
                    direct_press=direct_press_flag
                )
                
                if trajectory_array.size == 0:
                    print("Error: Failed to generate trajectory")
                    continue
                
                print(f"Generated trajectory shape: {trajectory_array.shape}")
                print(f"Executing RL fret + pluck")
                
                # Send to robot controller
                with robot_lock:
                    RobotController.main(trajectory_array)
                
                # Update last robot position
                global last_robot_position
                last_robot_position = trajectory_array[-1, :].copy()
                print(f"Updated last_robot_position after /RLFret")
                
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error in rlfret_processor: {e}")
            traceback.print_exc()
        
        time.sleep(0.001)


def config_processor():
    """
    Process /Config messages to update runtime flags.
    
    Supported flags:
    - graph: Enable/disable trajectory plotting (True/False)
    - unpress_after: Release presser after pluck (True/False)
    - force_adjustment_only: Skip unpress phase when adjusting force (True/False)
    - blend_percent: Trajectory blend percentage (0.0-1.0)
    - presser_points: Presser interpolation points (int)
    - slider_points: Slider motion points (int)
    - picker_points: Picker pluck motion points (int)
    - lh_prep_time: Left hand prep time before pick (seconds, float)
    
    Message formats:
    /Config "graph" True
    /Config "unpress_after" False
    /Config "blend_percent" 0.3
    /Config "presser_points" 15
    """
    while True:
        try:
            while not config_queue.empty():
                config_data = config_queue.get_nowait()
                print(f"Processing /Config message: {config_data}")
                
                if len(config_data) < 2:
                    print("Error: /Config requires [flag_name, value]")
                    continue
                
                flag_name = config_data[0]
                flag_value = config_data[1]
                
                # Boolean flags
                if flag_name == "graph":
                    tu.graph = bool(flag_value)
                    print(f"  ✓ Set tu.graph = {tu.graph}")
                    
                elif flag_name == "unpress_after":
                    # This is a parser-level flag, not in tune.py
                    # We'll store it as a global that parsers can access
                    global unpress_after_flag
                    unpress_after_flag = bool(flag_value)
                    print(f"  ✓ Set unpress_after = {unpress_after_flag}")
                    print("    Note: This affects new /Fret messages only")
                    
                elif flag_name == "force_adjustment_only":
                    # Parser-level flag for force testing
                    global force_adjustment_only_flag
                    force_adjustment_only_flag = bool(flag_value)
                    print(f"  ✓ Set force_adjustment_only = {force_adjustment_only_flag}")
                    print("    Note: This affects new /Fret messages only")

                elif flag_name == "direct_press":
                    # Skip the -650 unpress waypoint; presser goes current→target directly
                    global direct_press_flag
                    direct_press_flag = bool(flag_value)
                    print(f"  ✓ Set direct_press = {direct_press_flag}")
                    print("    True  → presser ramps current→target simultaneously with slider")
                    print("    False → UNPRESS (→-650) then SLIDE then PRESS (default)")

                elif flag_name == "unpress_after_points":
                    try:
                        value = int(flag_value)
                        if value > 0:
                            tu.PRESSER_UNPRESS_AFTER_POINTS = value
                            print(f"  ✓ Set tu.PRESSER_UNPRESS_AFTER_POINTS = {value}")
                            print(f"    Duration: {value * tu.TIME_STEP * 1000:.0f}ms")
                        else:
                            print(f"  ✗ Error: unpress_after_points must be > 0")
                    except ValueError:
                        print(f"  ✗ Error: Invalid int value: {flag_value}")

                # Numeric tuning parameters
                elif flag_name == "blend_percent":
                    try:
                        value = float(flag_value)
                        if 0.0 <= value <= 1.0:
                            tu.TRAJECTORY_BLEND_PERCENT = value
                            print(f"  ✓ Set tu.TRAJECTORY_BLEND_PERCENT = {value}")
                        else:
                            print(f"  ✗ Error: blend_percent must be 0.0-1.0 (got {value})")
                    except ValueError:
                        print(f"  ✗ Error: Invalid float value: {flag_value}")
                        
                elif flag_name == "presser_points":
                    try:
                        value = int(flag_value)
                        if value > 0:
                            tu.PRESSER_INTERPOLATION_POINTS = value
                            print(f"  ✓ Set tu.PRESSER_INTERPOLATION_POINTS = {value}")
                            print(f"    Duration: {value * tu.TIME_STEP * 1000:.1f}ms")
                        else:
                            print(f"  ✗ Error: presser_points must be > 0")
                    except ValueError:
                        print(f"  ✗ Error: Invalid int value: {flag_value}")
                        
                elif flag_name == "slider_points":
                    try:
                        value = int(flag_value)
                        if value > 0:
                            tu.LH_SLIDER_MOTION_POINTS = value
                            print(f"  ✓ Set tu.LH_SLIDER_MOTION_POINTS = {value}")
                            print(f"    Duration: {value * tu.TIME_STEP * 1000:.1f}ms")
                        else:
                            print(f"  ✗ Error: slider_points must be > 0")
                    except ValueError:
                        print(f"  ✗ Error: Invalid int value: {flag_value}")
                        
                elif flag_name == "picker_points":
                    try:
                        value = int(flag_value)
                        if value > 0:
                            tu.PICKER_PLUCK_MOTION_POINTS = value
                            print(f"  ✓ Set tu.PICKER_PLUCK_MOTION_POINTS = {value}")
                            print(f"    Duration: {value * tu.TIME_STEP * 1000:.1f}ms")
                        else:
                            print(f"  ✗ Error: picker_points must be > 0")
                    except ValueError:
                        print(f"  ✗ Error: Invalid int value: {flag_value}")
                        
                elif flag_name == "lh_prep_time":
                    try:
                        value = float(flag_value)
                        if value >= 0.0:
                            tu.LH_PREP_TIME_BEFORE_PICK = value
                            print(f"  ✓ Set tu.LH_PREP_TIME_BEFORE_PICK = {value}s")
                        else:
                            print(f"  ✗ Error: lh_prep_time must be >= 0")
                    except ValueError:
                        print(f"  ✗ Error: Invalid float value: {flag_value}")
                
                else:
                    print(f"  ✗ Unknown flag: {flag_name}")
                    print("    Available flags: graph, unpress_after, force_adjustment_only,")
                    print("                     direct_press, blend_percent, presser_points,")
                    print("                     unpress_after_points, slider_points, picker_points,")
                    print("                     lh_prep_time")
                
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error in config_processor: {e}")
            traceback.print_exc()
        
        time.sleep(0.001)

def reset_processor():
    """Process /Reset messages to return motors to initial positions."""
    while True:
        try:
            while not reset_queue.empty():
                reset_data = reset_queue.get_nowait()
                print(f"Processing /Reset message: {reset_data}")
                
                # Use the tracked robot position to create smooth trajectory to initial_point
                global last_robot_position
                
                print("Generating reset trajectory to initial positions...")
                print(f"Current robot position (last endpoint): {last_robot_position}")
                print(f"Target positions: {tu.initial_point}")
                
                # PHASE 1: Safely unpress all pressers first (motors 6-11)
                # This prevents string damage from moving sliders while pressed
                unpress_points = 400  # ~2000ms to unpress #TODO: magic numbers
                unpress_trajectory = np.zeros((unpress_points, 15))
                
                for motor in range(15):
                    q0 = last_robot_position[motor]
                    
                    if 6 <= motor <= 11:  # Pressers
                        # Move to unpressed position
                        qf = tu.LH_PRESSER_UNPRESSED_POS
                    else:  # Sliders and pickers
                        # Hold current position
                        qf = q0
                    
                    motor_traj = GuitarBotParser.interp_with_blend(
                        q0, qf, unpress_points, tu.TRAJECTORY_BLEND_PERCENT
                    )
                    unpress_trajectory[:, motor] = motor_traj
                
                print(f"  Phase 1: Unpressing pressers ({unpress_points} points, {unpress_points * 5}ms)...")
                
                # PHASE 2: Home sliders and pickers while keeping pressers unpressed
                home_points = 200  # ~1.0 seconds for smooth homing
                home_trajectory = np.zeros((home_points, 15))
                
                # Starting position is the end of phase 1
                phase1_end = unpress_trajectory[-1, :]
                
                for motor in range(15):
                    q0 = phase1_end[motor]
                    qf = tu.initial_point[motor]
                    
                    motor_traj = GuitarBotParser.interp_with_blend(
                        q0, qf, home_points, tu.TRAJECTORY_BLEND_PERCENT
                    )
                    home_trajectory[:, motor] = motor_traj
                
                print(f"  Phase 2: Homing sliders and pickers ({home_points} points, {home_points * 5}ms)...")
                
                # Combine both phases
                reset_trajectory = np.vstack([unpress_trajectory, home_trajectory])
                
                print(f"Generated reset trajectory: {reset_trajectory.shape}")
                print(f"  Total duration: {reset_trajectory.shape[0] * 5}ms")
                print(f"Waiting for active trajectory to finish before resetting...")
                
                # Acquire lock to ensure no other trajectory is running.
                # This blocks until any active /RLFret, /Fret, /Dyn, or song
                # trajectory completes — preventing mid-trajectory interruption.
                with robot_lock:
                    print(f"Executing safe reset motion...")
                    RobotController.main(reset_trajectory)
                
                # Update last robot position and reset parser states
                last_robot_position = tu.initial_point.copy()
                rh_parser.reset_positions()
                lh_parser.reset_positions()
                both_hands_parser.reset_all()
                print("Reset complete. Robot and parsers at initial positions.")
                
                print("Reset complete. All motors returned to initial positions.")
                
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error in reset_processor: {e}")
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
                    with robot_lock:
                        RobotController.main(song_trajectories_list)
                    
                    # Update last robot position
                    global last_robot_position
                    last_robot_position = song_trajectories_list[-1, :].copy()
                    print(f"Updated last_robot_position after song")

        except queue.Empty:
            pass
        time.sleep(0.001)

def cleanup_and_reset():
    """Send reset trajectory to robot before program exits."""
    try:
        global last_robot_position
        
        print("\n" + "="*60)
        print("SHUTDOWN - Resetting robot to safe state")
        print("="*60)
        
        # Generate smooth trajectory from current position to initial_point
        print(f"Current robot position: {last_robot_position[:3]}...")
        print(f"Target initial position: {tu.initial_point[:3]}...")
        
        # PHASE 1: Safely unpress all pressers first
        unpress_points = 100  # ~500ms
        unpress_trajectory = np.zeros((unpress_points, 15))
        
        for motor in range(15):
            q0 = last_robot_position[motor]
            
            if 6 <= motor <= 11:  # Pressers
                qf = tu.LH_PRESSER_UNPRESSED_POS
            else:  # Sliders and pickers - hold position
                qf = q0
            
            motor_traj = GuitarBotParser.interp_with_blend(
                q0, qf, unpress_points, tu.TRAJECTORY_BLEND_PERCENT
            )
            unpress_trajectory[:, motor] = motor_traj
        
        print(f"Phase 1: Unpressing pressers ({unpress_points * 5}ms)...")
        
        # PHASE 2: Home sliders and pickers
        home_points = 200  # ~1.0 seconds
        home_trajectory = np.zeros((home_points, 15))
        phase1_end = unpress_trajectory[-1, :]
        
        for motor in range(15):
            q0 = phase1_end[motor]
            qf = tu.initial_point[motor]
            motor_traj = GuitarBotParser.interp_with_blend(
                q0, qf, home_points, tu.TRAJECTORY_BLEND_PERCENT
            )
            home_trajectory[:, motor] = motor_traj
        
        print(f"Phase 2: Homing sliders and pickers ({home_points * 5}ms)...")
        
        # Combine phases
        reset_trajectory = np.vstack([unpress_trajectory, home_trajectory])
        
        print(f"Sending safe reset trajectory ({reset_trajectory.shape[0]} points, {reset_trajectory.shape[0] * 5}ms total)...")
        print("Waiting for active trajectory to complete before shutdown reset...")
        with robot_lock:
            RobotController.main(reset_trajectory)
        
        print("Reset complete. Motors at safe initial positions.")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"Error during cleanup reset: {e}")
        traceback.print_exc()

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

    rlfret_thread = threading.Thread(target=rlfret_processor, daemon=True)
    rlfret_thread.start()

    reset_thread = threading.Thread(target=reset_processor, daemon=True)
    reset_thread.start()

    config_thread = threading.Thread(target=config_processor, daemon=True)
    config_thread.start()

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
    print("  /RLFret - RL low-level fret + pluck (fractional frets, raw torque)")
    print("    Format: /RLFret <string_idx> <fret_position> <torque> [pluck_velocity]")
    print("      string_idx: 0, 2, or 4 (strings with pluckers)")
    print("      fret_position: 0.0-9.0 (fractional fret, e.g., 4.0, 5.5, 7.0)")
    print("      torque: 0-1000 (fretting pressure, 100=light, 400=normal)")
    print("      pluck_velocity: 0-127 (optional, defaults to state toggle)")
    print("    Examples:")
    print("      /RLFret 0 4.0 100       - String 0, fret 4 harmonic, light touch")
    print("      /RLFret 2 5.0 150       - String 2, fret 5 harmonic, light touch")
    print("      /RLFret 4 7.0 100 80    - String 4, fret 7, light touch, velocity 80")
    print("")
    print("  /Reset - Return all motors to initial positions")
    print("    Format:")
    print("      /Reset                  - Resets all parser states and moves motors home")
    print("")
    print("  /Config - Update runtime configuration flags")
    print("    Format:")
    print("      /Config \"graph\" True               - Enable/disable trajectory plotting")
    print("      /Config \"unpress_after\" True       - Release presser after pluck")
    print("      /Config \"direct_press\" True        - Skip -650 waypoint; presser current→target direct")
    print("      /Config \"unpress_after_points\" 60  - Points for slow presser release (60=300ms)")
    print("      /Config \"blend_percent\" 0.3        - Set trajectory blend (0.0-1.0)")
    print("      /Config \"presser_points\" 15        - Set presser motion points")
    print("      /Config \"slider_points\" 50         - Set slider motion points")
    print("      /Config \"picker_points\" 20         - Set picker pluck points")
    print("      /Config \"lh_prep_time\" 0.5         - Set LH prep time (seconds)")
    print("    Available flags: graph, unpress_after, force_adjustment_only,")
    print("                     direct_press, unpress_after_points, blend_percent,")
    print("                     presser_points, slider_points, picker_points, lh_prep_time")
    print("")
    print("NOTE: Robot will automatically reset to safe positions on program exit.")
    print("")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nCtrl+C detected - shutting down...")
        cleanup_and_reset()
        print("Program stopped.")
