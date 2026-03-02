"""
Parser.py - Orchestrates left and right hand parsers for complete note production

Combines LeftHandParser and RightHandParser to generate coordinated trajectories.
Similar in scope to GuitarBotParser but focused on dataset generation approach
for optimizing fretting force (/Fret messages) and dynamic range (/Dyn messages).

Key Features:
- Coordinates fretting and plucking for complete note production
- Handles both /Fret (fret + pluck) and /Dyn (pluck only) messages  
- Generates combined 15-motor trajectories
- Supports dataset generation workflows
- Maintains timing synchronization between hands
"""

import numpy as np
import pandas as pd
import copy
from LeftHandParser import LeftHandParser
from RightHandParser import RightHandParser
from GuitarBotParser import GuitarBotParser  # For interp_with_blend
import tune as tu
import plotly.graph_objects as go


class Parser:
    def __init__(self):
        # Initialize both hand parsers
        self.left_hand = LeftHandParser()
        self.right_hand = RightHandParser()
        
        # Timing coordination
        self.prep_time_before_pluck = tu.LH_PREP_TIME_BEFORE_PICK  # LH moves before RH plucks
        
    def parse_note_message(self, midi_note, presser_force=None, pluck_velocity=100, 
                          use_velocity_mapping=True, timestamp=0.0):
        """
        Parse complete note message - coordinates fretting and plucking.
        
        Args:
            midi_note: MIDI note number
            presser_force: Fretting force (0.0-1.0, optional)
            pluck_velocity: Plucking velocity (0-127)
            use_velocity_mapping: If True, use velocity for pluck depth; if False, use state toggle
            timestamp: When this note should start (in seconds)
            
        Returns:
            2D numpy array [num_timesteps x 15] with combined LH and RH trajectories
        """
        print(f"\\n=== Processing Note: MIDI {midi_note} ===")
        print(f"Presser force: {presser_force}, Pluck velocity: {pluck_velocity}, Timestamp: {timestamp}")
        
        # Generate left hand trajectory (fretting) - returns [num_timesteps x 12] numpy array
        print("Generating fretting trajectory...")
        lh_trajectory = self.left_hand.parse_fret_message(midi_note, presser_force, timestamp)
        
        if lh_trajectory.size == 0:
            print("Error: Could not generate fretting trajectory")
            return np.array([])
        
        # Calculate when RH should pluck (after LH prep time)
        rh_timestamp = timestamp + self.prep_time_before_pluck
        
        # Generate right hand trajectory (plucking) - returns list of 15-element arrays
        print(f"Generating plucking trajectory at timestamp {rh_timestamp}...")
        rh_trajectory_list = self.right_hand.parse_pluck_message(
            midi_note, pluck_velocity, use_velocity_mapping
        )
        
        if not rh_trajectory_list:
            print("Error: Could not generate plucking trajectory")
            return np.array([])
        
        # Coordinate timing - combine LH and RH trajectories
        coordinated_trajectory = self.coordinate_trajectories(lh_trajectory, rh_trajectory_list, rh_timestamp)
        
        print(f"Generated coordinated trajectory: {coordinated_trajectory.shape}")
        print(f"Duration: {coordinated_trajectory.shape[0] * tu.TIME_STEP:.3f}s")
        
        # Plot if graphing enabled
        if tu.graph:
            self.plot_combined_trajectory(coordinated_trajectory, f"Note MIDI {midi_note}")
        
        return coordinated_trajectory
    
    def parse_fret_only_message(self, midi_note, presser_force=None, timestamp=0.0):
        """
        Parse /Fret message for fretting only (no plucking).
        
        Args:
            midi_note: MIDI note number
            presser_force: Fretting force (0.0-1.0)
            timestamp: When this fret should start (in seconds)
            
        Returns:
            2D numpy array [num_timesteps x 15] with fretting trajectory (RH motors stay at initial positions)
        """
        print(f"\\n=== Processing Fret-Only: MIDI {midi_note} ===")
        
        # Get LH trajectory - returns [num_timesteps x 12] numpy array
        lh_trajectory = self.left_hand.parse_fret_message(midi_note, presser_force, timestamp)
        
        if lh_trajectory.size == 0:
            return np.array([])
        
        # Expand to 15 motors by adding RH motors at initial positions
        num_rows = lh_trajectory.shape[0]
        full_trajectory = np.zeros((num_rows, 15))
        full_trajectory[:, :12] = lh_trajectory  # Copy LH motors
        
        # Set RH motors (12-14) to initial positions
        for i in range(3):
            if i in self.right_hand.motor_info:
                full_trajectory[:, 12 + i] = self.right_hand.motor_info[i]['up_ticks']
        
        if tu.graph:
            self.plot_combined_trajectory(full_trajectory, f"Fret-Only MIDI {midi_note}")
        
        return full_trajectory
    
    def parse_dynamics_message(self, midi_notes, use_velocity_mapping=False):
        """
        Parse /Dyn message for plucking only (no fretting changes).
        
        Args:
            midi_notes: List of MIDI note numbers
            use_velocity_mapping: If True, use velocity control; if False, use state toggle
            
        Returns:
            2D numpy array [num_timesteps x 15] with plucking trajectory (LH motors stay at current positions)
        """
        print(f"\\n=== Processing Dynamics: {midi_notes} ===")
        
        # Get RH trajectory - returns list of 15-element arrays
        rh_trajectory_list = self.right_hand.parse_dynamics_message(midi_notes, use_velocity_mapping)
        
        if not rh_trajectory_list:
            return np.array([])
        
        # Convert list to numpy array for consistency
        trajectory = np.array(rh_trajectory_list)
        
        if tu.graph:
            self.plot_combined_trajectory(trajectory, f"Dynamics {midi_notes}")
        
        return trajectory
    
    def coordinate_trajectories(self, lh_trajectory, rh_trajectory_list, rh_timestamp):
        """
        Coordinate left and right hand trajectories with proper timing.
        Mimics the approach used in GuitarBotParser.parseAllMIDI()
        
        Args:
            lh_trajectory: Left hand trajectory - 2D numpy array [num_timesteps x 12]
            rh_trajectory_list: Right hand trajectory - list of 15-element arrays
            rh_timestamp: When RH motion should start (in seconds)
            
        Returns:
            2D numpy array [num_timesteps x 15] with coordinated LH and RH motion
        """
        if lh_trajectory.size == 0 or not rh_trajectory_list:
            print("Warning: Empty trajectory in coordination")
            return np.array([])
        
        print(f"Coordinating trajectories:")
        print(f"  LH: {lh_trajectory.shape}")
        print(f"  RH: {len(rh_trajectory_list)} points")
        print(f"  RH timestamp: {rh_timestamp}s")
        
        # Convert RH list to numpy array and extract RH motor columns (12-14)
        rh_array = np.array(rh_trajectory_list)
        rh_motors_only = rh_array[:, 12:15]  # Extract motors 12, 13, 14
        
        # Calculate array dimensions
        num_lh_rows = lh_trajectory.shape[0]
        num_rh_rows = rh_motors_only.shape[0]
        rh_start_index = int(rh_timestamp / tu.TIME_STEP)
        
        # Calculate total required rows (mimicking GuitarBotParser line 88-97)
        max_rows = max(num_lh_rows, rh_start_index + num_rh_rows)
        
        # Initialize combined trajectory array [max_rows x 15]
        combined_array = np.zeros((max_rows, 15))
        
        # Copy LH trajectory to first 12 columns
        combined_array[:num_lh_rows, :12] = lh_trajectory
        
        # Forward-fill LH positions if RH extends beyond LH
        if num_lh_rows < max_rows:
            last_lh_row = lh_trajectory[-1, :]
            for i in range(num_lh_rows, max_rows):
                combined_array[i, :12] = last_lh_row
        
        # Initialize RH motors (12-14) to current positions
        for picker_id in self.right_hand.motor_info:
            motor_idx = 12 + picker_id
            initial_pos = self.right_hand.current_positions[picker_id]
            combined_array[:, motor_idx] = initial_pos
        
        # Insert RH trajectory at the specified timestamp
        rh_end_index = min(rh_start_index + num_rh_rows, max_rows)
        rh_copy_length = rh_end_index - rh_start_index
        combined_array[rh_start_index:rh_end_index, 12:15] = rh_motors_only[:rh_copy_length, :]
        
        # Forward-fill RH positions after RH motion completes
        if rh_end_index < max_rows:
            last_rh_row = rh_motors_only[-1, :]
            combined_array[rh_end_index:, 12:15] = last_rh_row
        
        print(f"  Combined: {combined_array.shape}")
        
        return combined_array
    
    def parse_chord_sequence(self, chord_events, pluck_events=None):
        """
        Parse sequence of chord events with optional plucking.
        
        Args:
            chord_events: List of (midi_notes_list, timestamp, presser_force) tuples
            pluck_events: List of (midi_note, timestamp, velocity) tuples (optional)
            
        Returns:
            2D numpy array [num_timesteps x 15] for entire sequence
        """
        print(f"\\n=== Processing Chord Sequence: {len(chord_events)} chords ===")
        
        # Calculate total duration needed
        max_timestamp = 0
        if chord_events:
            max_timestamp = max(ts for _, ts, _ in chord_events)
        if pluck_events:
            max_timestamp = max(max_timestamp, max(ts for _, ts, _ in pluck_events))
        
        # Add buffer for last event
        total_duration = max_timestamp + 2.0  # 2 second buffer
        num_rows = int(total_duration / tu.TIME_STEP)
        
        # Initialize full trajectory array
        combined_trajectory = np.zeros((num_rows, 15))
        
        # Set initial positions
        combined_trajectory[0, :12] = self.left_hand.current_positions
        for picker_id in self.right_hand.motor_info:
            combined_trajectory[0, 12 + picker_id] = self.right_hand.current_positions[picker_id]
        
        # Process each chord event
        for i, (midi_notes, timestamp, presser_force) in enumerate(chord_events):
            print(f"\\nChord {i+1}: Notes {midi_notes} at t={timestamp}s")
            
            # For each note in the chord, generate fretting trajectory
            for midi_note in midi_notes:
                note_traj = self.left_hand.parse_fret_message(midi_note, presser_force, timestamp)
                if note_traj.size > 0:
                    # Merge this note's trajectory into combined array
                    start_idx = int(timestamp / tu.TIME_STEP)
                    end_idx = min(start_idx + note_traj.shape[0], num_rows)
                    copy_length = end_idx - start_idx
                    combined_trajectory[start_idx:end_idx, :12] = note_traj[:copy_length, :]
        
        # Process pluck events if provided
        if pluck_events:
            for midi_note, timestamp, velocity in pluck_events:
                print(f"Pluck: Note {midi_note} at t={timestamp}s")
                pluck_traj = self.right_hand.parse_pluck_message(midi_note, velocity)
                if pluck_traj:
                    # Convert to array and merge RH motors
                    pluck_array = np.array(pluck_traj)
                    start_idx = int(timestamp / tu.TIME_STEP)
                    end_idx = min(start_idx + len(pluck_traj), num_rows)
                    copy_length = end_idx - start_idx
                    combined_trajectory[start_idx:end_idx, 12:15] = pluck_array[:copy_length, 12:15]
        
        # Forward-fill any remaining NaN or zero values
        df = pd.DataFrame(combined_trajectory)
        df.replace(0, np.nan, inplace=True)
        df.ffill(inplace=True)
        df.fillna(0, inplace=True)
        combined_trajectory = df.to_numpy()
        
        print(f"\\nGenerated chord sequence: {combined_trajectory.shape}")
        print(f"Total duration: {combined_trajectory.shape[0] * tu.TIME_STEP:.3f}s")
        
        if tu.graph:
            self.plot_combined_trajectory(combined_trajectory, "Chord Sequence")
        
        return combined_trajectory
    
    def reset_all_positions(self):
        """Reset both left and right hand parsers to initial positions."""
        print("Resetting all motor positions")
        self.left_hand.reset_positions()
        self.right_hand.reset_positions()
    
    def get_combined_status(self):
        """Get status of both left and right hand parsers."""
        lh_status = self.left_hand.get_status()
        rh_status = self.right_hand.get_status()
        
        return {
            'left_hand': lh_status,
            'right_hand': rh_status,
            'timing': {
                'prep_time_seconds': self.prep_time_before_pluck,
                'prep_time_points': int(self.prep_time_before_pluck / tu.TIME_STEP)
            }
        }
    
    def plot_combined_trajectory(self, trajectory_array, title="Combined Trajectory"):
        """
        Plot complete 15-motor trajectory with left/right hand separation.
        Expects trajectory_array to be a 2D numpy array [num_timesteps x 15]
        Mimics plotting style from GuitarBotParser.parseAllMIDI()
        """
        if trajectory_array.size == 0:
            print("No trajectory to plot")
            return
        
        # Ensure we have a 2D array
        if len(trajectory_array.shape) == 1:
            trajectory_array = trajectory_array.reshape(-1, 15)
        
        num_rows = trajectory_array.shape[0]
        timestamps = np.arange(0, num_rows * tu.TIME_STEP, tu.TIME_STEP)
        
        fig = go.Figure()
        
        # Plot left hand motors (0-11)
        for motor in range(12):
            motor_type = "Slider" if motor < 6 else "Presser"
            string_id = motor if motor < 6 else motor - 6
            
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=trajectory_array[:, motor],
                    mode='lines',
                    name=f'LH {motor_type} {string_id}',
                    legendgroup='left_hand'
                )
            )
        
        # Plot right hand motors (12-14)
        for motor in range(12, min(15, trajectory_array.shape[1])):
            picker_id = motor - 12
            
            fig.add_trace(
                go.Scatter(
                    x=timestamps,
                    y=trajectory_array[:, motor],
                    mode='lines',
                    name=f'RH Picker {picker_id}',
                    line=dict(width=2),
                    legendgroup='right_hand'
                )
            )
        
        # Update layout (mimicking GuitarBotParser)
        fig.update_layout(
            title=title,
            xaxis_title='Time (s)',
            yaxis_title='Motor Position',
            legend_title='Motors'
        )
        
        fig.show()


