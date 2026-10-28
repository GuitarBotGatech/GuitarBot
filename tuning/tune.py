# tune.py
# Description: This file contains tunable parameters for the GuitarBotParser.
# Adjust these variables to fine-tune the robot's performance, physical calibration, and musical expression.

from pathlib import Path

# ----------------------------------------------------------------------------
# 1. Trajectory and Interpolation Parameters
# ----------------------------------------------------------------------------
# These variables control the shape, speed, and timing of motor movements.
# For each trajectory value, multiply it by 5 to get the duration of the movement in milliseconds.
# For example, 10 points = 50ms to do the movement.

TIME_STEP = .005

# Debug visuals for GuitarBotParser (control.debug.plan_viz). False = off.
graph = False

# Blend percentage for trajectory interpolation (0.0 to 1.0).
# A higher value creates a more gradual acceleration and deceleration.
TRAJECTORY_BLEND_PERCENT = 0.2

# Number of interpolation points for a single pluck.
PICKER_PLUCK_MOTION_POINTS = 11

# Position value for a fully unpressed left-hand presser motor.
LH_PRESSER_UNPRESSED_POS = -650

# Position value for a fully pressed left-hand presser motor.
LH_PRESSER_PRESSED_POS = 500

# Partial press that damps a string without fretting it. The slider can stay wherever it is.
LH_PRESSER_MUTE_POS = 100

# Torque value for a press, used for sliding to ensure string contact.
# Given in terms of LH_PRESSER_SLIDE_PRESS_POS/1000 % of torque rating. For example, LH_PRESSER_SLIDE_PRESS_POS = 650 then the motor is outputting 65% of the motors' rated torque value.
# Values over 1000 overwork the motor, which can result in overheating and stalling.
LH_PRESSER_SLIDE_PRESS_POS = 200

# ----------------------------------------------------------------------------
# 2. Timing and Synchronization Parameters
# ----------------------------------------------------------------------------
# These variables control delays between actions and thresholds for interpreting MIDI data.

# Time (in seconds) the left hand needs to prepare before a picker plucks a new note.
LH_PREP_TIME_BEFORE_PICK = 0.450

# After a string is idle this long, its next move takes LH_SLOW_SLIDE_TIME_MAX seconds.
LH_SLOW_SLIDE_IDLE_WINDOW = 20.0
LH_SLOW_SLIDE_TIME_MAX = 5.0

# The duration (in seconds) below which a MIDI note is considered a single "pluck"
# rather than the start of a "tremolo".
# Given in terms of seconds.
TREMOLO_DURATION_THRESHOLD = 0.500

# The default duration (in seconds) assigned to very short notes to ensure they are played.
SHORT_NOTE_DEFAULT_DURATION = 0.025

# ----------------------------------------------------------------------------
# 3. Left Hand (LH) Physical Parameters
# ----------------------------------------------------------------------------
# Calibration values that map musical concepts (frets) to physical robot positions (mm, encoder ticks).

# The physical distance (in mm) from the nut to the center of each fret.
# Controls where the slider lands for fret 1, fret 2, fret 3, etc. respectively.
# Index 0 corresponds to Fret 1.
SLIDER_MM_PER_FRET = [19, 52, 85, 112, 139, 164, 187, 211, 234]

# Conversion factor from millimeters to encoder ticks for the slider motors.
# Generally only needs to change if the motor is not Maxxon
# If you know the distance in mm and the encoder resolution of the motor, you can convert it directly to encoder ticks for that motor.
# Formula: (mm * ENCODER_RESOLUTION) / MM_PER_REVOLUTION
MM_TO_ENCODER_CONVERSION_FACTOR = 9.4

# An offset (in encoder ticks) applied to all slider motor calculations.
# Offsets the positions relative to the nut
SLIDER_ENCODER_OFFSET = -2000

# Multiplier to reverse the direction of specific slider motors if they are mounted mirrored.
# A value of -1 reverses the motor, 1 keeps it the same.
# Index corresponds to motor ID (String 1 = 0, String 2 = 1, etc.).
SLIDER_MOTOR_DIRECTION = [-1, 1, 1, -1, -1, 1]

# ----------------------------------------------------------------------------
# 4. Right Hand (RH) / Picker Physical Parameters
# ----------------------------------------------------------------------------
# Calibration values for the picking mechanism.

# Picker motor information: [down_pluck_mm, up_pluck_mm, encoder_resolution].
# Calibrate the mm positions for the desired picking depth and tone.
# Key is the motor ID.

PICKER_MOTOR_INFO = {
    0: {'down_pluck_mm': -2.75, 'up_pluck_mm': -6, 'resolution': 1024}, # E
    1: {'down_pluck_mm': 0.6, 'up_pluck_mm': 4.2, 'resolution': 2048}, # A
    2: {'down_pluck_mm': -0.8, 'up_pluck_mm': -3.6, 'resolution': 2048}, # D
    3: {'down_pluck_mm': 0.9, 'up_pluck_mm': 4.35, 'resolution': 1024}, # G
    4: {'down_pluck_mm': -2, 'up_pluck_mm':-5, 'resolution': 2048}, # B
    5: {'down_pluck_mm': 1.1, 'up_pluck_mm': 4, 'resolution': 2048} # E
}

