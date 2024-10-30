from mido import MidiFile, MidiTrack, Message

SMALL_MODEL = 'stanford-crfm/music-small-800k'     # faster inference, worse sample quality
MEDIUM_MODEL = 'stanford-crfm/music-medium-800k'   # slower inference, better sample quality
LARGE_MODEL = 'stanford-crfm/music-large-800k'     # slowest inference, best sample quality

PIANO_CODE = 0
GUITAR_CODE = 24

def add_rule_based_initial_chord(midi):
    midi.type = 1 # needed for multiple tracks
    midi.tracks.append(MidiTrack())

    # get track tempo information
    beats_per_bar = 4 # hardcoded, no simple way of detecting this ;(

    # get first melody note
    for msg in midi.tracks[0]:
        if msg.type == 'note_on':
            first_note_val = msg.note
            break
    
    while first_note_val < 52: # 40 is lowest guitar can play
        first_note_val += 12 # raise chord octave

    # major chord notes, first note assumed root 
    chord_notes = [first_note_val - 12, first_note_val - 8, first_note_val - 5]

    for note in chord_notes:
        midi.tracks[1].append(Message("note_on", note=note, velocity=80, time=0, channel=1))
    
    time_off = beats_per_bar*midi.ticks_per_beat
    for note in chord_notes:
        midi.tracks[1].append(Message("note_off", note=note, velocity=80, time=time_off, channel=1))
        time_off = 0

    midi.tracks[0].insert(0, Message('program_change', program=PIANO_CODE, channel=0))
    midi.tracks[1].insert(0, Message('program_change', program=GUITAR_CODE, channel=1))

def add_rule_based_initial_note(midi):
    midi.type = 1 # needed for multiple tracks
    midi.tracks.append(MidiTrack())

    # get root of first chord -- makes assumption first note in sequence will be the root, might be flawed
    for msg in midi.tracks[0]:
        if msg.type == 'note_on':
            first_note_val = msg.note
            break

    # major chord notes, first note assumed root 
    init_note = first_note_val + 12

    for i in range(4):
        midi.tracks[1].append(Message("note_on", note=init_note, velocity=80, time=0, channel=1))
        beats_played = 1 # one beat, quarter note
        time_off = beats_played * midi.ticks_per_beat
        midi.tracks[1].append(Message("note_off", note=init_note, velocity=80, time=time_off, channel=1))

    midi.tracks[0].insert(0, Message('program_change', program=PIANO_CODE, channel=0))
    midi.tracks[1].insert(0, Message('program_change', program=GUITAR_CODE, channel=1))

def get_tempo_from_midi(midi):
    tempo = None
    for msg in midi.tracks[0]:
        if msg.type == 'set_tempo':
            tempo = msg.tempo
            break

    if tempo is None:
        raise ValueError
    
    return tempo