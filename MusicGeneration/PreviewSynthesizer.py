import mido
from midi2audio import FluidSynth
import RandomNoteGenerator


def create_midi_preview(pluck_message, output_filename='preview.mid', ticks_per_beat=480, tempo=120):
    """
    Creates a MIDI file from a pluck_message, correctly handling polyphony.
    This version creates a timeline of all note_on and note_off events, sorts them,
    and then builds the MIDI track, which is a robust way to handle overlapping notes.
    """
    mid = mido.MidiFile(ticks_per_beat=ticks_per_beat)
    track = mido.MidiTrack()
    mid.tracks.append(track)

    # MIDI tempo is set in microseconds per beat
    microseconds_per_beat = mido.bpm2tempo(tempo)

    events = []
    velocity = 90  # Standard velocity for the notes

    for message in pluck_message:
        # message format: [note, duration, speed, slide_toggle, timestamp]
        note, duration, speed, _, timestamp = message

        # Handle tremolo notes (duration > 0.5 and speed > 1)
        if duration > 0.5 and speed > 1:
            num_tremolo_notes = int(speed)
            if num_tremolo_notes > 0:
                tremolo_note_duration = duration / num_tremolo_notes
                current_time = timestamp
                # Create a series of short on/off events for the tremolo
                for _ in range(num_tremolo_notes):
                    events.append({'type': 'note_on', 'time': current_time, 'note': note, 'velocity': velocity})
                    events.append(
                        {'type': 'note_off', 'time': current_time + tremolo_note_duration, 'note': note, 'velocity': 0})
                    current_time += tremolo_note_duration
        else:
            # A standard note is a single on event and a single off event
            events.append({'type': 'note_on', 'time': timestamp, 'note': note, 'velocity': velocity})
            events.append({'type': 'note_off', 'time': timestamp + duration, 'note': note, 'velocity': 0})

    # Sort the complete list of events by their onset
    events.sort(key=lambda e: e['time'])

    last_tick = 0
    for event in events:
        absolute_time_seconds = event['time']
        absolute_time_ticks = int(mido.second2tick(absolute_time_seconds, ticks_per_beat, microseconds_per_beat))

        # Calculate the delta time in ticks from the last event
        delta_ticks = absolute_time_ticks - last_tick

        track.append(mido.Message(
            event['type'],
            note=event['note'],
            velocity=event['velocity'],
            time=delta_ticks
        ))

        # Update the time of the last event
        last_tick = absolute_time_ticks

    mid.save(output_filename)
    print(f"MIDI file '{output_filename}' created successfully.")


def convert_midi_to_wav(midi_file, soundfont, output_filename='preview.wav'):
    """
    Converts a MIDI file to a WAV file using FluidSynth.

    Args:
        midi_file (str): The path to the MIDI file.
        soundfont (str): The path to the SoundFont file (.sf2).
        output_filename (str): The name of the output WAV file.
    """
    fs = FluidSynth(soundfont)
    fs.midi_to_audio(midi_file, output_filename)
    print(f"Audio file '{output_filename}' created successfully.")


if __name__ == '__main__':
    # --- Instructions ---
    # 1. Make sure 'RandomNoteGenerator.py' is in the same directory.
    # 2. You will need a SoundFont file (.sf2).
    # 3. Place the SoundFont file in the same directory
    soundfont_path = 'FluidR3_GM.sf2'
    # Generate musical data
    # You can choose which function to call from your script that makes GuitarBot Messages
    # pluck_message = RandomNoteGenerator.generateSong()
    # pluck_message = RandomNoteGenerator.generate_scale_progression(2)
    # pluck_message = RandomNoteGenerator.sequential_Plucks(1)
    # pluck_message = RandomNoteGenerator.generate_rhythmic_progression(3, 120)
    pluck_message = RandomNoteGenerator.generate_polyphonic_texture(2)

    midi_filename = 'guitar_preview.mid'
    wav_filename = 'guitar_preview.wav'

    # Create the MIDI file
    create_midi_preview(pluck_message, output_filename=midi_filename)

    # Convert the MIDI to a WAV file
    try:
        convert_midi_to_wav(midi_filename, soundfont_path, output_filename=wav_filename)
    except Exception as e:
        print(f"Error converting MIDI to WAV: {e}")
        print("Please ensure you have FluidSynth installed and a valid SoundFont file.")