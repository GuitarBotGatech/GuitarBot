# CRITICAL FIX: Pluck Timing with Torque=0

## Problem Identified

The pluck was happening while the presser motor was still applying force (torque > 0). This causes:
- **String damping**: The motor applying force prevents free vibration
- **Poor audio quality**: String can't ring properly
- **Inaccurate force measurements**: Vibration is affected by motor torque

## Root Cause

The original implementation applied torque and immediately plucked:
```
OLD (WRONG):
1. Apply torque (0 → 200)
2. Pluck ← STRING IS STILL UNDER TENSION!
```

## Solution

Added a **REST phase** where the motor releases to 0 (idle) before plucking:
```
NEW (CORRECT):
1. Apply torque (0 → 200)
2. REST - Release to 0 (200 → 0) ← Motor goes idle
3. Settling time (25ms)
4. Pluck ← String is now free to vibrate!
```

## Implementation Details

### LeftHandParser Changes

#### `_generate_simple_trajectory()`
Added 2-phase trajectory for force testing:

**Phase 1: Apply Target Torque**
- Interpolate from current torque to target torque
- Motor applies the test force

**Phase 2: REST - Release to 0**
- Interpolate from target torque to 0
- Motor goes idle (holding position but not applying force)
- String maintains fret contact but is free to vibrate

```python
# Phase 1: Apply target torque
t1 = interp_with_blend(current_torque, target_torque, num_points, ...)

# Phase 2: REST - Release to 0 (motor idle for pluck)
t2 = interp_with_blend(target_torque, 0, num_points, ...)
```

#### `_generate_simple_fret_change()`
Extended to 4 phases (added REST phase):

1. Release to idle (current torque → 0)
2. Slide (slider moves, torque = 0)
3. Apply target torque (0 → target)
4. **REST - Release to 0 (target → 0)** ← NEW!

### BothHandsParser Changes

#### Torque Analysis
Instead of estimating when presser stops, now **analyzes the actual trajectory**:

```python
# Extract presser trajectory
presser_trajectory = lh_trajectory[:, presser_motor_id]

# Find when torque reaches 0 (within tolerance of 5 units)
near_zero = np.abs(valid_traj) < 5.0

# Find the LAST contiguous block of near-zero values
# This is the REST phase
```

#### Pluck Timing
```python
torque_zero_time = timestamp + (torque_zero_idx * TIME_STEP)
pluck_timestamp = torque_zero_time + settling_time
```

## Why This Matters

### Physics of String Vibration

When a motor applies torque to press a string:
- **Torque > 0**: Motor actively pushes, adding stiffness and damping
- **Torque = 0**: Motor is idle, string contacts fret naturally

For accurate force testing:
- Apply force to establish string-fret contact
- Release to 0 so string can vibrate freely
- Pluck while motor is idle

### Audio Quality Impact

**With torque during pluck** (WRONG):
- Muted tone
- Reduced sustain
- Motor noise interferes

**With torque=0 during pluck** (CORRECT):
- Clear tone
- Full sustain
- Clean audio for analysis

## Testing

### Verification Script
`test_force_testing_with_pluck.py` now checks:

```python
def analyze_trajectory_timing(combined_traj, string_id):
    presser_traj = combined_traj[:, presser_motor_id]
    picker_traj = combined_traj[:, picker_motor_id]
    
    # Find when presser reaches 0
    presser_zero_idx = ...
    
    # Find when picker starts moving
    picker_start_idx = ...
    
    # Verify presser is at 0 BEFORE picker starts
    assert presser_traj[picker_start_idx] < 5.0, "Presser must be at 0 when plucking!"
```

### Visual Inspection

When plotting trajectories, you should see:
```
Presser torque:
    /\      Apply force
   /  \     
  /    \___  REST at 0
 /         

Picker position:
            /\  Pluck starts HERE (when presser=0)
           /  \
          /    \
         ------
```

## Migration Guide

### No Code Changes Needed

The fix is automatic - existing code using `force_adjustment_only=True` will now:
1. Apply target torque
2. Automatically add REST phase (torque → 0)
3. Pluck at correct time (when torque=0)

### What You'll Notice

**Better audio quality**:
- Cleaner tone
- Better sustain
- Less motor noise

**More accurate measurements**:
- String vibrates freely
- Force applied but not during vibration
- Consistent results across tests

## Technical Constants

```python
# Phase durations
PRESSER_INTERPOLATION_POINTS = 40  # 200ms per phase

# For same-fret force adjustment:
Total_phases = 2  # Apply + REST
Total_duration = 2 * 40 * 0.005 = 0.4s

# Timing breakdown:
Phase 1 (Apply): 0.0 - 0.2s  (torque increases)
Phase 2 (REST):  0.2 - 0.4s  (torque → 0)
Settling:        0.4 - 0.425s (25ms wait)
Pluck:          0.425s       (torque=0 ✓)
```

## Summary

**BEFORE**: Pluck happened while motor applied force → poor audio, inaccurate tests

**AFTER**: Motor applies force → releases to 0 → pluck → clean audio, accurate tests

**Key Principle**: Always pluck when torque = 0 (motor at rest) for accurate force testing.
