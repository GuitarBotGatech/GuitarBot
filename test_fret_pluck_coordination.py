"""
test_fret_pluck_coordination.py - Diagnostic tool for fret/pluck timing analysis

This script generates trajectories for various fret/pluck scenarios and logs
detailed timing information to help diagnose coordination issues.

Output:
- Detailed timing logs to console
- CSV file with trajectory analysis
- Optional trajectory plots
"""

import numpy as np
import sys
from pathlib import Path
from datetime import datetime
import csv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from BothHandsParser import BothHandsParser
from LeftHandParser import LeftHandParser
import tune as tu


class CoordinationTester:
    """Test and analyze fret/pluck coordination timing."""
    
    def __init__(self, output_dir=None):
        """Initialize tester."""
        self.parser = BothHandsParser()
        self.output_dir = Path(output_dir) if output_dir else Path(__file__).parent / "coordination_logs"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.output_dir / f"coordination_test_{timestamp}.csv"
        
        self.test_results = []
        
        print("="*80)
        print("FRET/PLUCK COORDINATION TESTER")
        print("="*80)
        print(f"Output directory: {self.output_dir}")
        print(f"Log file: {self.log_file.name}")
        print()
    
    def analyze_trajectory(self, trajectory, test_name, midi_note, presser_position, 
                          position_adjustment_only):
        """
        Analyze a trajectory to extract timing information.
        
        Args:
            trajectory: 2D numpy array [timesteps x 15]
            test_name: Name of this test
            midi_note: MIDI note number
            presser_position: Presser position used
            position_adjustment_only: Whether position_adjustment_only was used
            
        Returns:
            Dictionary with timing analysis
        """
        if trajectory.size == 0:
            return None
        
        # Get string/fret info
        string_fret_info = self.parser.left_hand.midi_note_to_string_fret(midi_note)
        if not string_fret_info:
            return None
        
        string_id, fret_num = string_fret_info
        
        # Motor indices
        slider_motor_id = string_id
        presser_motor_id = string_id + 6
        picker_motor_id = self.parser.right_hand.midi_note_to_picker_id(midi_note)
        
        if picker_motor_id is None:
            return None
        
        picker_motor_id += 12  # Offset for RH motors in 15-motor array
        
        # Extract trajectories
        slider_traj = trajectory[:, slider_motor_id]
        presser_traj = trajectory[:, presser_motor_id]
        picker_traj = trajectory[:, picker_motor_id]
        
        # Find key timing points
        
        # 1. Slider movement
        slider_changes = np.abs(np.diff(slider_traj))
        slider_moving = slider_changes > 1.0
        slider_start_idx = np.where(slider_moving)[0][0] if np.any(slider_moving) else 0
        slider_end_idx = np.where(slider_moving)[0][-1] + 1 if np.any(slider_moving) else 0
        
        # 2. Presser movement
        presser_changes = np.abs(np.diff(presser_traj))
        presser_moving = presser_changes > 1.0
        presser_start_idx = np.where(presser_moving)[0][0] if np.any(presser_moving) else 0
        presser_end_idx = np.where(presser_moving)[0][-1] + 1 if np.any(presser_moving) else 0
        
        # Find when presser reaches target position
        if presser_position is not None:
            target_presser_pos = presser_position
        else:
            target_presser_pos = tu.LH_PRESSER_PRESSED_POS
        
        tolerance = max(5.0, target_presser_pos * 0.05)
        at_target = np.abs(presser_traj - target_presser_pos) < tolerance
        
        presser_settled_idx = None
        for i in range(len(at_target) - 5):
            if at_target[i] and np.all(at_target[i:i+5]):
                presser_settled_idx = i
                break
        
        if presser_settled_idx is None:
            presser_settled_idx = presser_end_idx
        
        # 3. Picker movement
        picker_changes = np.abs(np.diff(picker_traj))
        picker_moving = picker_changes > 1.0
        picker_start_idx = np.where(picker_moving)[0][0] if np.any(picker_moving) else 0
        picker_end_idx = np.where(picker_moving)[0][-1] + 1 if np.any(picker_moving) else 0
        
        # Convert indices to time
        slider_start_time = slider_start_idx * tu.TIME_STEP
        slider_end_time = slider_end_idx * tu.TIME_STEP
        presser_start_time = presser_start_idx * tu.TIME_STEP
        presser_end_time = presser_end_idx * tu.TIME_STEP
        presser_settled_time = presser_settled_idx * tu.TIME_STEP
        picker_start_time = picker_start_idx * tu.TIME_STEP
        picker_end_time = picker_end_idx * tu.TIME_STEP
        
        # Calculate delays
        pluck_delay_from_presser_end = picker_start_time - presser_end_time
        pluck_delay_from_presser_settled = picker_start_time - presser_settled_time
        
        # Determine if coordination is correct
        # Pluck should start AFTER presser settles (positive delay)
        coordination_ok = pluck_delay_from_presser_settled > 0
        
        result = {
            'test_name': test_name,
            'midi_note': midi_note,
            'string_id': string_id,
            'fret_num': fret_num,
            'presser_position': presser_position if presser_position else target_presser_pos,
            'position_adjustment_only': position_adjustment_only,
            'trajectory_length': len(trajectory),
            'trajectory_duration': len(trajectory) * tu.TIME_STEP,
            
            # Slider timing
            'slider_start_idx': slider_start_idx,
            'slider_end_idx': slider_end_idx,
            'slider_start_time': slider_start_time,
            'slider_end_time': slider_end_time,
            'slider_duration': slider_end_time - slider_start_time,
            
            # Presser timing
            'presser_start_idx': presser_start_idx,
            'presser_end_idx': presser_end_idx,
            'presser_settled_idx': presser_settled_idx,
            'presser_start_time': presser_start_time,
            'presser_end_time': presser_end_time,
            'presser_settled_time': presser_settled_time,
            'presser_duration': presser_end_time - presser_start_time,
            'presser_target_position': target_presser_pos,
            'presser_final_position': presser_traj[presser_settled_idx] if presser_settled_idx < len(presser_traj) else presser_traj[-1],
            
            # Picker timing
            'picker_start_idx': picker_start_idx,
            'picker_end_idx': picker_end_idx,
            'picker_start_time': picker_start_time,
            'picker_end_time': picker_end_time,
            'picker_duration': picker_end_time - picker_start_time,
            
            # Coordination analysis
            'pluck_delay_from_presser_end': pluck_delay_from_presser_end,
            'pluck_delay_from_presser_settled': pluck_delay_from_presser_settled,
            'coordination_ok': coordination_ok,
            
            # Configured delays
            'configured_settling_time': self.parser.settling_time,
            'configured_pluck_delay': self.parser.pluck_delay_after_press,
        }
        
        return result
    
    def run_test(self, test_name, midi_note, presser_position=None, 
                 position_adjustment_only=False, reset_state=True):
        """
        Run a single coordination test.
        
        Args:
            test_name: Descriptive name for this test
            midi_note: MIDI note to play
            presser_position: Optional presser position
            position_adjustment_only: Whether to use position_adjustment_only mode
            reset_state: Whether to reset parser state before test
        """
        print(f"\n{'='*80}")
        print(f"TEST: {test_name}")
        print(f"{'='*80}")
        print(f"  MIDI Note: {midi_note}")
        print(f"  Presser Position: {presser_position if presser_position else 'default'}")
        print(f"  Position Adjustment Only: {position_adjustment_only}")
        print(f"  Reset State: {reset_state}")
        
        # Reset state if requested
        if reset_state:
            self.parser.left_hand.reset_positions()
            self.parser.right_hand.reset_positions()
            print("  State reset: YES")
        else:
            print("  State reset: NO (continuing from previous)")
        
        # Generate trajectory
        trajectory = self.parser.parse_fret_with_pluck(
            midi_note=midi_note,
            presser_position=presser_position,
            pluck_velocity=None,
            timestamp=0.0,
            position_adjustment_only=position_adjustment_only
        )
        
        # Analyze trajectory
        result = self.analyze_trajectory(
            trajectory, test_name, midi_note, presser_position, position_adjustment_only
        )
        
        if result:
            self.test_results.append(result)
            
            # Print analysis
            print(f"\n  TIMING ANALYSIS:")
            print(f"    Slider:  {result['slider_start_time']:.4f}s → {result['slider_end_time']:.4f}s (duration: {result['slider_duration']:.4f}s)")
            print(f"    Presser: {result['presser_start_time']:.4f}s → {result['presser_end_time']:.4f}s (duration: {result['presser_duration']:.4f}s)")
            print(f"    Presser settled at: {result['presser_settled_time']:.4f}s")
            print(f"    Picker:  {result['picker_start_time']:.4f}s → {result['picker_end_time']:.4f}s (duration: {result['picker_duration']:.4f}s)")
            
            print(f"\n  COORDINATION:")
            print(f"    Delay from presser end to pluck:     {result['pluck_delay_from_presser_end']:+.4f}s")
            print(f"    Delay from presser settled to pluck: {result['pluck_delay_from_presser_settled']:+.4f}s")
            print(f"    Configured settling time:             {result['configured_settling_time']:.4f}s")
            
            if result['coordination_ok']:
                print(f"    Status: ✓ OK - Pluck occurs AFTER presser settles")
            else:
                print(f"    Status: ✗ FAIL - Pluck occurs BEFORE presser settles!")
                print(f"            Gap: {result['pluck_delay_from_presser_settled']:.4f}s (negative = pluck too early)")
            
            print(f"\n  PRESSER POSITION:")
            print(f"    Target:  {result['presser_target_position']:.1f}")
            print(f"    Actual:  {result['presser_final_position']:.1f}")
        else:
            print("  ERROR: Could not analyze trajectory")
        
        return trajectory, result
    
    def save_results(self):
        """Save test results to CSV file."""
        if not self.test_results:
            print("\nNo results to save.")
            return
        
        print(f"\n{'='*80}")
        print("SAVING RESULTS")
        print(f"{'='*80}")
        
        # Write CSV
        fieldnames = self.test_results[0].keys()
        with open(self.log_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.test_results)
        
        print(f"Saved {len(self.test_results)} test results to: {self.log_file}")
        
        # Print summary
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        
        total_tests = len(self.test_results)
        ok_tests = sum(1 for r in self.test_results if r['coordination_ok'])
        fail_tests = total_tests - ok_tests
        
        print(f"Total tests: {total_tests}")
        print(f"  OK:   {ok_tests} ({100*ok_tests/total_tests:.1f}%)")
        print(f"  FAIL: {fail_tests} ({100*fail_tests/total_tests:.1f}%)")
        
        if fail_tests > 0:
            print(f"\nFailed tests:")
            for r in self.test_results:
                if not r['coordination_ok']:
                    print(f"  - {r['test_name']}: pluck {r['pluck_delay_from_presser_settled']:.4f}s before settled")
        
        # Timing statistics
        pluck_delays = [r['pluck_delay_from_presser_settled'] for r in self.test_results]
        mean_delay = np.mean(pluck_delays)
        std_delay = np.std(pluck_delays)
        min_delay = np.min(pluck_delays)
        max_delay = np.max(pluck_delays)
        
        print(f"\nPluck delay statistics (from presser settled):")
        print(f"  Mean:   {mean_delay:+.4f}s ± {std_delay:.4f}s")
        print(f"  Range:  [{min_delay:+.4f}s, {max_delay:+.4f}s]")
        print(f"  Target: {self.test_results[0]['configured_settling_time']:.4f}s")


