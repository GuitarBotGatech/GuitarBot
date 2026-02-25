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
        self.pluck_delay_after_press = tu.TIME_STEP * 20  # Delay pluck to allow fretter to settle
        self.settling_time = tu.TIME_STEP * 50  # Additional settling time before pluck starts
        
        print("=== BothHandsParser Initialized ===")
        print("Left Hand: 12 motors (sliders + pressers)")
        print("Right Hand: 3 motors (pickers)")
        print(f"Pluck delay: {self.pluck_delay_after_press:.3f}s after press")
        print(f"Settling time: {self.settling_time:.3f}s before pluck")
    
    def parse_fret_with_pluck(self, midi_note, presser_force=None, pluck_velocity=None, timestamp=0.0, force_adjustment_only=False, unpress_after=True):
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
            rest_phase_points = tu.PRESSER_UNPRESS_AFTER_POINTS
            rest_phase_duration = rest_phase_points * tu.TIME_STEP
        else:
            rest_phase_points = 100
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
        else:
            # No unpress - presser stays at target torque
            print(f"No unpress: Presser {presser_motor_id} stays at torque {current_presser_torque}")
        
        # 10. Combine LH and RH trajectories into single 15-motor array
        combined_trajectory = self._combine_trajectories(lh_trajectory, rh_trajectory)
        
        print(f"\nGenerated combined trajectory: {combined_trajectory.shape[0]} timesteps × 15 motors")
        print(f"Duration: {combined_trajectory.shape[0] * tu.TIME_STEP:.3f}s")
        
        # 9. Plot if enabled
        if tu.graph:
            self.plot_combined_trajectory(combined_trajectory, f"Fret+Pluck: MIDI {midi_note}")
        
        return combined_trajectory
    
    def parse_rlfret_with_pluck(self, string_idx, fret_position, torque,
                                 pluck_velocity=None, timestamp=0.0, unpress_after=True,
                                 direct_press=True):
        """
        Parse /RLFret message for RL low-level control with coordinated plucking.
        
        This is the primary interface for RL agents - uses fractional frets and
        raw torque values instead of MIDI notes and normalized force.
        
        Key differences from parse_fret_with_pluck:
        - Uses fractional fret position (0.0-9.0) instead of MIDI note
        - Uses raw torque (0-1000) instead of force (0-1)
        - Direct slider position calculation (no MIDI mapping)
        
        Trajectory sequence (default, direct_press=False):
        1. LH trajectory: UNPRESS (→ -650) → SLIDE → PRESS (→ target torque)
        2. Settling time (brief pause while string is pressed)
        3. RH pluck (pluck happens while string is still pressed)
        4. REST phase: presser returns to -650 (if unpress_after=True)

        Trajectory sequence (direct_press=True):
        1. LH trajectory: SLIDE + simultaneous presser ramp (current → target)
           Skips the -650 waypoint entirely — shorter trajectory, no unpress dip.
        2-4. Same as above.
        
        Args:
            string_idx: String index (0, 2, or 4 - must have plucker)
            fret_position: Fractional fret position (0.0 - 9.0)
            torque: Raw fretting torque (0 - 1000)
            pluck_velocity: Optional pluck velocity (0-127, None = state toggle)
            timestamp: When the note should start (seconds)
            unpress_after: If True, presser returns to -650 after pluck
            direct_press: If True, presser goes current→target directly during the
                          slide phase instead of detouring through -650.  Eliminates
                          the UNPRESS and separate PRESS phases.
            
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
        print(f"  Mode: {'direct_press (no -650 waypoint)' if direct_press else 'UNPRESS→SLIDE→PRESS'}")
        
        # Generate LH trajectory directly (bypass MIDI mapping)
        lh_trajectory = self._generate_rlfret_trajectory(
            string_idx=string_idx,
            slider_motor_id=slider_motor_id,
            presser_motor_id=presser_motor_id,
            current_slider_pos=current_slider_pos,
            current_presser_torque=current_presser_torque,
            target_slider_pos=target_slider_pos,
            target_torque=target_torque,
            timestamp=timestamp,
            direct_press=direct_press
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
        
        rest_phase_points = tu.PRESSER_UNPRESS_AFTER_POINTS if unpress_after else 100
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
            rest_ms = rest_phase_points * tu.TIME_STEP * 1000
            print(f"REST: Presser returns to {tu.LH_PRESSER_UNPRESSED_POS} at t={rest_start_time:.3f}s ({rest_ms:.0f}ms, {rest_phase_points} pts)")
        else:
            print(f"No unpress: Presser stays at torque {target_torque}")
        
        # Combine LH and RH trajectories
        combined_trajectory = self._combine_trajectories(lh_trajectory, rh_trajectory)
        
        print(f"\nGenerated combined trajectory: {combined_trajectory.shape[0]} timesteps × 15 motors")
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
                                     target_slider_pos, target_torque, timestamp,
                                     direct_press=False):
        """
        Generate LH trajectory for RL fretting (direct position/torque control).

        Two modes controlled by ``direct_press``:

        Default (direct_press=False) — UNPRESS → SLIDE → PRESS:
          Phase 1 (PRESSER_INTERPOLATION_POINTS): presser current → -650, slider holds.
          Phase 2 (LH_SINGLE_NOTE_MOTION_POINTS): slider moves, presser holds at -650.
          Phase 3 (PRESSER_INTERPOLATION_POINTS): presser -650 → target, slider holds.

        Direct (direct_press=True) — simultaneous SLIDE + PRESS:
          Single phase (LH_SINGLE_NOTE_MOTION_POINTS): slider and presser both
          interpolate from their current values to their targets at the same time.
          No detour through -650 — shorter trajectory, presser never releases.

        Args:
            string_idx: String index
            slider_motor_id: Motor ID for slider (0-5)
            presser_motor_id: Motor ID for presser (6-11)
            current_slider_pos: Current slider encoder position
            current_presser_torque: Current presser torque
            target_slider_pos: Target slider encoder position
            target_torque: Target presser torque
            timestamp: Start time
            direct_press: Skip the -650 waypoint (see above).

        Returns:
            2D numpy array [N x 12] with LH motor trajectories
        """
        num_points = tu.PRESSER_INTERPOLATION_POINTS
        slide_points = tu.LH_SINGLE_NOTE_MOTION_POINTS
        buffer_points = 100
        start_idx = int(timestamp / tu.TIME_STEP)

        if direct_press:
            # ── Direct mode: slide and press simultaneously ──────────────────
            # Total = SLIDE phase only (presser ramps alongside slider)
            total_points = slide_points
            total_rows = start_idx + total_points + buffer_points

            trajectory = np.full((total_rows, 12), np.nan)
            trajectory[0, :] = self.left_hand.current_positions

            slide_traj = GuitarBotParser.interp_with_blend(
                current_slider_pos, target_slider_pos, slide_points,
                tu.TRAJECTORY_BLEND_PERCENT
            )
            press_traj = GuitarBotParser.interp_with_blend(
                current_presser_torque, target_torque, slide_points,
                tu.TRAJECTORY_BLEND_PERCENT
            )

            phase_start = start_idx
            phase_end   = phase_start + slide_points

            for i in range(slide_points):
                idx = phase_start + i
                if idx < total_rows:
                    trajectory[idx, :] = trajectory[max(0, idx - 1), :]
                    trajectory[idx, slider_motor_id]  = slide_traj[i]
                    trajectory[idx, presser_motor_id] = press_traj[i]

            # Hold at target for buffer
            for idx in range(phase_end, total_rows):
                trajectory[idx, :] = trajectory[max(0, idx - 1), :]
                trajectory[idx, slider_motor_id]  = target_slider_pos
                trajectory[idx, presser_motor_id] = target_torque

            print(f"  DIRECT: SLIDE+PRESS simultaneous over {slide_points} pts")

        else:
            # ── Default mode: UNPRESS → SLIDE → PRESS ───────────────────────
            total_points = num_points + slide_points + num_points
            total_rows = start_idx + total_points + buffer_points

            trajectory = np.full((total_rows, 12), np.nan)
            trajectory[0, :] = self.left_hand.current_positions

            # Phase 1: UNPRESS (current torque → -650), slider holds
            unpress_traj = GuitarBotParser.interp_with_blend(
                current_presser_torque, tu.LH_PRESSER_UNPRESSED_POS,
                num_points, tu.TRAJECTORY_BLEND_PERCENT
            )
            slider_hold = GuitarBotParser.interp_with_blend(
                current_slider_pos, current_slider_pos,
                num_points, tu.TRAJECTORY_BLEND_PERCENT
            )
            phase1_start = start_idx
            phase1_end   = phase1_start + num_points
            for i in range(num_points):
                idx = phase1_start + i
                if idx < total_rows:
                    trajectory[idx, :] = trajectory[max(0, idx - 1), :]
                    trajectory[idx, slider_motor_id]  = slider_hold[i]
                    trajectory[idx, presser_motor_id] = unpress_traj[i]

            # Phase 2: SLIDE (slider moves, presser holds at -650)
            slide_traj = GuitarBotParser.interp_with_blend(
                current_slider_pos, target_slider_pos,
                slide_points, tu.TRAJECTORY_BLEND_PERCENT
            )
            phase2_start = phase1_end
            phase2_end   = phase2_start + slide_points
            for i in range(slide_points):
                idx = phase2_start + i
                if idx < total_rows:
                    trajectory[idx, :] = trajectory[max(0, idx - 1), :]
                    trajectory[idx, slider_motor_id]  = slide_traj[i]
                    trajectory[idx, presser_motor_id] = tu.LH_PRESSER_UNPRESSED_POS

            # Phase 3: PRESS (-650 → target torque), slider holds at target
            press_traj = GuitarBotParser.interp_with_blend(
                tu.LH_PRESSER_UNPRESSED_POS, target_torque,
                num_points, tu.TRAJECTORY_BLEND_PERCENT
            )
            phase3_start = phase2_end
            phase3_end   = phase3_start + num_points
            for i in range(num_points):
                idx = phase3_start + i
                if idx < total_rows:
                    trajectory[idx, :] = trajectory[max(0, idx - 1), :]
                    trajectory[idx, slider_motor_id]  = target_slider_pos
                    trajectory[idx, presser_motor_id] = press_traj[i]

            # Hold at target for buffer
            for idx in range(phase3_end, total_rows):
                trajectory[idx, :] = trajectory[max(0, idx - 1), :]
                trajectory[idx, slider_motor_id]  = target_slider_pos
                trajectory[idx, presser_motor_id] = target_torque

            print(f"  UNPRESS: {num_points} pts, SLIDE: {slide_points} pts, PRESS: {num_points} pts")

        # Forward-fill any remaining NaN
        for col in range(12):
            last_valid = trajectory[0, col]
            for row in range(total_rows):
                if np.isnan(trajectory[row, col]):
                    trajectory[row, col] = last_valid
                else:
                    last_valid = trajectory[row, col]

        # Update left hand state
        self.left_hand.current_positions[slider_motor_id]  = target_slider_pos
        self.left_hand.current_positions[presser_motor_id] = target_torque

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
    
    def _combine_trajectories(self, lh_trajectory, rh_trajectory):
        """
        Combine left hand (12 motors) and right hand (3 motors) into full 15-motor array.
        
        Args:
            lh_trajectory: [N x 12] array for LH motors
            rh_trajectory: [N x 3] array for RH motors, or None
            
        Returns:
            [N x 15] combined trajectory array
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
        
        # Combine: [LH(12) | RH(3)] = 15 motors
        combined = np.hstack([lh_trajectory, rh_trajectory])
        
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
        
        # Combine
        combined_trajectory = np.hstack([lh_trajectory, rh_trajectory])
        
        print(f"\nGenerated dynamics trajectory: {combined_trajectory.shape[0]} timesteps × 15 motors")
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
        print(f"Total trajectory: {combined.shape[0]} timesteps × 15 motors")
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
        
        num_timesteps = trajectory.shape[0]
        timestamps = np.arange(num_timesteps) * tu.TIME_STEP
        
        fig = go.Figure()
        
        # Plot LH motors (0-11)
        for motor in range(12):
            motor_type = "Slider" if motor < 6 else "Presser"
            string_id = motor if motor < 6 else motor - 6
            
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=trajectory[:, motor],
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
                    y=trajectory[:, motor],
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
