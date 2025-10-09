# Generates Random Notes in C for GuitarBot to play

import numpy as np
import random
# 1. Set string min and max midi values
# 2. Random amount of note changes per string (3 to 6) Random amount of string speeds per string (3 to 6)
# 3. Creates between 6 to 12 messages per string.

# MIDI Ranges in C major
midi_notes_e_range = [40, 41, 43, 45, 47, 48]
midi_notes_d_range = [50, 52, 53, 55, 57]
midi_notes_b_range = [59, 60, 62, 64, 65, 67]

def generateNotes(note_range, n):
    # min_midi: minimum Midi value
    # max_midi: maximum Midi value
    # n: number of notes
    notes  = []

    for x in range(n):
        r_note = random.choice(note_range)
        notes.append(r_note)
    # print(notes)

    return notes

def generateStringSpeeds(n):
    # n: number of durations
    rng = np.random.default_rng()
    durations = rng.integers(low=1, high=5, size=n)

    return durations

def generateMessages(notes, durations, n):
    # pluck_message = [[note (midi value), duration, speed, slide_toggle, timestamp]]
    messages = []
    rng = np.random.default_rng()
    speeds = rng.integers(low=1, high=10, size=n)
    curr_timestamp = 0
    for x in range(n):
        # Convert all NumPy types to standard Python int()
        message = [int(notes[x]), int(durations[x]), int(speeds[x]), 0, int(curr_timestamp)]
        curr_timestamp += durations[x]
        print(message)

        messages.append(message)

    return messages

def generateSong():
    print("Generating song")
    # Generate E Notes

    print("E NOTES")
    rng = np.random.default_rng()
    r_messages_E = rng.integers(low=30, high=35, size=1)
    E_notes = generateNotes(midi_notes_e_range, r_messages_E[0])
    E_durations = generateStringSpeeds(r_messages_E[0])
    E_messages = generateMessages(E_notes, E_durations, r_messages_E[0])
    # Generate D Notes

    print("D NOTES")
    rng = np.random.default_rng()
    r_messages_D = rng.integers(low=30, high=35, size=1)
    D_notes = generateNotes(midi_notes_d_range, r_messages_D[0])
    D_durations = generateStringSpeeds(r_messages_D[0])
    D_messages = generateMessages(D_notes, D_durations, r_messages_D[0])
    # Generate B Notes

    print("B NOTES")
    rng = np.random.default_rng()
    r_messages_B = rng.integers(low=30, high=35, size=1)
    B_notes = generateNotes(midi_notes_b_range, r_messages_B[0])
    B_durations = generateStringSpeeds(r_messages_B[0])
    B_messages = generateMessages(B_notes, B_durations, r_messages_B[0])

    all_messages = E_messages + D_messages + B_messages
    print("Combined Messages:", all_messages)

    return all_messages


#-----------
# Triad based Approach
#-----------


import random

# Voicings in the key of C
c_major_triads = [
    [40, 55, 60],  # Voicing: [E, G, C]
    [43, 52, 60],  # Voicing: [G, E, C]
    [48, 52, 67],  # Voicing: [C, E, G]
    [48, 55, 64]   # Voicing: [C, G, E]
]

d_minor_triads = [
    [41, 57, 62],  # Voicing: [F, A, D]
    [45, 50, 65]   # Voicing: [A, D, F]
]

e_minor_triads = [
    [40, 55, 59],  # Voicing: [E, G, B]
    [43, 52, 59],  # Voicing: [G, E, B]
    [47, 52, 67]   # Voicing: [B, E, G]
]

f_major_triads = [
    [41, 57, 60],  # Voicing: [F, A, C]
    [45, 53, 60],  # Voicing: [A, F, C]
    [48, 53, 65]   # Voicing: [C, F, A]
]

g_major_triads = [
    [43, 50, 59],  # Voicing: [G, D, B]
    [47, 55, 62]   # Voicing: [B, G, D]
]

a_minor_triads = [
    [40, 57, 60],  # Voicing: [E, A, C]
    [45, 52, 60],  # Voicing: [A, E, C]
    [48, 52, 64]   # Voicing: [C, E, E]
]

b_diminished_triads = [
    [41, 50, 59],  # Voicing: [F, D, B]
    [47, 50, 65]   # Voicing: [B, D, F]
]

