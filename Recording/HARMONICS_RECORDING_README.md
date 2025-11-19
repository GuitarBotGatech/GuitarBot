# Guitar Harmonics Recording Session

## Overview

`HarmonicsRecordingSession.py` is an automated script for recording and annotating natural harmonics on a 6-string guitar. The script guides you through recording each harmonic with interactive prompts and retry capability.

## Natural Harmonics Reference

### What are Natural Harmonics?

Natural harmonics are created by lightly touching the string at specific nodal points (without pressing down) and plucking. The string vibrates in segments, producing higher pitches.

GuitarBot cannot play every harmonic on guitar, so we are specifically looking at the 5th harmonic (4th fret) the 4th harmonic (5th fret), and the 3rd harmonic (7th fret). 
For simplicity, these will be refered to as harmonics 1-3 with respect to their corresponding MIDI note number (MNN):

### Harmonic Pitches on Guitar

| String | Harmonic #1 | Harmonic #2 | Harmonic #3 |
|--------|-------------|-------------|-------------|
| **E**  | 68          | 64          | 59          |
| **A**  | 73          | 69          | 64          |
| **D**  | 78          | 74          | 69          |
| **G**  | 83          | 79          | 74          |
| **B**  | 87          | 83          | 78          |
| **e**  | 92          | 88          | 83          |


### Physical Locations on Fretboard

- **Harmonic #1**: 4th fret (octave + major 3rd above open string)
- **Harmonic #2**: 5th fret (two octaves above open string)
- **Harmonic #3**: 7th fret (octave + perfect 5th above open string)

## Usage

### Quick Start

```bash
cd Recording
python HarmonicsRecordingSession.py
```

### Recording Modes

The script supports two modes:

#### Mode 1: Full Session (Default)
Records all 18 harmonics once (6 strings × 3 harmonics each)

#### Mode 2: Repeat Mode
Records ONE specific harmonic multiple times for dataset augmentation
- Choose string: **E** (low E), A, D, G, B, **e** (high e) - *case sensitive!*
- Choose harmonic number (1, 2, or 3)
- Choose number of repetitions (e.g., 10)
- Files saved with repetition numbers: `..._rep01.wav`, `..._rep02.wav`, etc.

### Interactive Workflow

1. **Setup**: 
   - Select mode (1=full session, 2=repeat mode)
   - Script automatically detects audio interface (prefers Scarlett)
   - Configure audio settings (or use defaults)
   
2. **For each recording**:
   - Script displays string, harmonic number, and fret location
   - Press **ENTER** when ready to record
   - 3-second countdown, then records
   - Option to view spectrogram to verify pitch and quality
   - Choose action:
     - `y` - Accept recording and continue
     - `n` - Discard and retry
     - `q` - Quit session

### Recording Specifications

- **Sample Rate**: 44.1 kHz (CD quality)
- **Bit Depth**: 24-bit (professional quality)
- **Duration**: 4.0 seconds per recording
- **Channels**: Mono
- **Format**: WAV (uncompressed)

### Output Files

Recordings are saved with these naming conventions:

**Full Session Mode:**
```
GB_NH_harmonic_n{num}_pitches{pitch}.wav
```

**Repeat Mode:**
```
GB_NH_harmonic_n{num}_pitches{pitch}_rep{XX}.wav
```

**Examples:**
- `GB_NH_harmonic_n1_pitches68.wav` - E string, harmonic #1 (full session)
- `GB_NH_harmonic_n2_pitches88.wav` - e string, harmonic #2 (full session)
- `GB_NH_harmonic_n1_pitches68_rep01.wav` - E string, harmonic #1, repetition 1 (repeat mode)
- `GB_NH_harmonic_n1_pitches68_rep02.wav` - E string, harmonic #1, repetition 2 (repeat mode)

### Directory Structure

**Full Session Mode:**
```
GuitarBot_Data/
└── harmonics/
    └── 2025_11_18/
        └── 20251118_143022/
            ├── GB_NH_harmonic_n1_pitches68.wav
            ├── GB_NH_harmonic_n1_pitches73.wav
            ├── ...
            └── [18 total files]
```

