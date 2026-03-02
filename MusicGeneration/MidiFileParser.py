import mido
import copy

def midi_to_pluck_messages(midi_file_path: str, length: float, target_bpm: float = None):
    pluck_messages = []
    try:
        mid = mido.MidiFile(midi_file_path)
    except Exception as e:
        print(f"Error opening or parsing MIDI file: {e}")
        return []

    # --- Tempo handling ---
    ticks_per_beat = mid.ticks_per_beat

    # If a target BPM is specified, calculate tempo from it.
    # Otherwise, start with the MIDI default (120 BPM) and read from the file.
    if target_bpm is not None:
        current_tempo = mido.bpm2tempo(target_bpm)
        print(f"Using specified target BPM: {target_bpm}")
    else:
        # Default MIDI tempo is 120 BPM (500,000 microseconds per beat)
        current_tempo = 500000

    absolute_ticks = 0
    open_notes = {}
    merged_track = mido.merge_tracks(mid.tracks)

    for msg in merged_track:
        absolute_ticks += msg.time

        # If no target_bpm is set, listen for tempo changes within the file.
        if target_bpm is None and msg.is_meta and msg.type == 'set_tempo':
            current_tempo = msg.tempo
            print(f"Tempo changed to {mido.tempo2bpm(current_tempo):.2f} BPM at tick {absolute_ticks}")

        # Convert current absolute tick time to seconds using the determined tempo
        absolute_time_seconds = mido.tick2second(absolute_ticks, ticks_per_beat, current_tempo)

        if msg.type == 'note_on' and msg.velocity > 0:
            note_key = (msg.channel, msg.note)
            open_notes[note_key] = {'onset': absolute_time_seconds, 'velocity': msg.velocity}

        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            note_key = (msg.channel, msg.note)
            if note_key in open_notes:
                note_on_info = open_notes.pop(note_key)
                onset = note_on_info['onset']
                velocity = note_on_info['velocity']

                duration_seconds = absolute_time_seconds - onset

                duration = round(duration_seconds - 0.01, 3)
                if duration > .5:
                    duration = round(duration_seconds - 0.01, 3)
                else:
                    duration = 0.49

                # Transpose note to valid range (39-70) for GuitarBot
                note_value = msg.note
                while note_value < 39:
                    note_value += 12
                while note_value > 70:
                    note_value -= 12

                pluck_message = [note_value, duration, 1, 0, round(onset, 3)]

                if round(onset, 3) <= length:
                    pluck_messages.append(pluck_message)



    # Sort messages by timestamp to ensure they are in order
    pluck_messages.sort(key=lambda x: x[4])
    print("\nMessages converted from Midi file to Pluck messages:")
    for msg in pluck_messages:
        print(msg)

    return pluck_messages

def mido_to_pluck_messages(mid, length: float, target_bpm: float = None):
    pluck_messages = []
    ticks_per_beat = mid.ticks_per_beat
    current_tempo = 500000  # Default MIDI tempo (120 BPM)
    absolute_ticks = 0
    open_notes = {}
    merged_track = mido.merge_tracks(mid.tracks)

    if target_bpm is not None:
        current_tempo = mido.bpm2tempo(target_bpm)
        print(f"Using specified target BPM: {target_bpm}")

    for msg in merged_track:
        absolute_ticks += msg.time

        if msg.is_meta and msg.type == 'set_tempo':
            current_tempo = msg.tempo

        absolute_time_seconds = mido.tick2second(absolute_ticks, ticks_per_beat, current_tempo)

        if msg.type == 'note_on' and msg.velocity > 0:
            note_key = (msg.channel, msg.note)
            open_notes[note_key] = {'onset': absolute_time_seconds, 'velocity': msg.velocity}

        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            note_key = (msg.channel, msg.note)
            if note_key in open_notes:
                note_on_info = open_notes.pop(note_key)
                onset = note_on_info['onset']
                velocity = note_on_info['velocity']

                duration_seconds = absolute_time_seconds - onset
                duration = round(duration_seconds - 0.01, 3) if duration_seconds > .5 else 0.49

                # Transpose note to valid range (39-70) for GuitarBot
                note_value = msg.note
                while note_value < 39:
                    note_value += 12
                while note_value > 70:
                    note_value -= 12

                pluck_message = [note_value, duration, 1, 0, round(onset, 3)]
                if round(onset, 3) <= length:
                    pluck_messages.append(pluck_message)

    pluck_messages.sort(key=lambda x: x[4])
    return pluck_messages
def midi_to_mido(midi_file_path: str):
    try:
        mid = mido.MidiFile(midi_file_path)
        print(f"Successfully loaded MIDI file: {midi_file_path}")
        return mid
    except Exception as e:
        print(f"Error opening or parsing MIDI file: {e}")
        return None

def get_pluck_segment(messages, start_time, end_time):
    """
    Extracts a segment of MIDI messages and re-aligns them to start at 1.0.
    """
    # 1. Filter the messages within the time range
    segment = [copy.deepcopy(msg) for msg in messages if start_time <= msg[4] <= end_time]

    # 2. Sort by timestamp just in case the list is out of order
    segment.sort(key=lambda x: x[4])

    # 3. Calculate the offset to move start_time to 1.0
    offset = start_time - 1.0

    # 4. Apply the offset to the timestamp (index 4) of each message
    for msg in segment:
        msg[4] = round(msg[4] - offset, 3)

    return segment

def transpose(mid, semitones):
    """
    Transposes all notes in a mido.MidiFile object by a specified number of semitones.
    
    Args:
        mid: mido.MidiFile object to transpose
        semitones: Number of semitones to transpose (positive = up, negative = down)
    
    Returns:
        Transposed mido.MidiFile object (new copy)
    """
    transposed_mid = copy.deepcopy(mid)
    
    for track in transposed_mid.tracks:
        for msg in track:
            # Only transpose note messages (note_on, note_off)
            # Skip meta messages and other message types
            if hasattr(msg, 'note') and msg.type in ('note_on', 'note_off'):
                # Transpose the note, clamping to valid MIDI range (0-127)
                new_note = msg.note + semitones
                msg.note = max(0, min(127, new_note))
    
    return transposed_mid

def transpose_pluck_messages(pluck_messages, semitones):
    """
    Transposes the note values in pluck messages by a specified number of semitones.
    
    Args:
        pluck_messages: List of pluck messages [note, duration, string, ?, timestamp]
        semitones: Number of semitones to transpose
    
    Returns:
        List of transposed pluck messages
    """
    transposed_messages = []
    for msg in pluck_messages:
        transposed_msg = copy.deepcopy(msg)
        # Note value is at index 0, clamp to MIDI range
        transposed_msg[0] = max(0, min(127, transposed_msg[0] + semitones))
        transposed_messages.append(transposed_msg)
    return transposed_messages