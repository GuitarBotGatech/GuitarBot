# Force Testing Workflow - Implementation Summary

## Problem Statement

The force testing workflow had two main issues:
1. **Unpressing between tests**: Each successive `/Fret` message would cause the presser to go through a full unpress→slide→press cycle, causing the string to lose contact between force measurements.
2. **Premature pluck timing**: The pluck was happening before the presser finished moving and settled.

## Solution Overview

### 1. Simplified Trajectory Generation (LeftHandParser)

Implemented `force_adjustment_only` mode with three helper methods:

#### `_generate_simple_trajectory()`
- **Purpose**: Apply target torque then release to rest
- **Phases**:
  1. Apply target torque (current → target)
  2. REST - Release to 0 (target → 0) - motor idle for pluck
- **Use Cases**:
  - Force increments on same fret
  - Unpressing when force=0 (single phase: → -650)
- **Behavior**: Ensures motor is at rest (torque=0) before pluck

#### `_generate_simple_fret_change()`
- **Purpose**: 2-phase trajectory for changing frets during force testing
- **Phases**:
  1. Release to idle (torque → 0)
  2. Slide and apply target torque (simultaneous)
- **Benefit**: Simpler than normal 3-phase fretting

### 2. Proper Pluck Timing (BothHandsParser)

Updated `parse_fret_with_pluck()` to ensure correct sequence:

```
1. Presser applies target torque
   ↓
2. Presser releases to 0 (motor idle/rest)
   ↓ (settling_time = 5 * TIME_STEP ≈ 25ms)
3. Plucker plucks (only when torque=0!)
   ↓
4. Pluck motion completes
   ↓
5. Trajectory continues with buffer
```

#### Key Improvements:
- **Trajectory analysis**: Analyzes presser trajectory to find when torque reaches 0
- **Rest phase detection**: Finds the last contiguous block of near-zero torque values
- **Automatic extension**: Extends LH trajectory if needed to accommodate pluck
- **Settling time**: Configurable delay between torque→0 and pluck start
- **Buffer verification**: Ensures pluck motion completes before trajectory ends

**Critical**: Pluck ONLY happens when presser torque = 0 (motor at rest), not while applying force.

**KEY INSIGHT**: The pluck MUST happen when torque=0 (motor idle), not when applying force. This allows the string to vibrate freely without damping from the presser motor.

#### Key Improvements:
- **Dynamic duration calculation**: Uses actual LH trajectory duration instead of fixed formula
- **Trajectory extension**: Automatically extends LH trajectory if needed to accommodate full pluck motion
- **Settling time**: Configurable delay between presser rest and pluck start
- **Buffer verification**: Ensures pluck motion completes before trajectory ends

## Torque Control Model

### Conceptual Shift
**OLD (Incorrect)**: Presser commands = absolute positions
**NEW (Correct)**: Presser commands = torque values

### Torque Values
- `0` = Motor idle/holding position
- `Positive value` = Motor applies force (value/1000 = % of rated torque)
- `LH_PRESSER_PRESSED_POS = 500` = 50% rated torque (max)
- `LH_PRESSER_SLIDE_PRESS_POS = 400` = 40% rated torque (for slides)
- `LH_PRESSER_UNPRESSED_POS = -650` = Unpressed position

### Example Force Sequence
```python
# Test with forces [0.2, 0.4, 0.6, 0.0]
Message 1: 0 → 100 torque → 0 (rest) → pluck
Message 2: 0 → 200 torque → 0 (rest) → pluck  # No unpressing to -650!
Message 3: 0 → 300 torque → 0 (rest) → pluck  # No unpressing to -650!
Message 4: 0 → -650 (unpress completely)  # Special: force=0 → fret_num=0
```

**Important**: Each message applies the target torque, then releases to 0 (motor idle) before plucking. This ensures the string can vibrate freely without motor damping.

## API Usage

### Force Testing Protocol

```python
from BothHandsParser import BothHandsParser

parser = BothHandsParser()

# Test sequence: increment force on same fret
force_levels = [0.2, 0.4, 0.6]
midi_note = 48  # C3

for force in force_levels:
    trajectory = parser.parse_fret_with_pluck(
        midi_note=midi_note,
        presser_force=force,
        pluck_velocity=None,  # State toggle
        timestamp=0.0,
        force_adjustment_only=True  # KEY: Enable simplified mode
    )
    # Send trajectory to robot...
    # Record audio...

# Final unpress
final_trajectory = parser.parse_fret_with_pluck(
    midi_note=midi_note,
    presser_force=None,
    timestamp=0.0,
    force_adjustment_only=True
)
```

