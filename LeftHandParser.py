"""
LeftHandParser.py - Left hand trajectory generation for fretting calibration

Handles /Fret OSC messages to test left hand fretting motor dynamics.
Focuses purely on fretting robotics - trajectory generation and motor control.

Motor Layout (Left Hand - First 12 motors of 15-motor array):
- Motors 0-5: Slider motors (one per string, move to fret positions)  
- Motors 6-11: Presser motors (one per string, press onto frets)

/Fret Message Format:
- midi_note_number: MIDI note (40-68, mapped to string/fret)
- presser_position: Presser position in encoder ticks (optional, uses default if not specified)

Control Model:
This parser uses POSITION-BASED CONTROL for presser motors. The presser_position
parameter directly specifies the encoder position (depth) the presser motor should
move to. This allows for intuitive control and optimization of presser depth at
each fret position.

Note: Right-hand plucking functionality moved to RightHandParser.py
"""

import numpy as np
import pandas as pd
import copy
from GuitarBotParser import GuitarBotParser  # Import for reusing interp_with_blend
import tune as tu
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class LeftHandParser:
    def __init__(self):
        # Current state tracking for all 12 LH motors (use initial_point from tune.py)
        self.current_positions = tu.initial_point[:12].copy()  # First 12 motors only
        
        # String/fret state tracking 
        self.string_states = {i: {'fret': 0, 'pressed': False} for i in range(6)}
    
    def string_fret_to_slider_position(self, string_id, fret_num):
        """
        Convert string/fret combination to slider motor position.
        Uses the EXACT same formula as GuitarBotParser.parseleftMIDI()
        
        Args:
            string_id: String index (0-5)
            fret_num: Fret number (0 for open, 1+ for frets)
            
        Returns:
            Slider position in encoder ticks
        """
        if fret_num == 0:  # Open string
            return 0  # GuitarBotParser uses 0 for open strings
        
        if fret_num > len(tu.SLIDER_MM_PER_FRET):
            print(f"Warning: Fret {fret_num} exceeds calibrated range")
            fret_num = len(tu.SLIDER_MM_PER_FRET)
        
        # Get physical position from tune.py calibration
        fret_mm = tu.SLIDER_MM_PER_FRET[fret_num - 1]  # Array is 0-indexed, but fret 1 = index 0
        
        # EXACT formula from GuitarBotParser line 449:
        # encoder_values = [((v * 2048) / tu.MM_TO_ENCODER_CONVERSION_FACTOR + tu.SLIDER_ENCODER_OFFSET) for v in tu.SLIDER_MM_PER_FRET]
        # then multiplied by direction
        direction = tu.SLIDER_MOTOR_DIRECTION[string_id]
        final_position = ((fret_mm * 2048) / tu.MM_TO_ENCODER_CONVERSION_FACTOR + tu.SLIDER_ENCODER_OFFSET) * direction
        
        return int(final_position)
    
    def get_presser_position(self, string_id, fret_num, presser_position=None):
        """
        Get presser position command for string/fret combination.
        
        Position-based control:
        - UNPRESSED_POS: Motor is fully released (no contact)
        - PRESSED_POS: Motor presses string onto fret (standard position)
        - Custom position: For optimization, can specify exact encoder position
        
        Args:
            string_id: String index (0-5)
            fret_num: Fret number (0 for open, 1+ for frets)
            presser_position: Optional position override (encoder ticks, None uses default)
            
        Returns:
            Presser position command (encoder ticks)
        """
        if fret_num == 0:  # Open string - no pressure needed
            return tu.LH_PRESSER_UNPRESSED_POS
        
        # Use position parameter if provided, otherwise use default pressed position
        if presser_position is not None:
            # Direct position control for optimization experiments
            return round(presser_position, 3)
        else:
            # Use default pressed position
            return tu.LH_PRESSER_PRESSED_POS
    
    def generate_fret_trajectory(self, string_id, fret_num, presser_position=None, 
                                num_points=tu.PRESSER_INTERPOLATION_POINTS,
                                timestamp=0.0,
                                position_adjustment_only=False):
        """
        Generate trajectory for fretting a single string at a specific fret.
        
        POSITION-BASED CONTROL:
        - Presser commands are POSITION values (encoder ticks)
        - Motor moves to target position and holds
        - Position determines how far presser travels toward fret
        
        Two modes:
        1. Normal fretting (position_adjustment_only=False):
           Phase 1: Unpress (position → UNPRESSED_POS)
           Phase 2: Slide (position = UNPRESSED_POS, slider moves)
           Phase 3: Press (UNPRESSED_POS → target position)
           
        2. Position adjustment (position_adjustment_only=True):
           Single phase: Position increment (current → target)
           For optimizing presser depth at a specific fret
           
        Args:
            string_id: String index (0-5)
            fret_num: Fret number (0=open, 1-24=frets)
            presser_position: Optional position value (encoder ticks, None uses default)
            num_points: Points per trajectory phase
            timestamp: When this fret should start (in seconds)
            position_adjustment_only: If True, adjust position without unpressing (for optimization)
            
        Returns:
            2D numpy array [num_timesteps x 12] with LH motor trajectories
        """
        print(f"Generating fret trajectory: String {string_id}, Fret {fret_num}, Position: {presser_position}, Timestamp: {timestamp}, Position-only: {position_adjustment_only}")
        
        # Calculate target positions
        slider_motor_id = string_id
        presser_motor_id = string_id + 6
        
        target_slider_pos = self.string_fret_to_slider_position(string_id, fret_num)
        target_presser_pos = self.get_presser_position(string_id, fret_num, presser_position)
        
        # Get current positions
        current_slider_pos = self.current_positions[slider_motor_id]
        current_presser_pos = self.current_positions[presser_motor_id]
        
        # Check if we're already on the correct fret and just adjusting position
        current_fret = self.string_states[string_id]['fret']
        same_fret = (current_fret == fret_num and fret_num > 0)
        
        # POSITION OPTIMIZATION MODE: Simplified trajectories
        # - If position=UNPRESSED: Unpress completely
        # - If position>0 and same fret: Just adjust position (no unpress/slide)
        # - If position>0 and different fret: Slide to new fret, then apply position
        if position_adjustment_only:
            if fret_num == 0 or target_presser_pos == tu.LH_PRESSER_UNPRESSED_POS:
                # Special case: fret=0 or unpressed position means unpress completely
                print(f"  Position adjustment mode: Unpressing (position → {tu.LH_PRESSER_UNPRESSED_POS})")
                return self._generate_simple_trajectory(
                    string_id, fret_num,
                    slider_motor_id, presser_motor_id,
                    current_slider_pos, current_presser_pos,
                    target_slider_pos, tu.LH_PRESSER_UNPRESSED_POS,
                    num_points, timestamp
                )
            elif same_fret:
                # Same fret, just adjust position (no unpressing)
                print(f"  Position adjustment mode: Position {current_presser_pos:.1f} → {target_presser_pos:.1f}")
                return self._generate_simple_trajectory(
                    string_id, fret_num,
                    slider_motor_id, presser_motor_id,
                    current_slider_pos, current_presser_pos,
                    target_slider_pos, target_presser_pos,
                    num_points, timestamp
                )
            else:
                # Different fret: Need to slide, but keep it simple
                # Go to unpressed → slide → apply position
                print(f"  Position adjustment mode: Fret {current_fret} → {fret_num}, position {target_presser_pos:.1f}")
                return self._generate_simple_fret_change(
                    string_id, fret_num,
                    slider_motor_id, presser_motor_id,
                    current_slider_pos, current_presser_pos,
                    target_slider_pos, target_presser_pos,
                    num_points, timestamp
                )
        
        # Calculate total trajectory duration to size array properly
        total_points = num_points + tu.LH_SINGLE_NOTE_MOTION_POINTS + num_points
        duration = total_points * tu.TIME_STEP
        buffer = 100 * tu.TIME_STEP
        num_rows = int((timestamp + duration + buffer) / tu.TIME_STEP)
        
        # Initialize trajectory array with NaN (will forward-fill later)
        trajectory_array = np.full((num_rows, 12), np.nan)
        trajectory_array[0, :] = self.current_positions
        
        # Calculate start index from timestamp
        start_index = int(timestamp / tu.TIME_STEP)
        
        # Standard 3-phase fretting trajectory (position-based)
        slider_points, presser_points = [], []
        q0_slider_motor = current_slider_pos
        q0_presser_pos = current_presser_pos
        qf_slider = int(target_slider_pos)
        qf_presser_pos = target_presser_pos
        
        # For open strings (fret 0), use special logic
        if fret_num == 0:
            qf_slider = q0_slider_motor
            qf_presser_pos = tu.LH_PRESSER_UNPRESSED_POS
        
        # Use standard non-slide fretting
        # Phase 1: UNPRESS (release to UNPRESSED_POS)
        s1 = GuitarBotParser.interp_with_blend(q0_slider_motor, q0_slider_motor, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        p1 = GuitarBotParser.interp_with_blend(q0_presser_pos, tu.LH_PRESSER_UNPRESSED_POS, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        slider_points.extend(s1)
        presser_points.extend(p1)
        
        # Phase 2: SLIDE (slider moves while presser stays unpressed)
        s2 = GuitarBotParser.interp_with_blend(q0_slider_motor, qf_slider, tu.LH_SINGLE_NOTE_MOTION_POINTS, tu.TRAJECTORY_BLEND_PERCENT)
        p2 = GuitarBotParser.interp_with_blend(tu.LH_PRESSER_UNPRESSED_POS, tu.LH_PRESSER_UNPRESSED_POS, tu.LH_SINGLE_NOTE_MOTION_POINTS, tu.TRAJECTORY_BLEND_PERCENT)
        slider_points.extend(s2)
        presser_points.extend(p2)
        
        # Phase 3: PRESS (move to target position)
        s3 = GuitarBotParser.interp_with_blend(qf_slider, qf_slider, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        p3 = GuitarBotParser.interp_with_blend(tu.LH_PRESSER_UNPRESSED_POS, qf_presser_pos, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        slider_points.extend(s3)
        presser_points.extend(p3)
        
        # Write to trajectory array
        num_generated_points = len(slider_points)
        if start_index + num_generated_points <= num_rows:
            trajectory_array[start_index: start_index + num_generated_points, slider_motor_id] = slider_points
            trajectory_array[start_index: start_index + num_generated_points, presser_motor_id] = presser_points
            # Update current positions
            self.current_positions[slider_motor_id] = slider_points[-1]
            self.current_positions[presser_motor_id] = presser_points[-1]
        else:
            safe_points = num_rows - start_index
            if safe_points > 0:
                trajectory_array[start_index:, slider_motor_id] = slider_points[:safe_points]
                trajectory_array[start_index:, presser_motor_id] = presser_points[:safe_points]
                self.current_positions[slider_motor_id] = slider_points[safe_points - 1]
                self.current_positions[presser_motor_id] = presser_points[safe_points - 1]
        
        # Forward-fill NaN values
        df = pd.DataFrame(trajectory_array)
        df.ffill(inplace=True)
        trajectory_array = df.to_numpy()
        
        # Update state tracking
        self.string_states[string_id] = {'fret': fret_num, 'pressed': fret_num > 0}
        
        print(f"Generated trajectory array shape: {trajectory_array.shape}")
        print(f"Final positions - Slider: {self.current_positions[slider_motor_id]}, Presser: {self.current_positions[presser_motor_id]}")
        
        return trajectory_array
    def _generate_force_adjustment_trajectory_torque(self, slider_motor_id, presser_motor_id,
                                                    current_slider_pos, current_pos,
                                                    target_slider_pos, target_pos,
                                                    num_points, timestamp):
        """
        DEPRECATED: Use _generate_simple_trajectory instead.
        
        This method was for torque-based control. Now using position-based control.
        Kept for backward compatibility but should not be called.
        """
        print("Warning: _generate_force_adjustment_trajectory_torque is deprecated. Use _generate_simple_trajectory.")
        return self._generate_simple_trajectory(
            0, 0,  # dummy string_id, fret_num
            slider_motor_id, presser_motor_id,
            current_slider_pos, current_pos,
            target_slider_pos, target_pos,
            num_points, timestamp
        )
    
    def _generate_simple_trajectory(self, string_id, fret_num,
                                   slider_motor_id, presser_motor_id,
                                   current_slider_pos, current_pos,
                                   target_slider_pos, target_pos,
                                   num_points, timestamp):
        """
        Generate simple trajectory for position optimization.
        
        For fret position optimization:
        Single phase: Apply target position (current → target)
        
        This allows testing different presser positions at the same fret
        to find the optimal depth for proper string contact.
        
        Args:
            string_id: String index (0-5)
            fret_num: Target fret number
            slider_motor_id: Slider motor index
            presser_motor_id: Presser motor index
            current_slider_pos: Current slider position
            current_pos: Current presser position
            target_slider_pos: Target slider position
            target_pos: Target presser position
            num_points: Number of interpolation points
            timestamp: Start time
            
        Returns:
            2D numpy array [num_timesteps x 12] with trajectory
        """
        # Single phase: smooth transition to target position
        total_points = num_points
        duration = total_points * tu.TIME_STEP
        buffer = 100 * tu.TIME_STEP
        num_rows = int((timestamp + duration + buffer) / tu.TIME_STEP)
        
        # Initialize trajectory
        trajectory_array = np.full((num_rows, 12), np.nan)
        trajectory_array[0, :] = self.current_positions
        
        start_index = int(timestamp / tu.TIME_STEP)
        
        # Generate smooth position transition
        slider_points = GuitarBotParser.interp_with_blend(
            current_slider_pos,
            target_slider_pos,
            num_points,
            tu.TRAJECTORY_BLEND_PERCENT
        )
        
        position_points = GuitarBotParser.interp_with_blend(
            current_pos,
            target_pos,
            num_points,
            tu.TRAJECTORY_BLEND_PERCENT
        )
        
        # Write to trajectory array
        num_generated_points = len(slider_points)
        if start_index + num_generated_points <= num_rows:
            trajectory_array[start_index: start_index + num_generated_points, slider_motor_id] = slider_points
            trajectory_array[start_index: start_index + num_generated_points, presser_motor_id] = position_points
            self.current_positions[slider_motor_id] = slider_points[-1]
            self.current_positions[presser_motor_id] = position_points[-1]
        else:
            safe_points = num_rows - start_index
            if safe_points > 0:
                trajectory_array[start_index:, slider_motor_id] = slider_points[:safe_points]
                trajectory_array[start_index:, presser_motor_id] = position_points[:safe_points]
                self.current_positions[slider_motor_id] = slider_points[safe_points - 1]
                self.current_positions[presser_motor_id] = position_points[safe_points - 1]
        
        # Forward-fill NaN values
        df = pd.DataFrame(trajectory_array)
        df.ffill(inplace=True)
        trajectory_array = df.to_numpy()
        
        # Update state tracking
        self.string_states[string_id] = {'fret': fret_num, 'pressed': target_pos > tu.LH_PRESSER_UNPRESSED_POS}
        
        print(f"  Simple trajectory: Position {current_pos:.1f}→{target_pos:.1f} over {duration:.3f}s")
        
        return trajectory_array
    
    def _generate_simple_fret_change(self, string_id, fret_num,
                                    slider_motor_id, presser_motor_id,
                                    current_slider_pos, current_pos,
                                    target_slider_pos, target_pos,
                                    num_points, timestamp):
        """
        Generate trajectory for changing frets during position optimization.
        
        Phase 1: Release to unpressed (position → UNPRESSED_POS)
        Phase 2: Slide (slider moves, position = UNPRESSED_POS)
        Phase 3: Apply target position (UNPRESSED_POS → target)
        
        Args:
            string_id: String index (0-5)
            fret_num: Target fret number
            slider_motor_id: Slider motor index
            presser_motor_id: Presser motor index
            current_slider_pos: Current slider position
            current_pos: Current presser position
            target_slider_pos: Target slider position
            target_pos: Target presser position
            num_points: Number of interpolation points per phase
            timestamp: Start time
            
        Returns:
            2D numpy array [num_timesteps x 12] with trajectory
        """
        # 3 phases for fret change
        total_points = num_points * 3
        duration = total_points * tu.TIME_STEP
        buffer = 100 * tu.TIME_STEP
        num_rows = int((timestamp + duration + buffer) / tu.TIME_STEP)
        
        # Initialize trajectory
        trajectory_array = np.full((num_rows, 12), np.nan)
        trajectory_array[0, :] = self.current_positions
        
        start_index = int(timestamp / tu.TIME_STEP)
        
        slider_points, presser_points = [], []
        
        # Phase 1: Release to unpressed
        s1 = GuitarBotParser.interp_with_blend(current_slider_pos, current_slider_pos, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        p1 = GuitarBotParser.interp_with_blend(current_pos, tu.LH_PRESSER_UNPRESSED_POS, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        slider_points.extend(s1)
        presser_points.extend(p1)
        
        # Phase 2: Slide to new fret (presser stays unpressed)
        s2 = GuitarBotParser.interp_with_blend(current_slider_pos, target_slider_pos, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        p2 = GuitarBotParser.interp_with_blend(tu.LH_PRESSER_UNPRESSED_POS, tu.LH_PRESSER_UNPRESSED_POS, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        slider_points.extend(s2)
        presser_points.extend(p2)
        
        # Phase 3: Apply target position
        s3 = GuitarBotParser.interp_with_blend(target_slider_pos, target_slider_pos, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        p3 = GuitarBotParser.interp_with_blend(tu.LH_PRESSER_UNPRESSED_POS, target_pos, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        slider_points.extend(s3)
        presser_points.extend(p3)
        
        # Write to trajectory array
        num_generated_points = len(slider_points)
        if start_index + num_generated_points <= num_rows:
            trajectory_array[start_index: start_index + num_generated_points, slider_motor_id] = slider_points
            trajectory_array[start_index: start_index + num_generated_points, presser_motor_id] = presser_points
            self.current_positions[slider_motor_id] = slider_points[-1]
            self.current_positions[presser_motor_id] = presser_points[-1]
        else:
            safe_points = num_rows - start_index
            if safe_points > 0:
                trajectory_array[start_index:, slider_motor_id] = slider_points[:safe_points]
                trajectory_array[start_index:, presser_motor_id] = presser_points[:safe_points]
                self.current_positions[slider_motor_id] = slider_points[safe_points - 1]
                self.current_positions[presser_motor_id] = presser_points[safe_points - 1]
        
        # Forward-fill NaN values
        df = pd.DataFrame(trajectory_array)
        df.ffill(inplace=True)
        trajectory_array = df.to_numpy()
        
        # Update state tracking
        self.string_states[string_id] = {'fret': fret_num, 'pressed': fret_num > 0}
        
        print(f"  Fret change: Release → Slide → Apply position {target_pos:.1f} (3 phases)")
        
        return trajectory_array
    
    def parse_fret_message(self, midi_note_number, presser_position=None, timestamp=0.0, position_adjustment_only=False):
        """
        Parse a /Fret OSC message and generate fretting trajectory.
        
        Args:
            midi_note_number: MIDI note number (40-68 based on STRING_MIDI_RANGES)
            presser_position: Optional position value (encoder ticks, None uses default)
            timestamp: When this fret should start (in seconds)
            position_adjustment_only: If True, only adjust position without unpressing (for optimization)
            
        Returns:
            2D numpy array [num_timesteps x 12] with LH motor trajectories
        """
        print(f"Processing /Fret message: MIDI Note {midi_note_number}, Position {presser_position}, Timestamp {timestamp}, Position-only: {position_adjustment_only}")
        
        # Validate MIDI note number and map to string/fret
        string_fret_info = self.midi_note_to_string_fret(midi_note_number)
        if not string_fret_info:
            print(f"Error: MIDI note {midi_note_number} not playable on available strings.")
            return np.array([])
        
        string_id, fret_num = string_fret_info
        
        # Validate inputs (presser_position is encoder ticks, can be any reasonable value)
        if presser_position is not None and presser_position < 0:
            print(f"Error: Invalid presser_position {presser_position}. Must be >= 0.")
            return np.array([])

        # Generate fretting trajectory
        trajectory = self.generate_fret_trajectory(
            string_id, fret_num, presser_position, 
            timestamp=timestamp,
            position_adjustment_only=position_adjustment_only
        )

        # Plot if graphing is enabled
        if tu.graph:
            print(f"Plotting trajectory for MIDI note {midi_note_number}")
            self.plot_trajectories(trajectory)
        
        return trajectory
    
    def midi_note_to_string_fret(self, midi_note):
        """
        Convert MIDI note number to string ID and fret number.
        
        Args:
            midi_note: MIDI note number
            
        Returns:
            Tuple (string_id, fret_num) or None if not playable
        """
        # Check each string's MIDI range
        for string_id, (low_note, high_note, direction) in enumerate(tu.STRING_MIDI_RANGES):
            if low_note <= midi_note <= high_note:
                # Calculate fret number: fret = midi_note - open_string_note
                fret_num = midi_note - low_note
                if 0 <= fret_num <= 24:  # Valid fret range
                    return (string_id, fret_num)
        
        return None  # Note not playable on any string
    

    
    def reset_positions(self):
        """Reset all LH motors to initial positions."""
        print("Resetting all LH motors to initial positions")
        self.current_positions = tu.initial_point[:12].copy()
        self.string_states = {i: {'fret': 0, 'pressed': False} for i in range(6)}
    
    def get_status(self):
        """
        Get current status of all LH motors and string states.
        
        Note: 'presser_position' represents encoder position values (0=unpressed, >0=pressed),
        reflecting the position-based control model used by the embedded controller.
        """
        status = {
            'motor_positions': self.current_positions.copy(),
            'string_states': self.string_states.copy()
        }
        
        # Add human-readable info
        for string_id in range(6):
            slider_pos = self.current_positions[string_id]
            presser_pos = self.current_positions[string_id + 6]  # This is a position value
            fret_num = self.string_states[string_id]['fret']
            
            status[f'string_{string_id}'] = {
                'fret': fret_num,
                'slider_position': slider_pos,
                'presser_position': presser_pos,  # Position-based control
                'pressed': self.string_states[string_id]['pressed']
            }
        
        return status
    
    def plot_trajectories(self, trajectory_array, title="Left Hand Trajectories"):
        """
        Plot LH motor trajectories with enhanced visualization.
        Expects trajectory_array to be a 2D numpy array [num_timesteps x 12]
        Mimics the plotting style from GuitarBotParser.parseAllMIDI()
        """
        if trajectory_array.size == 0 or trajectory_array.shape[1] < 12:
            print("Insufficient trajectory data for plotting")
            return
        
        # Create time axis (mimicking GuitarBotParser line 93)
        num_rows = trajectory_array.shape[0]
        timestamps = np.arange(0, num_rows * tu.TIME_STEP, tu.TIME_STEP)
        
        # Create figure (mimicking GuitarBotParser lines 94-107)
        fig = go.Figure()
        
        # Add a trace for each of the 12 LH motors
        for motor in range(12):
            motor_name = f'Slider {motor + 1}' if motor < 6 else f'Presser {motor-6 + 1}'
            fig.add_trace(
                go.Scatter(
                    x=timestamps, 
                    y=trajectory_array[:, motor], 
                    mode='lines', 
                    name=motor_name
                )
            )
        
        # Update layout (mimicking GuitarBotParser lines 103-108)
        fig.update_layout(
            title=title,
            xaxis_title='Time (s)',
            yaxis_title='Motor Position',
            legend_title='Motors'
        )
        fig.show()
    
# Example usage and testing  
if __name__ == "__main__":
    # Initialize parser
    parser = LeftHandParser()
    
    print("=== Left Hand Parser Test ===")
    
    # Test /Fret message processing with MIDI note numbers (fretting only)
    print("\nTesting /Fret message processing...")
    
    # Test MIDI note 40 (Low E open string) at timestamp 0.0
    trajectory_open = parser.parse_fret_message(midi_note_number=40, timestamp=0.0)
    print(f"MIDI 40 (Low E open): {trajectory_open.shape}")
    
    # Test MIDI note 45 (5th fret on Low E) with specific position at timestamp 0.5
    trajectory_fret5 = parser.parse_fret_message(midi_note_number=45, presser_position=400, timestamp=0.5)
    print(f"MIDI 45 (Low E 5th fret): {trajectory_fret5.shape}")
    
    # Test MIDI note 52 (D string) at timestamp 1.0
    trajectory_d_string = parser.parse_fret_message(midi_note_number=52, presser_position=350, timestamp=1.0)
    print(f"MIDI 52 (D string): {trajectory_d_string.shape}")
    
    # Test MIDI note 62 (B string) at timestamp 1.5
    trajectory_b_string = parser.parse_fret_message(midi_note_number=62, timestamp=1.5)
    print(f"MIDI 62 (B string): {trajectory_b_string.shape}")
    
    # Check status
    print("\nCurrent status:")
    status = parser.get_status()
    for string_id in range(6):
        string_info = status[f'string_{string_id}']
        print(f"String {string_id}: Fret {string_info['fret']}, Pressed: {string_info['pressed']}")
    
    # Reset all positions  
    parser.reset_positions()
    print("\nPositions reset to initial state.")
    
    print("=== Test Complete ===")