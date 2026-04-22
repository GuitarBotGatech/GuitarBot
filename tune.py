# tune.py
# Description: This file contains tunable parameters for the GuitarBotParser.
# Adjust these variables to fine-tune the robot's performance, physical calibration, and musical expression.

# ----------------------------------------------------------------------------
# 1. Trajectory and Interpolation Parameters
# ----------------------------------------------------------------------------
# These variables control the shape, speed, and timing of motor movements.
# For each trajectory value, multiply it by 5 to get the duration of the movement in milliseconds.
# For example, 10 points = 50ms to do the movement.

TIME_STEP = .005

#Graphing
# Controls graphing the functions used on each motor. False turns off, true turns on.
graph = False

# Blend percentage for trajectory interpolation (0.0 to 1.0).
# A higher value creates a more gradual acceleration and deceleration.
TRAJECTORY_BLEND_PERCENT = 0.2

# Number of interpolation points for presser movements (e.g., pressing/unpressing).
# More points result in a slower movement.
PRESSER_INTERPOLATION_POINTS = 50

# Number of interpolation points for the "unpress after" REST phase.
# This is intentionally much larger than PRESSER_INTERPOLATION_POINTS — the presser
# needs to release slowly so the string has time to ring out and the motor
# doesn't bounce back from the hard stop.
# 60 pts × 5ms = 300ms release time (adjust up if the motor still snaps back).
PRESSER_UNPRESS_AFTER_POINTS = 500

# Number of interpolation points for the main sliding motion of the left hand.
LH_SLIDER_MOTION_POINTS = 120

# Number of interpolation points when the left hand is moving to a single note.
LH_SINGLE_NOTE_MOTION_POINTS = 40

# Number of interpolation points for a single pluck.
PICKER_PLUCK_MOTION_POINTS = 11

# Position value for a fully unpressed left-hand presser motor.
LH_PRESSER_UNPRESSED_POS = -650

# Position value for a fully pressed left-hand presser motor.
LH_PRESSER_PRESSED_POS = 500

# Torque value for a press, used for sliding to ensure string contact.
# Given in terms of LH_PRESSER_SLIDE_PRESS_POS/1000 % of torque rating. For example, LH_PRESSER_SLIDE_PRESS_POS = 650 then the motor is outputting 65% of the motors' rated torque value.
# Values over 1000 overwork the motor, which can result in overheating and stalling.
LH_PRESSER_SLIDE_PRESS_POS = 200

# ----------------------------------------------------------------------------
# 2. Timing and Synchronization Parameters
# ----------------------------------------------------------------------------
# These variables control delays between actions and thresholds for interpreting MIDI data.

# Time (in seconds) the left hand needs to prepare before a picker plucks a new note.
# This is the maximum prep window; semitone-scaled moves can use less.
LH_PREP_TIME_BEFORE_PICK = 0.450

# Minimum prep time for very small/zero-distance fret transitions.
LH_PREP_TIME_MIN = 0.090

# Semitone delta that maps to full LH_PREP_TIME_BEFORE_PICK.
# Delta values above this are clamped to the max prep window.
LH_PREP_MAX_SEMITONE_DELTA = 18

# Upper fret boundary used by prep-time safety near chassis/end-stop travel.
# Guitar fret numbering: open = 0, then 1..N.
LH_MIN_FRET = 0
LH_MAX_FRET = 9

# Extra prep headroom for transitions that start/end near either chassis edge.
LH_EDGE_PREP_TIME_BONUS = 0.250
LH_EDGE_PREP_TIME_CAP = 0.750

# Backward-compatible aliases for older scripts/tests.
LH_HIGH_FRET_CAUTION_START_FRET = LH_MAX_FRET
LH_HIGH_FRET_EXTRA_PREP_TIME = LH_EDGE_PREP_TIME_BONUS
LH_HIGH_FRET_MAX_PREP_TIME = LH_EDGE_PREP_TIME_CAP
LH_MAX_FRET_PREP_TIME_BONUS = LH_EDGE_PREP_TIME_BONUS
LH_MAX_FRET_PREP_TIME_CAP = LH_EDGE_PREP_TIME_CAP

# The time window (in seconds) to check for overlaps between left-hand and picker movements.
# If a pick event occurs within this window of a left-hand event, it may be adjusted or ignored.
# Given in terms of seconds.
MOVEMENT_OVERLAP_WINDOW = 0.300

# The duration (in seconds) below which a MIDI note is considered a single "pluck"
# rather than the start of a "tremolo".
# Given in terms of seconds.
TREMOLO_DURATION_THRESHOLD = 0.500

# The default duration (in seconds) assigned to very short notes to ensure they are played.
SHORT_NOTE_DEFAULT_DURATION = 0.025

# Timestamp rounding factor. Formats the floats to be in terms of 5 ms.
TIMESTAMP_ROUNDING_FACTOR = 200.0