### Key Parameters

- **`force_adjustment_only=True`**: Enables simplified trajectories for force testing
  - Same fret: Direct torque adjustment (no unpressing)
  - Different fret: 2-phase trajectory (release → slide+press)
  - Force=0: Unpress to -650

- **`presser_force`**: Float 0.0-1.0
  - Scales torque: `torque = force * LH_PRESSER_PRESSED_POS`
  - None = use default (LH_PRESSER_PRESSED_POS)

- **`pluck_velocity`**: MIDI velocity 0-127 or None
  - None = state toggle (recommended for force testing)

## Timing Configuration

### BothHandsParser Settings
```python
self.settling_time = tu.TIME_STEP * 5  # 25ms settling before pluck
```

### Calculated Timing
```
Presser motion duration: Variable (from LH trajectory)
Buffer before pluck: 100 * TIME_STEP (500ms)
Settling time: 5 * TIME_STEP (25ms)
Pluck duration: PICKER_PLUCK_MOTION_POINTS * TIME_STEP (55ms)
Buffer after pluck: 50 * TIME_STEP (250ms)
```

## Testing

### Test Scripts

1. **`test_force_testing_workflow.py`**
   - Tests simplified trajectory generation
   - Verifies no unpressing between increments
   - Checks torque values

2. **`test_force_testing_with_pluck.py`**
   - Tests complete force testing workflow
   - Verifies pluck timing sequence
   - Ensures pluck motion completes

### Run Tests
```bash
cd /home/codmusic/GithubGuitarBot/GuitarBot
python test_force_testing_workflow.py
python test_force_testing_with_pluck.py
```

## Benefits

### For Force Testing
✓ **No string contact loss** between measurements
✓ **Faster test execution** (simplified trajectories)
✓ **More accurate** force measurements
✓ **Proper settling time** before pluck
✓ **Complete pluck motion** (not truncated)

### For Normal Playing
- Normal mode (`force_adjustment_only=False`) unchanged
- Full 3-phase fretting still available
- Backward compatible

## File Changes

### Modified Files
1. **LeftHandParser.py**
   - Added `_generate_simple_trajectory()`
   - Added `_generate_simple_fret_change()`
   - Updated `generate_fret_trajectory()` with force_adjustment_only logic
   - Changed `get_presser_position()` → `get_presser_torque()`
   - Updated `get_status()` to clarify torque values

2. **BothHandsParser.py**
   - Fixed pluck timing calculation
   - Added trajectory extension logic
   - Improved pluck motion verification
   - Added detailed timing logs

### New Test Files
1. **test_force_testing_workflow.py**
2. **test_force_testing_with_pluck.py**
3. **test_torque_control.py**

## Migration Notes

### For Existing Code
No changes needed for normal playing (force_adjustment_only defaults to False).

### For Force Testing
Update to use new API:
```python
# OLD (incorrect - would unpress between tests)
for force in forces:
    trajectory = parser.parse_fret_with_pluck(midi_note, force)

# NEW (correct - maintains engagement)
for force in forces:
    trajectory = parser.parse_fret_with_pluck(
        midi_note, force, force_adjustment_only=True
    )
```

## Constants Reference

From `tune.py`:
```python
TIME_STEP = 0.005  # 5ms per timestep
PRESSER_INTERPOLATION_POINTS = 40  # 200ms for pressing
LH_SINGLE_NOTE_MOTION_POINTS = 40  # 200ms for sliding
PICKER_PLUCK_MOTION_POINTS = 11  # 55ms for plucking

LH_PRESSER_PRESSED_POS = 500  # 50% rated torque
LH_PRESSER_SLIDE_PRESS_POS = 400  # 40% rated torque
LH_PRESSER_UNPRESSED_POS = -650  # Unpressed position
```

## Future Enhancements

### Potential Improvements
- [ ] Variable settling time based on force change magnitude
- [ ] Adaptive trajectory extension based on pluck velocity
- [ ] Per-string torque calibration
- [ ] Force feedback from encoder readings

### Compatibility
- Works with existing RobotController
- Compatible with RecordingTestSession
- Integrates with AudioAnalyzer and CrossAnalysis