# Logical string index → RH trajectory / CAN column index.
# After reassembly, B (4) and high-e (5) keep correct mounts but swapped node IDs
# (logical B drives node 18 / column 5; logical e drives node 17 / column 4).
# Calibration stays keyed by logical string; only the output column is remapped.
# Map is an involution: physical→logical uses the same table.
PICKER_LOGICAL_TO_PHYSICAL = (0, 1, 2, 3, 5, 4)


def picker_physical_index(logical_idx):
    """RH trajectory column for a logical string/picker index."""
    return PICKER_LOGICAL_TO_PHYSICAL[int(logical_idx)]

# ----------------------------------------------------------------------------
# 5. Note and Chord Definitions
# ----------------------------------------------------------------------------
# Defines the mapping of MIDI notes to guitar strings.

# MIDI note ranges for each string/picker.
# Format: (lowest_note, highest_note). Slider direction is SLIDER_MOTOR_DIRECTION.
STRING_MIDI_RANGES = [
    (40, 49),  # E
    (45, 54),  # A
    (50, 59),  # D
    (55, 64),  # G
    (59, 68),  # B
    (64, 73),  # e
]

def _picker_start_encoder(logical_idx):
    info = PICKER_MOTOR_INFO[logical_idx]
    return int(info["up_pluck_mm"] * info["resolution"] / MM_TO_ENCODER_CONVERSION_FACTOR)


# Initial Point
# Controls the starting point for the very first message sent to GuitarBot when the receiver file starts.
# Plucker columns follow physical CAN order, so use the logical string that maps to each column.
initial_point = [ #Bookmark
                 # Sliders
                 0, 0, 0, 0, 0, 0,
                 # Pressers
                 *([LH_PRESSER_UNPRESSED_POS] * 6),
                 # Pluckers (physical columns; B↔e remapped)
                 _picker_start_encoder(PICKER_LOGICAL_TO_PHYSICAL[0]),
                 _picker_start_encoder(PICKER_LOGICAL_TO_PHYSICAL[1]),
                 _picker_start_encoder(PICKER_LOGICAL_TO_PHYSICAL[2]),
                 _picker_start_encoder(PICKER_LOGICAL_TO_PHYSICAL[3]),
                 _picker_start_encoder(PICKER_LOGICAL_TO_PHYSICAL[4]),
                 _picker_start_encoder(PICKER_LOGICAL_TO_PHYSICAL[5]),
                 ]


# Filepath for the chord voicing library (under control/).
_REPO_ROOT = Path(__file__).resolve().parent.parent
CHORD_LIBRARY_FILE = str(_REPO_ROOT / "control" / "Alternate_Chords.csv")

# ----------------------------------------------------------------------------
# 6. Arduino/OpenCR firmware interop aliases (for header generation)
# ----------------------------------------------------------------------------
# These names mirror what the firmware expects, so the generator can export
# them directly without additional mapping. Keep values in sync above.
# Note that these values are not used in the python code, but are here so that 
# tune.h can be generated programmatically.

# Picker start state (positions). Physical CAN order; B↔e remapped like initial_point.
START_STATE_PICK = [
    PICKER_MOTOR_INFO[PICKER_LOGICAL_TO_PHYSICAL[i]]['up_pluck_mm']
    for i in range(6)
]

# Motor IDs for pickers (E, D, B). Adjust if wiring changes.
MOTOR_ID_PICK = [13, 14, 15, 16, 17, 18]

# Homing offsets
HOME_OFFSET_SLIDE = 50000
HOME_OFFSET_PRESS = -25
HOME_OFFSET_PICK = 0

# EPOS4 controller gains (p, i[, d, v, a])
CURRENT_CONTROL_SLIDE = [1575853, 4837093]
CURRENT_CONTROL_PICK = [1042729, 2976309]
CURRENT_CONTROL_PRESS = [3456649, 10257]

POS_CONTROL_SLIDE = [6933308, 139254287, 104848, 10219, 637]
POS_CONTROL_PICK = [18462573, 157853228, 170004, 9945, 585]
POS_CONTROL_PRESS = [200000, 905480, 2643, 507, 36]

# Unit conversion
MM_TO_ENC_CONVERSION_FACTOR = MM_TO_ENCODER_CONVERSION_FACTOR


if __name__ == "__main__":
    # When run directly, regenerate the firmware header from this module.
    from tuning.gen_tune_h import generate_tune_h

    out = generate_tune_h(
        tune_py_path=Path(__file__),
        header_out_path=_REPO_ROOT / "MicroController/LeftArm/Strikers/src/tune.h",
    )
    print(f"Regenerated header at: {out}")

