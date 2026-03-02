#!/usr/bin/env python3
"""
Test script for /Dyn OSC messages with velocity support.

This script demonstrates the different formats supported by the dynamics_processor:
1. Multiple notes, no velocity (state toggle)
2. Single note, no velocity (state toggle)
3. Single note with velocity
4. Multiple notes with respective velocities
"""

from pythonosc import udp_client
import time


def test_dyn_formats():
    """Test all /Dyn message formats."""
    
    # Connect to OSC server
    client = udp_client.SimpleUDPClient("127.0.0.1", 12000)
    
    print("="*70)
    print("TESTING /Dyn MESSAGE FORMATS")
    print("="*70)
    
    # Test 1: Multiple notes, no velocity (state toggle)
    print("\nTest 1: Multiple notes with state toggle")
    print("  Sending: /Dyn [40, 45, 50]")
    client.send_message("/Dyn", [40, 45, 50])
    time.sleep(2)
    
    # Test 2: Single note, no velocity (state toggle)
    print("\nTest 2: Single note with state toggle")
    print("  Sending: /Dyn 40")
    client.send_message("/Dyn", 40)
    time.sleep(2)
    
    # Test 3: Single note with velocity
    print("\nTest 3: Single note with velocity")
    print("  Sending: /Dyn 40 60")
    client.send_message("/Dyn", [40, 60])
    time.sleep(2)
    
    # Test 4: Multiple notes with velocities
    print("\nTest 4: Multiple notes with velocities")
    print("  Sending: /Dyn [40, 45] [60, 127]")
    client.send_message("/Dyn", [[40, 45], [60, 127]])
    time.sleep(2)
    
    # Test 5: Another single note with high velocity
    print("\nTest 5: Single note with high velocity")
    print("  Sending: /Dyn 50 127")
    client.send_message("/Dyn", [50, 127])
    time.sleep(2)
    
    # Test 6: Three notes with different velocities
    print("\nTest 6: Three notes with different velocities")
    print("  Sending: /Dyn [40, 45, 50] [30, 80, 127]")
    client.send_message("/Dyn", [[40, 45, 50], [30, 80, 127]])
    time.sleep(2)
    
    print("\n" + "="*70)
    print("ALL TESTS SENT")
    print("="*70)


def test_velocity_range():
    """Test different velocity values on the same note."""
    
    client = udp_client.SimpleUDPClient("127.0.0.1", 12000)
    
    print("\n" + "="*70)
    print("TESTING VELOCITY RANGE")
    print("="*70)
    
    midi_note = 45
    velocities = [0, 32, 64, 96, 127]
    
    for vel in velocities:
        print(f"\nSending MIDI note {midi_note} with velocity {vel}")
        client.send_message("/Dyn", [midi_note, vel])
        time.sleep(1.5)
    
    print("\n" + "="*70)
    print("VELOCITY RANGE TEST COMPLETE")
    print("="*70)


def test_state_toggle_sequence():
    """Test state toggle by sending same note multiple times."""
    
    client = udp_client.SimpleUDPClient("127.0.0.1", 12000)
    
    print("\n" + "="*70)
    print("TESTING STATE TOGGLE")
    print("="*70)
    
    midi_note = 45
    
    for i in range(5):
        print(f"\nPluck {i+1}: Sending MIDI note {midi_note} (state toggle)")
        client.send_message("/Dyn", midi_note)
        time.sleep(1)
    
    print("\n" + "="*70)
    print("STATE TOGGLE TEST COMPLETE")
    print("="*70)


def interactive_mode():
    """Interactive mode for manual testing."""
    
    client = udp_client.SimpleUDPClient("127.0.0.1", 12000)
    
    print("\n" + "="*70)
    print("INTERACTIVE MODE")
    print("="*70)
    print("\nCommands:")
    print("  1 - Send single note with state toggle")
    print("  2 - Send single note with velocity")
    print("  3 - Send multiple notes with velocities")
    print("  q - Quit")
    print("")
    
    while True:
        cmd = input("Enter command: ").strip()
        
        if cmd == 'q':
            break
        
        elif cmd == '1':
            note = input("  MIDI note (40-70): ").strip()
            try:
                note = int(note)
                print(f"  Sending /Dyn {note}")
                client.send_message("/Dyn", note)
            except ValueError:
                print("  Invalid note number")
        
        elif cmd == '2':
            note = input("  MIDI note (40-70): ").strip()
            vel = input("  Velocity (0-127): ").strip()
            try:
                note = int(note)
                vel = int(vel)
                print(f"  Sending /Dyn {note} {vel}")
                client.send_message("/Dyn", [note, vel])
            except ValueError:
                print("  Invalid note or velocity")
        
        elif cmd == '3':
            notes = input("  MIDI notes (comma-separated, e.g., 40,45,50): ").strip()
            vels = input("  Velocities (comma-separated, e.g., 60,80,127): ").strip()
            try:
                notes = [int(n.strip()) for n in notes.split(',')]
                vels = [int(v.strip()) for v in vels.split(',')]
                
                if len(notes) != len(vels):
                    print("  Error: Number of notes must match number of velocities")
                    continue
                
                print(f"  Sending /Dyn {notes} {vels}")
                client.send_message("/Dyn", [notes, vels])
            except ValueError:
                print("  Invalid input")
        
        else:
            print("  Unknown command")


if __name__ == "__main__":
    import sys
    
    print("""
╔══════════════════════════════════════════════════════════════╗
║           /Dyn OSC Message Format Tester                     ║
║           Velocity Support for Dynamics Messages             ║
╚══════════════════════════════════════════════════════════════╝

This script tests different /Dyn message formats:
1. State toggle (no velocity)
2. Single note with velocity
3. Multiple notes with velocities

Make sure arm_list_recieverNN.py is running!
""")
    
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        
        if mode == 'formats':
            test_dyn_formats()
        elif mode == 'velocity':
            test_velocity_range()
        elif mode == 'toggle':
            test_state_toggle_sequence()
        elif mode == 'interactive':
            interactive_mode()
        else:
            print(f"Unknown mode: {mode}")
            print("Available modes: formats, velocity, toggle, interactive")
    else:
        print("Usage: python test_dyn_velocity.py [mode]")
        print("\nModes:")
        print("  formats     - Test all message format variations")
        print("  velocity    - Test velocity range (0-127)")
        print("  toggle      - Test state toggle behavior")
        print("  interactive - Interactive manual testing")
        print("\nExample: python test_dyn_velocity.py formats")
