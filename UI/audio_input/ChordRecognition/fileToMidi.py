import librosa
import numpy as np
import mido
import pretty_midi
from mido import Message, MidiFile, MidiTrack

class Note:
    def __init__(self, velocity, midi_note, start, end):
        self.velocity = velocity
        self.midi_note = midi_note
        self.start = start
        self.end = end

class AudioMidiConverter:
    def __init__(self, root='E9', sr=44100, note_min='A0', note_max='E9', frame_size=2048,
                 hop_length=441, outlier_coeff=2):
        self.fmin = librosa.note_to_hz(note_min)
        self.fmax = librosa.note_to_hz(note_max)
        self.hop_length = hop_length
        self.frame_size = frame_size
        self.sr = sr
        self.root = librosa.note_to_midi(root)
        self.m = outlier_coeff
        self.empty_arr = np.array([])

    def convert(self, y, return_onsets=False, velocity=100):
        f0, voiced_flag, voiced_prob = librosa.pyin(y, fmin=self.fmin * 0.9, fmax=self.fmax * 1.1, sr=self.sr,
                                                    frame_length=self.frame_size, hop_length=self.hop_length)
        if len(f0) == 0:
            print("No f0")
            if return_onsets:
                return self.empty_arr, self.empty_arr
            return self.empty_arr

        pitch = librosa.hz_to_midi(f0)
        pitch[np.isnan(pitch)] = 0
        onsets = self.get_onsets(y)
        notes = np.zeros(len(onsets), dtype=int)
        for i in range(len(onsets) - 1):
            notes[i] = np.round(np.nanmedian(pitch[onsets[i]: onsets[i + 1]]))
        notes[-1] = np.round(np.nanmedian(pitch[onsets[-1]:]))

        onsets = onsets[notes > 0] * self.hop_length / self.sr
        notes = notes[notes > 0]

        if len(notes) > 0:
            notes = self.fix_outliers(notes, m=self.m)

        temp = []
        for i in range(len(notes)):
            if i < len(notes) - 1:
                end_time = onsets[i+1]
            else:
                end_time = onsets[i] + .1
            temp.append(Note(velocity, notes[i], start=onsets[i], end=end_time))

        if return_onsets:
            return temp, onsets
        return temp

    def save_midi(self, notes, filename, program_name, tempo):
        midi_data = pretty_midi.PrettyMIDI(initial_tempo=tempo)

        if program_name == 0:
            instrument = pretty_midi.Instrument(program=35)
        elif program_name == 1:
            instrument = pretty_midi.Instrument(program=25)
        elif program_name == 2:
            instrument = pretty_midi.Instrument(program=118)
        # Create notes
        if program_name != 2:
            for note in notes:
                start_time = note.start
                end_time = note.end

                midi_note = pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=note.midi_note,
                    start=start_time,
                    end=end_time
                )
                instrument.notes.append(midi_note)
        else:
            for note in notes:
                start_time = note.start
                end_time = note.end

                midi_note = pretty_midi.Note(
                    velocity=note.velocity,
                    pitch=38,
                    start=start_time,
                    end=end_time
                )
                instrument.notes.append(midi_note)
        midi_data.instruments.append(instrument)

        # Write the MIDI data to a file
        midi_data.write(filename)
        print(f"MIDI file saved as: {filename}")
        
    def get_onsets(self, y, threshold=0.01):
        onset_env = librosa.onset.onset_strength(y=y, sr=self.sr, hop_length=self.hop_length)
        onsets = librosa.onset.onset_detect(onset_envelope=onset_env, sr=self.sr, hop_length=self.hop_length, backtrack=True)
        return np.unique(np.hstack([0, onsets]))

    def fix_outliers(self, notes, m):
        median = np.median(notes)
        mad = np.median(np.abs(notes - median))
        lower_bound = median - m * mad
        upper_bound = median + m * mad
        return notes[(notes >= lower_bound) & (notes <= upper_bound)]

    @staticmethod
    def get_tempo(filename):
        y,sr = librosa.load(filename, duration = 10)

        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo = librosa.feature.tempo(onset_envelope=onset_env, sr=sr)
        return tempo[0]
   