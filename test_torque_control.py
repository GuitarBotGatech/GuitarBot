#!/usr/bin/env python3
"""
Test script for torque-based presser control in LeftHandParser.

This script demonstrates the CORRECT control model:
- Presser commands are TORQUE values (not positions)
- 0 = motor idle/holding position
- Positive value = motor applies force (value/1000 = % of rated torque)
- Force increments maintain engagement (like slide_toggle)

Tests:
1. Normal fretting (3-phase: release → idle → apply torque)
2. Force adjustment (single phase: increment torque without releasing)
3. Force increment sequence (0 → 150 → 300 → 450)
"""

import sys
import numpy as np
from LeftHandParser import LeftHandParser
import tune as tu

def test_torque_calculation():
    """Test that get_presser_torque returns correct torque values."""
    print("\n" + "="*70)
    print("TEST 1: Torque Calculation")
    print("="*70)
    
    parser = LeftHandParser()
    
    # Test open string (fret 0)
    torque_open = parser.get_presser_torque(string_id=0, fret_num=0)
    print(f"Open string (fret 0): {torque_open} (should be 0 = idle)")
    assert torque_open == 0, "Open string should have 0 torque"
    
    # Test default torque (no force specified)
    torque_default = parser.get_presser_torque(string_id=0, fret_num=5)
    print(f"Default torque (fret 5): {torque_default} (should be {tu.LH_PRESSER_PRESSED_POS})")
    assert torque_default == tu.LH_PRESSER_PRESSED_POS, "Default should be max torque"
    
    # Test force scaling
    test_forces = [0.0, 0.3, 0.6, 0.9, 1.0]
    print(f"\nForce scaling (max_torque = {tu.LH_PRESSER_PRESSED_POS}):")
    for force in test_forces:
        torque = parser.get_presser_torque(string_id=0, fret_num=5, presser_force=force)
        expected = force * tu.LH_PRESSER_PRESSED_POS
        print(f"  Force {force:.1f} → Torque {torque:.1f} (expected {expected:.1f})")
        assert abs(torque - expected) < 0.1, f"Torque calculation error: {torque} != {expected}"
    
    print("✓ All torque calculations correct\n")


def test_normal_fretting():
    """Test normal 3-phase fretting trajectory with torque control."""
    print("\n" + "="*70)
    print("TEST 2: Normal Fretting (3-Phase Torque Control)")
    print("="*70)
    
    parser = LeftHandParser()
    
    # Fret string 0 at fret 5 with 60% force
    string_id = 0
    fret_num = 5
    presser_force = 0.6
    
    print(f"Fretting string {string_id} at fret {fret_num} with {presser_force*100:.0f}% force")
    print(f"Expected torque: {presser_force * tu.LH_PRESSER_PRESSED_POS:.1f}")
    
    trajectory = parser.generate_fret_trajectory(
        string_id=string_id,
        fret_num=fret_num,
        presser_force=presser_force,
        timestamp=0.0,
        force_adjustment_only=False
    )
    
    # Verify trajectory shape
    assert trajectory.shape[1] == 12, "Should have 12 motor columns"
    
    # Extract presser trajectory
    presser_motor_id = string_id + 6
    presser_traj = trajectory[:, presser_motor_id]
    
    # Remove NaN values
    presser_traj = presser_traj[~np.isnan(presser_traj)]
    
    print(f"\nTrajectory analysis:")
    print(f"  Total timesteps: {len(presser_traj)}")
    print(f"  Initial torque: {presser_traj[0]:.1f}")
    print(f"  Final torque: {presser_traj[-1]:.1f}")
    print(f"  Min torque: {presser_traj.min():.1f}")
    print(f"  Max torque: {presser_traj.max():.1f}")
    
    # Verify 3-phase pattern
    target_torque = presser_force * tu.LH_PRESSER_PRESSED_POS
    
    # Phase 1: Should ramp down to 0
    phase1_end = tu.PRESSER_INTERPOLATION_POINTS
    if len(presser_traj) >= phase1_end:
        print(f"\nPhase 1 (Release to idle):")
        print(f"  Start: {presser_traj[0]:.1f} → End: {presser_traj[phase1_end-1]:.1f}")
        assert presser_traj[phase1_end-1] < 5, "Phase 1 should end near 0 (idle)"
    
    # Phase 2: Should stay at 0
    phase2_start = phase1_end
    phase2_end = phase1_end + tu.LH_SINGLE_NOTE_MOTION_POINTS
    if len(presser_traj) >= phase2_end:
        phase2_torques = presser_traj[phase2_start:phase2_end]
        print(f"Phase 2 (Idle during slide):")
        print(f"  Mean torque: {phase2_torques.mean():.1f} (should be ~0)")
        assert phase2_torques.max() < 5, "Phase 2 should stay near 0 (idle)"
    
    # Phase 3: Should ramp up to target
    phase3_start = phase2_end
    if len(presser_traj) >= phase3_start + tu.PRESSER_INTERPOLATION_POINTS:
        print(f"Phase 3 (Apply target torque):")
        print(f"  Start: {presser_traj[phase3_start]:.1f} → End: {presser_traj[-1]:.1f}")
        print(f"  Target: {target_torque:.1f}")
        assert abs(presser_traj[-1] - target_torque) < 5, f"Final torque should be ~{target_torque:.1f}"
    
    print("✓ 3-phase torque trajectory verified\n")


