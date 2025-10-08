# GuitarBot
## Robotic Musicianship Lab at the Georgia Institute of Technology
### Advisor: Dr. Gil Weinberg
---
Project repo for GuitarBot.

**Contributors:** Amit Rogel, Marcus Parker, Jack Keller, Derrick Joyce, Ryan Baker

---

## Ryan's Branch - New Parsing Architecture

**Goal: Enable the GuitarBot platform to have highly specified control messages to be used for audio-based calibration and learning**

This branch introduces a major refactoring of the parsing system to support dataset generation workflows for optimizing fretting force and dynamic range control.

### Major Changes

#### **New Modular Parser Architecture**
- **Replaced** monolithic parsing approach with modular left/right hand separation
- **Refactored** `DynamicsParser.py` → `RightHandParser.py` (enhanced with velocity mapping)
- **Cleaned** `LeftHandParser.py` to focus purely on fretting (removed right-hand concerns)  
- **Created** `Parser.py` as orchestrator for coordinated left/right hand trajectories

#### **Enhanced Message Protocols**
- **`/Fret` Messages**: MIDI note-based fretting with optional presser force control (0.0-1.0)
- **`/Dyn` Messages**: Right-hand dynamics testing with state-based or velocity-based plucking
- **Coordinated Messages**: Combined fretting + plucking for complete note production

#### **Dataset Generation Focus**
- **Fretting Optimization**: `/Fret` messages for calibrating optimal presser positions per fret
- **Dynamics Range**: `/Dyn` messages for testing plucking motor dynamic response
- **Clean Separation**: Robotics code separated from learning/dataset functionality

## Environment Setup (deprecated)
1. Clone this repository.
2. Install Python 3.9.18 [here](https://www.python.org/downloads/) (make sure to scroll down to the specific release version).
3. Install Conda [here](https://conda.io/projects/conda/en/latest/user-guide/install/index.html). While **Miniconda** is recommended, either of the Miniconda or Anaconda distributions are fine. Conda is a virtual environment and package manager for Python.
4. Once Conda is installed, open terminal in the cloned GuitarBot directory.
5. Run `conda env create -f environment/environment.yml` to create a new Conda environment for the project. It will automatically be named *guitarbot_env*.
6. To verify that the environment was installed correctly, run `conda env list`. You should see *guitarbot_env* as one of the options listed.
7. Run `conda activate guitarbot_env` to activate the new environment.
8. Note that if you're running the project from an IDE, you will need to select your new environment as the Python interpreter. See VSCode example below:
![VSCode interpreter selection](environment/screenshots/python_interpreter_selection.png)
![VSCode conda configuration](environment/screenshots/conda_configuration.png)

You're all set! Run the **UI/main.py** script to start the GuitarBot UI.

### New Parser Testing
To test the new parsing architecture:
```bash
# Test individual parsers
python LeftHandParser.py    # Test fretting trajectories
python RightHandParser.py   # Test plucking trajectories  
python Parser.py            # Test coordinated trajectories
```

### To Update Environment Configuration:
1. Navigate to the **GuitarBot/environment** directory.
2. If not already activated, run `conda activate guitarbot_env` to activate the guitarbot environment.
3. Run `conda env export > environment.yml` to export the guitarbot environment to a new environment.yml file. Make sure to replace the existing environment.yml file.

---

## New Parsing System Architecture

### File Structure
```
GuitarBot/
├── LeftHandParser.py      # Fretting trajectories (motors 0-11)
├── RightHandParser.py     # Plucking trajectories (motors 12-14) 
├── Parser.py              # Orchestrates both hands
├── GuitarBotParser.py     # Original parser (still used for interp_with_blend)
└── tune.py                # Calibration values and motor configurations
```

### Changes & Implementation Details

#### **LeftHandParser.py Changes**
- **Removed**: Right-hand plucking functionality (moved to RightHandParser)
- **Enhanced**: MIDI note → string/fret mapping using `STRING_MIDI_RANGES`
- **Maintained**: 3-phase fretting motion (unpress → slide → press)
- **Added**: Presser force control with calibrated position mapping
- **Simplified**: `/Fret` message parsing focuses purely on fretting

#### **RightHandParser.py (formerly DynamicsParser.py)**
- **Renamed**: DynamicsParser → RightHandParser for clarity
- **Enhanced**: Added MIDI velocity → pluck depth mapping
- **Maintained**: State-based plucking (alternates up/down positions) 
- **Added**: Velocity-based plucking option for dynamic control
- **Improved**: Better integration with `tune.py` PICKER_MOTOR_INFO
- **Consistent**: Uses same `interp_with_blend` as GuitarBotParser

#### **Parser.py Implementation**
- **Coordinates**: Left and right hand timing with configurable prep time
- **Supports**: Complete note production (fret + pluck), fret-only, dynamics-only
- **Handles**: Chord sequences with multiple note coordination
- **Maintains**: 15×N trajectory matrix format for system compatibility
- **Provides**: Combined status reporting and position reset functionality

### Message Protocol Updates

#### **Enhanced /Fret Messages**
```python
# Old format (string/fret based)
parse_fret_message(string_id=0, fret_num=5, presser_force=0.8)

# New format (MIDI note based)  
parse_fret_message(midi_note_number=45, presser_force=0.8)
```

#### **Enhanced /Dyn Messages**
```python
# State-based plucking (like original)
parse_dynamics_message([42, 55, 65], use_velocity_mapping=False)

# Velocity-based plucking (new)
parse_pluck_message(midi_note=45, velocity=127, use_velocity_mapping=True)
```

#### **New Coordinated Messages**
```python
# Complete note production
parse_note_message(midi_note=45, presser_force=0.8, pluck_velocity=100)
```

### Technical Improvements

#### **Trajectory Generation**
- **Consistent**: All parsers use `GuitarBotParser.interp_with_blend` for smooth motion
- **Robust**: Handle None returns from interpolation functions gracefully
- **Calibrated**: Use `tune.py` values for motor directions, positions, and conversions
- **Timed**: Proper coordination between left-hand prep and right-hand execution

#### **MIDI Integration** 
- **Unified**: All parsers use `STRING_MIDI_RANGES` for consistent note mapping
- **Flexible**: Support for full MIDI note range (40-68) across available strings
- **Validated**: Input validation for MIDI notes, velocities, and force parameters

#### **System Compatibility**
- **Format**: Maintains 15×N trajectory matrix (12 LH + 3 RH motors)
- **Integration**: Compatible with existing `RobotController` and OSC receiver
- **Plotting**: Enhanced visualization with separate left/right hand motor grouping
- **Status**: Comprehensive status reporting for debugging and calibration