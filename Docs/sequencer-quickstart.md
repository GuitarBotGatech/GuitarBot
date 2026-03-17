# GuitarBot Sequencer UI — Quickstart Guide

The **GuitarBot Sequencer** (`sequencer.html`) is a web-based timeline editor for composing robot guitar performances. Arrange pluck notes, chord symbols, and MIDI effects in a single interface, then export as JSON or send directly to the robot.

## Opening the Sequencer

### Start

1. From the GuitarBot root directory, start a simple HTTP server:
   ```bash
   python -m http.server 8000
   ```
2. Open your browser and navigate to: [http://localhost:8000/](http://localhost:8000/)

3. You'll see a timeline with example notes, chords, and MIDI events pre-loaded.

**Note:** Use a local server (not `file://`) to ensure proper asset loading and avoid CORS issues.

## Interface Overview

### Toolbar (Top)

- **Song Name** — Enter a name for your arrangement (auto-filled on export).
- **BPM** — Tempo in beats per minute (20–300).
- **Key** — Root note + mode (major/minor) for reference.
- **Time Signature** — 4/4, 3/4, 6/8, 2/4, 5/4.
- **Bars** — Number of measures to display.
- **Play / Stop** — Transport controls.
- **Position Display** — Current playhead position (bar.beat).
- **Zoom ± ** — Expand or contract the timeline.
- **Import / Export** — Load or save JSON arrangements.

### Canvas Regions (Left to Right)

1. **Label Column** — Note names (C, C#, D, ..., B) and lane labels (CHD, FX).
2. **Grid** — Beat-aligned timeline with measure and beat markers.
3. **Chord Lane** (top) — Stacked chord symbols over time.
4. **Pluck Roll** (middle) — Individual note events on a piano-roll grid; each string has its own color.
5. **MIDI Lane** (bottom) — Control change, note, program, and pitch bend events.

### Inspector Panel (Right)

When you select a pluck note, the **Inspector** slides in from the right showing:

- **Note** — Display name and MIDI number.
- **String** — Which playable string(s) include this note.
- **Speed** — Plucking velocity (0–127 slider).
- **Slide** — Enable slide-in effect (toggle).
- **Duration** — Note hold time in beats.
- **String Override** — Force a specific string instead of auto-select.
- **Delete Button** — Remove the note.

## Creating Events

### Add a Pluck Note

1. Click on any empty cell in the **Pluck Roll** (middle region).
2. The note is created at that beat and pitch; the Inspector opens.
3. Adjust speed, slide, duration, and string override as needed.

**Drag to move:** Click and drag a note to a new beat/pitch.  
**Resize:** Grab the right edge of a note and drag to change duration.  
**Delete:** Right-click or press **Delete/Backspace** while selected.

### Add a Chord Symbol

1. Click on any empty cell in the **Chord Lane** (top).
2. A popup appears; pick a chord from the dropdown or type a custom symbol.
3. Confirm the beat position and close the popup.

**Edit:** Click an existing chord to open its popup.  
**Delete:** Press **Delete/Backspace** or click the "Delete" button in the popup.

### Add a MIDI Event

1. Click on any empty cell in the **MIDI Lane** (bottom).
2. Select an OSC address (/cc, /note, /noteoff, /program, /pitch).
3. Enter arguments (e.g., `7, 64` for CC#7 value 64).
4. Toggle "Interpolate" to smooth the value across a range.

**Edit:** Click an existing event to open its popup.  
**Delete:** Press **Delete/Backspace** or click the "Delete" button in the popup.

## Playback

- Click **▶ (Play)** to start from beat 1.1.
- The **position display** updates in real time (bar.beat).
- Click **■ (Stop)** to halt and reset to the start.
- The **playhead line** (red) shows current position.

*(Note: Playback within the sequencer is visual only; actual robot/MIDI sending requires integration via OSC.)*

## Scrolling & Navigation

**Horizontal scroll:** Scroll wheel or Shift + scroll wheel.  
**Zoom:** Ctrl/Cmd + scroll wheel, or click zoom buttons.  
**Pan:** Middle-mouse drag (if supported) or shift-scroll.

## Import & Export

### Export

1. Click **↓ Export** to download a JSON file.
2. Filename is auto-generated from the song name.
3. JSON contains metadata (BPM, key, time signature) and all event tracks.

### Import

1. Click **↑ Import** and select a previously exported `.json` file.
2. All song data (metadata, notes, chords, MIDI) is loaded.
3. Existing events are replaced (no merge).

## JSON Preview

1. Click the **"JSON Preview"** bar at the bottom to expand it.
2. A live syntax-highlighted view of your arrangement appears (read-only).
3. Useful for debugging custom JSON or verifying structure before export.

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Delete selected event | **Delete** or **Backspace** |
| Zoom in/out | **Ctrl/Cmd + Scroll Wheel** |
| Scroll horizontally | **Scroll Wheel** or **Shift + Scroll** |
| Close popup | **Escape** (or click outside) |
| Deselect | Click empty area on canvas |

## Tips & Best Practices

- **Snap to Grid:** All events snap to 16th-note subdivisions automatically.
- **Beat Labels:** Positions are stored as `bar.beat` (e.g., `2.3` = bar 2, beat 3).
- **String Override:** Leave empty to auto-assign strings; use override only when specific fingering is critical.
- **Tremolo Detection:** Notes shorter than 0.5 beats are marked as tremolo (wavy pattern).
- **Speed/Dynamics:** Vary pluck speed (0–127) for expressive playing.
- **MIDI Interpolation:** Use `/cc` with interpolation to create smooth parameter sweeps (e.g., volume crescendo).

## Common Workflows

### Hand-Author a Simple Song

1. Set BPM, key, time signature in the toolbar.
2. Click the pluck roll to add notes.
3. Adjust durations and speeds via the inspector.
4. Export to JSON.

### Harmonize with Chords

1. Add chord symbols in the chord lane to mark progression.
2. Create pluck notes that match each chord.
3. Use string override to keep voicing natural.

### Add MIDI Control

1. Create a `/cc` event for volume or filter cutoff.
2. Enable "Interpolate" and set values at start and end beats.
3. Export and route the OSC messages to your synth or effects unit.

### Load a Previous Arrangement

1. Click **↑ Import**.
2. Select a JSON file from a previous session.
3. Resume editing.

## Troubleshooting

**Notes not appearing?**  
- Check that you're clicking within the note-roll region (between the grid and the label column).
- Verify the MIDI range (C1 = 40, G3 = 68).

**Chords not saving?**  
- Confirm the beat position is formatted correctly (`bar.beat`, e.g., `1.1`).

**Exported JSON is empty?**  
- Ensure you've added at least one event before exporting.

**Playback doesn't hear anything?**  
- The sequencer UI plays back visually but does not produce audio directly.
- To send OSC to the robot or MIDI to a synth, integrate with `OSC_Message_Send.py` or configure external routing.

## Next Steps

- See [Song Format & Schema](song-format/schema.md) for detailed JSON structure.
- Review [Arrangement Plan](song-format/arrangement-plan.md) for timeline transforms and composition strategies.
- Integrate with [OSC_Message_Send.py](../OSC_Message_Send.py) to transmit to the robot in real time.

---

**Last Updated:** March 2026  
**Version:** 1.0
