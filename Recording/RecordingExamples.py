"""
RecordingExamples.py - Common use case examples for RecordingTestSession

Copy and modify these examples for your specific testing needs.
"""

from RecordingTestSession import RecordingTestSession
import time


# ============================================================================
# Example 1: Replicate Original OSC_Message_Receiver.py with Recording
# ============================================================================

def example_replicate_original():
    """Exact replication of OSC_Message_Receiver.py but with audio recording."""
    print("\n=== Example 1: Replicate Original Test ===\n")
    
    session = RecordingTestSession(session_name="replicate_original")
    
    # Original pattern: 4x note 40, 4x note 50, 4x note 60
    test_sequence = [
        (40, 4),  # MIDI note 40, 4 repetitions
        (50, 4),  # MIDI note 50, 4 repetitions
        (60, 4),  # MIDI note 60, 4 repetitions
    ]
    
    for midi_note, repetitions in test_sequence:
        for rep in range(repetitions):
            test_info = {
                'test_type': 'original_pattern',
                'midi_note': midi_note,
                'repetition': rep + 1,
                'parameter': f'note{midi_note}_rep{rep+1}'
            }
            
            session.execute_test("/Dyn", midi_note, test_info)
            time.sleep(8.0)  # Original 8-second delay
    
    session.close_session()
    print("\n✓ Original pattern complete with recordings!\n")


# ============================================================================
# Example 2: Quick Single Note Test
# ============================================================================

def example_single_note():
    """Test a single note quickly - useful for debugging."""
    print("\n=== Example 2: Single Note Test ===\n")
    
    session = RecordingTestSession(session_name="single_note_test")
    
    # Test just one note
    test_info = {
        'test_type': 'quick_test',
        'midi_note': 45,
        'parameter': 'test1'
    }
    
    session.execute_test("/Dyn", 45, test_info)
    
    session.close_session()
    print("\n✓ Single note test complete!\n")


# ============================================================================
# Example 3: Compare Multiple Strings
# ============================================================================

def example_compare_strings():
    """Compare sound across different strings."""
    print("\n=== Example 3: String Comparison ===\n")
    
    session = RecordingTestSession(session_name="string_comparison")
    
    # Test each string at same fret position
    strings = {
        'Low_E': 40,   # String 1 - open
        'D': 50,       # String 3 - open  
        'B': 60,       # String 5 - open
    }
    
    for string_name, midi_note in strings.items():
        test_info = {
            'test_type': 'string_comparison',
            'string_name': string_name,
            'midi_note': midi_note,
            'parameter': string_name
        }
        
        session.execute_test("/Dyn", midi_note, test_info)
        time.sleep(5.0)
    
    session.close_session()
    print("\n✓ String comparison complete!\n")


# ============================================================================
# Example 4: Test Fretting Force Range
# ============================================================================

def example_fretting_force_sweep():
    """Find optimal fretting force for clean notes."""
    print("\n=== Example 4: Fretting Force Sweep ===\n")
    
    session = RecordingTestSession(session_name="fretting_force_sweep")
    
    midi_note = 45  # Low E, 5th fret
    
    # Test force from light to heavy
    forces = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    
    for force in forces:
        test_info = {
            'test_type': 'fretting_force',
            'midi_note': midi_note,
            'force_level': force,
            'parameter': f'force{int(force*100)}'
        }
        
        # Send /Fret message with force parameter
        session.execute_test("/Fret", [midi_note, force], test_info)
        time.sleep(4.0)
    
    session.close_session()
    print("\n✓ Fretting force sweep complete!\n")
    print("Listen to recordings to find optimal force level.")


# ============================================================================
# Example 5: Velocity Response Curve
# ============================================================================

def example_velocity_response():
    """Map MIDI velocity to acoustic output."""
    print("\n=== Example 5: Velocity Response Curve ===\n")
    
    session = RecordingTestSession(session_name="velocity_response")
    
    midi_note = 40  # Low E open
    
    # Test velocities from soft to loud
    velocities = [20, 40, 60, 80, 100, 120, 127]
    
    for velocity in velocities:
        test_info = {
            'test_type': 'velocity_response',
            'midi_note': midi_note,
            'velocity': velocity,
            'parameter': f'vel{velocity}'
        }
        
        session.execute_test("/Pluck", [midi_note, velocity], test_info)
        time.sleep(3.0)
    
    session.close_session()
    print("\n✓ Velocity response test complete!\n")


# ============================================================================
# Example 6: Mechanical Repeatability Check
# ============================================================================

def example_repeatability():
    """Test mechanical consistency - same command multiple times."""
    print("\n=== Example 6: Repeatability Test ===\n")
    
    session = RecordingTestSession(session_name="repeatability_check")
    
    # Execute same command 10 times
    midi_note = 45
    repetitions = 10
    
    for rep in range(repetitions):
        test_info = {
            'test_type': 'repeatability',
            'midi_note': midi_note,
            'repetition': rep + 1,
            'total_repetitions': repetitions,
            'parameter': f'rep{rep+1:02d}'
        }
        
        session.execute_test("/Dyn", midi_note, test_info)
        time.sleep(4.0)
    
    session.close_session()
    print("\n✓ Repeatability test complete!\n")
    print("Analyze audio files to check consistency.")