**Repeat Mode (example: E string, harmonic #1, 5 repetitions):**
```
GuitarBot_Data/
└── harmonics/
    └── 2025_11_18/
        └── 20251118_150530/
            ├── GB_NH_harmonic_n1_pitches68_rep01.wav
            ├── GB_NH_harmonic_n1_pitches68_rep02.wav
            ├── GB_NH_harmonic_n1_pitches68_rep03.wav
            ├── GB_NH_harmonic_n1_pitches68_rep04.wav
            └── GB_NH_harmonic_n1_pitches68_rep05.wav
```

## Use Cases

### When to Use Full Session Mode
- Initial dataset creation (one sample of each harmonic)
- Testing/validation of recording setup
- Quick reference library of all harmonics
- Single-shot data collection

### When to Use Repeat Mode
- **Machine Learning**: Need multiple samples for training (e.g., 10-50 per harmonic)
- **Statistical Analysis**: Study variability in playing technique
- **Data Augmentation**: Build robust datasets with natural variations
- **Quality Control**: Multiple takes to select best recordings
- **Difficult Harmonics**: Practice and record challenging harmonics repeatedly
- **Specific Research**: Focus on one particular harmonic for detailed study

### Typical Workflow
1. Run **Full Session Mode** first to get baseline dataset (18 recordings)
2. Run **Repeat Mode** for harmonics that need more samples
3. Example: Need 20 samples of E string harmonic #1 for ML training
   - Select Mode 2
   - String: E, Harmonic: 1, Repetitions: 20
   - Results in 20 files: `...rep01.wav` through `...rep20.wav`

## Customization

### Custom Settings

When running the script, you can customize:
- Sample rate (default: 44100 Hz)
- Bit depth (16, 24, or 32-bit; default: 24)
- Recording duration (default: 4.0 seconds)

### Custom Output Directory

```python
from HarmonicsRecordingSession import HarmonicsRecordingSession

session = HarmonicsRecordingSession(
    sample_rate=48000,
    bit_depth=24,
    recording_duration=5.0,
    output_dir="/path/to/custom/dir"
)

session.run_session()
```

## Tips for Best Results

### Recording Environment
- Use a quiet room with minimal background noise
- Position microphone 6-12 inches from the guitar
- Avoid air conditioning or fan noise
- Close windows to reduce external sounds

### Playing Technique
- Touch string lightly at exact nodal point (don't press down)
- Pluck string with consistent moderate force
- Let harmonic ring for full duration
- Wait for silence before accepting/retrying

### Audio Interface Setup
- Use a quality audio interface (e.g., Focasrite Scarlett)
- Set input gain appropriately (avoid clipping)
- Use phantom power if needed for condenser mic
- Monitor levels before starting session

## Troubleshooting

### No Audio Devices Found
```bash
# List available audio devices
python -c "import sounddevice as sd; print(sd.query_devices())"
```

### Recording Sounds Distorted
- Lower input gain on audio interface
- Move microphone further from guitar
- Check for clipping in recording software

### File Not Saving
- Check write permissions for output directory
- Ensure sufficient disk space
- Verify scipy and numpy are installed

### Wrong Device Selected
- Script will prompt for device selection if Scarlett not found
- Manually select device index from list

## Data Usage

These annotated recordings can be used for:

- **Machine Learning**: Training pitch detection models
- **Analysis**: Studying harmonic content and timbre
- **Calibration**: Tuning GuitarBot's harmonic detection
- **Reference**: Building a harmonic sample library
- **Research**: Analyzing natural vs. artificial harmonics

## Dependencies

Required packages (see `recording_requirements.txt`):
- `sounddevice>=0.4.6` - Audio recording
- `scipy>=1.11.0` - WAV file I/O and spectrogram generation
- `numpy>=1.24.0` - Audio processing
- `matplotlib>=3.7.0` - Spectrogram visualization

Install with:
```bash
pip install sounddevice scipy numpy matplotlib
```

## Session Statistics

### Full Session Mode
- **Total recordings**: 18 (6 strings × 3 harmonics)
- **Time per recording**: ~30 seconds (including prompts)
- **Estimated session time**: 10-15 minutes (without retries)
- **Storage per session**: ~50-100 MB (depending on bit depth)

### Repeat Mode
- **Total recordings**: User-defined (e.g., 10, 20, 50 repetitions)
- **Time per recording**: ~30 seconds (including prompts)
- **Estimated session time**: 
  - 10 repetitions: ~5 minutes
  - 20 repetitions: ~10 minutes
  - 50 repetitions: ~25 minutes
- **Storage**: ~3-5 MB per recording (24-bit, 4s duration)

## Related Scripts

- `RecordingTestSession.py` - General purpose recording with OSC
- `AudioAnalyzer.py` - Analyze recorded audio files
- `CrossAnalysis.py` - Compare multiple recordings

## Support

For issues or questions:
1. Check that all dependencies are installed
2. Verify audio interface is connected and recognized
3. Test audio recording with system tools first
4. Review sounddevice documentation: https://python-sounddevice.readthedocs.io/

## License

Part of the GuitarBot project. See repository LICENSE file.
