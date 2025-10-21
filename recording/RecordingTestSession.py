"""
RecordingTestSession.py - Automated audio recording and labeling for GuitarBot testing

This script combines OSC message sending with synchronized audio recording and 
programmatic labeling. Useful for:
- Dataset generation for machine learning
- Audio-based calibration
- Dynamic range testing
- Fretting force optimization
- Quality assurance testing

Features:
- Cross-platform audio recording (Linux/Windows/Mac)
- Automatic labeling with test parameters
- CSV metadata export
- WAV file naming with embedded metadata
- Configurable pre/post recording delays
- Multiple test protocols (dynamics, fretting, plucking)

Requirements:
- sounddevice (cross-platform audio I/O)
- scipy (WAV file writing)
- pythonosc (OSC communication)
"""

import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wavfile
import time
import csv
import json
from pathlib import Path
from datetime import datetime
from pythonosc.udp_client import SimpleUDPClient
# from TestMessageGenerator import TestMessageGenerator


class RecordingTestSession:
    def __init__(self, 
                 osc_ip="127.0.0.1", 
                 osc_port=12000,
                 sample_rate=44100,
                 output_dir="recordings",
                 session_name=None):
        """
        Initialize recording test session.
        
        Args:
            osc_ip: IP address of OSC receiver
            osc_port: Port of OSC receiver
            sample_rate: Audio recording sample rate (Hz)
            output_dir: Directory for saving recordings and metadata
            session_name: Name for this session (defaults to timestamp)
        """
        self.osc_client = SimpleUDPClient(osc_ip, osc_port)
        self.sample_rate = sample_rate
        self.output_dir = Path(output_dir)
        self.session_name = session_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create output directories
        self.session_dir = self.output_dir / self.session_name
        self.audio_dir = self.session_dir / "audio"
        self.metadata_dir = self.session_dir / "metadata"
        
        for directory in [self.session_dir, self.audio_dir, self.metadata_dir]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Test results storage
        self.test_results = []
        self.test_counter = 0
        
        # Recording settings
        self.pre_trigger_time = 0.5  # Record 0.5s before OSC message
        self.post_trigger_time = 2.0  # Record 3s after OSC message
        
        print(f"=== Recording Test Session Initialized ===")
        print(f"Session: {self.session_name}")
        print(f"Output: {self.session_dir}")
        print(f"Sample rate: {self.sample_rate} Hz")
        print(f"OSC target: {osc_ip}:{osc_port}")
    
    def send_osc_message(self, address, data):
        """Send OSC message and log it."""
        timestamp = time.time()
        print(f"[{timestamp:.3f}] Sending OSC: {address} <- {data}")
        self.osc_client.send_message(address, data)
        return timestamp
    
    def record_audio_segment(self, duration, test_label="test"):
        """
        Record audio segment with specified duration.
        
        Args:
            duration: Recording duration in seconds
            test_label: Label for this recording
            
        Returns:
            Numpy array of recorded audio
        """
        print(f"Recording {duration:.2f}s of audio for '{test_label}'...")
        
        try:
            # Record audio
            audio_data = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32'
            )
            sd.wait()  # Wait for recording to complete
            
            print(f"Recording complete: {audio_data.shape[0]} samples")
            return audio_data.flatten()
            
        except Exception as e:
            print(f"Error recording audio: {e}")
            return None
    
    def save_audio_file(self, audio_data, test_info):
        """
        Save audio data to WAV file with metadata in filename.
        
        Args:
            audio_data: Audio samples
            test_info: Dictionary with test metadata
            
        Returns:
            Path to saved file
        """
        # Create filename with embedded metadata
        test_type = test_info.get('test_type', 'unknown')
        test_num = test_info.get('test_number', self.test_counter)
        midi_note = test_info.get('midi_note', '')
        param = test_info.get('parameter', '')
        
        filename = f"{test_num:04d}_{test_type}"
        if midi_note:
            filename += f"_note{midi_note}"
        if param:
            filename += f"_param{param}"
        filename += ".wav"
        
        filepath = self.audio_dir / filename
        
        # Normalize and save
        audio_data = np.clip(audio_data, -1.0, 1.0)
        wavfile.write(filepath, self.sample_rate, audio_data)
        
        print(f"Saved: {filepath.name}")
        return filepath
    
    def save_metadata(self, test_info):
        """Save test metadata to JSON file."""
        test_num = test_info.get('test_number', self.test_counter)
        metadata_file = self.metadata_dir / f"{test_num:04d}_metadata.json"
        
        with open(metadata_file, 'w') as f:
            json.dump(test_info, f, indent=2)
        
        return metadata_file
    
    def execute_test(self, osc_address, osc_data, test_info):
        """
        Execute single test: record audio, send OSC, save everything.
        
        Args:
            osc_address: OSC address (e.g., "/Dyn", "/Fret")
            osc_data: OSC data to send
            test_info: Dictionary with test metadata
            
        Returns:
            Dictionary with test results
        """
        self.test_counter += 1
        test_info['test_number'] = self.test_counter
        test_info['timestamp'] = datetime.now().isoformat()
        test_info['osc_address'] = osc_address
        test_info['osc_data'] = osc_data
        
        print(f"\n=== Test {self.test_counter}: {test_info.get('test_type', 'Unknown')} ===")
        
        # Calculate total recording duration
        total_duration = self.pre_trigger_time + self.post_trigger_time
        
        # Start recording in background
        print(f"Starting background recording ({total_duration:.1f}s)...")
        recording_started = time.time()
        
        # Start recording
        audio_data = sd.rec(
            int(total_duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32'
        )
        
        # Wait for pre-trigger time
        time.sleep(self.pre_trigger_time)
        
        # Send OSC message
        osc_timestamp = self.send_osc_message(osc_address, osc_data)
        test_info['osc_timestamp'] = osc_timestamp
        
        # Wait for post-trigger time
        time.sleep(self.post_trigger_time)
        
        # Complete recording
        sd.wait()
        audio_data = audio_data.flatten()
        
        recording_ended = time.time()
        test_info['recording_duration'] = recording_ended - recording_started
        
        # Save audio file
        audio_file = self.save_audio_file(audio_data, test_info)
        test_info['audio_file'] = str(audio_file.name)
        
        # Save metadata
        metadata_file = self.save_metadata(test_info)
        test_info['metadata_file'] = str(metadata_file.name)
        
        # Store results
        self.test_results.append(test_info)
        
        print(f"Test {self.test_counter} complete\n")
        
        return test_info
    
    def test_dynamics_sweep(self, midi_notes, delay_between=3.0):
        """
        Test dynamics across multiple MIDI notes.
        
        Args:
            midi_notes: List of MIDI note numbers
            delay_between: Delay between tests (seconds)
        """
        print(f"\n{'='*60}")
        print(f"DYNAMICS SWEEP TEST")
        print(f"Notes: {midi_notes}")
        print(f"{'='*60}\n")
        
        for midi_note in midi_notes:
            test_info = {
                'test_type': 'dynamics',
                'midi_note': midi_note,
                'parameter': 'state_toggle'
            }
            
            self.execute_test("/Dyn", midi_note, test_info)
            
            if midi_note != midi_notes[-1]:
                print(f"Waiting {delay_between}s before next test...")
                time.sleep(delay_between)
    
    def test_fretting_force(self, midi_note, force_levels, delay_between=3.0):
        """
        Test fretting force levels for a single note.
        
        Args:
            midi_note: MIDI note number
            force_levels: List of force values (0.0-1.0)
            delay_between: Delay between tests (seconds)
        """
        print(f"\n{'='*60}")
        print(f"FRETTING FORCE TEST")
        print(f"Note: {midi_note}")
        print(f"Force levels: {force_levels}")
        print(f"{'='*60}\n")
        
        for force in force_levels:
            test_info = {
                'test_type': 'fretting_force',
                'midi_note': midi_note,
                'parameter': force,
                'force_level': force
            }
            
            # Send /Fret message with force parameter
            self.execute_test("/Fret", [midi_note, force], test_info)
            
            if force != force_levels[-1]:
                print(f"Waiting {delay_between}s before next test...")
                time.sleep(delay_between)
    
    def test_pluck_velocity(self, midi_note, velocities, delay_between=3.0):
        """
        Test pluck velocities for a single note.
        
        Args:
            midi_note: MIDI note number
            velocities: List of MIDI velocities (0-127)
            delay_between: Delay between tests (seconds)
        """
        print(f"\n{'='*60}")
        print(f"PLUCK VELOCITY TEST")
        print(f"Note: {midi_note}")
        print(f"Velocities: {velocities}")
        print(f"{'='*60}\n")
        
        for velocity in velocities:
            test_info = {
                'test_type': 'pluck_velocity',
                'midi_note': midi_note,
                'parameter': velocity,
                'velocity': velocity
            }
            
            # Send /Pluck message with velocity
            self.execute_test("/Pluck", [midi_note, velocity], test_info)
            
            if velocity != velocities[-1]:
                print(f"Waiting {delay_between}s before next test...")
                time.sleep(delay_between)
    
    def test_repeatability(self, osc_address, osc_data, repetitions=5, delay_between=3.0):
        """
        Test repeatability by executing same command multiple times.
        
        Args:
            osc_address: OSC address
            osc_data: OSC data
            repetitions: Number of repetitions
            delay_between: Delay between tests (seconds)
        """
        print(f"\n{'='*60}")
        print(f"REPEATABILITY TEST")
        print(f"Command: {osc_address} {osc_data}")
        print(f"Repetitions: {repetitions}")
        print(f"{'='*60}\n")
        
        for rep in range(repetitions):
            test_info = {
                'test_type': 'repeatability',
                'repetition': rep + 1,
                'total_repetitions': repetitions,
                'parameter': f'rep{rep+1}'
            }
            
            self.execute_test(osc_address, osc_data, test_info)
            
            if rep < repetitions - 1:
                print(f"Waiting {delay_between}s before next repetition...")
                time.sleep(delay_between)
    
    def export_session_summary(self):
        """Export session summary to CSV and JSON files."""
        # CSV export
        csv_file = self.session_dir / "session_summary.csv"
        if self.test_results:
            keys = self.test_results[0].keys()
            with open(csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(self.test_results)
            print(f"\nCSV summary saved: {csv_file}")
        
        # JSON export
        json_file = self.session_dir / "session_summary.json"
        summary = {
            'session_name': self.session_name,
            'total_tests': self.test_counter,
            'sample_rate': self.sample_rate,
            'pre_trigger_time': self.pre_trigger_time,
            'post_trigger_time': self.post_trigger_time,
            'test_results': self.test_results
        }
        with open(json_file, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"JSON summary saved: {json_file}")
        
        return csv_file, json_file
    
    def close_session(self):
        """Close session and export summaries."""
        print(f"\n{'='*60}")
        print(f"SESSION COMPLETE")
        print(f"Total tests: {self.test_counter}")
        print(f"{'='*60}\n")
        
        self.export_session_summary()
        
        print(f"\nAll files saved to: {self.session_dir}")


# Example test protocols
def protocol_dynamics_sweep():
    """Protocol: Test dynamics across all available strings."""
    session = RecordingTestSession(session_name="dynamics_sweep")
    
    # Test MIDI notes for each string (based on STRING_MIDI_RANGES from tune.py)
    notes = [
        40,  # Low E string
        50,  # D string  
        60,  # B string
    ]
    
    session.test_dynamics_sweep(notes, delay_between=5.0)
    session.close_session()


def protocol_fretting_force_optimization():
    """Protocol: Optimize fretting force for clean notes."""
    session = RecordingTestSession(session_name="fretting_force_optimization")
    
    # Test multiple force levels on Low E 5th fret
    midi_note = 45
    force_levels = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    
    session.test_fretting_force(midi_note, force_levels, delay_between=4.0)
    session.close_session()


def protocol_repeatability_test():
    """Protocol: Test repeatability of single command."""
    session = RecordingTestSession(session_name="repeatability_test")
    
    # Test same note 10 times
    session.test_repeatability("/Dyn", 40, repetitions=10, delay_between=4.0)
    session.close_session()


def protocol_custom_test():
    """Protocol: Custom test sequence (mimics Send_msg_Test_NN.py)."""
    session = RecordingTestSession(session_name="custom_test")
    
    # Replicate the original test pattern
    test_sequence = [
        (40, 4),  # Note 40, 4 times
        (50, 4),  # Note 50, 4 times
        (60, 4),  # Note 60, 4 times
    ]
    
    for midi_note, repetitions in test_sequence:
        for rep in range(repetitions):
            test_info = {
                'test_type': 'custom_dynamics',
                'midi_note': midi_note,
                'repetition': rep + 1,
                'parameter': f'note{midi_note}_rep{rep+1}'
            }
            
            session.execute_test("/Dyn", midi_note, test_info)
            time.sleep(8.0)  # Original delay
    
    session.close_session()


# Main execution
if __name__ == "__main__":
    import sys
    
    print("""
╔═══════════════════════════════════════════════════════════════╗
║         GuitarBot Recording Test Session                      ║
║         Automated Audio Recording & Labeling                  ║
╚═══════════════════════════════════════════════════════════════╝
""")
    devices = sd.query_devices()
    print("Select a device:")
    print(devices)
    selected_device = int(input())
    # sd.default.device = str(devices[selected_device])
    sd.default.device = selected_device
    print("Selected Device:")
    print(sd.default.device)
    print("Available test protocols:")
    print("  1. Dynamics Sweep (test all strings)")
    print("  2. Fretting Force Optimization")
    print("  3. Repeatability Test")
    print("  4. Custom Test (original pattern)")
    print("  5. Quick Demo")
    print()
    
    if len(sys.argv) > 1:
        protocol = sys.argv[1]
    else:
        protocol = input("Select protocol (1-5) or press Enter for demo: ").strip()
    
    if protocol == "1":
        protocol_dynamics_sweep()
    elif protocol == "2":
        protocol_fretting_force_optimization()
    elif protocol == "3":
        protocol_repeatability_test()
    elif protocol == "4":
        protocol_custom_test()
    else:
        # Quick demo - just a few tests
        print("\n=== Running Quick Demo ===\n")
        session = RecordingTestSession(session_name="demo")
        
        session.execute_test("/Dyn", 40, {
            'test_type': 'demo',
            'midi_note': 40,
            'parameter': 'demo1'
        })
        time.sleep(3)
        
        session.execute_test("/Dyn", 50, {
            'test_type': 'demo',
            'midi_note': 50,
            'parameter': 'demo2'
        })
        time.sleep(3)
        
        session.close_session()
    
    print("\n✓ Recording session complete!")
    print("Check the 'recordings/' directory for output files.")
