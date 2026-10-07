# GuitarBot
## Robotic Musicianship Lab at the Georgia Institute of Technology
### Advisor: Dr. Gil Weinberg
---
Project repo for GuitarBot.

**Contributors:** Amit Rogel, Marcus Parker, Jack Keller, Derrick Joyce, Ryan Baker

---

A six plucker iteration of Guitarbot, featuring a web-based UI with a karplus-strong sequencer that can upload directly to the bot.

## Environment Setup
**Prerequisites:** [Miniconda](https://conda.io/projects/conda/en/latest/user-guide/install/index.html).

1. Clone this repository.
2. From the GuitarBot directory, run:
   ```
   conda env create -f Docs/environment/environment.yml
   conda activate guitarbot_env
   ```
3. Note that if you're running the project from an IDE, you will need to select your new environment as the Python interpreter. See VSCode example below:
![VSCode interpreter selection](Docs/environment/screenshots/python_interpreter_selection.png)
![VSCode conda configuration](Docs/environment/screenshots/conda_configuration.png)

Run strikers.io in Arduino IDE by uploading to the OpenCR board, turning on the robot, and opening the serial monitor.

You're all set! Start the GuitarBot UI and play/reset server with `python launch.py` (add `--dry-run` to plan without sending UDP to the robot). Legacy OSC scripts **OSC_Message_Send.py** and **OSC_Message_Receiver.py** remain available for RL and other non-UI control.

### Parsers
**GuitarBotParser.py** handles pluck and chord messages for longer form song trajectories.

**BothHandsParser.py** is designed for fine control of single-note events, i.e. for dataset generation and machine learning. 


### To Update Environment Configuration:
1. Activate the env: `conda activate guitarbot_env`
2. From `Docs/environment/`, run `conda env export > environment.yml` (or edit that file by hand) and replace the existing file carefully — prefer keeping the lean hand-written dependency list.

---

### Message Protocol Updates

The OSC message types are reported in the terminal by running **OSC_Message_Receiver.py**

### Technical Improvements

#### **Trajectory Generation**
- **Robust**: Handle None returns from interpolation functions gracefully
- **Tested**: Run tests on trajectories to validate parsing numerically before running on the robot
- **Calibration**: Use `tune.py` values for motor directions, positions, and conversions
#### **MIDI Integration** 
- **Flexible**: Support for full MIDI note range (40-74) across 6 strings
- **Audio Effects** Automate MIDI CC directly from web interface

#### **System Compatibility**
- **Format**: 18×N trajectory matrix (12 LH + 6 RH motors)
- **Play API**: `POST /play` with arrangement JSON and `POST /reset` on the Flask server (`python launch.py`)