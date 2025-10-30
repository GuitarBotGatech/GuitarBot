# /Dyn OSC Message Format - Velocity Support

## Overview

The `/Dyn` message now supports multiple formats for sending pluck commands with optional velocity control. This allows for both simple state-toggle plucking and dynamic velocity-based plucking.

## Supported Message Formats

### Format 1: Single Note, State Toggle
```python
/Dyn 40
```
- **Description**: Pluck a single note using state toggle (up/down alternating)
- **Parameters**: Single MIDI note number
- **Behavior**: Picker alternates between up and down positions
- **Use Case**: Simple plucking without velocity control

### Format 2: Multiple Notes, State Toggle
```python
/Dyn [40, 45, 50]
```
- **Description**: Pluck multiple notes using state toggle
- **Parameters**: List of MIDI note numbers
- **Behavior**: Each picker toggles its state independently
- **Use Case**: Pluck multiple strings simultaneously

### Format 3: Single Note with Velocity
```python
/Dyn 40 60
```
- **Description**: Pluck a single note with specified velocity
- **Parameters**: 
  - First: MIDI note number
  - Second: Velocity (0-127)
- **Behavior**: Picker position calculated from velocity mapping
- **Use Case**: Dynamic plucking with volume control

### Format 4: Multiple Notes with Velocities
```python
/Dyn [40, 45] [60, 127]
```
- **Description**: Pluck multiple notes, each with its own velocity
- **Parameters**: 
  - First list: MIDI note numbers
  - Second list: Corresponding velocities (0-127)
- **Behavior**: Each note plucked at its specified velocity
- **Use Case**: Dynamic multi-string plucking
- **Constraint**: Note count must match velocity count

## Implementation Details

### Message Parsing Logic

The `dynamics_processor()` function handles all formats:

```python
def dynamics_processor():
    # Parse incoming OSC data
    if isinstance(dyn_data, list):
        if isinstance(dyn_data[0], list):
            # Format 4: [[notes], [velocities]]
            midi_notes = dyn_data[0]
            velocities = dyn_data[1]
            use_velocity = True
        elif len(dyn_data) == 2:
            # Format 3: [note, velocity]
            midi_notes = [dyn_data[0]]
            velocities = [dyn_data[1]]
            use_velocity = True
        else:
            # Format 2: [notes]
            midi_notes = dyn_data
            use_velocity = False
    else:
        # Format 1: single note
        midi_notes = [dyn_data]
        use_velocity = False
```

### Velocity Mapping

When velocities are provided:
- **use_velocity_mapping=True**: Uses `velocity_to_position()` mapping
- Each note processed with its corresponding velocity
- Velocity range: 0-127 (MIDI standard)
- Position calculated based on velocity curve

When no velocities:
- **use_velocity_mapping=False**: Uses state toggle
- Pickers alternate between up/down positions
- Independent state per picker

## RightHandParser Integration

### Method Signature
```python
def parse_dynamics_message(self, midi_notes, velocity=100, use_velocity_mapping=False):
```

### Parameters
- **midi_notes**: List of MIDI note numbers (or single int)
- **velocity**: Single velocity value (default: 100)
- **use_velocity_mapping**: Boolean to enable velocity-based positioning

### Behavior
- **State Toggle** (use_velocity_mapping=False):
  - Alternates picker between up/down
  - Maintains state per picker
  - Position: RH_PICKER_STRUM_UP_POS or RH_PICKER_STRUM_DOWN_POS

- **Velocity Mapping** (use_velocity_mapping=True):
  - Calculates position from velocity
  - Formula: position = velocity_to_position(picker_id, velocity)
  - Allows dynamic control

## Example Usage

### Python with pythonosc

```python
from pythonosc import udp_client

client = udp_client.SimpleUDPClient("127.0.0.1", 12000)

# State toggle - single note
client.send_message("/Dyn", 40)

# State toggle - multiple notes
client.send_message("/Dyn", [40, 45, 50])

# Velocity - single note
client.send_message("/Dyn", [40, 60])

# Velocity - multiple notes
client.send_message("/Dyn", [[40, 45], [60, 127]])
```

### Max/MSP or Pure Data

```
# State toggle
/Dyn 40

# Multiple notes
/Dyn 40 45 50

# Single note with velocity
/Dyn 40 60

# Multiple notes with velocities (requires list packing)
/Dyn [40 45] [60 127]
```

## Velocity Range and Behavior

### Velocity Values
- **0**: Softest (minimal picker movement)
- **64**: Medium (50% movement)
- **127**: Loudest (maximum picker movement)

### Velocity Curve
The velocity-to-position mapping uses a linear or curved relationship defined in RightHandParser:
- Low velocity → Small picker displacement
- High velocity → Large picker displacement
- Affects both amplitude and attack of the pluck

## Error Handling

### Mismatched Counts
```python
/Dyn [40, 45, 50] [60, 127]  # 3 notes, 2 velocities
```
**Result**: Warning logged, falls back to state toggle

### Empty Messages
```python
/Dyn []
```
**Result**: Warning logged, message skipped

### Invalid Note Numbers
```python
/Dyn 999
```
**Result**: Warning logged in RightHandParser, note skipped

## Testing

### Test Script
```bash
# Run the test script
python test_dyn_velocity.py formats    # Test all formats
python test_dyn_velocity.py velocity   # Test velocity range
python test_dyn_velocity.py toggle     # Test state toggle
python test_dyn_velocity.py interactive # Manual testing
```

### Expected Output
```
Processing dynamics message: [40, 60]
  Parsed - Notes: [40], Velocities: [60]
Dynamics Trajs Shape: (11, 15)
Executing dynamics test
```

## Comparison with /Fret

| Feature | /Dyn | /Fret |
|---------|------|-------|
| Changes fretting | ❌ No | ✅ Yes |
| Plucks strings | ✅ Yes | ✅ Yes |
| Velocity control | ✅ Yes | ✅ Yes |
| Force control | ❌ No | ✅ Yes |
| Motors controlled | RH only (3) | LH+RH (15) |
| Use case | Quick pluck | Complete note |

## Performance Considerations

### Trajectory Generation
- **State toggle**: Single trajectory per picker
- **Velocity mode**: Separate trajectory per note
- Multiple notes with velocities: Stacked trajectories

### Timing
- Each pluck: ~11 timesteps (55ms at TIME_STEP=0.005s)
- Multiple notes: Sequential plucking
- Processing: <1ms per message

## Backward Compatibility

### Old Format (Still Supported)
```python
/Dyn [40, 45, 50]  # State toggle only
```

### New Formats (Added)
```python
/Dyn 40 60                    # Velocity control
/Dyn [40, 45] [60, 127]       # Multi-note velocity
```

All existing code continues to work without changes.

## Troubleshooting

### Issue: Velocity not working
**Check**: 
- Is second parameter a number (0-127)?
- Is message format correct?
- Check logs for "Parsed - Notes: X, Velocities: Y"

### Issue: Wrong picker activated
**Check**:
- MIDI note number mapping (see RightHandParser.midi_note_to_picker_id)
- Note must be in range for available strings

### Issue: Multiple notes play same velocity
**Check**:
- Velocity list length matches note list length
- Both are lists: `[[notes], [velocities]]`

## Future Enhancements

Potential improvements:
- [ ] Per-string velocity calibration
- [ ] Velocity curves (linear, exponential, etc.)
- [ ] Velocity mapping profiles
- [ ] MIDI-style note-on/note-off with duration