def generate_scale_progression(iterations):
    """
    Generates a pluck message list that plays through the C Major scale.
    For each chord in the scale, a random triad voicing is chosen.

    Args:
        iterations (int): The number of times to play the full scale progression.

    Returns:
        list: A list of pluck messages formatted for the robot.
    """
    # Create a list of the chords in the key of C, in order.
    # Each element is a list of available voicings for that chord.
    chords_in_key = [
        c_major_triads,
        d_minor_triads,
        e_minor_triads,
        f_major_triads,
        g_major_triads,
        a_minor_triads,
        b_diminished_triads
    ]

    message = []
    curr_ts = 0

    # The main loop for repeating the entire scale progression
    for i in range(iterations):
        # Loop that progresses through the chords of the scale
        for chord_voicings in chords_in_key:
            # Randomly select one triad voicing from the current chord's options
            random_triad = random.choice(chord_voicings)

            # Create the pluck messages for the 3 notes in the chosen triad.
            for note in random_triad:
                # pluck_message = [[note, duration, speed, slide_toggle, timestamp]]
                rand_speed = random.randint(1, 10)
                curr_message = [note, .4, 1, 0, curr_ts]
                message.append(curr_message)

                # Increment the timestamp for the next chord in the progression.
                curr_ts += .5

    print("Scale Progression Message:", message)
    return message

def sequential_Plucks(iterations):
# Triad: Triad Voicing
    message = []
    curr_ts = 0
    triad = c_major_triads
    for x in range(iterations):
        for voice in triad:
            for note in voice:
                curr_message = [note, .1, 1, 0, curr_ts]
                message.append(curr_message)
                curr_ts += .5
    print(message)
    return message


# Add this near the top of your script, with the other triad definitions.

# A library of rhythmic patterns to be applied to the triads.
# Each pattern exists within one measure (4 beats).
# Format: [(start_beat, duration_in_beats), ...]
RHYTHMIC_PATTERNS = {
    # 1. Simple whole note chord, slightly strummed
    "strummed_chord": [
        (0, 4),
        (0.05, 4),  # Stagger the start times for a strum effect
        (0.1, 4)
    ],
    # 2."Alberti Bass" style arpeggio (bottom, top, middle, top)
    "alberti_arpeggio": [
        (0, 0.9),
        (1, 0.9),
        (2, 0.9),
        (3, 0.9)
    ],
    # 3. A simple quarter-note arpeggio going up
    "arpeggio_up": [
        (0, 1),
        (1, 1),
        (2, 1)
    ],
    # 4. syncopated rhythm
    "syncopated_pulse": [
        (0, 0.4),
        (0.75, 0.4),
        (1.5, 0.4),
        (2.5, 0.4),
        (3.25, 0.4)
    ],
    # 5. Power chord rhythm - pulsing quarter notes
    "quarter_note_pulse": [
        (0, 0.8),
        (1, 0.8),
        (2, 0.8),
        (3, 0.8)
    ]
}

# Combination Attempts
def generate_rhythmic_progression(iterations, bpm=120):
    """
    Generates a musical piece by applying rhythmic patterns to a diatonic
    chord progression.

    Args:
        iterations (int): The number of times to play the full scale progression.
        bpm (int): The tempo in beats per minute, to calculate timing.

    Returns:
        list: A list of pluck messages formatted for the robot.
    """
    chords_in_key = [
        c_major_triads, d_minor_triads, e_minor_triads,
        f_major_triads, g_major_triads, a_minor_triads, b_diminished_triads
    ]

    # Get a list of the pattern names to choose from
    pattern_names = list(RHYTHMIC_PATTERNS.keys())

    # Calculate timing constants
    seconds_per_beat = 60.0 / bpm
    measure_duration_in_seconds = 4 * seconds_per_beat

    messages = []
    current_timestamp = 0.0

    print(f"Generating rhythmic progression for {iterations} iteration(s) at {bpm} BPM.")

    for i in range(iterations):
        # Loop through the chord progression (I-ii-iii-IV-V-vi-vii°)
        for chord_voicings in chords_in_key:
            # 1. HARMONY STEP: Choose a voicing for the current chord in the progression.
            random_triad = random.choice(chord_voicings)

            # 2. RHYTHM STEP: Choose a random rhythmic pattern to apply.
            chosen_pattern_name = random.choice(pattern_names)
            rhythmic_pattern = RHYTHMIC_PATTERNS[chosen_pattern_name]

            # Special handling for arpeggios to make them sound right
            notes_to_play = random_triad[:]  # Make a copy
            if chosen_pattern_name == "alberti_arpeggio":
                # Reorder notes to Bottom, Top, Middle, Top for Alberti style
                if len(notes_to_play) == 3:
                    notes_to_play = [notes_to_play[0], notes_to_play[2], notes_to_play[1], notes_to_play[2]]

            # 3. APPLICATION STEP: Create MIDI messages for each event in the pattern.
            for i, (start_beat, duration_in_beats) in enumerate(rhythmic_pattern):
                # Cycle through the notes of the triad for the pattern
                note = notes_to_play[i % len(notes_to_play)]

                # Calculate the absolute start time and duration in seconds
                note_start_time = current_timestamp + (start_beat * seconds_per_beat)
                note_duration = duration_in_beats * seconds_per_beat

                # [[note, duration, speed, slide_toggle, timestamp]]
                # Speed is set to 1, as these are not intended as tremolo notes.
                message = [note, note_duration, 1, 0, note_start_time]
                messages.append(message)

            # Advance the clock by one measure for the next chord
            current_timestamp += measure_duration_in_seconds

    return messages