def test_force_adjustment():
    """Test force adjustment mode (increment torque without releasing)."""
    print("\n" + "="*70)
    print("TEST 3: Force Adjustment (Torque Increment Without Release)")
    print("="*70)
    
    parser = LeftHandParser()
    string_id = 0
    fret_num = 5
    
    # First, fret at 30% force
    initial_force = 0.3
    print(f"Initial fretting: string {string_id}, fret {fret_num}, force {initial_force*100:.0f}%")
    
    traj1 = parser.generate_fret_trajectory(
        string_id=string_id,
        fret_num=fret_num,
        presser_force=initial_force,
        timestamp=0.0,
        force_adjustment_only=False
    )
    
    initial_torque = initial_force * tu.LH_PRESSER_PRESSED_POS
    print(f"  Initial torque: {initial_torque:.1f}")
    
    # Now increment to 60% force using force_adjustment_only
    new_force = 0.6
    print(f"\nForce adjustment: increment to {new_force*100:.0f}% force")
    
    traj2 = parser.generate_fret_trajectory(
        string_id=string_id,
        fret_num=fret_num,
        presser_force=new_force,
        timestamp=traj1.shape[0] * tu.TIME_STEP,
        force_adjustment_only=True  # KEY: This enables torque increment mode
    )
    
    target_torque = new_force * tu.LH_PRESSER_PRESSED_POS
    print(f"  Target torque: {target_torque:.1f}")
    
    # Extract presser trajectory
    presser_motor_id = string_id + 6
    presser_traj = traj2[:, presser_motor_id]
    presser_traj = presser_traj[~np.isnan(presser_traj)]
    
    print(f"\nForce adjustment trajectory:")
    print(f"  Start torque: {presser_traj[0]:.1f}")
    print(f"  End torque: {presser_traj[-1]:.1f}")
    print(f"  Min torque: {presser_traj.min():.1f}")
    
    # CRITICAL CHECK: Torque should NEVER go to 0 during force adjustment
    print(f"\nCritical check:")
    print(f"  Torque never reaches 0: {presser_traj.min() > 5} (min = {presser_traj.min():.1f})")
    assert presser_traj.min() > initial_torque * 0.8, "Torque should stay engaged during adjustment"
    assert abs(presser_traj[-1] - target_torque) < 5, f"Final torque should be ~{target_torque:.1f}"
    
    print("✓ Force adjustment maintains engagement (no release to 0)\n")


