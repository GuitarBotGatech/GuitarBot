"""
LeftHandParser.py - Left hand trajectory generation for fretting calibration

Handles /Fret OSC messages to test left hand fretting motor dynamics.
Focuses purely on fretting robotics - trajectory generation and motor control.

Motor Layout (Left Hand - First 12 motors of 15-motor array):
- Motors 0-5: Slider motors (one per string, move to fret positions)  
- Motors 6-11: Presser motors (one per string, press onto frets)

/Fret Message Format:
- midi_note_number: MIDI note (40-68, mapped to string/fret)
- presser_force: Force level (0.0-1.0, optional)

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
    
    def get_presser_torque(self, string_id, fret_num, presser_force=None):
        """
        Get presser torque command for string/fret combination.
        
        Torque-based control:
        - Positive value: Motor applies force (torque as % of rated capacity * 1000)
        - Zero: Motor is idle/holding
        - Inspired by slide_toggle behavior in GuitarBotParser
        
        The presser_force parameter (0.0-1.0) scales the target torque:
        - force=1.0 → full torque (LH_PRESSER_PRESSED_POS = 500)
        - force=0.5 → half torque (250)
        - force=None → full torque (default)
        
        Args:
            string_id: String index (0-5)
            fret_num: Fret number (0 for open, 1+ for frets)
            presser_force: Force level 0.0-1.0 (None = full force)
            
        Returns:
            Presser torque command (0 = idle, up to 500 = apply force)
        """
        if fret_num == 0:  # Open string - no pressure needed
            return 0  # Idle
        
        # Scale torque based on force parameter
        max_torque = tu.LH_PRESSER_PRESSED_POS  # e.g., 500
        
        if presser_force is not None:
            # Clamp force to valid range
            force_factor = max(0.1, min(1.0, presser_force))
            torque = int(max_torque * force_factor)
        else:
            # Default to full torque
            torque = max_torque
        
        return torque
    
    def generate_fret_trajectory(self, string_id, fret_num, presser_force=None, 
                                num_points=tu.PRESSER_INTERPOLATION_POINTS * 10,
                                timestamp=0.0,
                                force_adjustment_only=False):
        """
        Generate trajectory for fretting a single string at a specific fret.
        
        TORQUE-BASED CONTROL (inspired by slide_toggle):
        - Presser commands are TORQUE values, not positions
        - Positive value = motor applies force
        - Zero = motor is idle/holding position
        - -650 = motor is unpressing

        Two modes:
        1. Normal fretting (force_adjustment_only=False):
           Phase 1: Unpress (torque → -650)
           Phase 2: Slide (torque = 0, slider moves)
           Phase 3: Press (torque → increase → 0 (stops increasing))
           
        2. Force adjustment (force_adjustment_only=True):
           Single phase: Torque increment (current → target)
           
        Args:
            string_id: String index (0-5)
            fret_num: Fret number (0=open, 1-24=frets)
            presser_force: Optional force level (0.0-1.0)
            num_points: Points per trajectory phase
            timestamp: When this fret should start (in seconds)
            force_adjustment_only: If True, increment torque without releasing (for force tests)
            
        Returns:
            2D numpy array [num_timesteps x 12] with LH motor trajectories
        """
        print(f"Generating fret trajectory: String {string_id}, Fret {fret_num}, Force: {presser_force}, Timestamp: {timestamp}, Force-only: {force_adjustment_only}")
        
        # Calculate target positions using EXACT same logic as GuitarBotParser
        slider_motor_id = string_id
        presser_motor_id = string_id + 6
        
        target_slider_pos = self.string_fret_to_slider_position(string_id, fret_num)
        target_presser_torque = self.get_presser_torque(string_id, fret_num, presser_force)
        
        # Get current positions
        current_slider_pos = self.current_positions[slider_motor_id]
        current_presser_torque = self.current_positions[presser_motor_id]
        
        # Check if we're already on the correct fret and just adjusting force
        current_fret = self.string_states[string_id]['fret']
        same_fret = (current_fret == fret_num and fret_num > 0)
        
        # FORCE TESTING MODE: Simplified trajectories
        # - If force=0: Unpress completely (go to LH_PRESSER_UNPRESSED_POS)
        # - If force>0 and same fret: Just adjust torque (no unpress/slide)
        # - If force>0 and different fret: Slide to new fret, then apply torque
        if force_adjustment_only:
            if fret_num == 0:
                # Special case: force=0 means unpress completely
                print(f"  Force adjustment mode: Unpressing (torque → {tu.LH_PRESSER_UNPRESSED_POS})")
                return self._generate_simple_trajectory(
                    string_id, fret_num,
                    slider_motor_id, presser_motor_id,
                    current_slider_pos, current_presser_torque,
                    target_slider_pos, tu.LH_PRESSER_UNPRESSED_POS,
                    num_points, timestamp, presser_force
                )
            elif same_fret:
                # Same fret, just adjust force duration (no unpressing)
                print(f"  Force adjustment mode: Force={presser_force} (controls hold duration)")
                return self._generate_simple_trajectory(
                    string_id, fret_num,
                    slider_motor_id, presser_motor_id,
                    current_slider_pos, current_presser_torque,
                    target_slider_pos, target_presser_torque,
                    num_points, timestamp, presser_force
                )
            else:
                # Different fret: Need to slide, but keep it simple
                # Go to idle (0) → slide → apply torque
                print(f"  Force adjustment mode: Fret {current_fret} → {fret_num}, force={presser_force}")
                return self._generate_simple_fret_change(
                    string_id, fret_num,
                    slider_motor_id, presser_motor_id,
                    current_slider_pos, current_presser_torque,
                    target_slider_pos, target_presser_torque,
                    num_points, timestamp, presser_force
                )
        
        # Calculate total trajectory duration to size array properly
        # 3 phases: UNPRESS + SLIDE + PRESS (ends at target torque)
        # NOTE: No hold phase - ends immediately at target torque
        total_points = num_points + tu.LH_SINGLE_NOTE_MOTION_POINTS + num_points
        duration = total_points * tu.TIME_STEP
        buffer = 100 * tu.TIME_STEP
        num_rows = int((timestamp + duration + buffer) / tu.TIME_STEP)
        
        # Initialize trajectory array with NaN (will forward-fill later, mimicking GuitarBotParser)
        trajectory_array = np.full((num_rows, 12), np.nan)
        trajectory_array[0, :] = self.current_positions
        
        # Calculate start index from timestamp
        start_index = int(timestamp / tu.TIME_STEP)
        
        # EXACT replication of GuitarBotParser.lh_interpolate 'note' event logic (lines 301-366)
        # BUT using TORQUE for presser instead of position
        slider_points, presser_points = [], []
        q0_slider_motor = current_slider_pos
        q0_presser_torque = current_presser_torque
        qf_slider = int(target_slider_pos)
        qf_presser_torque = target_presser_torque
        
        # For open strings (fret 0), use special logic
        if fret_num == 0:
            qf_slider = q0_slider_motor
            qf_presser_torque = 0  # Idle torque
        
        # Use standard non-slide fretting (like slide_toggle=False)
        # Phase 1: UNPRESS (release torque to 0 = idle)
        s1 = GuitarBotParser.interp_with_blend(q0_slider_motor, q0_slider_motor, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        p1 = GuitarBotParser.interp_with_blend(q0_presser_torque, 0, num_points, tu.TRAJECTORY_BLEND_PERCENT)  # Torque → 0
        slider_points.extend(s1)
        presser_points.extend(p1)
        
        # Phase 2: SLIDE (slider moves while presser is idle at 0 torque)
        s2 = GuitarBotParser.interp_with_blend(q0_slider_motor, qf_slider, tu.LH_SINGLE_NOTE_MOTION_POINTS, tu.TRAJECTORY_BLEND_PERCENT)
        p2 = GuitarBotParser.interp_with_blend(0, 0, tu.LH_SINGLE_NOTE_MOTION_POINTS, tu.TRAJECTORY_BLEND_PERCENT)  # Keep at 0
        slider_points.extend(s2)
        presser_points.extend(p2)
        
        # Phase 3: PRESS (apply target torque, ends here)
        # Trajectory ENDS at target torque - REST phase handled by BothHandsParser
        s3 = GuitarBotParser.interp_with_blend(qf_slider, qf_slider, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        p3 = GuitarBotParser.interp_with_blend(0, qf_presser_torque, num_points, tu.TRAJECTORY_BLEND_PERCENT)  # 0 → target
        slider_points.extend(s3)
        presser_points.extend(p3)
        
        # Write to trajectory array (mimicking GuitarBotParser lines 354-366)
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
        
        # Forward-fill NaN values (mimicking GuitarBotParser line 370)
        df = pd.DataFrame(trajectory_array)
        df.ffill(inplace=True)
        trajectory_array = df.to_numpy()
        
        # Update state tracking
        self.string_states[string_id] = {'fret': fret_num, 'pressed': fret_num > 0}
        
        print(f"Generated trajectory: 3 phases (UNPRESS→SLIDE→PRESS)")
        print(f"  Target torque: {qf_presser_torque}, Array shape: {trajectory_array.shape}")
        print(f"  Final positions - Slider: {self.current_positions[slider_motor_id]}, Presser: {self.current_positions[presser_motor_id]}")
        print(f"  NOTE: Ends at target torque ({qf_presser_torque}). REST phase handled by BothHandsParser after pluck.")
        
        return trajectory_array
    def _generate_force_adjustment_trajectory_torque(self, slider_motor_id, presser_motor_id,
                                                    current_slider_pos, current_torque,
                                                    target_slider_pos, target_torque,
                                                    num_points, timestamp):
        """
        Generate trajectory for adjusting presser TORQUE without releasing.
        Inspired by slide_toggle behavior - maintains engagement while changing force.
        
        Args:
            slider_motor_id: Slider motor index
            presser_motor_id: Presser motor index
            current_slider_pos: Current slider position
            current_torque: Current presser torque
            target_slider_pos: Target slider position (usually unchanged)
            target_torque: Target presser torque
            num_points: Number of interpolation points
            timestamp: Start time
            
        Returns:
            2D numpy array [num_timesteps x 12] with trajectory
        """
        # Single phase: smoothly transition torque while maintaining engagement
        total_points = num_points
        duration = total_points * tu.TIME_STEP
        buffer = 100 * tu.TIME_STEP
        num_rows = int((timestamp + duration + buffer) / tu.TIME_STEP)
        
        # Initialize trajectory
        trajectory_array = np.full((num_rows, 12), np.nan)
        trajectory_array[0, :] = self.current_positions
        
        start_index = int(timestamp / tu.TIME_STEP)
        
        # Generate smooth torque transition (like slide_toggle maintains torque during motion)
        torque_points = GuitarBotParser.interp_with_blend(
            current_torque,
            target_torque,
            num_points,
            tu.TRAJECTORY_BLEND_PERCENT
        )
        
        # Slider stays at current position
        slider_points = [current_slider_pos] * num_points
        
        # Write to trajectory array
        if start_index + num_points <= num_rows:
            trajectory_array[start_index: start_index + num_points, slider_motor_id] = slider_points
            trajectory_array[start_index: start_index + num_points, presser_motor_id] = torque_points
            self.current_positions[slider_motor_id] = slider_points[-1]
            self.current_positions[presser_motor_id] = torque_points[-1]
        else:
            safe_points = num_rows - start_index
            if safe_points > 0:
                trajectory_array[start_index:, slider_motor_id] = slider_points[:safe_points]
                trajectory_array[start_index:, presser_motor_id] = torque_points[:safe_points]
                self.current_positions[slider_motor_id] = slider_points[safe_points - 1]
                self.current_positions[presser_motor_id] = torque_points[safe_points - 1]
        
        # Forward-fill NaN values
        df = pd.DataFrame(trajectory_array)
        df.ffill(inplace=True)
        trajectory_array = df.to_numpy()
        
        print(f"  Torque adjustment: {current_torque:.1f} → {target_torque:.1f} over {duration:.3f}s ({num_points} points)")
        
        return trajectory_array
    
    def _generate_simple_trajectory(self, string_id, fret_num,
                                   slider_motor_id, presser_motor_id,
                                   current_slider_pos, current_torque,
                                   target_slider_pos, target_torque,
                                   num_points, timestamp, presser_force=None):
        """
        Generate simple trajectory for force testing.
        
        For force testing, applies target torque and ends there.
        Force parameter affects the target torque magnitude.
        
        Pattern: 0 → target_torque (ends here)
        
        Args:
            string_id: String index (0-5)
            fret_num: Target fret number
            slider_motor_id: Slider motor index
            presser_motor_id: Presser motor index
            current_slider_pos: Current slider position
            current_torque: Current presser torque (ignored for force testing, starts from 0)
            target_slider_pos: Target slider position
            target_torque: Target presser torque (scaled by force, or LH_PRESSER_UNPRESSED_POS for unpressing)
            num_points: Number of interpolation points
            timestamp: Start time
            presser_force: Force level (0.0-1.0) affects target_torque magnitude
            
        Returns:
            2D numpy array [num_timesteps x 12] with trajectory
        """
        # Special case: If target is unpressed position, just do single phase
        is_unpressing = (target_torque == tu.LH_PRESSER_UNPRESSED_POS)
        
        # Single phase: ramp to target
        total_points = num_points
        
        duration = total_points * tu.TIME_STEP
        buffer = 100 * tu.TIME_STEP
        num_rows = int((timestamp + duration + buffer) / tu.TIME_STEP)
        
        # Initialize trajectory
        trajectory_array = np.full((num_rows, 12), np.nan)
        trajectory_array[0, :] = self.current_positions
        
        start_index = int(timestamp / tu.TIME_STEP)
        
        slider_points = []
        torque_points = []
        
        if is_unpressing:
            # Single phase: smooth transition to unpressed
            slider_points = GuitarBotParser.interp_with_blend(
                current_slider_pos,
                target_slider_pos,
                num_points,
                tu.TRAJECTORY_BLEND_PERCENT
            )
            
            torque_points = GuitarBotParser.interp_with_blend(
                current_torque,
                target_torque,
                num_points,
                tu.TRAJECTORY_BLEND_PERCENT
            )
        else:
            # Single phase: PRESS - Apply target torque (0 → target)
            # Trajectory ENDS here - REST phase handled by BothHandsParser
            s1 = GuitarBotParser.interp_with_blend(
                current_slider_pos,
                target_slider_pos,
                num_points,
                tu.TRAJECTORY_BLEND_PERCENT
            )
            t1 = GuitarBotParser.interp_with_blend(
                0,  # Start from idle (0)
                target_torque,  # Press to target torque
                num_points,
                tu.TRAJECTORY_BLEND_PERCENT
            )
            slider_points.extend(s1)
            torque_points.extend(t1)
        
        # Write to trajectory array
        num_generated_points = len(slider_points)
        if start_index + num_generated_points <= num_rows:
            trajectory_array[start_index: start_index + num_generated_points, slider_motor_id] = slider_points
            trajectory_array[start_index: start_index + num_generated_points, presser_motor_id] = torque_points
            self.current_positions[slider_motor_id] = slider_points[-1]
            self.current_positions[presser_motor_id] = torque_points[-1]
        else:
            safe_points = num_rows - start_index
            if safe_points > 0:
                trajectory_array[start_index:, slider_motor_id] = slider_points[:safe_points]
                trajectory_array[start_index:, presser_motor_id] = torque_points[:safe_points]
                self.current_positions[slider_motor_id] = slider_points[safe_points - 1]
                self.current_positions[presser_motor_id] = torque_points[safe_points - 1]
        
        # Forward-fill NaN values
        df = pd.DataFrame(trajectory_array)
        df.ffill(inplace=True)
        trajectory_array = df.to_numpy()
        
        # Update state tracking
        self.string_states[string_id] = {'fret': fret_num, 'pressed': not is_unpressing}
        
        if is_unpressing:
            print(f"  Simple trajectory (unpress): Torque {current_torque:.1f}→{target_torque:.1f}")
        else:
            print(f"  Simple trajectory: 0 → {target_torque} (ends at target torque)")
        
        return trajectory_array
    
    def _generate_simple_fret_change(self, string_id, fret_num,
                                    slider_motor_id, presser_motor_id,
                                    current_slider_pos, current_torque,
                                    target_slider_pos, target_torque,
                                    num_points, timestamp, presser_force=None):
        """
        Generate trajectory for changing frets during force testing.
        
        Force parameter affects target torque magnitude.
        
        Pattern: current → 0 → (slide) → 0 → target_torque (ends here)
        NOTE: REST phase is handled by BothHandsParser AFTER pluck
        
        Phase 1: Release to idle (current_torque → 0)
        Phase 2: Slide (slider moves, torque = 0)
        Phase 3: Apply target torque (0 → target_torque) - ENDS HERE
        
        Args:
            string_id: String index (0-5)
            fret_num: Target fret number
            slider_motor_id: Slider motor index
            presser_motor_id: Presser motor index
            current_slider_pos: Current slider position
            current_torque: Current presser torque
            target_slider_pos: Target slider position
            target_torque: Target presser torque (scaled by force)
            num_points: Number of interpolation points per phase
            timestamp: Start time
            presser_force: Force level (0.0-1.0) affects target_torque
            
        Returns:
            2D numpy array [num_timesteps x 12] with trajectory
        """
        # 3 phases for fret change: RELEASE + SLIDE + PRESS (ends at target torque)
        total_points = num_points * 3
        duration = total_points * tu.TIME_STEP
        buffer = 100 * tu.TIME_STEP
        num_rows = int((timestamp + duration + buffer) / tu.TIME_STEP)
        
        # Initialize trajectory
        trajectory_array = np.full((num_rows, 12), np.nan)
        trajectory_array[0, :] = self.current_positions
        
        start_index = int(timestamp / tu.TIME_STEP)
        
        slider_points, presser_points = [], []
        
        # Phase 1: Release to idle (0 torque)
        s1 = GuitarBotParser.interp_with_blend(current_slider_pos, current_slider_pos, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        p1 = GuitarBotParser.interp_with_blend(current_torque, 0, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        slider_points.extend(s1)
        presser_points.extend(p1)
        
        # Phase 2: Slide to new fret (torque stays at 0)
        s2 = GuitarBotParser.interp_with_blend(current_slider_pos, target_slider_pos, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        p2 = GuitarBotParser.interp_with_blend(0, 0, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        slider_points.extend(s2)
        presser_points.extend(p2)
        
        # Phase 3: PRESS - Apply target torque (0 → target_torque)
        # Trajectory ENDS here - REST phase handled by BothHandsParser
        s3 = GuitarBotParser.interp_with_blend(target_slider_pos, target_slider_pos, num_points, tu.TRAJECTORY_BLEND_PERCENT)
        p3 = GuitarBotParser.interp_with_blend(0, target_torque, num_points, tu.TRAJECTORY_BLEND_PERCENT)
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
        
        print(f"  Fret change: Release → Slide → 0 → {target_torque} (ends at target torque, 3 phases)")
        
        return trajectory_array
    
    def parse_fret_message(self, midi_note_number, presser_force=None, timestamp=0.0, force_adjustment_only=False):
        """
        Parse a /Fret OSC message and generate fretting trajectory.
        
        Args:
            midi_note_number: MIDI note number (40-68 based on STRING_MIDI_RANGES)
            presser_force: Optional force level (0.0-1.0)
            timestamp: When this fret should start (in seconds)
            force_adjustment_only: If True, only adjust force without unpressing (for force tests)
            
        Returns:
            2D numpy array [num_timesteps x 12] with LH motor trajectories
        """
        print(f"Processing /Fret message: MIDI Note {midi_note_number}, Force {presser_force}, Timestamp {timestamp}, Force-only: {force_adjustment_only}")
        
        # Validate MIDI note number and map to string/fret
        string_fret_info = self.midi_note_to_string_fret(midi_note_number)
        if not string_fret_info:
            print(f"Error: MIDI note {midi_note_number} not playable on available strings.")
            return np.array([])
        
        string_id, fret_num = string_fret_info
        
        # Validate inputs
        if presser_force is not None and not (0.0 <= presser_force <= 1.0):
            print(f"Error: Invalid presser_force {presser_force}. Must be 0.0-1.0.")
            return np.array([])

        # TODO: 15 x N trajectory array that preserves state.
        # TODO: Get encoder state from arduino and save that.
        # Generate fretting trajectory
        trajectory = self.generate_fret_trajectory(
            string_id, fret_num, presser_force, 
            timestamp=timestamp,
            force_adjustment_only=force_adjustment_only
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
        
        Note: 'presser_torque' represents torque commands (0=idle, >0=apply force),
        not absolute positions. This reflects the actual control model used by the
        embedded controller.
        """
        status = {
            'motor_positions': self.current_positions.copy(),
            'string_states': self.string_states.copy()
        }
        
        # Add human-readable info
        for string_id in range(6):
            slider_pos = self.current_positions[string_id]
            presser_torque = self.current_positions[string_id + 6]  # This is a torque value
            fret_num = self.string_states[string_id]['fret']
            
            status[f'string_{string_id}'] = {
                'fret': fret_num,
                'slider_position': slider_pos,
                'presser_torque': presser_torque,  # Renamed to clarify it's torque, not position
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
    
    # Test MIDI note 45 (5th fret on Low E) with specific force at timestamp 0.5
    trajectory_fret5 = parser.parse_fret_message(midi_note_number=45, presser_force=0.8, timestamp=0.5)
    print(f"MIDI 45 (Low E 5th fret): {trajectory_fret5.shape}")
    
    # Test MIDI note 52 (D string) at timestamp 1.0
    trajectory_d_string = parser.parse_fret_message(midi_note_number=52, presser_force=0.6, timestamp=1.0)
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