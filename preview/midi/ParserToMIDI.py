from mido import Message
from chords.chord_dict import chord_dict, sharp_to_flat

MAJOR_THIRD, PERFECT_FOURTH = 4, 5

# Given a position, seeks to the next strum
def get_next_chord_strum(left_arm, right_arm, bpm, subdiv_per_beat, measure_idx, subdiv_idx, curr_chord_name):
    next_chord_name = curr_chord_name # holds next chord if change made in meantime

    is_downstrum = right_arm[measure_idx][subdiv_idx].lower() == "d"
    subdiv_idx += 1 # points to next strum input
    curr_chord_subdiv_count = 1
    break_outer = False
    
    while measure_idx < len(right_arm):
        while subdiv_idx < len(right_arm[measure_idx]):
            chord_idx = int(subdiv_idx / subdiv_per_beat) # account for the fact that there's only 1 chord input per beat

            # update the next chord if it's a new chord
            if chord_idx < len(left_arm[measure_idx]) and left_arm[measure_idx][chord_idx] != "":
                next_chord_name = left_arm[measure_idx][chord_idx]

            # break if the next strum input is a new strum
            if right_arm[measure_idx][subdiv_idx] != "":
                break_outer = True # set flag to break out of outer loop
                break # next strum/chord will be converted to midi in the next iteration

            curr_chord_subdiv_count += 1
            subdiv_idx += 1

        if (break_outer):
            break
        subdiv_idx = 0
        measure_idx += 1

    MIDI_note_ons, MIDI_note_offs = chord_name_to_MIDI(curr_chord_name, is_downstrum)

    note_duration = (60 / (bpm * subdiv_per_beat)) * curr_chord_subdiv_count # subdiv_duration * subdiv_count
    MIDI_tuple = (MIDI_note_ons, MIDI_note_offs, note_duration)
    curr_chord_name = next_chord_name

    return measure_idx, subdiv_idx, MIDI_tuple, curr_chord_name

# Takes in arms and timing info information, uses them to create MIDI message for whole song
# left_arm: same ideas as one in UIGen.py
# right_arm: created in UIGen.py
def arms_to_MIDI(left_arm, right_arm, bpm, subdiv_per_beat):
    MIDI_song = [] # list of tuples of form (note_ons, note_offs, duration in seconds for chord)

    measure_idx, subdiv_idx = 0, 0
    curr_chord_name = ''

    # If the first beat contains a chord, begin from there
    if (left_arm[0][0] != ''):
        curr_chord_name = left_arm[0][0]
    else:
        # find first chord and set measure_idx, subdiv_idx accordingly
        break_outer = False

        while measure_idx < len(right_arm):
            while subdiv_idx < len(right_arm[measure_idx]):
                chord_idx = int(subdiv_idx / subdiv_per_beat) # account for the fact that there's only 1 chord input per beat
            
                # find first chord/strum input
                if left_arm[measure_idx][chord_idx] != '' and right_arm[measure_idx][subdiv_idx] != '':
                    curr_chord_name = left_arm[measure_idx][chord_idx]
                    break_outer = True
                    break
                else:
                    subdiv_idx += 1

            if break_outer:
                break
            subdiv_idx = 0
            measure_idx += 1
    
    while measure_idx < len(left_arm):
        measure_idx, subdiv_idx, MIDI_tuple, curr_chord_name = get_next_chord_strum(left_arm, right_arm, bpm, subdiv_per_beat, measure_idx, subdiv_idx, curr_chord_name)
        MIDI_song.append(MIDI_tuple)

    return MIDI_song