def test_force_increment_sequence():
    """Test a sequence of force increments (like force testing experiments)."""
    print("\n" + "="*70)
    print("TEST 4: Force Increment Sequence (0% → 30% → 60% → 90%)")
    print("="*70)
    
    parser = LeftHandParser()
    string_id = 0
    fret_num = 5
    
    force_sequence = [0.3, 0.6, 0.9]
    torque_sequence = [f * tu.LH_PRESSER_PRESSED_POS for f in force_sequence]
    
    print(f"Testing force sequence on string {string_id}, fret {fret_num}:")
    for i, (force, target_torque) in enumerate(zip(force_sequence, torque_sequence)):
        print(f"\nStep {i+1}: Force {force*100:.0f}% (Torque {target_torque:.1f})")
        
        # First step uses normal fretting, rest use force_adjustment_only
        force_adjustment_only = (i > 0)
        
        traj = parser.generate_fret_trajectory(
            string_id=string_id,
            fret_num=fret_num,
            presser_force=force,
            timestamp=i * 0.5,  # Space out by 500ms
            force_adjustment_only=force_adjustment_only
        )
        
        # Extract presser trajectory
        presser_motor_id = string_id + 6
        presser_traj = traj[:, presser_motor_id]
        presser_traj = presser_traj[~np.isnan(presser_traj)]
        
        print(f"  Final torque: {presser_traj[-1]:.1f}")
        
        if force_adjustment_only:
            # After first step, torque should never go to 0
            print(f"  Min torque during adjustment: {presser_traj.min():.1f}")
            assert presser_traj.min() > 50, "Torque should stay engaged during increments"
        
        assert abs(presser_traj[-1] - target_torque) < 5, f"Final torque should be ~{target_torque:.1f}"
    
    print("\n✓ Force increment sequence verified (maintains engagement)\n")


def compare_with_position_based():
    """Compare torque-based vs old position-based approach."""
    print("\n" + "="*70)
    print("COMPARISON: Torque-Based vs Position-Based Control")
    print("="*70)
    
    print("\nOLD APPROACH (Position-Based - INCORRECT):")
    print("  - Treated presser commands as absolute positions")
    print("  - Force adjustment: Move from position A to position B")
    print("  - Problem: Motor must unpress → move → repress")
    print("  - Result: String loses contact during force changes")
    
    print("\nNEW APPROACH (Torque-Based - CORRECT):")
    print("  - Presser commands are torque values (0 = idle, >0 = force)")
    print("  - Force adjustment: Increment torque while maintaining contact")
    print("  - Inspired by slide_toggle (maintains torque during motion)")
    print("  - Result: String stays pressed during force changes")
    
    print("\nKey Insight:")
    print("  - Embedded controller handles position control internally")
    print("  - We send torque commands (% of rated torque)")
    print("  - Motor applies force and finds equilibrium position")
    print("  - This is how slide_toggle works in GuitarBotParser")
    
    print("\nConstants:")
    print(f"  - LH_PRESSER_PRESSED_POS = {tu.LH_PRESSER_PRESSED_POS} (50% rated torque)")
    print(f"  - LH_PRESSER_SLIDE_PRESS_POS = {tu.LH_PRESSER_SLIDE_PRESS_POS} (40% rated torque)")
    print(f"  - 0 = Motor idle/holding position")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("TORQUE-BASED PRESSER CONTROL TEST SUITE")
    print("="*70)
    print("\nThis test suite validates the conversion from position-based to")
    print("torque-based control for the presser motors.")
    print("\nKey concept: Presser commands are TORQUE values, not positions.")
    
    try:
        test_torque_calculation()
        test_normal_fretting()
        test_force_adjustment()
        test_force_increment_sequence()
        compare_with_position_based()
        
        print("\n" + "="*70)
        print("ALL TESTS PASSED ✓")
        print("="*70)
        print("\nTorque-based control is working correctly!")
        print("Force adjustments maintain engagement (no release to 0).")
        print("This matches the slide_toggle behavior in GuitarBotParser.")
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
