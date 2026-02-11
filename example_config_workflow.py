#!/usr/bin/env python3
"""
example_config_workflow.py - Example workflow using /Config messages

This demonstrates a practical use case: testing different force levels
and motion speeds without restarting the receiver.
"""

from pythonosc import udp_client
from config_helper import ConfigHelper
import time


def test_force_levels():
    """Test different presser force levels with varying motion speeds."""
    
    print("="*70)
    print("Force Level Test - Using /Config to adjust parameters on the fly")
    print("="*70)
    
    # Setup
    osc_client = udp_client.SimpleUDPClient("127.0.0.1", 12000)
    config = ConfigHelper()
    
    # Configure for testing
    print("\n1. Setting up test environment...")
    config.disable_graph()  # Faster execution
    config.set_unpress_after(True)  # Auto-release after each note
    
    # Test different motion speeds
    speeds = [
        ("Fast", 5, 20),    # presser_points, slider_points
        ("Medium", 10, 40),  # Default
        ("Slow", 20, 80),
    ]
    
    test_note = 45  # MIDI note to test
    forces = [0.3, 0.5, 0.7, 0.9]
    
    for speed_name, presser_pts, slider_pts in speeds:
        print(f"\n{'='*70}")
        print(f"Testing with {speed_name} motion speed")
        print(f"  Presser points: {presser_pts} ({presser_pts * 5}ms)")
        print(f"  Slider points: {slider_pts} ({slider_pts * 5}ms)")
        print(f"{'='*70}")
        
        # Update motion speed
        config.set_presser_points(presser_pts)
        config.set_slider_points(slider_pts)
        time.sleep(0.2)
        
        for force in forces:
            print(f"\n  Testing force: {force}")
            # Send /Fret message with current force
            osc_client.send_message("/Fret", [test_note, force])
            
            # Wait for motion to complete
            # Duration = presser + slider + presser + pluck
            duration = (presser_pts * 2 + slider_pts + 20) * 0.005
            time.sleep(duration + 0.5)  # Extra buffer for pluck ring
    
    # Cleanup
    print("\n\nTest complete! Resetting to defaults...")
    config.default_motion()
    config.set_unpress_after(False)
    config.enable_graph()
    
    print("\nReset complete.")


def test_with_force_adjustment_mode():
    """Test force adjustments without full motion (faster testing)."""
    
    print("="*70)
    print("Force Adjustment Test - Using force_adjustment_only mode")
    print("="*70)
    
    osc_client = udp_client.SimpleUDPClient("127.0.0.1", 12000)
    config = ConfigHelper()
    
    # Setup
    print("\n1. Initial fretting at default force...")
    config.disable_graph()
    config.set_force_adjustment_only(False)  # Normal mode first
    
    test_note = 50
    osc_client.send_message("/Fret", [test_note, 0.5])
    time.sleep(2.0)
    
    # Now enable force_adjustment_only to skip unpress/slide
    print("\n2. Enabling force_adjustment_only mode...")
    config.set_force_adjustment_only(True)
    time.sleep(0.2)
    
    print("\n3. Testing incremental force changes (no motion)...")
    forces = [0.6, 0.7, 0.8, 0.9, 1.0]
    
    for force in forces:
        print(f"   Adjusting to force: {force}")
        osc_client.send_message("/Fret", [test_note, force])
        time.sleep(0.5)  # Just wait for force change
    
    # Cleanup
    print("\n4. Resetting configuration...")
    config.set_force_adjustment_only(False)
    config.enable_graph()
    
    print("\nTest complete!")


def live_tuning_example():
    """Example of tuning parameters during a live session."""
    
    print("="*70)
    print("Live Tuning Example - Adjust timing while testing")
    print("="*70)
    
    config = ConfigHelper()
    osc_client = udp_client.SimpleUDPClient("127.0.0.1", 12000)
    
    # Start with testing mode
    print("\n1. Entering testing mode (fast motion, no graphs)...")
    config.testing_mode()
    
    # Play a sequence
    print("\n2. Playing test sequence with fast motion...")
    notes = [40, 45, 50, 55]
    for note in notes:
        osc_client.send_message("/Fret", [note, 0.7])
        time.sleep(0.8)  # Fast motion
    
    # Adjust for better sound
    print("\n3. Hmm, notes sound harsh. Let's slow down and smooth out...")
    config.set_blend_percent(0.4)  # Smoother transitions
    config.set_presser_points(15)  # Slower presser
    config.set_slider_points(60)   # Slower slider
    time.sleep(0.2)
    
    # Play again
    print("\n4. Playing again with adjusted parameters...")
    for note in notes:
        osc_client.send_message("/Fret", [note, 0.7])
        time.sleep(1.2)  # Slower motion
    
    # Perfect! Lock it in
    print("\n5. That sounds better! Locking in these settings...")
    config.disable_graph()  # Keep graphs off for performance
    
    print("\n6. You can continue playing with these optimized settings.")
    print("   Parameters are now:")
    print(f"     blend_percent = 0.4")
    print(f"     presser_points = 15 (75ms)")
    print(f"     slider_points = 60 (300ms)")
    
    print("\nLive tuning complete!")


if __name__ == "__main__":
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "GuitarBot Config Workflow Examples" + " "*19 + "║")
    print("╚" + "="*68 + "╝")
    print("\nMake sure arm_list_recieverNN.py is running before starting!\n")
    
    # Uncomment the test you want to run:
    
    # Test 1: Force levels at different speeds
    # test_force_levels()
    
    # Test 2: Force adjustment mode (faster testing)
    # test_with_force_adjustment_mode()
    
    # Test 3: Live tuning workflow
    # live_tuning_example()
    
    # For now, just show the menu
    print("Available examples:")
    print("  1. test_force_levels()          - Test forces at different motion speeds")
    print("  2. test_with_force_adjustment_mode() - Quick force testing")
    print("  3. live_tuning_example()        - Adjust parameters during playback")
    print("\nUncomment the function you want to run in the script.")
    print("\nOr import this module and call the functions directly:")
    print("  from example_config_workflow import test_force_levels")
    print("  test_force_levels()")