# Example usage and testing
if __name__ == "__main__":
    parser = Parser()
    
    print("=== Parser Test - Coordinated Left/Right Hand ===")
    
    print("\\n=== Test 1: Complete Note Production ===")
    # Test complete note (fret + pluck)
    note_traj = parser.parse_note_message(
        midi_note=45,  # Low E 5th fret
        presser_force=0.8,
        pluck_velocity=100,
        use_velocity_mapping=True,
        timestamp=0.0
    )
    print(f"Note trajectory shape: {note_traj.shape}")
    
    print("\\n=== Test 2: Fret-Only Message ===") 
    # Test fretting without plucking
    fret_traj = parser.parse_fret_only_message(midi_note=52, presser_force=0.6, timestamp=1.0)
    print(f"Fret-only trajectory shape: {fret_traj.shape}")
    
    print("\\n=== Test 3: Dynamics-Only Message ===")
    # Test plucking without fretting
    dyn_traj = parser.parse_dynamics_message([42, 55, 65])
    print(f"Dynamics trajectory shape: {dyn_traj.shape}")
    
    print("\\n=== Test 4: Chord Sequence ===")
    # Test chord progression
    chord_events = [
        ([40, 52, 64], 0.0, 0.7),    # C major chord at t=0
        ([42, 54, 66], 2.0, 0.8),    # D major chord at t=2
    ]
    pluck_events = [
        (40, 0.5, 120),  # Pluck low E
        (52, 1.0, 100),  # Pluck D
    ]
    
    chord_traj = parser.parse_chord_sequence(chord_events, pluck_events)
    print(f"Chord sequence trajectory shape: {chord_traj.shape}")
    
    print("\\n=== Combined Status ===")
    status = parser.get_combined_status()
    
    print("Left Hand Status:")
    for string_id in range(6):
        if f'string_{string_id}' in status['left_hand']:
            info = status['left_hand'][f'string_{string_id}']
            print(f"  String {string_id}: Fret {info['fret']}, Pressed: {info['pressed']}")
    
    print("\\nRight Hand Status:")
    for picker_id, info in status['right_hand'].items():
        print(f"  {picker_id}: Motor {info['motor_id']}, {info['state']}, "
              f"{info['position_mm']:.2f}mm")
    
    print(f"\\nTiming: {status['timing']['prep_time_seconds']}s prep time "
          f"({status['timing']['prep_time_points']} points)")
    
    # Reset everything
    parser.reset_all_positions()
    
    print("\\n=== Test Complete ===")