# ============================================================================
# Example 7: Full Scale Test
# ============================================================================

def example_full_scale():
    """Play a complete chromatic scale."""
    print("\n=== Example 7: Chromatic Scale ===\n")
    
    session = RecordingTestSession(session_name="chromatic_scale")
    
    # Low E string chromatic scale (frets 0-12)
    scale_notes = list(range(40, 53))  # MIDI 40-52
    
    for i, midi_note in enumerate(scale_notes):
        fret = i
        test_info = {
            'test_type': 'chromatic_scale',
            'midi_note': midi_note,
            'fret_number': fret,
            'parameter': f'fret{fret:02d}'
        }
        
        session.execute_test("/Dyn", midi_note, test_info)
        time.sleep(2.0)
    
    session.close_session()
    print("\n✓ Chromatic scale complete!\n")


# ============================================================================
# Example 8: Timing Accuracy Test
# ============================================================================

def example_timing_test():
    """Test timing precision with rapid notes."""
    print("\n=== Example 8: Timing Accuracy ===\n")
    
    session = RecordingTestSession(session_name="timing_test")
    
    # Adjust recording window for rapid notes
    session.pre_trigger_time = 0.3
    session.post_trigger_time = 1.5
    
    midi_note = 40
    delays = [0.5, 1.0, 1.5, 2.0]  # Different delays
    
    for delay in delays:
        test_info = {
            'test_type': 'timing_test',
            'midi_note': midi_note,
            'delay_seconds': delay,
            'parameter': f'delay{int(delay*1000)}ms'
        }
        
        session.execute_test("/Dyn", midi_note, test_info)
        time.sleep(delay)
    
    session.close_session()
    print("\n✓ Timing test complete!\n")


# ============================================================================
# Example 9: Environmental Noise Baseline
# ============================================================================

def example_noise_baseline():
    """Record background noise for SNR calculations."""
    print("\n=== Example 9: Noise Baseline ===\n")
    
    session = RecordingTestSession(session_name="noise_baseline")
    
    # Record silence (no OSC messages)
    test_info = {
        'test_type': 'noise_baseline',
        'parameter': 'silence'
    }
    
    print("Recording environmental noise (no robot motion)...")
    audio = session.record_audio_segment(5.0, "noise_baseline")
    
    if audio is not None:
        session.save_audio_file(audio, test_info)
        session.save_metadata(test_info)
    
    session.close_session()
    print("\n✓ Noise baseline recorded!\n")


# ============================================================================
# Example 10: Custom Protocol from Scratch
# ============================================================================

def example_custom_protocol():
    """Create your own custom test protocol."""
    print("\n=== Example 10: Custom Protocol ===\n")
    
    session = RecordingTestSession(session_name="custom_protocol")
    
    # Your custom test sequence here
    # This example tests alternating strings
    
    test_pattern = [40, 50, 60, 50, 40]  # Pattern: E-D-B-D-E
    
    for i, midi_note in enumerate(test_pattern):
        test_info = {
            'test_type': 'custom_pattern',
            'midi_note': midi_note,
            'position_in_pattern': i + 1,
            'parameter': f'pos{i+1}'
        }
        
        session.execute_test("/Dyn", midi_note, test_info)
        time.sleep(3.0)
    
    session.close_session()
    print("\n✓ Custom protocol complete!\n")


# ============================================================================
# Main Menu - Run Examples
# ============================================================================

if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════╗
║    RecordingTestSession Examples                          ║
║    Choose an example to run                               ║
╚════════════════════════════════════════════════════════════╝
""")
    
    examples = {
        '1': ('Replicate Original OSC_Message_Receiver.py', example_replicate_original),
        '2': ('Single Note Quick Test', example_single_note),
        '3': ('Compare Multiple Strings', example_compare_strings),
        '4': ('Fretting Force Sweep', example_fretting_force_sweep),
        '5': ('Velocity Response Curve', example_velocity_response),
        '6': ('Mechanical Repeatability', example_repeatability),
        '7': ('Full Chromatic Scale', example_full_scale),
        '8': ('Timing Accuracy Test', example_timing_test),
        '9': ('Environmental Noise Baseline', example_noise_baseline),
        '10': ('Custom Protocol', example_custom_protocol),
    }
    
    print("Available examples:")
    for key, (name, _) in examples.items():
        print(f"  {key:>2}. {name}")
    print()
    
    choice = input("Select example (1-10): ").strip()
    
    if choice in examples:
        name, func = examples[choice]
        print(f"\nRunning: {name}\n")
        func()
        print("\n✓ Example complete!")
        print(f"Check 'recordings/' directory for output files.")
    else:
        print("Invalid choice. Running demo (Example 2)...")
        example_single_note()
