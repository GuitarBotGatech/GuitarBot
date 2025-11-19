# Spectrogram Visualization Feature

## Overview

The `HarmonicsRecordingSession.py` script now includes spectrogram visualization instead of audio playback. This allows users to visually verify the recording quality and pitch content before accepting each recording.

## What Changed

### Before
- After recording, users were prompted to **play back** the audio
- Audio was played through speakers/headphones
- No visual feedback on frequency content

### After
- After recording, users are prompted to **view spectrogram**
- Visual display shows frequency content over time
- Expected pitch is marked with a red dashed line for reference
- Helps verify harmonics are clean and correct

## How to Use

### During Recording Session

1. Record a harmonic (press ENTER, countdown, record)
2. When prompted: `▶ View spectrogram? (y/n):`
   - Type `y` to see the spectrogram
   - Type `n` to skip visualization
3. If viewing spectrogram:
   - A matplotlib window will open showing the frequency analysis
   - Red dashed line shows the expected fundamental frequency
   - Close the window to continue
4. Then accept (`y`), retry (`n`), or quit (`q`)

### Spectrogram Features

The spectrogram display shows:

- **X-axis**: Time (seconds) from start of recording
- **Y-axis**: Frequency (Hz) from 0 to 5000 Hz
- **Color**: Power/intensity (dB scale)
  - Brighter colors = stronger frequency components
  - Darker colors = weaker frequency components
- **Red dashed line**: Expected fundamental frequency based on MIDI pitch
- **Title**: Shows expected MIDI pitch and frequency in Hz

### What to Look For

**Good Recording:**
- Strong horizontal band at the expected frequency (red line)
- Clear harmonic series above the fundamental (multiples of base frequency)
- Minimal noise between harmonics
- Stable frequency over time (horizontal bands, not wobbly)

**Problem Indicators:**
- No energy at expected frequency → wrong note played
- Energy spread across many frequencies → noisy recording
- Weak signal overall → too quiet, increase gain
- Clipping/distortion → too loud, decrease gain
- Multiple strong fundamentals → string accidentally touched other strings

## Technical Details

### Implementation

```python
def show_spectrogram(self, audio_data, expected_pitch):
    """Display spectrogram of recorded audio with expected pitch reference."""
    # Convert MIDI to frequency
    expected_freq = 440.0 * (2.0 ** ((expected_pitch - 69) / 12.0))
    
    # Compute spectrogram using scipy.signal.spectrogram
    frequencies, times, Sxx = signal.spectrogram(
        audio_data, 
        fs=self.sample_rate,
        nperseg=2048,      # FFT window size
        noverlap=1536      # 75% overlap for smooth visualization
    )
    
    # Display with matplotlib
    plt.pcolormesh(times, frequencies, 10 * np.log10(Sxx + 1e-10), 
                  shading='gouraud', cmap='viridis')
    # ... add labels, reference line, etc.
```

### Parameters

- **FFT Window Size (`nperseg`)**: 2048 samples
  - At 44.1 kHz, this gives ~46ms time resolution
  - Frequency resolution: ~21.5 Hz bins
  
- **Overlap (`noverlap`)**: 1536 samples (75% overlap)
  - Provides smooth visualization over time
  - Balance between time resolution and computational cost

- **Frequency Range**: 0-5000 Hz
  - Covers musical range for guitar harmonics
  - Higher harmonics up to ~8th partial are visible

- **Color Map**: Viridis (perceptually uniform)
  - Good contrast for identifying features
  - Colorblind-friendly

## Dependencies

The spectrogram feature requires matplotlib:

```bash
pip install matplotlib
```

Already included in `recording_requirements.txt`.

### If Display Issues Occur

**Linux (X11 forwarding issues):**
```bash
# Use TkAgg backend
export MPLBACKEND=TkAgg
python HarmonicsRecordingSession.py
```

**Headless systems (no display):**
- Skip spectrogram option (press `n`)
- Recordings can still be made and saved
- Analyze spectrograms later with separate tools

**Backend errors:**
```python
# Add to top of script if needed:
import matplotlib
matplotlib.use('TkAgg')  # or 'Qt5Agg', 'GTK3Agg'
```

## Benefits

### Quality Control
- Immediate visual feedback on recording quality
- Identify problems before accepting recording
- Reduce retakes by catching issues early

### Educational
- Learn what harmonics look like in frequency domain
- Understand harmonic series visually
- Compare different harmonic locations (4th, 5th, 7th fret)

### Documentation
- Visual record of what was captured
- Can screenshot spectrograms for analysis
- Compare spectrograms across sessions

### Scientific
- Verify harmonic content matches theory
- Identify unexpected resonances or noise
- Quantitative analysis of frequency components

## Example Use Cases

### Scenario 1: Wrong Note
- **Problem**: Accidentally played 5th fret instead of 4th fret
- **Spectrogram shows**: Energy at wrong frequency (not aligned with red line)
- **Action**: Press `n` to retry, play correct fret

### Scenario 2: Multiple Strings
- **Problem**: Hand touched adjacent string while playing
- **Spectrogram shows**: Multiple strong fundamental frequencies
- **Action**: Press `n` to retry, isolate single string

### Scenario 3: Too Much Noise
- **Problem**: Room noise, buzzing, or finger scraping
- **Spectrogram shows**: Energy spread across many frequencies (broadband noise)
- **Action**: Press `n` to retry in quieter conditions

### Scenario 4: Perfect Recording
- **Problem**: None!
- **Spectrogram shows**: Clean fundamental at red line, clear harmonic series above
- **Action**: Press `y` to accept and continue

## Future Enhancements

Potential additions:
- Auto-detect fundamental frequency and compare to expected
- Highlight harmonic series (2f, 3f, 4f, etc.)
- Calculate SNR (signal-to-noise ratio)
- Save spectrogram image alongside audio file
- Real-time spectrogram during recording
- Pitch tracking overlay
- Harmonic-to-noise ratio calculation

## Related Documentation

- `HARMONICS_RECORDING_README.md` - Complete recording guide
- `recording_requirements.txt` - All dependencies
- `test_harmonic_recording.py` - Audio system test script

## Troubleshooting

### Spectrogram won't display
```
✗ Error displaying spectrogram: ...
```
**Solutions:**
1. Install matplotlib: `pip install matplotlib`
2. Check display is available: `echo $DISPLAY`
3. Try different backend: `export MPLBACKEND=TkAgg`
4. Skip spectrogram, just record audio

### Window appears blank
- Wait a few seconds for rendering
- Try closing and viewing again
- Check matplotlib version: `pip show matplotlib`

### Colors hard to see
- Close window and adjust monitor brightness
- Try different colormap (edit code: `cmap='plasma'` or `cmap='hot'`)

### Frequency axis looks wrong
- This is normal - uses logarithmic-like perception
- Red line should align with brightest band
- Harmonics appear as parallel bands above

## Summary

The spectrogram feature transforms the recording workflow from blind audio playback to informed visual analysis. Users can now:

✅ Verify correct pitch was played  
✅ Assess recording quality immediately  
✅ Identify and fix problems before accepting  
✅ Learn about harmonic structure visually  
✅ Build confidence in dataset quality  

Simply answer `y` when prompted to view the spectrogram, examine the visualization, close the window, and then decide whether to accept the recording.
