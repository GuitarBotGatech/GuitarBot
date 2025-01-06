from mido import MidiFile, MidiTrack, Message, MetaMessage
# from ChordRecognition.audioInput import inputAudio
# from ChordRecognition.ISMIR_LVCR.chord_recognition import chord_recognition
from MusicGeneration.expand_accompaniment import expand_accompaniment

import librosa

chordtype_intervals = {
    'min/b7' : [0, 3, 7, 10],
    'min/2'  : [0, 3, 7, 14],
    'maj/b7' : [0, 4, 7, 10],
    'maj/2'  : [0, 4, 7, 14],
    'sus4(b7)' : [0, 5, 7, 10],
    "sus2" : [0, 2, 7],
    "sus4" : [0, 5, 7],
    "13" : [0, 4, 7, 10, 14, 17],
    "11" : [0, 4, 7, 10, 14],
    "min9" : [0, 3, 7, 10, 14],
    "9" : [0, 4, 7, 10, 14],
    "maj9" : [0, 4, 7, 11, 14],
    "dim7" : [0, 3, 6, 9],
    "hdim7" : [0, 3, 6, 10],
    "min7" : [0, 3, 7, 10],
    "7" : [0, 4, 7, 10],
    "maj7" : [0, 4, 7, 11],
    "min/5" : [0, 3, 7, 14],
    "min/b3" : [0, 3, 7],
    "maj/5" : [0, 4, 7, 14],
    "maj/3" : [0, 4, 7],
    "dim" : [0, 3, 6],
    "aug" : [0, 4, 8],
    "min" : [0, 3, 7],
    "maj" : [0, 4, 7]
}


note_midinum = {
    "A"   : 57, 
    "A#"  : 58,
    "Bb"  : 58,
    "B"   : 59,
    "C"   : 60,
    "C#"  : 61,
    "Db"  : 61,
    "D"   : 62,
    "D#"  : 63,
    "Eb"  : 63,
    "E"   : 64,
    "F"   : 65,
    "F#"  : 66,
    "Gb"  : 66,
    "G"   : 67,
    "G#"  : 68,
    "Ab"  : 68
}

def _chordname_to_midi(midifile, chord_rows, bpm=120):    
    for chord_row in chord_rows:
        chordname = chord_row[0]
        root_note = note_midinum[chordname[0:chordname.index(':')]]
        chord_notes = chordtype_intervals[chordname[chordname.index(':')+1:]]

        for i in range(len(chord_notes)):
            chord_notes[i] += root_note

        for note in chord_notes:
            midifile.tracks[0].append(Message('note_on', note=note, velocity=64, time=0))

        quarter_note_duration = midifile.ticks_per_beat*4 # whole note actually
        for note in chord_notes:
            midifile.tracks[0].append(Message('note_off', note=note, velocity=64, time=quarter_note_duration))
            quarter_note_duration = 0 # only first note in chord needs note_off time != 0
    
    midifile.tracks[0].insert(0, MetaMessage('set_tempo', tempo=500_000)) # equiv to 120 bpm

    return midifile

def main():
    # ad = inputAudio(waveName='output.mp3')
    # ad.start()
    # ad.outputWav()

    # chord_progression = chord_recognition('output.mp3')

    midifile = MidiFile()
    midifile.tracks.append(MidiTrack())
    midi = _chordname_to_midi(midifile, [['C:maj'], ['C:aug'], ['F:7']])
    expanded_midi = expand_accompaniment(midi)

    expanded_midi.save('temp.mid')
    print('Saved to file temp.mid')

main()