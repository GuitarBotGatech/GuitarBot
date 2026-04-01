# GuitarBot Sequencer UI — Overview

Use this guide for day-to-day editing inside `sequencer.html`: layout, controls, event editing, shortcuts, and common UI troubleshooting.

## Interface Overview

### Toolbar (Top)

- **Song Name** — Enter a name for your arrangement (auto-filled on export).
- **BPM** — Tempo in beats per minute (`20–300`).
- **Key** — Root note + mode (`major` / `minor`) for reference.
- **Time Signature** — `4/4`, `3/4`, `6/8`, `2/4`, `5/4`.
- **Bars** — Number of measures to display.
- **Play / Stop** — Transport controls.
- **Position Display** — Current playhead position (`bar.beat`).
- **Zoom ±** — Expand or contract the timeline view.
- **Import** — Load JSON or MIDI (`.mid/.midi`) arrangements from one file dialog.
- **Export** — Opens the OS save dialog with JSON/MIDI file type options (or a format dropdown fallback).
- **Warnings / FIX** — Warning badge shows note-timing conflicts; **FIX** auto-adjusts octave and on/off timing to reduce overlap/too-close warnings.

### Canvas Regions (Left to Right)

1. **Label Column** — Note names (`C`, `C#`, `D`, ..., `B`) and lane labels (`CHD`, `FX`).
2. **Grid** — Beat-aligned timeline with measure and beat markers.
3. **Chord Lane** (top) — Stacked chord symbols over time.
4. **Pluck Roll** (middle) — Individual note events on a piano-roll grid; each string has its own color.
5. **MIDI Lane** (bottom) — Control change, note, program, and pitch bend events.

### Inspector Panel (Right)

When a pluck note is selected, the **Inspector** panel appears with:

- **Note** — Display name and MIDI number.
- **String** — Playable string(s) that include this note.
- **Speed** — Plucking velocity (`0–127`).
- **Slide** — Slide-in effect toggle.
- **Duration** — Note hold time in beats.
- **String Override** — Force a specific string instead of auto-select.
- **Delete Button** — Remove the selected note.

## Creating Events

### Add a Pluck Note

1. Click any empty cell in the **Pluck Roll**.
2. A note is created at that beat and pitch; the Inspector opens.
3. Adjust speed, slide, duration, and string override as needed.

**Move:** Click-drag to a new beat/pitch.  
**Resize:** Drag the right edge to change duration.  
**Delete:** Right-click, or press **Delete/Backspace** while selected.

### Add a Chord Symbol

1. Click any empty cell in the **Chord Lane**.
2. In the popup, pick a chord from the dropdown or type a custom symbol.
3. Confirm beat position and close the popup.

**Edit:** Click an existing chord.  
**Delete:** Press **Delete/Backspace** or use the popup delete button.

### Add a MIDI Event

1. Click any empty cell in the **MIDI Lane**.
2. Select an OSC address (`/cc`, `/note`, `/noteoff`, `/program`, `/pitch`).
3. Enter arguments (example: `7, 64` for CC#7 value 64).
4. Optionally enable **Interpolate** for value ramps.

**Edit:** Click an existing event.  
**Delete:** Press **Delete/Backspace** or use the popup delete button.

## Playback

- Click **▶ Play** to start from beat `1.1`.
- **Position Display** updates in real time (`bar.beat`).
- Click **■ Stop** to halt and reset to the start.
- The red playhead shows current timeline position.

Playback in the sequencer is visual only. Robot/MIDI output requires OSC or bridge integration.

## Navigation

- **Horizontal scroll** — Mouse wheel, or **Shift + Scroll**.
- **Zoom** — **Ctrl/Cmd + Scroll** or toolbar zoom buttons.
- **Pan** — Middle-mouse drag (if supported by your environment).

## Import, Export, and JSON Preview

### Export

1. Click **↓ Export**.
2. Choose the file type in the save dialog (`.json` or `.mid/.midi`).
3. Filename is generated from song name.
4. JSON export includes metadata + all event tracks.

### MIDI Export

1. Click **↓ Export** and select MIDI file type.
2. Pluck notes are exported as MIDI notes.
3. MIDI lane `/cc` events are exported as MIDI CC data.
4. Tempo automation is exported as tempo changes.

### Import

1. Click **↑ Import** and select `.json`, `.mid`, or `.midi`.
2. JSON loads song metadata + tracks directly.
3. MIDI loads notes into the **Pluck Roll** and CC/program/pitch events into the **MIDI Lane**.
4. Existing events are replaced (no merge).

### JSON Preview

1. Expand the **JSON Preview** bar at the bottom.
2. Review a live syntax-highlighted, read-only arrangement.
3. Use it to validate structure before export/send.

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Delete selected event | **Delete** or **Backspace** |
| Close popup | **Escape** (or click outside) |
| Grid smaller (finer) | **Ctrl/Cmd + 1** |
| Grid bigger (coarser) | **Ctrl/Cmd + 2** |
| Convert current grid to triplet | **Ctrl/Cmd + 3** |
| Zoom in/out | **Ctrl/Cmd + Scroll Wheel** |
| Scroll timeline horizontally | **Shift + Scroll Wheel** |
| Deselect current selection | Click empty canvas area |

## Tips

- **Snap to Grid:** Events snap to 16th-note subdivisions.
- **Beat Labels:** Stored as `bar.beat` / `bar.beat.sub` (examples: `2.3`, `3.2.2`).
- **Raw Beat Format:** Off-grid values may be stored as `~<beats>` (example: `~9.3333`, where `0` is `1.1`).
- **String Override:** Leave empty for auto string assignment unless fingering must be forced.
- **Tremolo Detection:** Notes shorter than `0.5` beats are marked as tremolo.
- **Dynamics:** Vary speed (`0–127`) for expression.
- **MIDI Interpolation:** Use `/cc` + interpolate to create smooth sweeps.

## Troubleshooting

**Notes not appearing?**  
- Click within the note-roll grid area (not the label column).
- Confirm expected MIDI range (`C1 = 40`, `G3 = 68`).

**Chords not saving?**  
- Check beat format (`bar.beat`, e.g., `1.1`).

**Exported JSON empty?**  
- Ensure at least one event exists before exporting.

**Playback is silent?**  
- UI playback is visual only.
- Route through OSC/bridge for robot or synth output.
