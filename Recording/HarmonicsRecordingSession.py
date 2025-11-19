"""
HarmonicsRecordingSession.py - Automated harmonic recording with user prompts

This script guides the user through recording all natural harmonics on the guitar.
Each recording is annotated with the harmonic number and pitch value.

Harmonic locations (MIDI note numbers):
- E string: Harmonic #1=68, #2=64, #3=59
- A string: Harmonic #1=73, #2=69, #3=64
- D string: Harmonic #1=78, #2=74, #3=69
- G string: Harmonic #1=83, #2=79, #3=74
- B string: Harmonic #1=87, #2=83, #3=78
- e string: Harmonic #1=92, #2=88, #3=83

Physical locations:
- Harmonic #1: 4th fret (octave + major 3rd above open string)
- Harmonic #2: 5th fret (two octaves above open string)
- Harmonic #3: 7th fret (octave + perfect 5th above open string)

Output format: GB_NH_harmonic_n{num}_pitches{pitch}.wav
Recording specs: 44.1kHz, 24-bit
"""

import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wavfile
import time
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
from scipy import signal


class HarmonicsRecordingSession:
    """Interactive recording session for guitar harmonics."""
    
    # Define all harmonics: (string_name, harmonic_num, midi_pitch)
    HARMONICS = [
        # E string harmonics
        ("E", 1, 68),  # 4th fret
        ("E", 2, 64),  # 5th fret
        ("E", 3, 59),  # 7th fret
        
        # A string harmonics
        ("A", 1, 73),  # 4th fret
        ("A", 2, 69),  # 5th fret
        ("A", 3, 64),  # 7th fret
        
        # D string harmonics
        ("D", 1, 78),  # 4th fret
        ("D", 2, 74),  # 5th fret
        ("D", 3, 69),  # 7th fret
        
        # G string harmonics
        ("G", 1, 83),  # 4th fret
        ("G", 2, 79),  # 5th fret
        ("G", 3, 74),  # 7th fret
        
        # B string harmonics
        ("B", 1, 87),  # 4th fret
        ("B", 2, 83),  # 5th fret
        ("B", 3, 78),  # 7th fret
        
        # e string harmonics
        ("e", 1, 92),  # 4th fret
        ("e", 2, 88),  # 5th fret
        ("e", 3, 83),  # 7th fret
    ]
    
    def __init__(self, 
                 sample_rate=44100,
                 bit_depth=24,
                 recording_duration=4.0,
                 output_dir=None,
                 session_name=None):
        """
        Initialize harmonics recording session.
        
        Args:
            sample_rate: Audio recording sample rate (Hz) - default 44.1kHz
            bit_depth: Bit depth for recordings - default 24-bit
            recording_duration: Length of each recording in seconds
            output_dir: Directory for saving recordings (defaults to ../GuitarBot_Data/harmonics)
            session_name: Name for this session (defaults to timestamp)
        """
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.recording_duration = recording_duration
        
        # Validate bit depth
        if bit_depth not in [16, 24, 32]:
            raise ValueError(f"Bit depth must be 16, 24, or 32 (got {bit_depth})")
        
        # Map bit depth to numpy dtype
        if bit_depth == 16:
            self.dtype = np.int16
            self.subtype = 'PCM_16'
        elif bit_depth == 24:
            self.dtype = np.int32  # SciPy writes 24-bit as 32-bit container
            self.subtype = 'PCM_24'
        else:  # 32-bit
            self.dtype = np.int32
            self.subtype = 'PCM_32'
        
        # Default to external data directory
        if output_dir is None:
            repo_root = Path(__file__).parent.parent
            output_dir = repo_root.parent / "GuitarBot_Data" / "harmonics"
        
        self.output_dir = Path(output_dir)
        self.session_name = session_name or datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create output directory with date subdirectory
        date_str = datetime.now().strftime("%Y_%m_%d")
        self.session_dir = self.output_dir / date_str / self.session_name
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # Recording state
        self.recordings_completed = 0
        self.total_recordings = len(self.HARMONICS)
        self.selected_input_device = None
        self.selected_input_device_name = None
        
        print(f"\n{'='*70}")
        print(f"  GUITAR HARMONICS RECORDING SESSION")
        print(f"{'='*70}")
        print(f"Session: {self.session_name}")
        print(f"Output directory: {self.session_dir}")
        print(f"Recording specs: {self.sample_rate} Hz, {self.bit_depth}-bit")
        print(f"Recording duration: {self.recording_duration}s")
        print(f"Total harmonics to record: {self.total_recordings}")
        print(f"{'='*70}\n")
        
        # Configure audio input device
        try:
            self._configure_audio_input_device(preferred_substring="Scarlett")
        except Exception as e:
            print(f"Warning: Failed to configure audio input device: {e}")
            print("Using system default input device.\n")
    
    def _configure_audio_input_device(self, preferred_substring: str = "Scarlett"):
        """
        Select an input device, preferring names containing preferred_substring.
        Sets sd.default.device and stores selection for metadata.
        """
        devices = sd.query_devices()
        preferred_substring_l = preferred_substring.lower()
        
        # Try to find preferred device automatically
        for idx, dev in enumerate(devices):
            try:
                name = dev.get('name', '')
                max_in = dev.get('max_input_channels', 0)
            except Exception:
                name = str(dev)
                max_in = 0
            
            if max_in > 0 and preferred_substring_l in name.lower():
                sd.default.device = (idx, sd.default.device[1] if isinstance(sd.default.device, tuple) else None)
                sd.default.samplerate = self.sample_rate
                self.selected_input_device = idx
                self.selected_input_device_name = name
                print(f"✓ Selected input device: [{idx}] {name}")
                print(f"  Input channels: {max_in}\n")
                return
        
        # No preferred device found, list and prompt
        print(f"No '{preferred_substring}' device found. Available input devices:")
        input_indices = []
        for idx, dev in enumerate(devices):
            try:
                name = dev.get('name', '')
                max_in = dev.get('max_input_channels', 0)
            except Exception:
                name = str(dev)
                max_in = 0
            
            if max_in > 0:
                input_indices.append(idx)
                print(f"  [{idx}] {name} (inputs: {max_in})")
        
        if not input_indices:
            print("No input devices found. Using system default.")
            return
        
        # Prompt user for device selection
        while True:
            sel = input("\nEnter input device index (or press Enter for default): ").strip()
            if sel == "":
                print("Using system default input device.\n")
                return
            
            try:
                sel_idx = int(sel)
                if sel_idx not in input_indices:
                    print("Invalid device index. Please choose from the list.")
                    continue
                
                dev = devices[sel_idx]
                name = dev.get('name', str(dev))
                sd.default.device = (sel_idx, sd.default.device[1] if isinstance(sd.default.device, tuple) else None)
                sd.default.samplerate = self.sample_rate
                self.selected_input_device = sel_idx
                self.selected_input_device_name = name
                print(f"✓ Selected input device: [{sel_idx}] {name}\n")
                return
            except ValueError:
                print("Please enter a valid integer.")
            except Exception as e:
                print(f"Error selecting device: {e}")
                return
    
    def _generate_filename(self, harmonic_num, pitch):
        """
        Generate filename following the specified format.
        
        Format: GB_NH_harmonic_n1_pitches{pitch}.wav
        Example: GB_NH_harmonic_n1_pitches68.wav
        
        Args:
            harmonic_num: Harmonic number (1, 2, or 3)
            pitch: MIDI pitch value (single integer)
        """
        return f"GB_NH_harmonic_n1_pitches{pitch}.wav"
    
    def record_audio(self):
        """
        Record audio segment.
        
        Returns:
            Numpy array of recorded audio samples (float32, -1.0 to 1.0)
        """
        try:
            print(f"  🔴 Recording... ({self.recording_duration}s)")
            
            # Record audio
            audio_data = sd.rec(
                int(self.recording_duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32'
            )
            sd.wait()  # Wait until recording is complete
            
            print(f"  ✓ Recording complete ({audio_data.shape[0]} samples)")
            return audio_data.flatten()
            
        except Exception as e:
            print(f"  ✗ Error recording audio: {e}")
            return None
    
    def save_audio_file(self, audio_data, filename):
        """
        Save audio data to WAV file with proper bit depth.
        
        Args:
            audio_data: Audio samples (float32, -1.0 to 1.0)
            filename: Output filename
            
        Returns:
            Path to saved file
        """
        filepath = self.session_dir / filename
        
        try:
            # Convert float32 to target bit depth
            if self.bit_depth == 16:
                # Convert to 16-bit PCM
                audio_int = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
            elif self.bit_depth == 24:
                # Convert to 24-bit PCM (stored in 32-bit container)
                audio_int = np.clip(audio_data * 8388607, -8388608, 8388607).astype(np.int32)
            else:  # 32-bit
                # Convert to 32-bit PCM
                audio_int = np.clip(audio_data * 2147483647, -2147483648, 2147483647).astype(np.int32)
            
            # Write WAV file with specific subtype
            wavfile.write(filepath, self.sample_rate, audio_int)
            
            # Verify file was created
            if filepath.exists():
                file_size_kb = filepath.stat().st_size / 1024
                print(f"  ✓ Saved: {filename} ({file_size_kb:.1f} KB)")
                return filepath
            else:
                print(f"  ✗ Error: File was not created")
                return None
                
        except Exception as e:
            print(f"  ✗ Error saving audio: {e}")
            return None
    
    def show_spectrogram(self, audio_data, expected_pitch):
        """
        Display spectrogram of the recorded audio.
        
        Args:
            audio_data: Audio samples (float32, -1.0 to 1.0)
            expected_pitch: Expected MIDI pitch for reference
        """
        try:
            # Convert MIDI to frequency for reference
            expected_freq = 440.0 * (2.0 ** ((expected_pitch - 69) / 12.0))
            
            # Compute spectrogram
            frequencies, times, Sxx = signal.spectrogram(
                audio_data, 
                fs=self.sample_rate,
                nperseg=2048,
                noverlap=1536
            )
            
            # Create figure
            plt.figure(figsize=(12, 6))
            
            # Plot spectrogram
            plt.pcolormesh(times, frequencies, 10 * np.log10(Sxx + 1e-10), 
                          shading='gouraud', cmap='viridis')
            plt.ylabel('Frequency (Hz)')
            plt.xlabel('Time (s)')
            plt.title(f'Spectrogram - Expected Pitch: {expected_pitch} MIDI ({expected_freq:.1f} Hz)')
            plt.colorbar(label='Power (dB)')
            
            # Add reference line for expected frequency
            plt.axhline(y=expected_freq, color='r', linestyle='--', linewidth=2, 
                       label=f'Expected: {expected_freq:.1f} Hz', alpha=0.7)
            
            # Limit frequency range to musical range (focus on harmonics)
            plt.ylim([0, min(5000, self.sample_rate / 2)])
            plt.legend()
            plt.tight_layout()
            
            # Show the plot
            plt.show(block=True)
            
            print("  ✓ Spectrogram displayed")
            
        except Exception as e:
            print(f"  ✗ Error displaying spectrogram: {e}")
            print(f"     Make sure matplotlib is installed and display is available")
    
    def record_harmonic(self, string_name, harmonic_num, pitch, attempt=1):
        """
        Record a single harmonic with user interaction.
        
        Args:
            string_name: Name of string (E, A, D, G, B, e)
            harmonic_num: Harmonic number (1, 2, 3)
            pitch: MIDI pitch value (single integer)
            attempt: Attempt number for this harmonic
            
        Returns:
            True if recording was accepted, False if user wants to retry
        """
        # Display harmonic information
        print(f"\n{'─'*70}")
        print(f"Harmonic {self.recordings_completed + 1}/{self.total_recordings}")
        print(f"{'─'*70}")
        print(f"String: {string_name}")
        print(f"Harmonic: #{harmonic_num}")
        
        # Map harmonic number to fret location
        fret_map = {1: "4th", 2: "5th", 3: "7th"}
        print(f"Location: {fret_map[harmonic_num]} fret")
        print(f"Expected pitch: {pitch} (MIDI)")
        if attempt > 1:
            print(f"Attempt: {attempt}")
        print(f"{'─'*70}")
        
        # Prompt user to prepare
        input("\n▶ Press ENTER when ready to record...")
        
        # Countdown
        print("\nStarting in: ", end="", flush=True)
        for i in range(3, 0, -1):
            print(f"{i}... ", end="", flush=True)
            time.sleep(1)
        print("GO!\n")
        
        # Record audio
        audio_data = self.record_audio()
        
        if audio_data is None:
            print("\n✗ Recording failed. Try again.")
            return False
        
        # Spectrogram option
        show_spec = input("\n▶ View spectrogram? (y/n): ").strip().lower()
        if show_spec == 'y':
            print("  📊 Displaying spectrogram (close window to continue)...")
            self.show_spectrogram(audio_data, pitch)
        
        # Ask user if recording is acceptable
        while True:
            response = input("\n▶ Accept this recording? (y=accept, n=retry, q=quit): ").strip().lower()
            
            if response == 'y':
                # Save the recording
                filename = self._generate_filename(harmonic_num, pitch)
                filepath = self.save_audio_file(audio_data, filename)
                
                if filepath:
                    self.recordings_completed += 1
                    print(f"\n✓ Recording #{self.recordings_completed} saved successfully!")
                    return True
                else:
                    print("\n✗ Failed to save recording. Try again.")
                    return False
            
            elif response == 'n':
                print("\n↻ Discarding recording. Let's try again...")
                return False
            
            elif response == 'q':
                print("\n⊗ Quitting session...")
                raise KeyboardInterrupt
            
            else:
                print("Invalid input. Please enter 'y', 'n', or 'q'.")
    
    def run_session(self):
        """
        Run the complete harmonic recording session.
        Guides user through all harmonics with retry capability.
        """
        print("\n" + "="*70)
        print("  STARTING RECORDING SESSION")
        print("="*70)
        print("\nInstructions:")
        print("  • You will be prompted for each harmonic")
        print("  • Press ENTER when ready to record")
        print("  • Optionally view spectrogram to verify recording quality")
        print("  • After each recording, choose:")
        print("    - 'y' to accept and continue")
        print("    - 'n' to discard and retry")
        print("    - 'q' to quit session")
        print("\nLet's begin!\n")
        
        try:
            for string_name, harmonic_num, pitch in self.HARMONICS:
                # Keep trying until user accepts the recording
                attempt = 1
                while True:
                    accepted = self.record_harmonic(string_name, harmonic_num, pitch, attempt)
                    if accepted:
                        break
                    attempt += 1
            
            # Session complete
            print("\n" + "="*70)
            print("  🎉 SESSION COMPLETE!")
            print("="*70)
            print(f"Total recordings: {self.recordings_completed}/{self.total_recordings}")
            print(f"Output directory: {self.session_dir}")
            print("="*70 + "\n")
            
        except KeyboardInterrupt:
            print("\n\n" + "="*70)
            print("  ⊗ SESSION INTERRUPTED")
            print("="*70)
            print(f"Recordings completed: {self.recordings_completed}/{self.total_recordings}")
            print(f"Partial data saved to: {self.session_dir}")
            print("="*70 + "\n")
        
        except Exception as e:
            print(f"\n\n✗ Unexpected error: {e}")
            print(f"Recordings completed: {self.recordings_completed}/{self.total_recordings}")
            print(f"Data saved to: {self.session_dir}\n")
    
    def run_repeat_mode(self, string_name, harmonic_num, pitch, num_repetitions):
        """
        Record the same harmonic multiple times for dataset augmentation.
        
        Args:
            string_name: Name of string (E, A, D, G, B, e)
            harmonic_num: Harmonic number (1, 2, 3)
            pitch: MIDI pitch value
            num_repetitions: Number of times to record this harmonic
        """
        print("\n" + "="*70)
        print("  REPEAT MODE - Single Harmonic Multiple Recordings")
        print("="*70)
        print(f"\nTarget harmonic:")
        print(f"  String: {string_name}")
        print(f"  Harmonic: #{harmonic_num}")
        fret_map = {1: "4th", 2: "5th", 3: "7th"}
        print(f"  Location: {fret_map[harmonic_num]} fret")
        print(f"  Pitch: {pitch} (MIDI)")
        print(f"  Repetitions: {num_repetitions}")
        print("\nInstructions:")
        print("  • Record the same harmonic multiple times")
        print("  • Each recording is numbered separately")
        print("  • Optionally view spectrogram after each recording")
        print("  • Accept, retry, or quit after each recording")
        print("="*70 + "\n")
        
        try:
            for rep in range(1, num_repetitions + 1):
                print(f"\n{'='*70}")
                print(f"  REPETITION {rep}/{num_repetitions}")
                print(f"{'='*70}")
                
                attempt = 1
                while True:
                    # Display info for this repetition
                    print(f"\n{'─'*70}")
                    print(f"Recording {rep}/{num_repetitions} (Total recorded: {self.recordings_completed})")
                    print(f"{'─'*70}")
                    print(f"String: {string_name}")
                    print(f"Harmonic: #{harmonic_num}")
                    print(f"Location: {fret_map[harmonic_num]} fret")
                    print(f"Expected pitch: {pitch} (MIDI)")
                    if attempt > 1:
                        print(f"Attempt: {attempt}")
                    print(f"{'─'*70}")
                    
                    # Prompt user to prepare
                    input("\n▶ Press ENTER when ready to record...")
                    
                    # Countdown
                    print("\nStarting in: ", end="", flush=True)
                    for i in range(3, 0, -1):
                        print(f"{i}... ", end="", flush=True)
                        time.sleep(1)
                    print("GO!\n")
                    
                    # Record audio
                    audio_data = self.record_audio()
                    
                    if audio_data is None:
                        print("\n✗ Recording failed. Try again.")
                        attempt += 1
                        continue
                    
                    # Spectrogram option
                    show_spec = input("\n▶ View spectrogram? (y/n): ").strip().lower()
                    if show_spec == 'y':
                        print("  📊 Displaying spectrogram (close window to continue)...")
                        self.show_spectrogram(audio_data, pitch)
                    
                    # Ask user if recording is acceptable
                    while True:
                        response = input("\n▶ Accept this recording? (y=accept, n=retry, q=quit): ").strip().lower()
                        
                        if response == 'y':
                            # Save with repetition number in filename
                            filename = f"GB_NH_harmonic_n{harmonic_num}_pitches{pitch}_rep{rep:02d}.wav"
                            filepath = self.save_audio_file(audio_data, filename)
                            
                            if filepath:
                                self.recordings_completed += 1
                                print(f"\n✓ Recording {rep}/{num_repetitions} saved successfully!")
                                break
                            else:
                                print("\n✗ Failed to save recording. Try again.")
                                attempt += 1
                                break
                        
                        elif response == 'n':
                            print("\n↻ Discarding recording. Let's try again...")
                            attempt += 1
                            break
                        
                        elif response == 'q':
                            print("\n⊗ Quitting repeat mode...")
                            raise KeyboardInterrupt
                        
                        else:
                            print("Invalid input. Please enter 'y', 'n', or 'q'.")
                    
                    if response == 'y':
                        break  # Move to next repetition
            
            # All repetitions complete
            print("\n" + "="*70)
            print("  🎉 REPEAT MODE COMPLETE!")
            print("="*70)
            print(f"Total recordings: {num_repetitions}")
            print(f"Output directory: {self.session_dir}")
            print("="*70 + "\n")
            
        except KeyboardInterrupt:
            print("\n\n" + "="*70)
            print("  ⊗ REPEAT MODE INTERRUPTED")
            print("="*70)
            print(f"Recordings completed: {self.recordings_completed}/{num_repetitions}")
            print(f"Partial data saved to: {self.session_dir}")
            print("="*70 + "\n")
        
        except Exception as e:
            print(f"\n\n✗ Unexpected error: {e}")
            print(f"Recordings completed: {self.recordings_completed}/{num_repetitions}")
            print(f"Data saved to: {self.session_dir}\n")


def main():
    """Main entry point for harmonics recording script."""
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║       GUITAR HARMONICS RECORDING - Automated Annotation           ║
║                                                                   ║
║  This script will guide you through recording all natural         ║
║  harmonics on the guitar with proper labeling.                    ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    # Choose recording mode
    print("Recording modes:")
    print("  1. Full session - Record all 18 harmonics (one of each)")
    print("  2. Repeat mode - Record ONE harmonic multiple times")
    print()
    
    mode = input("Select mode (1 or 2) [1]: ").strip() or "1"
    
    # Allow customization
    print("\nConfiguration options:")
    print(f"  Default: 44.1kHz, 24-bit, 4.0s recordings")
    
    customize = input("\nUse default settings? (y/n): ").strip().lower()
    
    if customize == 'n':
        try:
            sample_rate = int(input("Sample rate (Hz) [44100]: ").strip() or "44100")
            bit_depth = int(input("Bit depth (16/24/32) [24]: ").strip() or "24")
            duration = float(input("Recording duration (seconds) [4.0]: ").strip() or "4.0")
        except ValueError:
            print("Invalid input. Using defaults.")
            sample_rate, bit_depth, duration = 44100, 24, 4.0
    else:
        sample_rate, bit_depth, duration = 44100, 24, 4.0
    
    # Create session
    session = HarmonicsRecordingSession(
        sample_rate=sample_rate,
        bit_depth=bit_depth,
        recording_duration=duration
    )
    
    # Run appropriate mode
    if mode == "2":
        # Repeat mode - select harmonic
        print("\n" + "="*70)
        print("  REPEAT MODE SETUP")
        print("="*70)
        print("\nAvailable strings:")
        print("  E (uppercase) = Low E string")
        print("  A, D, G, B    = Middle strings")
        print("  e (lowercase) = High e string")
        print("\nHarmonic numbers: 1 (4th fret), 2 (5th fret), 3 (7th fret)")
        print()
        
        # Get string selection
        string_input = input("Enter string (E/A/D/G/B/e): ").strip()
        
        # Handle case sensitivity: lowercase 'e' = high E string, uppercase 'E' = low E string
        if string_input == 'e':
            string_name = 'e'  # High e string (lowercase)
        elif string_input.upper() in ['E', 'A', 'D', 'G', 'B']:
            string_name = string_input.upper()  # Low E, A, D, G, B strings (uppercase)
        else:
            print(f"Invalid string '{string_input}'. Defaulting to low E string.")
            string_name = 'E'
        
        # Get harmonic number
        try:
            harmonic_num = int(input("Enter harmonic number (1/2/3): ").strip())
            if harmonic_num not in [1, 2, 3]:
                print("Invalid harmonic number. Defaulting to 1")
                harmonic_num = 1
        except ValueError:
            print("Invalid input. Defaulting to 1")
            harmonic_num = 1
        
        # Get number of repetitions
        try:
            num_reps = int(input("How many recordings? [10]: ").strip() or "10")
            if num_reps < 1:
                print("Must be at least 1. Using 10.")
                num_reps = 10
        except ValueError:
            print("Invalid input. Using 10.")
            num_reps = 10
        
        # Find the pitch for this harmonic
        pitch = None
        for s, h, p in session.HARMONICS:
            if s == string_name and h == harmonic_num:
                pitch = p
                break
        
        if pitch is None:
            print(f"Error: Could not find harmonic for {string_name} string, harmonic #{harmonic_num}")
            return
        
        # Run repeat mode
        session.run_repeat_mode(string_name, harmonic_num, pitch, num_reps)
    
    else:
        # Full session mode
        session.run_session()


if __name__ == "__main__":
    main()