# Step size (in seconds) used when generating interpolated MIDI messages.
# When a timed MIDI event has its interpolation flag set, intermediate messages
# are inserted at this fixed interval regardless of how far apart the endpoints are.
# 0.005 s = 5 ms → 200 interpolated steps per second.
MIDI_INTERPOLATION_INTERVAL_S = 0.005

# ----------------------------------------------------------------------------
# 3. Left Hand (LH) Physical Parameters
# ----------------------------------------------------------------------------
# Calibration values that map musical concepts (frets) to physical robot positions (mm, encoder ticks).

# The physical distance (in mm) from the nut to the center of each fret.
# Controls where the slider lands for fret 1, fret 2, fret 3, etc. respectively.
# Index 0 corresponds to Fret 1.
SLIDER_MM_PER_FRET = [19, 52, 85, 112, 139, 164, 187, 211, 234]


# Position values for the three states of the presser motors:
# 1: Open/Unpressed, 2: Pressed, 3: Muted (partially pressed).
PRESSER_ENCODER_POSITIONS = [-650, 500, 100]

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
    0: {'down_pluck_mm': -6.0, 'up_pluck_mm': -9.5, 'resolution': 1024}, # E
    1: {'down_pluck_mm': 6.4, 'up_pluck_mm': 10.5, 'resolution': 2048}, # A
    2: {'down_pluck_mm': -6.3, 'up_pluck_mm': -9.5, 'resolution': 2048}, # D
    3: {'down_pluck_mm': 6.0, 'up_pluck_mm': 9.5, 'resolution': 1024}, # G
    4: {'down_pluck_mm': 5.7, 'up_pluck_mm': 8.8, 'resolution': 2048}, # B
    5: {'down_pluck_mm': -2.7, 'up_pluck_mm': -6.3, 'resolution': 2048} # E
}

# ----------------------------------------------------------------------------
# 5. Note and Chord Definitions
# ----------------------------------------------------------------------------
# Defines the mapping of MIDI notes to guitar strings.

# MIDI note ranges for each string/picker.
# Format: (lowest_note, highest_note, slider_direction_multiplier)
# The multiplier is used to account for mirrored slider mechanisms relative to the picker.
STRING_MIDI_RANGES = [
    (40, 49, SLIDER_MOTOR_DIRECTION[0]),  # String 1,E
    (45, 54, SLIDER_MOTOR_DIRECTION[1]),  # String 2,A
    (50, 59, SLIDER_MOTOR_DIRECTION[2]),  # String 3,D
    (55, 64, SLIDER_MOTOR_DIRECTION[3]), # String 4.B
    (59, 68, SLIDER_MOTOR_DIRECTION[4]),  # String 5,G
    (64, 73, SLIDER_MOTOR_DIRECTION[5])   # String 6,E
]

# Initial Point
# Controls the starting point for the very first message sent to GuitarBot when the receiver file starts.
initial_point = [ #Bookmark
                 # Sliders
                 0, 0, 0, 0, 0, 0,
                 # Pressers
                 -650, -650, -650, -650, -650, -650, # Position, not Torque value
                 # Pluckers
                 int(PICKER_MOTOR_INFO[0]["up_pluck_mm"]*1024/9.4),
                 int(PICKER_MOTOR_INFO[1]["up_pluck_mm"]*2048/9.4),
                 int(PICKER_MOTOR_INFO[2]["up_pluck_mm"]*2048/9.4),
                 int(PICKER_MOTOR_INFO[3]["up_pluck_mm"]*1024/9.4),
                 int(PICKER_MOTOR_INFO[4]["up_pluck_mm"]*2048/9.4),
                 int(PICKER_MOTOR_INFO[5]["up_pluck_mm"]*2048/9.4)

                 ]


# Filepath for the chord voicing library.
CHORD_LIBRARY_FILE = "Alternate_Chords.csv"

# ----------------------------------------------------------------------------
# 6. Arduino/OpenCR firmware interop aliases (for header generation)
# ----------------------------------------------------------------------------
# These names mirror what the firmware expects, so the generator can export
# them directly without additional mapping. Keep values in sync above.
# Note that these values are not used in the python code, but are here so that 
# tune.h can be generated programmatically.

# Picker start state (positions). Should match picker motor dictionary 'up_pluck_mm'
START_STATE_PICK = [PICKER_MOTOR_INFO[0]['up_pluck_mm'], PICKER_MOTOR_INFO[1]['up_pluck_mm'], 
                    PICKER_MOTOR_INFO[2]['up_pluck_mm'], PICKER_MOTOR_INFO[3]['up_pluck_mm'], 
                    PICKER_MOTOR_INFO[4]['up_pluck_mm'], PICKER_MOTOR_INFO[5]['up_pluck_mm']]

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
    from pathlib import Path
    from gen_tune_h import generate_tune_h

    out = generate_tune_h(
        tune_py_path=Path(__file__),
        header_out_path=Path(__file__).parent / "MicroController/LeftArm/Strikers/src/tune.h",
    )
    print(f"Regenerated header at: {out}")

