# Repeat Mode Usage Guide

## Overview

Repeat Mode allows you to record the same harmonic multiple times in a single session. This is essential for:
- Building machine learning datasets
- Collecting statistical samples
- Data augmentation with natural variations
- Quality control (record multiple takes, pick the best)

## Quick Example

### Goal: Record 10 samples of E string harmonic #1

```bash
cd Recording
python HarmonicsRecordingSession.py
```

**Prompts and Responses:**
```
Select mode (1 or 2) [1]: 2
Use default settings? (y/n): y

Enter string (E/A/D/G/B/e): E
Enter harmonic number (1/2/3): 1
How many recordings? [10]: 10
```

**Result:** 10 files created:
- `GB_NH_harmonic_n1_pitches68_rep01.wav`
- `GB_NH_harmonic_n1_pitches68_rep02.wav`
- ...
- `GB_NH_harmonic_n1_pitches68_rep10.wav`

## Step-by-Step Walkthrough

### Step 1: Start the Script
```bash
python HarmonicsRecordingSession.py
```

### Step 2: Select Repeat Mode
```
Recording modes:
  1. Full session - Record all 18 harmonics (one of each)
  2. Repeat mode - Record ONE harmonic multiple times

Select mode (1 or 2) [1]: 2
```
**Action:** Type `2` and press ENTER

### Step 3: Configure Audio (Optional)
```
Configuration options:
  Default: 44.1kHz, 24-bit, 4.0s recordings

Use default settings? (y/n):
```
**Action:** Type `y` for defaults, or `n` to customize

### Step 4: Select Target Harmonic

**Choose String:**
```
Enter string (E/A/D/G/B/e): E
```
**Important - Case Sensitive:**
- `E` (uppercase) = Low E string (thickest)
- `A`, `D`, `G`, `B` = Middle strings
- `e` (lowercase) = High e string (thinnest)

**Choose Harmonic Number:**
```
Enter harmonic number (1/2/3): 1
```
- `1` = 4th fret (octave + major 3rd)
- `2` = 5th fret (two octaves)
- `3` = 7th fret (octave + perfect 5th)

**Choose Repetitions:**
```
How many recordings? [10]: 20
```
Enter desired number (default is 10)

### Step 5: Recording Loop

For each repetition (1 through N):

1. **Review information:**
   ```
   REPETITION 1/20
   ─────────────────────────────────────
   String: E
   Harmonic: #1
   Location: 4th fret
   Expected pitch: 68 (MIDI)
   ```

2. **Prepare to record:**
   ```
   ▶ Press ENTER when ready to record...
   ```
   **Action:** Position fingers, press ENTER

3. **Countdown and record:**
   ```
   Starting in: 3... 2... 1... GO!
   🔴 Recording... (4.0s)
   ✓ Recording complete
   ```

4. **Optional spectrogram:**
   ```
   ▶ View spectrogram? (y/n):
   ```
   **Action:** Type `y` to see frequency analysis, `n` to skip

5. **Accept or retry:**
   ```
   ▶ Accept this recording? (y=accept, n=retry, q=quit):
   ```
   - `y` = Save and move to next repetition
   - `n` = Discard and retry this repetition
   - `q` = Quit and save what you have so far

6. **Repeat for next recording...**

### Step 6: Session Complete
```
═══════════════════════════════════════
  🎉 REPEAT MODE COMPLETE!
═══════════════════════════════════════
Total recordings: 20
Output directory: GuitarBot_Data/harmonics/2025_11_18/...
```

## Common Use Cases

### Use Case 1: ML Training Dataset
**Goal:** 50 samples per harmonic for neural network training

**Strategy:**
- Run repeat mode 6 times (once per string)
- Each run: select harmonic #1, 50 repetitions
- Total: 300 recordings (6 strings × 50 samples)

**Time estimate:** ~25 minutes per string = 2.5 hours total

### Use Case 2: Quality Selection
**Goal:** Record 5 takes of a difficult harmonic, choose best

**Strategy:**
- Run repeat mode: target harmonic, 5 repetitions
- Use spectrogram to evaluate each
- Accept all 5, analyze later to pick best
- Or retry until you get a perfect take

**Time estimate:** ~3 minutes

### Use Case 3: Variability Study
**Goal:** Study natural variations in playing technique

**Strategy:**
- Run repeat mode: same harmonic, 30 repetitions
- Record with intentional variations:
  - Different pluck strengths
  - Different finger positions
  - Different touch pressure on nodal point
- Analyze spectrograms for differences

**Time estimate:** ~15 minutes

### Use Case 4: Data Augmentation
**Goal:** Expand existing dataset with more samples

**Strategy:**
- Already have 1 sample per harmonic (full session)
- Need 10 more of E string harmonics for balanced dataset
- Run repeat mode 3 times:
  - E string, harmonic #1, 10 reps
  - E string, harmonic #2, 10 reps
  - E string, harmonic #3, 10 reps

**Time estimate:** ~15 minutes total

