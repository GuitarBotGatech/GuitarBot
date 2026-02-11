"""
BothHandsParser.py - Coordinated left and right hand trajectory generation

Combines LeftHandParser and RightHandParser to generate complete 15-motor trajectories
for the GuitarBot. Handles /Fret messages with automatic synchronized plucking.

Motor Layout (15-motor array):
- Motors 0-5: Slider motors (left hand - move to fret positions)
- Motors 6-11: Presser motors (left hand - press onto frets)
- Motors 12-14: Picker motors (right hand - pluck strings)

Message Handling:
- /Fret [midi_note, force]: Fret a note AND pluck it
- /Dyn [midi_notes]: Pluck notes without fretting changes
- Automatic timing coordination between fretting and plucking

Features:
- Synchronized fretting + plucking trajectories
- Configurable pluck delay after fretting
- State preservation across both hands
- Complete 15-motor trajectory generation
"""

import numpy as np
import pandas as pd
from pathlib import Path
from LeftHandParser import LeftHandParser
from RightHandParser import RightHandParser
from GuitarBotParser import GuitarBotParser
import tune as tu
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class BothHandsParser:
    def __init__(self):
        """Initialize coordinated parser for both hands."""
        self.left_hand = LeftHandParser()
        self.right_hand = RightHandParser()
        
        # Timing configuration for coordination
        self.pluck_delay_after_press = tu.TIME_STEP * 5  # Delay pluck to allow fretter to settle
        self.settling_time = tu.TIME_STEP * 5  # Additional settling time before pluck starts
        
        print("=== BothHandsParser Initialized ===")
        print("Left Hand: 12 motors (sliders + pressers)")
        print("Right Hand: 3 motors (pickers)")
        print(f"Pluck delay: {self.pluck_delay_after_press:.3f}s after press")
        print(f"Settling time: {self.settling_time:.3f}s before pluck")
    
    def parse_fret_with_pluck(self, midi_note, presser_force=None, pluck_velocity=None, timestamp=0.0, force_adjustment_only=False, unpress_after=False):
        """
        Parse /Fret message and generate coordinated fretting + plucking trajectory.
        
        This is the main function for playing notes - it frets AND plucks automatically.
        
        Trajectory sequence:
        1. LH trajectory: UNPRESS → SLIDE → PRESS → HOLD (ends at target torque)
        2. Settling time (brief pause while string is pressed)
        3. RH pluck (pluck happens while string is still pressed)
        4. REST phase: presser returns to -650 (after pluck completes) - if unpress_after=True
        
        This ensures the pluck ALWAYS happens while the string is pressed.
        
        Args:
            midi_note: MIDI note number (40-68)
            presser_force: Force level 0.0-1.0 (affects target torque, None = full force 500)
            pluck_velocity: Optional pluck velocity (0-127, None = state toggle)
            timestamp: When the note should start (seconds)
            force_adjustment_only: If True, only adjust force without unpressing (for force tests)
            unpress_after: If True (default), presser returns to -650 after pluck for safety.
                          If False, presser stays at target torque after pluck.
            
        Returns:
            2D numpy array [num_timesteps x 15] with complete motor trajectories
        """
        print(f"\n{'='*60}")
        print(f"COORDINATED FRET + PLUCK")
        print(f"MIDI Note: {midi_note}, Force: {presser_force}, Velocity: {pluck_velocity}, Time: {timestamp}s")
        print(f"Force-only: {force_adjustment_only}, Unpress after: {unpress_after}")
        print(f"{'='*60}")
        
        # 1. Generate left hand fretting trajectory (12 motors)
        # This ends at target torque (500) - string is pressed
        lh_trajectory = self.left_hand.parse_fret_message(
            midi_note_number=midi_note,
            presser_force=presser_force,
            timestamp=timestamp,
            force_adjustment_only=force_adjustment_only
        )
        
        if lh_trajectory.size == 0:
            print("Error: Failed to generate left hand trajectory")
            return np.array([])
        
        # 2. Get string/fret info for the presser motor ID
        string_fret_info = self.left_hand.midi_note_to_string_fret(midi_note)
        if not string_fret_info:
            print(f"Error: Cannot determine string for MIDI note {midi_note}")
            return np.array([])
        
        string_id, fret_num = string_fret_info
        presser_motor_id = string_id + 6  # Presser motors are 6-11
        
        # Get current presser torque (should be 500 at end of LH trajectory)
        current_presser_torque = lh_trajectory[-1, presser_motor_id]
        
        # 3. Get LH trajectory duration - pluck will be placed AFTER this
        lh_num_points = lh_trajectory.shape[0]
        lh_duration = lh_num_points * tu.TIME_STEP
        
        print(f"LH trajectory: {lh_num_points} points, {lh_duration:.3f}s duration")
        print(f"  Presser {presser_motor_id} ends at torque: {current_presser_torque}")
        
        # 4. Calculate pluck timing - place it after LH trajectory + settling time
        pluck_timestamp = lh_duration + self.settling_time
        
        # 5. Calculate total duration needed:
        # LH + settling + pluck motion + (REST phase if unpress_after) + buffer
        # REST phase duration scales inversely with torque to reduce bouncing
        # Lower torque = slower unpress to avoid string pushing back on motor
        pluck_motion_duration = tu.PICKER_PLUCK_MOTION_POINTS * tu.TIME_STEP
        
        if unpress_after:
            # Scale REST phase points based on torque level
            # Lower torque needs more points (slower release) to avoid bouncing
            # torque_ratio: 0.0 (low) → 1.0 (high torque 500)
            max_torque = tu.LH_PRESSER_PRESSED_POS  # e.g., 500
            torque_ratio = current_presser_torque / max_torque if max_torque > 0 else 1.0
            torque_ratio = max(0.1, min(1.0, torque_ratio))  # Clamp to 0.1-1.0
            
            # Scale factor: lower torque = more points (slower)
            # e.g., torque_ratio=1.0 → 1x points, torque_ratio=0.1 → 3x points
            rest_scale_factor = 1.0 + (3.0 * (1.0 - torque_ratio))  # 1.0 to 3.0
            
            rest_phase_points = int(tu.PRESSER_INTERPOLATION_POINTS * rest_scale_factor)
            rest_phase_duration = rest_phase_points * tu.TIME_STEP
        else:
            rest_phase_points = 100 #TODO: magic number alert
            rest_phase_duration = rest_phase_points * tu.TIME_STEP
        
        total_duration = pluck_timestamp + pluck_motion_duration + rest_phase_duration + (50 * tu.TIME_STEP)
        
        # 6. Extend LH trajectory to accommodate the pluck and REST phase
        total_points = int(total_duration / tu.TIME_STEP)
        if total_points > lh_num_points:
            additional_timesteps = total_points - lh_num_points
            last_row = lh_trajectory[-1:, :]
            extension = np.tile(last_row, (additional_timesteps, 1))
            lh_trajectory = np.vstack([lh_trajectory, extension])
            print(f"Extended LH trajectory: {lh_num_points} → {lh_trajectory.shape[0]} points ({total_duration:.3f}s)")
        
        # 7. Determine which picker to use based on MIDI note
        picker_id = self.right_hand.midi_note_to_picker_id(midi_note)
        if picker_id is None:
            print(f"Warning: MIDI note {midi_note} has no corresponding picker")
            # Return LH trajectory padded with RH motors at current positions
            return self._combine_trajectories(lh_trajectory, None)
        
        # 8. Generate right hand plucking trajectory (3 motors)
        rh_trajectory = self._generate_synchronized_pluck(
            picker_id=picker_id,
            pluck_timestamp=pluck_timestamp,
            pluck_velocity=pluck_velocity,
            total_duration=total_duration  # Use total duration including REST
        )
        
        # 9. Generate REST phase - presser returns to -650 AFTER pluck completes (if enabled)
        rest_start_time = pluck_timestamp + pluck_motion_duration
        rest_start_idx = int(rest_start_time / tu.TIME_STEP)
        
        print(f"Timing: LH ends at t={lh_duration:.3f}s, Pluck at t={pluck_timestamp:.3f}s")
        
        if unpress_after:
            # Generate REST trajectory for presser (current_torque → -650)
            # Uses scaled point count for slower release at lower torques
            rest_points = GuitarBotParser.interp_with_blend(
                current_presser_torque, 
                tu.LH_PRESSER_UNPRESSED_POS,  # Return to unpressed (-650)
                rest_phase_points, 
                tu.TRAJECTORY_BLEND_PERCENT
            )
            
            # Insert REST phase into LH trajectory
            rest_end_idx = min(rest_start_idx + len(rest_points), lh_trajectory.shape[0])
            for i, torque in enumerate(rest_points):
                if rest_start_idx + i < lh_trajectory.shape[0]:
                    lh_trajectory[rest_start_idx + i, presser_motor_id] = torque
            
            # Hold at unpressed for remaining trajectory
            if rest_end_idx < lh_trajectory.shape[0]:
                lh_trajectory[rest_end_idx:, presser_motor_id] = tu.LH_PRESSER_UNPRESSED_POS
            
            # Update left hand's current position to reflect the REST
            self.left_hand.current_positions[presser_motor_id] = tu.LH_PRESSER_UNPRESSED_POS
            
            rest_duration_ms = rest_phase_points * tu.TIME_STEP * 1000
            print(f"REST phase: Presser {presser_motor_id} returns to {tu.LH_PRESSER_UNPRESSED_POS} at t={rest_start_time:.3f}s")
            print(f"  Torque: {current_presser_torque}→{tu.LH_PRESSER_UNPRESSED_POS}, Duration: {rest_duration_ms:.0f}ms ({rest_phase_points} points)")
            print(f"  Scale factor: {rest_scale_factor:.2f}x (lower torque = slower unpress to reduce bouncing)")
        else:
            # No unpress - presser stays at target torque
            print(f"No unpress: Presser {presser_motor_id} stays at torque {current_presser_torque}")
        
        # 10. Combine LH and RH trajectories into 16-column array (15 motors + control flag)
        combined_trajectory = self._combine_trajectories(lh_trajectory, rh_trajectory)
        
        print(f"\nGenerated combined trajectory: {combined_trajectory.shape[0]} timesteps × {combined_trajectory.shape[1]} cols")
        print(f"Duration: {combined_trajectory.shape[0] * tu.TIME_STEP:.3f}s")
        
        # 9. Plot if enabled
        if tu.graph:
            self.plot_combined_trajectory(combined_trajectory, f"Fret+Pluck: MIDI {midi_note}")
        
        return combined_trajectory
    
    def parse_rlfret_with_pluck(self, string_idx, fret_position, torque, 
                                 pluck_velocity=None, timestamp=0.0, unpress_after=False):
        """
        Parse /RLFret message for RL low-level control with coordinated plucking.
        
        This is the primary interface for RL agents - uses fractional frets and
        raw torque values instead of MIDI notes and normalized force.
        
        Key differences from parse_fret_with_pluck:
        - Uses fractional fret position (0.0-9.0) instead of MIDI note
        - Uses raw torque (0-1000) instead of force (0-1)
        - Direct slider position calculation (no MIDI mapping)
        
        Trajectory sequence:
        1. LH trajectory: UNPRESS → SLIDE → PRESS (ends at target torque)
        2. Settling time (brief pause while string is pressed)
        3. RH pluck (pluck happens while string is still pressed)
        4. REST phase: presser returns to -650 (if unpress_after=True)
        
        Args:
            string_idx: String index (0, 2, or 4 - must have plucker)
            fret_position: Fractional fret position (0.0 - 9.0)
            torque: Raw fretting torque (0 - 1000)
            pluck_velocity: Optional pluck velocity (0-127, None = state toggle)
            timestamp: When the note should start (seconds)
            unpress_after: If True, presser returns to -650 after pluck
            
        Returns:
            2D numpy array [num_timesteps x 15] with complete motor trajectories
        """
        print(f"\n{'='*60}")
        print(f"RL COORDINATED FRET + PLUCK")
        print(f"String: {string_idx}, Fret: {fret_position:.2f}, Torque: {torque:.0f}")
        print(f"Velocity: {pluck_velocity}, Time: {timestamp}s, Unpress after: {unpress_after}")
        print(f"{'='*60}")
        
        # Validate string has a plucker
        PLUCKER_TO_STRING = {0: 0, 1: 2, 2: 4}
        STRING_TO_PLUCKER = {0: 0, 2: 1, 4: 2}
        PLAYABLE_STRINGS = [0, 2, 4]
        
        if string_idx not in PLAYABLE_STRINGS:
            print(f"Error: String {string_idx} has no plucker. Use {PLAYABLE_STRINGS}")
            return np.array([])
        
        # Clamp values to safe ranges
        fret_position = max(0.0, min(9.0, fret_position))
        # Clamp torque to safe operating range (0-500 for normal operation)
        # Values above 500 can overheat motors, but we allow up to 650 for slides
        torque = max(0.0, min(650.0, torque))  # Clamped to safe max
        
        # Convert fractional fret to slider position (mm → encoder ticks)
        slider_mm = self._fret_to_mm(fret_position)
        slider_position = self._mm_to_encoder(slider_mm, string_idx)
        
        print(f"  Fret {fret_position:.2f} → {slider_mm:.1f}mm → {slider_position} encoder ticks")
        
        # Motor IDs
        slider_motor_id = string_idx
        presser_motor_id = string_idx + 6
        picker_id = STRING_TO_PLUCKER[string_idx]
        
        # Get current positions from left hand parser
        current_slider_pos = self.left_hand.current_positions[slider_motor_id]
        current_presser_torque = self.left_hand.current_positions[presser_motor_id]
        
        # Target positions
        target_slider_pos = int(slider_position)
        target_torque = int(torque)
        
        print(f"  Slider: {current_slider_pos} → {target_slider_pos}")
        print(f"  Presser: {current_presser_torque} → {target_torque}")
        
        # Generate LH trajectory directly (bypass MIDI mapping)
        lh_trajectory = self._generate_rlfret_trajectory(
            string_idx=string_idx,
            slider_motor_id=slider_motor_id,
            presser_motor_id=presser_motor_id,
            current_slider_pos=current_slider_pos,
            current_presser_torque=current_presser_torque,
            target_slider_pos=target_slider_pos,
            target_torque=target_torque,
            timestamp=timestamp
        )
        
        if lh_trajectory.size == 0:
            print("Error: Failed to generate left hand trajectory")
            return np.array([])
        
        # Get LH trajectory duration
        lh_num_points = lh_trajectory.shape[0]
        lh_duration = lh_num_points * tu.TIME_STEP
        
        print(f"LH trajectory: {lh_num_points} points, {lh_duration:.3f}s duration")
        
        # Calculate pluck timing - place it after LH trajectory + settling time
        pluck_timestamp = lh_duration + self.settling_time
        
        # Calculate total duration
        pluck_motion_duration = tu.PICKER_PLUCK_MOTION_POINTS * tu.TIME_STEP
        
        if unpress_after:
            # Scale REST phase based on torque
            max_torque = tu.LH_PRESSER_PRESSED_POS
            torque_ratio = target_torque / max_torque if max_torque > 0 else 1.0
            torque_ratio = max(0.1, min(1.0, torque_ratio))
            rest_scale_factor = 1.0 + (3.0 * (1.0 - torque_ratio))
            rest_phase_points = int(tu.PRESSER_INTERPOLATION_POINTS * rest_scale_factor)
        else:
            rest_phase_points = 100
        
        rest_phase_duration = rest_phase_points * tu.TIME_STEP
        total_duration = pluck_timestamp + pluck_motion_duration + rest_phase_duration + (50 * tu.TIME_STEP)
        
        # Extend LH trajectory
        total_points = int(total_duration / tu.TIME_STEP)
        if total_points > lh_num_points:
            additional_timesteps = total_points - lh_num_points
            last_row = lh_trajectory[-1:, :]
            extension = np.tile(last_row, (additional_timesteps, 1))
            lh_trajectory = np.vstack([lh_trajectory, extension])
            print(f"Extended LH trajectory: {lh_num_points} → {lh_trajectory.shape[0]} points")
        
        # Generate RH plucking trajectory
        rh_trajectory = self._generate_synchronized_pluck(
            picker_id=picker_id,
            pluck_timestamp=pluck_timestamp,
            pluck_velocity=pluck_velocity,
            total_duration=total_duration
        )
        
        # Generate REST phase if enabled
        rest_start_time = pluck_timestamp + pluck_motion_duration
        rest_start_idx = int(rest_start_time / tu.TIME_STEP)
        
        if unpress_after:
            rest_points = GuitarBotParser.interp_with_blend(
                target_torque, 
                tu.LH_PRESSER_UNPRESSED_POS,
                rest_phase_points, 
                tu.TRAJECTORY_BLEND_PERCENT
            )
            
            for i, tq in enumerate(rest_points):
                if rest_start_idx + i < lh_trajectory.shape[0]:
                    lh_trajectory[rest_start_idx + i, presser_motor_id] = tq
            
            rest_end_idx = min(rest_start_idx + len(rest_points), lh_trajectory.shape[0])
            if rest_end_idx < lh_trajectory.shape[0]:
                lh_trajectory[rest_end_idx:, presser_motor_id] = tu.LH_PRESSER_UNPRESSED_POS
            
            self.left_hand.current_positions[presser_motor_id] = tu.LH_PRESSER_UNPRESSED_POS
            print(f"REST: Presser returns to {tu.LH_PRESSER_UNPRESSED_POS} at t={rest_start_time:.3f}s")
        else:
            print(f"No unpress: Presser stays at torque {target_torque}")
        
        # Combine LH and RH trajectories with force_torque_mode=True for RL control
        combined_trajectory = self._combine_trajectories(lh_trajectory, rh_trajectory, force_torque_mode=True)
        
        print(f"\nGenerated combined trajectory: {combined_trajectory.shape[0]} timesteps × {combined_trajectory.shape[1]} cols (force_torque_mode=True)")
        print(f"Duration: {combined_trajectory.shape[0] * tu.TIME_STEP:.3f}s")
        
        if tu.graph:
            self.plot_combined_trajectory(combined_trajectory, f"RLFret: String {string_idx}, Fret {fret_position:.1f}")
        
        return combined_trajectory
    
    def _fret_to_mm(self, fret_position):
        """
        Convert fractional fret position to mm from nut.
        
        Uses linear interpolation between fret positions from tune.py.
        
        Args:
            fret_position: Fractional fret (0.0 = open, 5.5 = between frets 5-6)
            
        Returns:
            Slider position in mm
        """
        if fret_position <= 0.0:
            return 0.0
        
        # Build fret → mm lookup (fret 0 = 0mm, fret 1-9 from SLIDER_MM_PER_FRET)
        fret_mm_lookup = {0: 0.0}
        for i, mm in enumerate(tu.SLIDER_MM_PER_FRET):
            fret_mm_lookup[i + 1] = mm
        
        fret_low = int(np.floor(fret_position))
        fret_high = int(np.ceil(fret_position))
        
        # Clamp to available range
        max_fret = len(tu.SLIDER_MM_PER_FRET)
        fret_low = min(fret_low, max_fret)
        fret_high = min(fret_high, max_fret)
        
        if fret_low == fret_high:
            return fret_mm_lookup.get(fret_low, tu.SLIDER_MM_PER_FRET[-1])
        
        mm_low = fret_mm_lookup.get(fret_low, 0.0)
        mm_high = fret_mm_lookup.get(fret_high, tu.SLIDER_MM_PER_FRET[-1])
        
        fraction = fret_position - fret_low
        return mm_low + fraction * (mm_high - mm_low)
    
    def _mm_to_encoder(self, mm, string_idx):
        """
        Convert mm position to encoder ticks for a specific string's slider.
        
        Uses the EXACT formula from GuitarBotParser for consistency.
        
        Args:
            mm: Position in mm from nut
            string_idx: String index (for direction multiplier)
            
        Returns:
            Encoder position in ticks
        """
        direction = tu.SLIDER_MOTOR_DIRECTION[string_idx]
        # Formula from GuitarBotParser.parseleftMIDI() line 449
        encoder_pos = ((mm * 2048) / tu.MM_TO_ENCODER_CONVERSION_FACTOR + tu.SLIDER_ENCODER_OFFSET) * direction
        return int(encoder_pos)
    
    def _generate_rlfret_trajectory(self, string_idx, slider_motor_id, presser_motor_id,
                                     current_slider_pos, current_presser_torque,
                                     target_slider_pos, target_torque, timestamp):
        """
        Generate LH trajectory for RL fretting (direct position/torque control).
        
        Sequence: UNPRESS → SLIDE → PRESS
        
        Args:
            string_idx: String index
            slider_motor_id: Motor ID for slider (0-5)
            presser_motor_id: Motor ID for presser (6-11)
            current_slider_pos: Current slider encoder position
            current_presser_torque: Current presser torque
            target_slider_pos: Target slider encoder position
            target_torque: Target presser torque
            timestamp: Start time
            
        Returns:
            2D numpy array [N x 12] with LH motor trajectories
        """
        # Trajectory phases
        num_points = tu.PRESSER_INTERPOLATION_POINTS
        slider_points = tu.LH_SINGLE_NOTE_MOTION_POINTS
        
        # Total points: UNPRESS + SLIDE + PRESS
        total_points = num_points + slider_points + num_points
        buffer_points = 100
        start_idx = int(timestamp / tu.TIME_STEP)
        total_rows = start_idx + total_points + buffer_points
        
        # Initialize trajectory with NaN (forward-fill later)
        trajectory = np.full((total_rows, 12), np.nan)
        trajectory[0, :] = self.left_hand.current_positions
        
        # Phase 1: UNPRESS (current torque → -650)
        unpress_traj = GuitarBotParser.interp_with_blend(
            current_presser_torque,
            tu.LH_PRESSER_UNPRESSED_POS,
            num_points,
            tu.TRAJECTORY_BLEND_PERCENT
        )
        
        phase1_start = start_idx
        phase1_end = phase1_start + num_points
        
        # Hold slider during unpress
        slider_hold = GuitarBotParser.interp_with_blend(
            current_slider_pos, current_slider_pos, num_points, tu.TRAJECTORY_BLEND_PERCENT
        )
        
        for i in range(num_points):
            idx = phase1_start + i
            if idx < total_rows:
                trajectory[idx, :] = trajectory[max(0, idx-1), :]
                trajectory[idx, slider_motor_id] = slider_hold[i]
                trajectory[idx, presser_motor_id] = unpress_traj[i]
        
        # Phase 2: SLIDE (move slider while unpressed)
        slide_traj = GuitarBotParser.interp_with_blend(
            current_slider_pos,
            target_slider_pos,
            slider_points,
            tu.TRAJECTORY_BLEND_PERCENT
        )
        
        phase2_start = phase1_end
        phase2_end = phase2_start + slider_points
        
        for i in range(slider_points):
            idx = phase2_start + i
            if idx < total_rows:
                trajectory[idx, :] = trajectory[max(0, idx-1), :]
                trajectory[idx, slider_motor_id] = slide_traj[i]
                trajectory[idx, presser_motor_id] = tu.LH_PRESSER_UNPRESSED_POS
        
        # Phase 3: PRESS (apply torque)
        press_traj = GuitarBotParser.interp_with_blend(
            tu.LH_PRESSER_UNPRESSED_POS,
            target_torque,
            num_points,
            tu.TRAJECTORY_BLEND_PERCENT
        )
        
        phase3_start = phase2_end
        phase3_end = phase3_start + num_points
        
        for i in range(num_points):
            idx = phase3_start + i
            if idx < total_rows:
                trajectory[idx, :] = trajectory[max(0, idx-1), :]
                trajectory[idx, slider_motor_id] = target_slider_pos
                trajectory[idx, presser_motor_id] = press_traj[i]
        
        # Hold at target for buffer
        for idx in range(phase3_end, total_rows):
            trajectory[idx, :] = trajectory[max(0, idx-1), :]
            trajectory[idx, slider_motor_id] = target_slider_pos
            trajectory[idx, presser_motor_id] = target_torque
        
        # Forward-fill any remaining NaN
        for col in range(12):
            last_valid = trajectory[0, col]
            for row in range(total_rows):
                if np.isnan(trajectory[row, col]):
                    trajectory[row, col] = last_valid
                else:
                    last_valid = trajectory[row, col]
        
        # Update left hand state
        self.left_hand.current_positions[slider_motor_id] = target_slider_pos
        self.left_hand.current_positions[presser_motor_id] = target_torque
        
        print(f"  UNPRESS: {num_points} pts, SLIDE: {slider_points} pts, PRESS: {num_points} pts")
        print(f"  Total: {total_rows} pts ({total_rows * tu.TIME_STEP:.3f}s)")
        
        return trajectory

    def _generate_synchronized_pluck(self, picker_id, pluck_timestamp, pluck_velocity, total_duration):
        """
        Generate plucking trajectory synchronized with fretting timeline.
        
        Args:
            picker_id: Which picker motor (0, 1, 2)
            pluck_timestamp: When to pluck (seconds from start)
            pluck_velocity: MIDI velocity or None for state toggle
            total_duration: Total duration to match (seconds)
            
        Returns:
            2D numpy array [num_timesteps x 3] for RH motors
        """
        num_timesteps = int(total_duration / tu.TIME_STEP)
        rh_trajectory = np.zeros((num_timesteps, 3))
        
        # Initialize all pickers at current positions
        for pid in range(3):
            if pid in self.right_hand.current_positions:
                rh_trajectory[:, pid] = self.right_hand.current_positions[pid]
        
        # Calculate pluck trajectory
        if pluck_velocity is not None:
            # Velocity-based plucking
            target_pos = self.right_hand.velocity_to_position(picker_id, pluck_velocity)
        else:
            # State-based toggle plucking
            target_pos, new_state = self.right_hand.get_next_state_position(picker_id)
        
        if target_pos is None:
            print(f"Warning: Could not determine target position for picker {picker_id}")
            return rh_trajectory
        
        # Generate pluck motion
        start_pos = self.right_hand.current_positions[picker_id]
        pluck_motion = self.right_hand.generate_pluck_trajectory(picker_id, target_pos)
        
        # Insert pluck motion at correct timestamp
        pluck_start_idx = int(pluck_timestamp / tu.TIME_STEP)
        pluck_end_idx = min(pluck_start_idx + len(pluck_motion), num_timesteps)
        motion_length = pluck_end_idx - pluck_start_idx
        
        if motion_length > 0:
            if motion_length < len(pluck_motion):
                print(f"WARNING: Pluck motion truncated! Expected {len(pluck_motion)} points, only {motion_length} fit")
            
            rh_trajectory[pluck_start_idx:pluck_end_idx, picker_id] = pluck_motion[:motion_length]
            # Hold at final position for remainder
            if pluck_end_idx < num_timesteps:
                rh_trajectory[pluck_end_idx:, picker_id] = target_pos
        else:
            print(f"ERROR: Pluck timestamp {pluck_timestamp:.3f}s is beyond trajectory duration {total_duration:.3f}s!")
        
        # Update state
        self.right_hand.current_positions[picker_id] = target_pos
        
        print(f"Pluck scheduled: Picker {picker_id} at t={pluck_timestamp:.3f}s (index {pluck_start_idx}), motion length={motion_length}/{len(pluck_motion)} points")
        
        return rh_trajectory
    
    def _combine_trajectories(self, lh_trajectory, rh_trajectory, force_torque_mode=False):
        """
        Combine left hand (12 motors) and right hand (3 motors) into full 16-column array.
        
        The 16th column is a control flag sent to the microcontroller:
          0 = normal behavior (presser position override when near zero)
          1 = force torque mode for pressers (RL agent direct control)
        
        Args:
            lh_trajectory: [N x 12] array for LH motors
            rh_trajectory: [N x 3] array for RH motors, or None
            force_torque_mode: If True, sets the control flag to 1 (skip position override)
            
        Returns:
            [N x 16] combined trajectory array (15 motors + 1 control flag)
        """
        num_timesteps = lh_trajectory.shape[0]
        
        if rh_trajectory is None:
            # Create RH trajectory with current positions
            rh_trajectory = np.zeros((num_timesteps, 3))
            for picker_id in range(3):
                if picker_id in self.right_hand.current_positions:
                    rh_trajectory[:, picker_id] = self.right_hand.current_positions[picker_id]
        else:
            # Ensure RH trajectory matches LH length
            if rh_trajectory.shape[0] < num_timesteps:
                # Pad with last values
                padding = np.tile(rh_trajectory[-1:, :], (num_timesteps - rh_trajectory.shape[0], 1))
                rh_trajectory = np.vstack([rh_trajectory, padding])
            elif rh_trajectory.shape[0] > num_timesteps:
                # Truncate
                rh_trajectory = rh_trajectory[:num_timesteps, :]
        
        # Control flag column: 1.0 = force torque mode, 0.0 = normal
        flag_col = np.full((num_timesteps, 1), 1.0 if force_torque_mode else 0.0)
        
        # Combine: [LH(12) | RH(3) | FLAG(1)] = 16 columns
        combined = np.hstack([lh_trajectory, rh_trajectory, flag_col])
        
        return combined
    
    def parse_dynamics_message(self, midi_notes, timestamp=0.0):
        """
        Parse /Dyn message - pluck notes WITHOUT changing fretting.
        
        Args:
            midi_notes: List of MIDI note numbers or single note
            timestamp: When to pluck (seconds)
            
        Returns:
            2D numpy array [num_timesteps x 15] with complete motor trajectories
        """
        print(f"\n{'='*60}")
        print(f"DYNAMICS (PLUCK ONLY)")
        print(f"Notes: {midi_notes}, Time: {timestamp}s")
        print(f"{'='*60}")
        
        # Ensure midi_notes is a list
        if not isinstance(midi_notes, list):
            midi_notes = [midi_notes]
        
        # Generate plucking trajectory using RightHandParser
        # This returns a list of 15-motor arrays
        trajectories_list = self.right_hand.parse_dynamics_message(midi_notes, use_velocity_mapping=False)
        
        if not trajectories_list:
            print("Error: Failed to generate right hand trajectory")
            return np.array([])
        
        # Convert list to numpy array
        rh_full_trajectory = np.array(trajectories_list)
        
        # Extract just the RH motors (last 3)
        rh_trajectory = rh_full_trajectory[:, 12:15]
        
        # Get current LH positions and hold them
        num_timesteps = rh_trajectory.shape[0]
        lh_trajectory = np.tile(self.left_hand.current_positions, (num_timesteps, 1))
        
        # Combine with control flag column (0 = normal mode for dynamics)
        flag_col = np.zeros((num_timesteps, 1))
        combined_trajectory = np.hstack([lh_trajectory, rh_trajectory, flag_col])
        
        print(f"\nGenerated dynamics trajectory: {combined_trajectory.shape[0]} timesteps × {combined_trajectory.shape[1]} cols")
        print(f"Duration: {combined_trajectory.shape[0] * tu.TIME_STEP:.3f}s")
        
        # Plot if enabled
        if tu.graph:
            self.plot_combined_trajectory(combined_trajectory, f"Dynamics: {midi_notes}")
        
        return combined_trajectory
    
    def parse_sequence(self, events):
        """
        Parse a sequence of events (multiple /Fret or /Dyn messages).
        
        Args:
            events: List of event dictionaries with format:
                {'type': 'fret' or 'dyn',
                 'midi_note': int (for fret) or 'midi_notes': list (for dyn),
                 'presser_force': float (optional, for fret),
                 'pluck_velocity': int (optional, for fret),
                 'timestamp': float}
        
        Returns:
            2D numpy array [num_timesteps x 15] with complete sequence
        """
        print(f"\n{'='*60}")
        print(f"PARSING SEQUENCE: {len(events)} events")
        print(f"{'='*60}")
        
        all_trajectories = []
        
        for i, event in enumerate(events):
            event_type = event.get('type', 'fret')
            timestamp = event.get('timestamp', 0.0)
            
            if event_type == 'fret':
                midi_note = event.get('midi_note')
                presser_force = event.get('presser_force', None)
                pluck_velocity = event.get('pluck_velocity', None)
                
                trajectory = self.parse_fret_with_pluck(
                    midi_note=midi_note,
                    presser_force=presser_force,
                    pluck_velocity=pluck_velocity,
                    timestamp=timestamp
                )
            
            elif event_type == 'dyn':
                midi_notes = event.get('midi_notes', [])
                trajectory = self.parse_dynamics_message(
                    midi_notes=midi_notes,
                    timestamp=timestamp
                )
            
            else:
                print(f"Warning: Unknown event type '{event_type}', skipping")
                continue
            
            if trajectory.size > 0:
                all_trajectories.append(trajectory)
        
        if not all_trajectories:
            print("Error: No valid trajectories generated")
            return np.array([])
        
        # Concatenate all trajectories
        combined = np.vstack(all_trajectories)
        
        print(f"\n{'='*60}")
        print(f"SEQUENCE COMPLETE")
        print(f"Total trajectory: {combined.shape[0]} timesteps × {combined.shape[1]} cols")
        print(f"Total duration: {combined.shape[0] * tu.TIME_STEP:.3f}s")
        print(f"{'='*60}")
        
        return combined
    
    def reset_all(self):
        """Reset both hands to initial positions."""
        print("\n=== Resetting Both Hands ===")
        self.left_hand.reset_positions()
        self.right_hand.reset_positions()
        print("All motors reset to initial positions")
    
    def get_status(self):
        """Get status of all 15 motors."""
        status = {
            'left_hand': self.left_hand.get_status(),
            'right_hand': self.right_hand.get_status()
        }
        return status
    
    def plot_combined_trajectory(self, trajectory, title="Combined Trajectory"):
        """
        Plot complete 15-motor trajectory on a single plot.
        
        Args:
            trajectory: [N x 15] numpy array
            title: Plot title
        """
        if trajectory.size == 0 or trajectory.shape[1] < 15:
            print("Insufficient trajectory data for plotting")
            return
        
        # Support both 15-col and 16-col (with control flag) trajectories
        motor_data = trajectory[:, :15]
        
        num_timesteps = motor_data.shape[0]
        timestamps = np.arange(num_timesteps) * tu.TIME_STEP
        
        fig = go.Figure()
        
        # Plot LH motors (0-11)
        for motor in range(12):
            motor_type = "Slider" if motor < 6 else "Presser"
            string_id = motor if motor < 6 else motor - 6
            
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=motor_data[:, motor],
                    mode='lines',
                    name=f'LH {motor_type} {string_id}'
                )
            )
        
        # Plot RH motors (12-14)
        for motor in range(12, 15):
            picker_id = motor - 12
            
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=motor_data[:, motor],
                    mode='lines+markers',
                    name=f'RH Picker {picker_id}',
                    line=dict(width=3),
                    marker=dict(size=4)
                )
            )
        
        fig.update_layout(
            title=title,
            showlegend=True,
            height=800,
            hovermode='x unified',
            xaxis_title="Time (s)",
            yaxis_title="Position (ticks)"
        )
        
        fig.show()


