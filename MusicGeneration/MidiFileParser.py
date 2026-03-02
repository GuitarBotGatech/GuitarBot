
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


                # Preserving original filtering logic
                while msg.note < 39:
                    msg.note = msg.note + 12
                while msg.note > 70:
                    msg.note = msg.note - 12

                pluck_message = [msg.note, duration, 1, 0, round(onset, 3)]

                if round(onset, 3) <= length:
                    pluck_messages.append(pluck_message)



    # Sort messages by timestamp to ensure they are in order
    pluck_messages.sort(key=lambda x: x[4])
    print("\nMessages converted from Midi file to Pluck messages:")
    for msg in pluck_messages:
        print(msg)

    return pluck_messages



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
