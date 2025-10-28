#!/usr/bin/env python3
"""
Test script for force testing workflow in LeftHandParser.

This tests the CORRECT behavior for force testing:
1. Each /Fret message with force>0: Apply torque directly (no unpress→slide→press)
2. Successive messages: Just adjust torque (no unpressing)
3. Final message with force=0: Unpress to -650

Expected trajectory pattern:
- Message 1 (force=0.2): 0 → 100 (apply 20% torque)
- Message 2 (force=0.4): 100 → 200 (adjust to 40% torque)
- Message 3 (force=0.6): 200 → 300 (adjust to 60% torque)
- Message 4 (force=0): 300 → -650 (unpress completely)

NO unpressing between messages 1-3!
"""

import numpy as np
from LeftHandParser import LeftHandParser
import tune as tu

def test_force_testing_sequence():
    """Test the complete force testing workflow."""
    print("\n" + "="*70)
    print("FORCE TESTING WORKFLOW TEST")
    print("="*70)
    
    parser = LeftHandParser()
    
    # Test parameters
    midi_note = 48  # C3 on string 2
    string_id = 2
    fret_num = 8
    
    force_sequence = [0.2, 0.4, 0.6, 0.0]  # Final 0 means unpress
    expected_torques = [
        0.2 * tu.LH_PRESSER_PRESSED_POS,  # 100
        0.4 * tu.LH_PRESSER_PRESSED_POS,  # 200
        0.6 * tu.LH_PRESSER_PRESSED_POS,  # 300
        tu.LH_PRESSER_UNPRESSED_POS        # -650
    ]
    
    print(f"\nTesting force sequence on MIDI note {midi_note} (String {string_id}, Fret {fret_num})")
    print(f"Forces: {force_sequence}")
    print(f"Expected torques: {expected_torques}")
    
    presser_motor_id = string_id + 6
    all_trajectories = []
    
    for i, (force, expected_torque) in enumerate(zip(force_sequence, expected_torques)):
        print(f"\n--- Message {i+1}: Force {force} (Expected torque: {expected_torque:.1f}) ---")
        
        # Generate trajectory
        if force == 0:
            # Special case: Send fret 0 for unpressing
            traj = parser.generate_fret_trajectory(
                string_id=string_id,
                fret_num=0,  # Force=0 means open string (unpress)
                presser_force=None,
                timestamp=i * 1.0,  # 1 second apart
                force_adjustment_only=True
            )
        else:
            traj = parser.generate_fret_trajectory(
                string_id=string_id,
                fret_num=fret_num,
                presser_force=force,
                timestamp=i * 1.0,
                force_adjustment_only=True  # KEY: Enable simplified mode
            )
        
        # Extract presser trajectory
        presser_traj = traj[:, presser_motor_id]
        presser_traj = presser_traj[~np.isnan(presser_traj)]
        
        print(f"  Start torque: {presser_traj[0]:.1f}")
        print(f"  End torque: {presser_traj[-1]:.1f}")
        print(f"  Min torque: {presser_traj.min():.1f}")
        print(f"  Max torque: {presser_traj.max():.1f}")
        
        all_trajectories.append(presser_traj)
        
        # Verify end torque matches expected
        assert abs(presser_traj[-1] - expected_torque) < 10, \
            f"End torque {presser_traj[-1]:.1f} doesn't match expected {expected_torque:.1f}"
        
        # Critical check: For messages 2-3, torque should NOT go to 0 or -650
        if i > 0 and i < 3:  # Messages 2 and 3
            print(f"  ✓ Checking no unpressing during increment...")
            min_allowed = expected_torques[i-1] * 0.8  # Should stay above 80% of previous
            assert presser_traj.min() > min_allowed, \
                f"Torque dropped to {presser_traj.min():.1f}, should stay above {min_allowed:.1f}"
            print(f"    Torque stayed above {min_allowed:.1f} ✓")
    
    print("\n" + "="*70)
    print("✓ FORCE TESTING WORKFLOW VERIFIED")
    print("="*70)
    print("\nSummary:")
    print("- Message 1: Applied initial torque (no unpressing)")
    print("- Messages 2-3: Adjusted torque (maintained engagement, no unpressing)")
    print("- Message 4: Unpressed to -650")
    print("\nThis is the CORRECT behavior for force testing!")
    
    return True


def test_comparison():
    """Show the difference between normal mode and force_adjustment_only mode."""
    print("\n" + "="*70)
    print("COMPARISON: Normal vs Force Testing Mode")
    print("="*70)
    
    print("\nNORMAL MODE (force_adjustment_only=False):")
    print("  - Full 3-phase trajectory:")
    print("    Phase 1: Unpress (torque → 0)")
    print("    Phase 2: Slide (torque = 0, slider moves)")
    print("    Phase 3: Press (torque → target)")
    print("  - Used for: Normal music playing")
    
    print("\nFORCE TESTING MODE (force_adjustment_only=True):")
    print("  - Simplified trajectories:")
    print("    • Same fret: Just adjust torque (1 phase)")
    print("    • Different fret: Release → Slide+Press (2 phases)")
    print("    • Force=0: Unpress to -650")
    print("  - Used for: Force calibration experiments")
    
    print("\nKey Benefits:")
    print("  ✓ No unnecessary unpressing between tests")
    print("  ✓ Faster test execution")
    print("  ✓ String maintains contact during force changes")
    print("  ✓ More accurate force testing")


if __name__ == "__main__":
    try:
        test_force_testing_sequence()
        test_comparison()
        
        print("\n" + "="*70)
        print("ALL TESTS PASSED ✓")
        print("="*70)
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
