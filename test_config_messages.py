#!/usr/bin/env python3
"""
test_config_messages.py - Test script for /Config OSC messages

This script demonstrates how to send configuration updates to the
running arm_list_recieverNN.py server to change runtime flags.

Usage:
    1. Start arm_list_recieverNN.py in one terminal
    2. Run this script in another terminal
    3. Watch the receiver update its configuration
"""

from pythonosc import udp_client
import time

# OSC server address (same as arm_list_recieverNN.py)
OSC_IP = "127.0.0.1"
OSC_PORT = 12000

def send_config(client, flag_name, value):
    """Send a /Config message to update a runtime flag."""
    print(f"\nSending: /Config \"{flag_name}\" {value}")
    client.send_message("/Config", [flag_name, value])
    time.sleep(0.1)  # Small delay to see output


def main():
    print("="*60)
    print("GuitarBot Configuration Test")
    print("="*60)
    print(f"Connecting to OSC server at {OSC_IP}:{OSC_PORT}\n")
    
    # Create OSC client
    client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
    
    print("Testing configuration updates...\n")
    
    # Test 1: Toggle graphing
    print("--- Test 1: Toggle Graphing ---")
    send_config(client, "graph", False)
    time.sleep(0.5)
    send_config(client, "graph", True)
    time.sleep(0.5)
    
    # Test 2: Behavioral flags
    print("\n--- Test 2: Behavioral Flags ---")
    send_config(client, "unpress_after", True)
    time.sleep(0.5)
    send_config(client, "force_adjustment_only", False)
    time.sleep(0.5)
    
    # Test 3: Trajectory timing parameters
    print("\n--- Test 3: Trajectory Timing ---")
    send_config(client, "blend_percent", 0.3)
    time.sleep(0.5)
    send_config(client, "presser_points", 15)
    time.sleep(0.5)
    send_config(client, "slider_points", 50)
    time.sleep(0.5)
    send_config(client, "picker_points", 20)
    time.sleep(0.5)
    
    # Test 4: Timing parameters
    print("\n--- Test 4: Coordination Timing ---")
    send_config(client, "lh_prep_time", 0.5)
    time.sleep(0.5)
    
    # Test 5: Reset to defaults
    print("\n--- Test 5: Reset to Defaults ---")
    send_config(client, "graph", True)
    send_config(client, "blend_percent", 0.2)
    send_config(client, "presser_points", 10)
    send_config(client, "slider_points", 40)
    send_config(client, "picker_points", 11)
    send_config(client, "lh_prep_time", 0.450)
    send_config(client, "unpress_after", False)
    send_config(client, "force_adjustment_only", False)
    
    # Test 6: Error handling
    print("\n--- Test 6: Error Handling ---")
    print("Testing invalid flag name...")
    send_config(client, "invalid_flag", True)
    time.sleep(0.5)
    
    print("Testing out-of-range value...")
    send_config(client, "blend_percent", 2.0)  # Out of range (0-1)
    time.sleep(0.5)
    
    print("Testing invalid type...")
    send_config(client, "presser_points", "not_a_number")
    time.sleep(0.5)
    
    print("\n" + "="*60)
    print("Configuration test complete!")
    print("="*60)
    print("\nQuick reference for available flags:")
    print("  Boolean flags:")
    print("    - graph: Enable/disable trajectory plotting")
    print("    - unpress_after: Release presser after pluck")
    print("    - force_adjustment_only: Skip unpress phase")
    print("")
    print("  Numeric flags:")
    print("    - blend_percent (0.0-1.0): Trajectory smoothness")
    print("    - presser_points (int): Presser motion duration")
    print("    - slider_points (int): Slider motion duration")
    print("    - picker_points (int): Picker pluck duration")
    print("    - lh_prep_time (float): LH prep time before pick (seconds)")
    print("")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
