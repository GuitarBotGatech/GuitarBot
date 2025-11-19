"""
test_harmonic_recording.py - Quick audio test for harmonics recording

Run this before starting a full harmonics recording session to verify:
- Audio interface is working
- Recording quality is good
- File saving works correctly
"""

import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wavfile
from pathlib import Path


def test_audio_devices():
    """List all available audio devices."""
    print("\n" + "="*70)
    print("AVAILABLE AUDIO DEVICES")
    print("="*70)
    
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        try:
            name = dev.get('name', 'Unknown')
            max_in = dev.get('max_input_channels', 0)
            max_out = dev.get('max_output_channels', 0)
            default_sr = dev.get('default_samplerate', 0)
            
            device_type = []
            if max_in > 0:
                device_type.append(f"Input({max_in}ch)")
            if max_out > 0:
                device_type.append(f"Output({max_out}ch)")
            
            type_str = ", ".join(device_type) if device_type else "No I/O"
            
            print(f"[{idx}] {name}")
            print(f"    Type: {type_str}")
            print(f"    Sample rate: {default_sr} Hz")
            print()
            
        except Exception as e:
            print(f"[{idx}] Error reading device: {e}\n")
    
    print("="*70 + "\n")


def test_recording(duration=3.0, sample_rate=44100):
    """Record a test audio segment and save it."""
    print("\n" + "="*70)
    print("AUDIO RECORDING TEST")
    print("="*70)
    print(f"Duration: {duration} seconds")
    print(f"Sample rate: {sample_rate} Hz")
    print(f"Bit depth: 24-bit")
    print()
    
    # Get default input device info
    try:
        default_device = sd.default.device
        if isinstance(default_device, tuple):
            input_idx = default_device[0]
        else:
            input_idx = default_device
        
        device_info = sd.query_devices(input_idx)
        print(f"Using device: {device_info.get('name', 'Default')}")
        print(f"Max input channels: {device_info.get('max_input_channels', 'Unknown')}")
        print()
    except Exception as e:
        print(f"Warning: Could not get device info: {e}\n")
    
    input("\nPress ENTER to start recording...")
    
    # Countdown
    print("\nStarting in: ", end="", flush=True)
    import time
    for i in range(3, 0, -1):
        print(f"{i}... ", end="", flush=True)
        time.sleep(1)
    print("GO!\n")
    
    try:
        # Record
        print(f"🔴 Recording {duration}s...")
        audio_data = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='float32'
        )
        sd.wait()
        audio_data = audio_data.flatten()
        
        print(f"✓ Recording complete")
        print(f"  Samples: {len(audio_data)}")
        print(f"  Duration: {len(audio_data) / sample_rate:.2f}s")
        print(f"  Peak level: {np.max(np.abs(audio_data)):.3f}")
        
        # Check for clipping
        if np.max(np.abs(audio_data)) > 0.95:
            print("  ⚠ WARNING: Signal may be clipping! Lower input gain.")
        elif np.max(np.abs(audio_data)) < 0.05:
            print("  ⚠ WARNING: Signal very quiet. Increase input gain.")
        else:
            print("  ✓ Signal level looks good")
        
        # Play back
        playback = input("\nPlay back recording? (y/n): ").strip().lower()
        if playback == 'y':
            print("♪ Playing back...")
            sd.play(audio_data, sample_rate)
            sd.wait()
            print("✓ Playback complete")
        
        # Save test file
        save = input("\nSave test recording? (y/n): ").strip().lower()
        if save == 'y':
            test_dir = Path(__file__).parent / "test_recordings"
            test_dir.mkdir(exist_ok=True)
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"test_harmonic_{timestamp}.wav"
            filepath = test_dir / filename
            
            # Convert to 24-bit
            audio_int = np.clip(audio_data * 8388607, -8388608, 8388607).astype(np.int32)
            wavfile.write(filepath, sample_rate, audio_int)
            
            file_size_kb = filepath.stat().st_size / 1024
            print(f"\n✓ Saved: {filepath}")
            print(f"  Size: {file_size_kb:.1f} KB")
        
        print("\n" + "="*70)
        print("TEST COMPLETE - Audio system is working!")
        print("="*70 + "\n")
        return True
        
    except Exception as e:
        print(f"\n✗ Error during recording: {e}")
        print("\nPossible issues:")
        print("  - No audio interface connected")
        print("  - Wrong input device selected")
        print("  - Permission denied for audio access")
        print("  - Driver issues")
        print("\n" + "="*70 + "\n")
        return False


def main():
    """Run audio system tests."""
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║          HARMONICS RECORDING - Audio System Test                 ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    print("This script will:")
    print("  1. List available audio devices")
    print("  2. Record a test audio segment")
    print("  3. Verify recording quality")
    print("  4. Test playback")
    print("  5. Save a test file")
    print()
    
    # Test 1: List devices
    test_audio_devices()
    
    # Test 2: Record audio
    input("Press ENTER to continue with recording test...")
    success = test_recording(duration=3.0)
    
    if success:
        print("\n✓ All tests passed! You're ready to start recording harmonics.")
        print("\nTo begin the full recording session, run:")
        print("  python HarmonicsRecordingSession.py")
    else:
        print("\n✗ Audio test failed. Please fix issues before recording.")
        print("\nTroubleshooting:")
        print("  1. Check audio interface is connected")
        print("  2. Install/update audio drivers")
        print("  3. Grant microphone permissions")
        print("  4. Try a different audio device")
    print()


if __name__ == "__main__":
    main()
