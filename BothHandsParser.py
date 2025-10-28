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
    
    def parse_fret_with_pluck(self, midi_note, presser_force=None, pluck_velocity=None, timestamp=0.0, force_adjustment_only=False):
        """
        Parse /Fret message and generate coordinated fretting + plucking trajectory.
        
        This is the main function for playing notes - it frets AND plucks automatically.
        
        Args:
            midi_note: MIDI note number (40-68)
            presser_force: Optional force level for pressing (0.0-1.0, None = default)
            pluck_velocity: Optional pluck velocity (0-127, None = state toggle)
            timestamp: When the note should start (seconds)
            force_adjustment_only: If True, only adjust force without unpressing (for force tests)
            
        Returns:
            2D numpy array [num_timesteps x 15] with complete motor trajectories
        """
        print(f"\n{'='*60}")
        print(f"COORDINATED FRET + PLUCK")
        print(f"MIDI Note: {midi_note}, Force: {presser_force}, Velocity: {pluck_velocity}, Time: {timestamp}s, Force-only: {force_adjustment_only}")
        print(f"{'='*60}")
        
        # 1. Generate left hand fretting trajectory (12 motors)
        lh_trajectory = self.left_hand.parse_fret_message(
            midi_note_number=midi_note,
            presser_force=presser_force,
            timestamp=timestamp,
            force_adjustment_only=force_adjustment_only
        )
        
        if lh_trajectory.size == 0:
            print("Error: Failed to generate left hand trajectory")
            return np.array([])
        
        # 2. Find when the presser torque reaches 0 (rest state)
        # We need to analyze the LH trajectory to find when presser is at 0
        
        # Determine which presser motor based on MIDI note
        string_fret_info = self.left_hand.midi_note_to_string_fret(midi_note)
        if not string_fret_info:
            print(f"Error: Cannot determine string for MIDI note {midi_note}")
            return np.array([])
        
        string_id, _ = string_fret_info
        presser_motor_id = string_id + 6
        
        # Extract presser trajectory
        presser_trajectory = lh_trajectory[:, presser_motor_id]
        
        # Find when torque reaches 0 (or close to 0, within tolerance)
        # For force testing, the trajectory should end with torque=0
        # We want to find the LAST time it reaches 0 before the buffer
        
        # Remove NaN values and find non-zero regions
        valid_indices = ~np.isnan(presser_trajectory)
        valid_traj = presser_trajectory[valid_indices]
        
        if len(valid_traj) == 0:
            print("Warning: No valid presser trajectory data")
            torque_zero_idx = 0
        else:
            # Find indices where torque is close to 0 (within 5 units)
            near_zero = np.abs(valid_traj) < 5.0
            
            if np.any(near_zero):
                # Find the last contiguous block of near-zero values
                # This should be the REST phase
                zero_indices = np.where(near_zero)[0]
                
                # Find the start of the last zero block
                # Look for gaps larger than 5 indices
                gaps = np.diff(zero_indices)
                large_gaps = np.where(gaps > 5)[0]
                
                if len(large_gaps) > 0:
                    # Start of last block
                    last_block_start = zero_indices[large_gaps[-1] + 1]
                else:
                    # All zeros are contiguous, use first zero
                    last_block_start = zero_indices[0]
                
                torque_zero_idx = last_block_start
            else:
                # Torque never reaches 0, use end of trajectory
                print("Warning: Torque never reaches 0 in trajectory")
                torque_zero_idx = len(valid_traj) - 1
        
        torque_zero_time = timestamp + (torque_zero_idx * tu.TIME_STEP)
        
        print(f"Presser torque analysis:")
        print(f"  Torque reaches 0 at index {torque_zero_idx}, t={torque_zero_time:.3f}s")
        if torque_zero_idx > 0 and torque_zero_idx < len(presser_trajectory):
            print(f"  Torque value at rest: {presser_trajectory[torque_zero_idx]:.1f}")
        
        # 3. Add settling time AFTER torque reaches 0, BEFORE pluck starts
        pluck_timestamp = torque_zero_time + self.settling_time
        
        # 4. Calculate pluck duration
        pluck_motion_duration = tu.PICKER_PLUCK_MOTION_POINTS * tu.TIME_STEP
        lh_duration = lh_trajectory.shape[0] * tu.TIME_STEP
        
        # 5. Ensure trajectory is long enough for: all phases + settling + pluck + buffer
        min_required_duration = pluck_timestamp + pluck_motion_duration + (50 * tu.TIME_STEP)
        
        if lh_duration < min_required_duration:
            # Extend LH trajectory to accommodate pluck
            additional_timesteps = int((min_required_duration - lh_duration) / tu.TIME_STEP) + 1
            last_row = lh_trajectory[-1:, :]
            extension = np.tile(last_row, (additional_timesteps, 1))
            lh_trajectory = np.vstack([lh_trajectory, extension])
            lh_duration = lh_trajectory.shape[0] * tu.TIME_STEP
            print(f"Extended LH trajectory to {lh_duration:.3f}s to accommodate pluck")
        
        print(f"Timing: Torque→0 at t={torque_zero_time:.3f}s, Settling={self.settling_time:.3f}s, Pluck at t={pluck_timestamp:.3f}s, Pluck duration={pluck_motion_duration:.3f}s")
        
        # 6. Determine which picker to use based on MIDI note
        picker_id = self.right_hand.midi_note_to_picker_id(midi_note)
        # 6. Determine which picker to use based on MIDI note
        picker_id = self.right_hand.midi_note_to_picker_id(midi_note)
        if picker_id is None:
            print(f"Warning: MIDI note {midi_note} has no corresponding picker")
            # Return LH trajectory padded with RH motors at current positions
            return self._combine_trajectories(lh_trajectory, None)
        
        # 7. Generate right hand plucking trajectory (3 motors)
        # Create a minimal trajectory that matches the LH timing
        rh_trajectory = self._generate_synchronized_pluck(
            picker_id=picker_id,
            pluck_timestamp=pluck_timestamp,
            pluck_velocity=pluck_velocity,
            total_duration=lh_duration
        )
        
        # 8. Combine LH and RH trajectories into single 15-motor array
        combined_trajectory = self._combine_trajectories(lh_trajectory, rh_trajectory)
        
        print(f"\nGenerated combined trajectory: {combined_trajectory.shape[0]} timesteps × 15 motors")
        print(f"Duration: {combined_trajectory.shape[0] * tu.TIME_STEP:.3f}s")
        
        # 9. Plot if enabled
        if tu.graph:
            self.plot_combined_trajectory(combined_trajectory, f"Fret+Pluck: MIDI {midi_note}")
        
        return combined_trajectory
    
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
        Plot complete 15-motor trajectory.
        
        Args:
            trajectory: [N x 15] numpy array
            title: Plot title
        """
        if trajectory.size == 0 or trajectory.shape[1] < 15:
            print("Insufficient trajectory data for plotting")
            return
        
        num_timesteps = trajectory.shape[0]
        timestamps = np.arange(num_timesteps) * tu.TIME_STEP
        
        # Create subplots: LH and RH separate
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=('Left Hand Motors (0-11)', 'Right Hand Motors (12-14)'),
            vertical_spacing=0.12
        )
        
        # Plot LH motors (0-11)
        for motor in range(12):
            motor_type = "Slider" if motor < 6 else "Presser"
            string_id = motor if motor < 6 else motor - 6
            
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=trajectory[:, motor],
                    mode='lines',
                    name=f'LH {motor_type} {string_id}',
                    legendgroup='LH'
                ),
                row=1, col=1
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
                    marker=dict(size=4),
                    legendgroup='RH'
                ),
                row=2, col=1
            )
        
        fig.update_layout(
            title=title,
            showlegend=True,
            height=800,
            hovermode='x unified'
        )
        
        fig.update_xaxes(title_text="Time (s)", row=2, col=1)
        fig.update_yaxes(title_text="Position (ticks)", row=1, col=1)
        fig.update_yaxes(title_text="Position (ticks)", row=2, col=1)
        
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