## Tips for Efficient Recording

### Before Starting
✅ Tune guitar carefully
✅ Set up microphone position
✅ Test audio levels (run test_harmonic_recording.py)
✅ Prepare comfortable seating
✅ Have water nearby (long sessions)

### During Recording
✅ Stay consistent with playing technique
✅ Use spectrogram to verify quality early on
✅ Take breaks every 10-15 recordings
✅ If fatigued, stop and resume later
✅ Accept slightly imperfect recordings (natural variation is good for ML)

### Handling Mistakes
- **Wrong fret:** Press `n` to retry immediately
- **String buzz:** Press `n`, adjust technique
- **Background noise:** Press `n`, wait for quiet
- **Tired:** Press `q`, resume session later

### Maximizing Quality
1. First repetition: View spectrogram to verify setup
2. If first looks good, skip spectrograms for speed
3. View spectrogram again if recording sounds off
4. Accept minor variations (natural data is valuable)
5. Only retry if clearly wrong (wrong note, major noise)

## File Organization

Files are automatically organized by session:

```
GuitarBot_Data/harmonics/
├── 2025_11_18/
│   ├── session1_143022/          # Full session (18 harmonics)
│   │   ├── GB_NH_harmonic_n1_pitches68.wav
│   │   ├── GB_NH_harmonic_n1_pitches73.wav
│   │   └── ...
│   ├── session2_150530/          # Repeat mode: E string H1 (10 reps)
│   │   ├── GB_NH_harmonic_n1_pitches68_rep01.wav
│   │   ├── GB_NH_harmonic_n1_pitches68_rep02.wav
│   │   └── ...
│   └── session3_152015/          # Repeat mode: A string H2 (20 reps)
│       ├── GB_NH_harmonic_n2_pitches69_rep01.wav
│       ├── GB_NH_harmonic_n2_pitches69_rep02.wav
│       └── ...
```

Each session gets a unique timestamp directory.

## Keyboard Shortcuts

During recording prompts:
- **ENTER** - Ready to record (triggers countdown)
- **y** - Yes (view spectrogram, accept recording)
- **n** - No (skip spectrogram, retry recording)
- **q** - Quit (save progress and exit)

## Troubleshooting

### Problem: Selected wrong string
**Solution:** Press `q` to quit, restart script

### Problem: Too many repetitions entered
**Solution:** Press `q` after desired number, remaining won't be recorded

### Problem: Recording sounds different
**Solution:** 
1. View spectrogram to diagnose
2. Check finger position on fret
3. Verify guitar is in tune
4. Check for string wear/dirt

### Problem: Session interrupted
**Solution:** All accepted recordings are saved. Note how many completed, run again with remaining count.

### Problem: Files overwriting each other
**Solution:** Each session gets unique timestamp directory, no overwrites possible

## Best Practices

### Recording Environment
- Quiet room, minimal background noise
- Consistent microphone position
- Stable audio interface settings
- Avoid time of day with external noise (traffic, etc.)

### Playing Technique
- Light, consistent touch on nodal point
- Same pluck strength for all repetitions
- Allow full ring-out before next recording
- Keep finger placement consistent

### Data Management
- Record in batches (10-20 at a time)
- Take breaks to avoid fatigue
- Backup recordings immediately after session
- Keep notes on any special conditions (new strings, different guitar, etc.)

### Quality vs. Quantity
- For ML: More samples with natural variation > perfect samples
- For reference: Fewer perfect samples > many imperfect
- For research: Document any intentional variations
- For training: Accept all reasonable recordings (70%+ quality)

## Example: Complete ML Dataset Collection

**Goal:** 25 samples of each harmonic for ML training

**Plan:**
1. Day 1: E and A strings (6 harmonics × 25 = 150 recordings)
2. Day 2: D and G strings (6 harmonics × 25 = 150 recordings)  
3. Day 3: B and e strings (6 harmonics × 25 = 150 recordings)

**Total:** 450 recordings in 3 sessions

**Execution (Day 1):**
```bash
# Session 1: E string, harmonic #1
python HarmonicsRecordingSession.py
# Mode: 2, String: E, Harmonic: 1, Reps: 25

# Session 2: E string, harmonic #2
python HarmonicsRecordingSession.py
# Mode: 2, String: E, Harmonic: 2, Reps: 25

# Session 3: E string, harmonic #3
python HarmonicsRecordingSession.py
# Mode: 2, String: E, Harmonic: 3, Reps: 25

# ... repeat for A string ...
```

**Time estimate:** ~75 minutes per day

## Summary

Repeat Mode is a powerful feature for:
✅ Building large datasets efficiently
✅ Collecting multiple samples of specific harmonics
✅ Studying variability and consistency
✅ Quality control through multiple takes

Key advantages:
- Focused recording (one harmonic at a time)
- Automatic file numbering (rep01, rep02, ...)
- Same quality controls (spectrogram, retry option)
- Organized output (timestamped sessions)

Perfect for machine learning, research, and data augmentation workflows!
