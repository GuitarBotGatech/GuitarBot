# Fret/Pluck Coordination Test Tool

## Purpose
Diagnostic tool to analyze timing coordination between fretting (presser) and plucking (picker) motors. Generates detailed logs showing when each motor moves and whether the pluck occurs at the correct time relative to presser settling.

## Usage

### Run the test:
```bash
python test_fret_pluck_coordination.py
```

### Output:
1. **Console output**: Detailed timing analysis for each test
2. **CSV log file**: `coordination_logs/coordination_test_YYYYMMDD_HHMMSS.csv`

## Test Scenarios

The script runs 4 test scenarios:

### Scenario 1: Basic Fret Changes (Full Trajectory)
- Tests normal fret changes with full unpress → slide → press sequence
- Expected: Pluck occurs AFTER presser settles

### Scenario 2: Position Optimization (Same Fret)
- Tests increasing positions on the same fret (200→250→300→350→400)
- Expected: Auto-enables `position_adjustment_only` mode
- Expected: No unpressing between position changes
- Expected: Pluck occurs AFTER each position settles

### Scenario 3: Explicit Position Adjustment Mode
- Tests with `position_adjustment_only=True` explicitly set
- Expected: Direct position transitions

### Scenario 4: Different Strings
- Tests coordination across multiple strings
- Expected: Each string's pluck occurs after its presser settles

## Output Fields

The CSV log contains these fields for each test:

### Test Info:
- `test_name`: Descriptive name
- `midi_note`: MIDI note number
- `string_id`: String index (0-5)
- `fret_num`: Fret number
- `presser_position`: Position used (encoder ticks)
- `position_adjustment_only`: Whether mode was enabled

### Timing Data (all in seconds):
- `slider_start_time`, `slider_end_time`: When slider moves
- `presser_start_time`, `presser_end_time`: When presser moves
- `presser_settled_time`: When presser reaches and holds target
- `picker_start_time`, `picker_end_time`: When picker moves

### Coordination Analysis:
- `pluck_delay_from_presser_end`: Time between presser stopping and pluck starting
- `pluck_delay_from_presser_settled`: Time between presser settling and pluck starting
- `coordination_ok`: True if pluck occurs AFTER presser settles (positive delay)

### Configuration:
- `configured_settling_time`: The settling time setting (from `BothHandsParser`)
- `configured_pluck_delay`: The pluck delay setting

## Interpreting Results

### Good Coordination:
```
Status: ✓ OK - Pluck occurs AFTER presser settles
Delay from presser settled to pluck: +0.0100s
```
- Positive delay means pluck starts after presser settles
- Should match or exceed `configured_settling_time`

### Bad Coordination:
```
Status: ✗ FAIL - Pluck occurs BEFORE presser settles!
Delay from presser settled to pluck: -0.0050s
Gap: -0.0050s (negative = pluck too early)
```
- Negative delay means pluck starts before presser settles
- This is the bug we're trying to fix

## Common Issues

### Issue 1: Inconsistent Timing
**Symptom**: Some tests pass, some fail
**Possible causes**:
- Settling detection algorithm has bugs
- Different trajectory types (full vs position-only) behave differently
- State carryover between tests

### Issue 2: Always Fails
**Symptom**: All tests show negative delay
**Possible causes**:
- `settling_time` is too small
- Presser settling detection is wrong
- Pluck timing calculation is incorrect

### Issue 3: Pluck Way Too Early
**Symptom**: Large negative delays (e.g., -0.5s)
**Possible causes**:
- Presser settle detection finds wrong point in trajectory
- Trajectory extension logic has bugs

## Debugging Tips

1. **Check settle detection**:
   - Look at `presser_settled_idx` vs `presser_end_idx`
   - Should be at or slightly after `presser_end_idx`
   - If much earlier, settling detection is broken

2. **Compare delays**:
   - `pluck_delay_from_presser_end` = raw motor timing
   - `pluck_delay_from_presser_settled` = with settling detection
   - If very different, settling detection is questionable

3. **Look for patterns**:
   - Do position-only tests behave differently?
   - Do certain strings always fail?
   - Does reset state matter?

4. **Check configured values**:
   - Is `configured_settling_time` reasonable? (should be ~0.01s)
   - Does actual delay match configured delay?

## Example Good Output

```
TEST: Test 2c: Fret 5, position 300
  MIDI Note: 45
  Presser Position: 300
  Position Adjustment Only: False
  State reset: NO (continuing from previous)
  
Auto-enabled position_adjustment_only: already on fret 5

TIMING ANALYSIS:
  Slider:  0.0000s → 0.0000s (duration: 0.0000s)
  Presser: 0.0000s → 0.0240s (duration: 0.0240s)
  Presser settled at: 0.0240s
  Picker:  0.0340s → 0.0500s (duration: 0.0160s)

COORDINATION:
  Delay from presser end to pluck:     +0.0100s
  Delay from presser settled to pluck: +0.0100s
  Configured settling time:             0.0100s
  Status: ✓ OK - Pluck occurs AFTER presser settles

PRESSER POSITION:
  Target:  300.0
  Actual:  300.0
```

## Modifying Tests

To add your own tests, use:

```python
tester.run_test(
    "Custom test name",
    midi_note=45,              # MIDI note to play
    presser_position=350,       # Encoder ticks (or None for default)
    position_adjustment_only=False,  # Force mode on/off
    reset_state=True            # Reset before test
)
```

## Files Generated

- `coordination_logs/coordination_test_YYYYMMDD_HHMMSS.csv` - Full test results
- Console output captures all timing details