MELODIC_PATTERNS = {
    "alberti_arpeggio": RHYTHMIC_PATTERNS["alberti_arpeggio"],
    "syncopated_pulse": RHYTHMIC_PATTERNS["syncopated_pulse"],
    "arpeggio_up": RHYTHMIC_PATTERNS["arpeggio_up"]
}


def generate_polyphonic_texture(iterations, bpm=120):
    """
    Generates a polyphonic texture by assigning musical roles (bass, harmony,
    melodic) to the notes of a triad, utilizing sustained tremolos.

    Args:
        iterations (int): Number of times to repeat the full scale progression.
        bpm (int): Tempo in beats per minute.

    Returns:
        list: A list of pluck messages formatted for the robot.
    """
    chords_in_key = [
        c_major_triads, d_minor_triads, e_minor_triads,
        f_major_triads, g_major_triads, a_minor_triads, b_diminished_triads
    ]

    pattern_names = list(MELODIC_PATTERNS.keys())

    seconds_per_beat = 60.0 / bpm
    measure_duration_in_seconds = 4 * seconds_per_beat

    messages = []
    current_timestamp = 0.0

    print(f"Generating polyphonic texture for {iterations} iteration(s) at {bpm} BPM.")

    for i in range(iterations):
        for chord_voicings in chords_in_key:
            # 1. HARMONY: Choose a triad voicing for this measure.
            # We sort it to ensure the lowest note is always the bass.
            random_triad = sorted(random.choice(chord_voicings))

            # --- GENERATE THE THREE MUSICAL LAYERS ---

            # 2. BASS ROLE: A slow, sustained tremolo on the lowest note.
            bass_note = random_triad[0]
            bass_speed = random.randint(1, 4)  # Slow tremolo speed
            # The bass note sustains for the entire measure.
            bass_message = [bass_note, measure_duration_in_seconds, bass_speed, 0, current_timestamp]
            messages.append(bass_message)

            # 3. HARMONY ROLE: A sustained tremolo on the middle note, starting later.
            harmony_note = random_triad[1]
            harmony_speed = random.randint(4, 7)  # Medium tremolo speed
            # Have the harmony come in on beat 2 to create some movement.
            harmony_start_time = current_timestamp + (2 * seconds_per_beat)
            harmony_duration = 2 * seconds_per_beat  # Lasts for the rest of the measure.
            harmony_message = [harmony_note, harmony_duration, harmony_speed, 0, harmony_start_time]
            messages.append(harmony_message)

            # 4. MELODIC ROLE: An active, rhythmic pattern on the highest note.
            melodic_note = random_triad[2]
            chosen_pattern_name = random.choice(pattern_names)
            rhythmic_pattern = MELODIC_PATTERNS[chosen_pattern_name]

            # Apply the chosen pattern to the single melodic note
            for start_beat, duration_in_beats in rhythmic_pattern:
                note_start_time = current_timestamp + (start_beat * seconds_per_beat)
                # Ensure short notes don't accidentally become tremolos. Max duration is 0.49s.
                note_duration = min(0.5, duration_in_beats * seconds_per_beat)
                print(duration_in_beats * seconds_per_beat)

                # These are non-tremolo notes
                rand_speed = random.randint(6, 10)
                melodic_message = [melodic_note, note_duration, rand_speed, 0, note_start_time]
                messages.append(melodic_message)

            # Advance the master clock by one measure for the next chord
            current_timestamp += measure_duration_in_seconds

    return messages
# Example usages
# generateSong() # Random plucks in C Major
# pluck_message = generate_scale_progression(12) # Play the C Major scale x times
# pluck_message = sequential_Plucks(1)