# Example usage and testing
if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════╗
║         BothHandsParser - Coordinated Trajectory Generation   ║
║         Left Hand (Fretting) + Right Hand (Plucking)          ║
╚═══════════════════════════════════════════════════════════════╝
""")
    
    # Initialize parser
    parser = BothHandsParser()
    
    print("\n=== Test 1: Single Note with Auto-Pluck ===")
    # Play MIDI note 45 (Low E, 5th fret) with automatic plucking
    traj1 = parser.parse_fret_with_pluck(
        midi_note=45,
        presser_force=0.7,
        pluck_velocity=None,  # Use state toggle
        timestamp=0.0
    )
    print(f"Trajectory 1 shape: {traj1.shape}")
    
    print("\n=== Test 2: Dynamics (Pluck Only) ===")
    # Pluck without changing fret position
    traj2 = parser.parse_dynamics_message(
        midi_notes=[45],
        timestamp=0.0
    )
    print(f"Trajectory 2 shape: {traj2.shape}")
    
    print("\n=== Test 3: Sequence of Notes ===")
    # Play a sequence: E (open) -> A (5th fret) -> D (7th fret)
    events = [
        {
            'type': 'fret',
            'midi_note': 40,  # Low E open
            'timestamp': 0.0
        },
        {
            'type': 'fret',
            'midi_note': 45,  # Low E, 5th fret
            'presser_force': 0.8,
            'timestamp': 1.0
        },
        {
            'type': 'fret',
            'midi_note': 47,  # Low E, 7th fret
            'presser_force': 0.8,
            'timestamp': 2.0
        },
        {
            'type': 'dyn',  # Pluck again without moving
            'midi_notes': [47],
            'timestamp': 3.0
        }
    ]
    
    traj3 = parser.parse_sequence(events)
    print(f"Sequence trajectory shape: {traj3.shape}")
    print(f"Total duration: {traj3.shape[0] * tu.TIME_STEP:.3f}s")
    
    print("\n=== Test 4: Multiple Strings ===")
    # Play notes on different strings
    events_multi = [
        {
            'type': 'fret',
            'midi_note': 45,  # String 0
            'timestamp': 0.0
        },
        {
            'type': 'fret',
            'midi_note': 52,  # String 1
            'timestamp': 0.5
        },
        {
            'type': 'fret',
            'midi_note': 62,  # String 2
            'timestamp': 1.0
        }
    ]
    
    traj4 = parser.parse_sequence(events_multi)
    print(f"Multi-string trajectory shape: {traj4.shape}")
    
    print("\n=== Final Status ===")
    status = parser.get_status()
    
    print("\nLeft Hand Status:")
    for string_id in range(6):
        if f'string_{string_id}' in status['left_hand']:
            info = status['left_hand'][f'string_{string_id}']
            print(f"  String {string_id}: Fret {info['fret']}, Pressed: {info['pressed']}")
    
    print("\nRight Hand Status:")
    for key, info in status['right_hand'].items():
        if key.startswith('picker_'):
            print(f"  {key}: Motor {info['motor_id']}, {info['position_ticks']:.1f} ticks, {info['state']}")
    
    print("\n=== Test Complete ===")
    print("All trajectories are 15-motor arrays ready for RobotController")
