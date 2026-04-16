# GuitarBot
## Robotic Musicianship Lab at the Georgia Institute of Technology
### Advisor: Dr. Gil Weinberg
---
Project repo for GuitarBot.

**Contributors:** Amit Rogel, Marcus Parker, Jack Keller, Derrick Joyce, Ryan Baker

---

A six plucker iteration of Guitarbot, featuring a web-based UI with a karplus-strong sequencer that can upload directly to the bot.

## Environment Setup
**Prerequisites:** [Miniconda](https://conda.io/projects/conda/en/latest/user-guide/install/index.html) and the [midification](https://github.com/bakerbass/midification) repo cloned as a sibling directory (directory name remains `midification`).

1. Clone this repository.
2. Clone `midification` into the same parent directory as GuitarBot (i.e. `../midification` on disk).
3. From the GuitarBot directory, run:
   ```
   conda env create -f environment/environment.yml
   conda activate guitarbot_env
   ```
4. Note that if you're running the project from an IDE, you will need to select your new environment as the Python interpreter. See VSCode example below:
![VSCode interpreter selection](environment/screenshots/python_interpreter_selection.png)
![VSCode conda configuration](environment/screenshots/conda_configuration.png)

Run strikers.io in Arduino IDE by uploading to the OpenCR board, turning on the robot, and opening the serial monitor.

You're all set! Start sending messages using the **OSC_Message_Send.py** and **OSC_Message_Receiver.py** scripts to start the GuitarBot UI.

### New Parser
**GuitarBotParser.py** still handles pluck messages for longer form song trajectories.

**BothHandsParser.py** is designed for fine control of single-note events, i.e. for dataset generation and machine learning. 
 - **RightHandParser.py** and **LeftHandParser.py** are mostly just copied from **GuitarBotParser.py**


### To Update Environment Configuration:
1. Navigate to the **GuitarBot/environment** directory.
2. If not already activated, run `conda activate guitarbot_env` to activate the guitarbot environment.
3. Run `conda env export > environment.yml` to export the guitarbot environment to a new environment.yml file. Make sure to replace the existing environment.yml file.

---

### Message Protocol Updates

The new message types are reported in the terminal by running **OSC_Message_Receiver.py**

### Technical Improvements

#### **Trajectory Generation**
- **Consistent**: All parsers use `GuitarBotParser.interp_with_blend` for smooth motion
- **Robust**: Handle None returns from interpolation functions gracefully
- **Calibrated**: Use `tune.py` values for motor directions, positions, and conversions
- **Timed**: Explicit and easier-to-read coordination between left-hand prep and right-hand execution

#### **MIDI Integration** 
- **Unified**: All parsers use `STRING_MIDI_RANGES` for consistent note mapping
- **Flexible**: Support for full MIDI note range (40-68) across available strings
- **Validated**: Input validation for MIDI notes, velocities, and force parameters

#### **System Compatibility**
- **Format**: 18×N trajectory matrix (12 LH + 6 RH motors)
- **Integration**: Compatible with existing `RobotController` and OSC receiver
- **Plotting**: Clearer motor labels ([Function] No. vs. Motor No.)