# Takes in tab and timing information, mapping inputs to MIDI.
###        chord: name of chord
### subdivisions: number of eigth notes chord rings
### is_downstrum: true if downstrum, false if upstrum
def chord_name_to_MIDI(chord_name, is_downstrum):
    MIDI_note_ons, MIDI_note_offs = [], []
    open_note = 40 # E2 in standard tuning

    # map sharps to flats
    if len(chord_name) >= 2 and chord_name[1] == '#':
        chord_name = sharp_to_flat[chord_name[:2]] + ('' if len(chord_name) < 3 else chord_name[2:])

    chord_tab = chord_dict[chord_name] # list of ints in tab notation where 6th string, low bass, comes first

    string_idx = 7
    # TODO: velocity, or loudness, should vary by note to correspond with upstrum/downstrum?
    # should emphasize 1 and 3 beats in 4/4?
    for fret_number_of_note in chord_tab:
        string_idx -= 1
        if fret_number_of_note == 'X' or fret_number_of_note == 'x': 
            continue
        MIDI_note_ons.append(Message("note_on", note=open_note+fret_number_of_note, velocity=80, channel=0).bytes()) # default velocity is 64
        MIDI_note_offs.append(Message("note_off", note=open_note+fret_number_of_note, channel=0).bytes()) # removed duration, doesn't work w/ VST?
        if string_idx != 3:
            open_note += PERFECT_FOURTH
        else:
            open_note += MAJOR_THIRD

    if not is_downstrum: # upstrum
        MIDI_note_ons.reverse() # reverse order of notes to mimic upstrum (high e comes first)
        MIDI_note_offs.reverse()

    return MIDI_note_ons, MIDI_note_offs


# Each interval "constant" holds the appropriate offset
# MINOR_FIRST, FIRST, MINOR_SECOND, MINOR_THIRD, MAJOR_THIRD = 1, 2, 3, 4, 5
# PERFECT_FOURTH, PERFECT_FIFTH, MINOR_SIXTH, MAJOR_SIXTH = 6, 7, 8, 9
# MINOR_SEVENTH, MAJOR_SEVENTH, OCTAVE = 10, 11, 12
# Function that returns an E major shape MIDI voicing of the given chord formatted in a MIDO message.
### chord: chord name, 
### eightNotes: number of eigth notes chord rings
### tempo: BPM it is played in
### NOTE: Assumes chord is not an inversion, logic can be adjusted later to check for / char
# def barre_chord(chord, eightNotes, tempo):
#     rootNoteNum = ord(chord[0]) - 29 # uppercase ASCII -> MIDI bass note
#     offsetIfMinor = -1 if (len(chord) > 1 and chord[1] == 'm') else 0
#     duration = eightNotes * 30/tempo
#     if (rootNoteNum < 40): # ensures no dips below standard tuning E2 limit
#         rootNoteNum += OCTAVE
#     # TODO: adjust velocity to scale with duration?
#     return [Message("note_on", note=rootNoteNum, velocity=80, channel=0),
#             Message("note_on", note=rootNoteNum+PERFECT_FIFTH, velocity=80, channel=0),
#             Message("note_on", note=rootNoteNum+OCTAVE, velocity=80, channel=0),
#             Message("note_on", note=rootNoteNum+OCTAVE+MAJOR_THIRD+offsetIfMinor, velocity=80, channel=0),
#             Message("note_on", note=rootNoteNum+OCTAVE+PERFECT_FIFTH, velocity=80, channel=0),
#             Message("note_on", note=rootNoteNum+2*OCTAVE, velocity=80, channel=0),
#                 Message("note_off", note=rootNoteNum, time=duration, channel=0),
#                 Message("note_off", note=rootNoteNum+PERFECT_FIFTH, time=duration, channel=0),
#                 Message("note_off", note=rootNoteNum+OCTAVE, time=duration, channel=0),
#                 Message("note_off", note=rootNoteNum+OCTAVE+MAJOR_THIRD+offsetIfMinor, time=duration, channel=0),
#                 Message("note_off", note=rootNoteNum+OCTAVE+PERFECT_FIFTH, time=duration, channel=0),
#                 Message("note_off", note=rootNoteNum+2*OCTAVE, time=duration, channel=0)]