def main():
    """Run coordination tests."""
    tester = CoordinationTester()
    
    # Test 1: Basic fret change (should unpress, slide, press)
    print("\n" + "="*80)
    print("SCENARIO 1: Basic Fret Changes (Full Trajectory)")
    print("="*80)
    print("Expected: Unpress → Slide → Press → Pluck")
    
    tester.run_test(
        "Test 1a: MIDI 45 (E string, fret 5) from reset",
        midi_note=45,
        presser_position=400,
        position_adjustment_only=False,
        reset_state=True
    )
    
    tester.run_test(
        "Test 1b: MIDI 47 (E string, fret 7) from fret 5",
        midi_note=47,
        presser_position=400,
        position_adjustment_only=False,
        reset_state=False
    )
    
    # Test 2: Same fret, different positions (should auto-enable position_adjustment_only)
    print("\n" + "="*80)
    print("SCENARIO 2: Position Optimization (Same Fret, Increasing Position)")
    print("="*80)
    print("Expected: Smooth position transitions WITHOUT unpressing")
    print("Should auto-enable position_adjustment_only mode")
    
    # Start at fret 5
    tester.run_test(
        "Test 2a: Fret 5, position 200",
        midi_note=45,
        presser_position=200,
        position_adjustment_only=False,  # Should auto-enable
        reset_state=True
    )
    
    tester.run_test(
        "Test 2b: Fret 5, position 250",
        midi_note=45,
        presser_position=250,
        position_adjustment_only=False,  # Should auto-enable
        reset_state=False
    )
    
    tester.run_test(
        "Test 2c: Fret 5, position 300",
        midi_note=45,
        presser_position=300,
        position_adjustment_only=False,  # Should auto-enable
        reset_state=False
    )
    
    tester.run_test(
        "Test 2d: Fret 5, position 350",
        midi_note=45,
        presser_position=350,
        position_adjustment_only=False,  # Should auto-enable
        reset_state=False
    )
    
    tester.run_test(
        "Test 2e: Fret 5, position 400",
        midi_note=45,
        presser_position=400,
        position_adjustment_only=False,  # Should auto-enable
        reset_state=False
    )
    
    # Test 3: Explicit position_adjustment_only mode
    print("\n" + "="*80)
    print("SCENARIO 3: Explicit Position Adjustment Mode")
    print("="*80)
    print("Expected: Direct position changes")
    
    tester.run_test(
        "Test 3a: Fret 7, position 350, explicit mode",
        midi_note=47,
        presser_position=350,
        position_adjustment_only=True,
        reset_state=True
    )
    
    tester.run_test(
        "Test 3b: Fret 7, position 450, explicit mode",
        midi_note=47,
        presser_position=450,
        position_adjustment_only=True,
        reset_state=False
    )
    
    # Test 4: Different strings
    print("\n" + "="*80)
    print("SCENARIO 4: Different Strings")
    print("="*80)
    
    tester.run_test(
        "Test 4a: String 0 (E), fret 5",
        midi_note=45,
        presser_position=400,
        position_adjustment_only=False,
        reset_state=True
    )
    
    tester.run_test(
        "Test 4b: String 1 (D), fret 5",
        midi_note=52,
        presser_position=400,
        position_adjustment_only=False,
        reset_state=False
    )
    
    tester.run_test(
        "Test 4c: String 2 (B), fret 5",
        midi_note=62,
        presser_position=400,
        position_adjustment_only=False,
        reset_state=False
    )
    
    # Save results
    tester.save_results()
    
    print(f"\n{'='*80}")
    print("TESTING COMPLETE")
    print(f"{'='*80}")
    print(f"Log file: {tester.log_file}")
    print()


if __name__ == "__main__":
    main()
