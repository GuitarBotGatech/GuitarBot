# Fret/Pluck Coordination Diagnostic Tool

## Created: November 6, 2025

## Purpose
Lightweight test script to diagnose timing coordination issues between fretting (presser) and plucking (picker) motors.

## Problem Statement
The fret/pluck coordination is inconsistent:
- Sometimes the pluck occurs AFTER the presser settles (correct)
- Sometimes the pluck occurs BEFORE the presser settles (incorrect)

## Solution
Created `test_fret_pluck_coordination.py` to:
1. Generate test trajectories for various scenarios
2. Analyze exact timing of each motor movement
3. Calculate delays between presser settling and pluck start
4. Log all results to CSV for detailed analysis
5. Report pass/fail status for each test

## Key Features

### 1. Detailed Trajectory Analysis
For each test, extracts:
- Slider movement timing (start, end, duration)
- Presser movement timing (start, end, settled point)
- Picker movement timing (start, end, duration)
- Coordination delays (pluck relative to presser)

### 2. Multiple Test Scenarios
- **Scenario 1**: Basic fret changes (full trajectory)
- **Scenario 2**: Position optimization (same fret, increasing positions)
- **Scenario 3**: Explicit position_adjustment_only mode
- **Scenario 4**: Different strings

### 3. Pass/Fail Determination
Each test is marked:
- ✓ **PASS**: Pluck starts AFTER presser settles (positive delay)
- ✗ **FAIL**: Pluck starts BEFORE presser settles (negative delay)

### 4. Statistics and Summary
At the end:
- Total tests run
- Pass/fail counts and percentages
- Mean delay ± standard deviation
- Range of delays
- List of failed tests with details

## Usage

### Run the test:
```bash
cd /home/codmusic/GithubGuitarBot/GuitarBot
python test_fret_pluck_coordination.py
```

### Output files:
```
coordination_logs/
  coordination_test_YYYYMMDD_HHMMSS.csv
```

### Console output shows:
```
TEST: Test 2c: Fret 5, position 300
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
```

## CSV Log Fields

### Timing Fields (seconds):
- `slider_start_time`, `slider_end_time`, `slider_duration`
- `presser_start_time`, `presser_end_time`, `presser_settled_time`, `presser_duration`
- `picker_start_time`, `picker_end_time`, `picker_duration`

### Coordination Fields:
- `pluck_delay_from_presser_end`: Raw delay (presser stops → pluck starts)
- `pluck_delay_from_presser_settled`: Actual delay (presser settled → pluck starts)
- `coordination_ok`: Boolean (True = pass, False = fail)

### Configuration Fields:
- `configured_settling_time`: From `BothHandsParser.settling_time`
- `configured_pluck_delay`: From `BothHandsParser.pluck_delay_after_press`

## Interpreting Results

### Good Result:
```
Delay from presser settled to pluck: +0.0100s
Status: ✓ OK
```
Positive delay = pluck occurs AFTER presser settles (correct behavior)

### Bad Result:
```
Delay from presser settled to pluck: -0.0050s
Status: ✗ FAIL
```
Negative delay = pluck occurs BEFORE presser settles (bug!)

### Analysis Focus:
1. **If all tests fail**: Settling detection or timing calculation is fundamentally broken
2. **If position-only tests fail**: Auto-enable logic or simplified trajectory has issues
3. **If random tests fail**: Non-deterministic bug, possibly state-dependent

## Expected Findings

The test will likely reveal:

1. **Settling detection issues**: 
   - `presser_settled_idx` may be found too early in trajectory
   - Tolerance for "at target" may be wrong
   - Stability check (5 consecutive frames) may not be working

2. **Position-only mode issues**:
   - Auto-enable logic may not be triggering correctly
   - Simplified trajectory may have different timing characteristics
   - Settling may happen at different point than full trajectory

3. **Trajectory extension issues**:
   - LH trajectory may not be extended enough for pluck
   - Extension logic may be adding wrong amount of buffer
   - Pluck timestamp calculation may be off

## Next Steps After Running

1. **Run the test** to get baseline data
2. **Analyze CSV** to find patterns in failures
3. **Compare timing** between passing and failing tests
4. **Focus on**:
   - Difference between `presser_end_time` and `presser_settled_time`
   - Whether `pluck_delay_from_presser_settled` matches `configured_settling_time`
   - Whether position-only tests behave differently than full trajectory tests

## Files Created

1. `test_fret_pluck_coordination.py` - Main test script (517 lines)
2. `test_fret_pluck_coordination_README.md` - User documentation
3. `COORDINATION_TEST_TOOL_NOTES.md` - This file (developer notes)

## Code Structure

### CoordinationTester Class:
- `__init__()`: Setup output directory and log file
- `analyze_trajectory()`: Extract timing info from 15-motor trajectory
- `run_test()`: Generate trajectory and analyze it
- `save_results()`: Write CSV and print summary

### Main Function:
- Runs 13 tests across 4 scenarios
- Saves results to timestamped CSV
- Prints comprehensive summary

## Integration

The test script:
- Imports `BothHandsParser` and `LeftHandParser` directly
- Uses actual trajectory generation code (not mocked)
- Calls `parse_fret_with_pluck()` just like real usage
- Analyzes the resulting 15-motor trajectories

This means:
- ✓ Tests real behavior, not simulated
- ✓ Will expose actual bugs in coordination logic
- ✓ Results directly applicable to fixing the code
- ✓ Can be re-run after fixes to verify improvement
