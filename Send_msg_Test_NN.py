import numpy as np
import time
from pythonosc.udp_client import SimpleUDPClient
UDP_IP = "127.0.0.1"
UDP_PORT = 12000
from MusicGeneration import RandomNoteGenerator
import mido


def midi_to_pluck_messages(midi_file_path: str, length: float, target_bpm: float = None):
    pluck_messages = []
    try:
        mid = mido.MidiFile("Midi/" + midi_file_path)
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

                pluck_message = [msg.note, duration, 1, 0, round(onset, 3)]

                # Preserving original filtering logic
                if round(onset, 3) <= length and 39 < msg.note < 70:
                    pluck_messages.append(pluck_message)

    # Sort messages by timestamp to ensure they are in order
    pluck_messages.sort(key=lambda x: x[4])
    print("\nMessages converted from Midi file to Pluck messages:")
    for msg in pluck_messages:
        print(msg)

    return pluck_messages

# FORMAT
# chords_message = [[Chord, timestamp]]
# strum_message = [["DOWN"/"UP"], timestamp]
# pluck_message = [[note (midi value), duration, speed, slide_toggle, timestamp]]
# NOTES
# Duration cannot overlap with the onset of new notes.

#chords_message = [["A", 0.0], ["D", 4.0], ["E", 5.0], ["A", 6.0], ["On", 8.0]] # Marcus Demo 3/6/2025
# strum_message = [ ["DOWN", 1.0], ["UP", 2.0], ["DOWN", 4.0], ["UP", 5.0], ["DOWN", 6.0]] # Marcus Demo 3/6/2025
#pluck_message = [[45, .1, 10, 1], [47, .5, 10, 2], [48, 3, 4, 3], ] # Marcus Demo 3/6/2025

# pluck_message = [[45, 1, 10, 1],[51, 1, 4, 1.5], [45, 1, 5, 3], [51, 1, 8, 3.5], [45, 1, 5, 5.0], [51, 1.5, 8, 5.5],
#                 [45, 1, 10, 7],[51, 1, 4, 7.5], [45, 1, 5, 9], [51, 1, 8, 9.5], [45, 1, 5, 11], [51, 1.5, 8, 11.5],
#                 [45, 1, 10, 13],[51, 1, 4, 13.5], [45, 1, 5, 15], [51, 1, 8, 15.5], [45, 1, 5, 17], [51, 1.5, 8, 17.5]]

# pluck_message = [[40, 5, 10, 1], [51, 5, 10, 2], [56, 5, 10, 3]]

# pluck_message = [[56, 1, 2, 5]]
# Final Countdown
# chords_message = [["On", 3.0]]
# chords_message = [["F#m", 1.0], ["D", 2.0], ["Bm", 4.0], ["E", 6.0], ["Fdim7", 7.0],["F#m", 8.0], ["D", 10.0], ["Bm", 12.0], ["On", 14.0]]
# strum_message =  [["UP", 0.0], ["UP", 2.0], ["DOWN", 4.0], ["UP", 6.0], ["DOWN", 7.0], ["UP", 8.0], ["DOWN", 10.0], ["UP", 12.0]]
# pluck_message =  [[59, 1, 10, 0]]

# Testing Sliding
# chords_message = [["On", 12]]
# strum_message =  [["UP", 0]]
# # pluck_message = [[55, 1, 10, 0]]
# pluck_message = [[59, 4, 10, 1], [65, 4, 10, 3.5], [63, 4, 10, 6], [67, 4, 10, 8.5], [63, 4, 10, 11]]

# Testing Sliding Toggle. [midi_note, duration, speed, slide_toggle, timestamp]. Slide = 1, no slide = 0
# chords_message = [["On", 12]]
# strum_message =  [["UP", 0]]
# # SLIDES:
# pluck_message = [[59, 1, 7, 1, 1], [60, 1, 7, 1, 2], [61, 1, 7, 1, 3], [62, 1, 7, 1, 4], [63, 1, 7, 1, 5], [64, 1, 7, 1, 6], [65, 1, 7, 1, 7], [66, 7, 7, 1, 8], [67, 1, 7, 1, 9], [50, 1, 7, 1, 1], [51, 1, 7, 1, 2], [52, 1, 7, 1, 3], [53, 1, 7, 1, 4], [54, 1, 7, 1, 5], [55, 1, 7, 1, 6], [56, 1, 7, 1, 7], [57, 7, 7, 1, 8], [58, 1, 7, 1, 9]]
# pluck_message = [[50, 1, 7, 1, 1], [51, 1, 7, 1, 2], [52, 1, 7, 1, 3], [53, 1, 7, 1, 4], [54, 1, 7, 1, 5], [55, 1, 7, 1, 6], [56, 1, 7, 1, 7], [57, 7, 7, 1, 8], [58, 1, 7, 1, 9]]

# REGULAR NOTE CHANGES
# pluck_message = [[59, 4, 10, 1, 1], [65, 4, 10, 1, 3.5], [63, 4, 10, 1, 6], [67, 4, 10, 1, 8.5], [63, 4, 10, 1, 11]]

# chords_message = [["On", 50]]
# strum_message =  [["UP", 0]]
# pluck_message = [[40, 0.1, 10, 0, 1], [40, 0.1, 10, 0, 5], [40, 0.1, 10, 0, 10], [40, 0.1, 10, 0, 15], [40, 0.1, 10, 0, 20], [40, 0.1, 10, 0, 25], [40, 0.1, 10, 0, 30], [40, 0.1, 10, 0, 35], [40, 0.1, 10, 0, 40], [40, 0.1, 10, 0, 45]]

#
# chords_message_2 = [["On", 2]]
# pluck_message_2 = [[65, .5, 10, 3]]
# strum_message_2 =  [["UP", 2.3], ["DOWN", 2]]
#Two plucker Derrick Demo
# pluck_message = [[60, 1, 1, 1], [60, 1, 2, 2], [60, 1, 3, 3], [60, 1, 4, 4], [60, 1, 5, 5], [60, 1, 6, 6], [60, 1, 7, 7], [60, 1, 8, 8], [60, 1, 9, 9], [60, 1, 10, 10]]
# pluck_message = [[50, 10, 7, 1]]
# pluck_message = [[54, 2, 7, 1], [62, 2, 7, 1], [52, 0.3, 7, 2], [60, 0.3, 7, 2], [53, 2, 7, 2.5], [61, 2, 7, 2.5]]
# pluck_message = [[53, 0.5, 7, 1], [64, 0.5, 7, 1], [53, 0.3, 7, 1.8], [64, 0.3, 7, 2.05], [51, 0.5, 7, 2.5], [62, 0.5, 7, 2.5], [52, 0.5, 7, 2.9], [63, 0.5, 7, 2.9]]
# pluck_message = [[53, 0.3, 7, 1]]
# Ryan Demo, two phrase

# chords_message = [["On", 25]]
# chords_message_2 = [["On", 32]]
# strum_message =  [["UP", 0.0]]
# strum_message_2 =  [["UP", 0.0]]
# pluck_message =[
#         [50, 1, 5, 0],
#         [55, 0.5, 2, .5],
#         [62, 1.0, 4, 1.0],
#         [67, 0.5, 6, 2.0],
#         [59, 0.5, 5, 2.5],
#         [55, 0.5, 4, 3.0],
#         [50, 0.5, 2, 3.5],
#         [60, 0.5, 4, 4.0],
#         [67, 1.5, 6, 4.5],
#         [60, 0.5, 6, 6.0],
#         [55, 0.5, 4, 6.5],
#         [60, 0.5, 5, 7.0],
#         [55, 1.0, 4, 7.5],
#         [59, 1.5, 4, 8.5],
#         [50, 1.0, 2, 10.0],
#         [57, 0.5, 3, 11.0],
#         [50, 2.0, 2, 11.5],
#         [62, 1.5, 4, 13.5],
#         [50, 0.5, 2, 15.0],
#         [55, 0.5, 2, 15.5],
#         [60, 0.5, 4, 16.0],
#         [57, 2.5, 4, 16.5],
#         [60, 0.5, 5, 19.0],
#         [64, 0.5, 6, 19.5],
#         [62, 1.0, 6, 20.0],
#         [57, 0.5, 5, 21.0],
#         [62, 0.5, 6, 21.5],
#         [50, 0.5, 3, 22.0],
#         [57, 1.0, 3, 22.5],
#         [62, 0.5, 5, 23.5],
#         [55, 1.0, 4, 24.0],
#         [59, 0.5, 4, 25.0],
#         [55, 0.5, 3, 25.5],
#         [52, 0.5, 2, 26.0],
#         [55, 0.5, 2, 26.5],
#         [52, 1.0, 2, 27.0],
#         [66, 1.0, 5, 28.0],
#         [62, 0.5, 6, 29.0],
#         [66, 0.5, 7, 29.5],
#         [64, 1.0, 7, 30.0],
#         [52, 0.5, 4, 31.0]]
#
#         # Second Message
# pluck_message_2 = [[50, 0.5, 1, 0],
#         [59, 0.5, 3, 0.5],
#         [62, 1.0, 5, 1.0],
#         [55, 0.5, 4, 2.0],
#         [67, 0.5, 6, 2.5],
#         [55, 0.5, 4, 3.0],
#         [59, 0.5, 4, 3.5],
#         [60, 0.5, 5, 4.0],
#         [67, 1.5, 7, 4.5],
#         [60, 1.5, 6, 6.0],
#         [64, 1.0, 7, 7.5],
#         [67, 1.5, 8, 8.5],
#         [50, 1.0, 4, 10.0],
#         [57, 0.5, 4, 11.0],
#         [50, 0.5, 2, 11.5],
#         [62, 0.5, 4, 12.0],
#         [50, 1.0, 2, 12.5],
#         [55, 1.0, 2, 13.5],
#         [62, 0.5, 4, 14.5],
#         [55, 1.0, 3, 15.0],
#         [57, 1.5, 3, 16.0],
#         [52, 0.5, 2, 17.5],
#         [64, 0.5, 5, 18.0],
#         [60, 0.5, 5, 18.5],
#         [57, 0.5, 4, 19.0],
#         [52, 0.5, 3, 19.5],
#         [57, 1.0, 3, 20.0],
#         [66, 0.5, 6, 21.0],
#         [62, 0.5, 6, 21.5],
#         [57, 0.5, 5, 22.0],
#         [62, 1.5, 6, 22.5],
#         [55, 1.0, 4, 24.0],
#         [54, 0.5, 3, 25.0],
#         [55, 0.5, 3, 25.5],
#         [59, 1.0, 4, 26.0],
#         [52, 0.5, 3, 27.0],
#         [59, 0.5, 4, 27.5],
#         [57, 0.5, 4, 28.0],
#         [50, 0.5, 2, 28.5],
#         [57, 0.5, 3, 29.0],
#         [50, 0.5, 2, 29.5],
#         [60, 1.0, 4, 30.0],
#         [64, 0.5, 6, 31.0]]

# , [51, .1, 10, 2], [61, .1, 10, 3]
# Derrick Demo for 2/27/2025 -- Randomly generated three picker tremolos with amplitude scaling
def create_tremolo_message():
    #1. Generate 5 random speeds
    speeds = np.arange(1, 11)
    rand_speeds = speeds[np.random.choice(len(speeds), 5)]
    print(rand_speeds)

    #2. Generate 5 random MIDI values (for the 3 current strings)
    midi_notes = np.array([45, 51])
    rand_notes = midi_notes[np.random.choice(len(midi_notes), 5, replace=True)]
    print(rand_notes)

    #3. Generate 5 random durations
    durations = np.arange(1, 11)
    rand_durations = durations[np.random.choice(len(durations), 5)]
    print(rand_durations)

    # 3. Generate 5 random timestamps
    #timestamps = np.arange(1, 6)
    #rand_times = timestamps[np.random.choice(len(timestamps), 5)]
    #print(rand_times)

    np_messages = []
    for i in range(len(rand_speeds)):
        message = [rand_notes[i], rand_durations[i], rand_speeds[i], i+1]
        np_messages.append(message)

    pluck_messages = np.vstack(np_messages)
    return pluck_messages.tolist()

# MARCUS DEMOS POSTER DAY
# 1. Pluck Speeds
# chords_message = [["On", 8]]
# strum_message =  [["UP", 0]]
# # E
# pluck_message = [[42, 6, 10, 0, 1], [46, 2, 10, 0, 4]]

# D
# pluck_message = [[50, 2, 1, 0, 1], [52, 2, 10, 0, 4]]

# B
# pluck_message = [[59, 2, 1, 0, 1], [61, 2, 10, 0, 4]]

# 2. Glissando Multiple Strings
# chords_message = [["On", 10]]
# # # strum_message =  [["UP", 0]]
# pluck_message = [
#                [59, 1, 8, 0, 1], [61, 1, 3, 0, 3], [63, 1, 1, 0, 5], [65, 1, 9, 0, 7],
#                [50, 3, 1, 0, 2], [52, 3, 1, 0, 4], [54, 3, 1, 0, 6], [56, 2, 1, 0, 8],
#                [40, 1, 10, 0, 3], [42, 1, 5, 0, 5], [44, 1, 3, 0, 7], [46, 1, 7, 0, 9]
#                 ]
#
# chords_message_2 = [["On", 10]]
# # # strum_message =  [["UP", 0]]
# pluck_message_2 = [
#                [65, 1, 7, 0, 3], [63, 1, 3, 0, 5], [61, 1, 1, 0, 7], [59, 1, 7, 0, 9],
#                [56, 3, 1, 0, 2], [54, 3, 1, 0, 4], [52, 3, 1, 0, 6], [50, 2, 1, 0, 8],
#                [46, 1, 9, 0, 1], [44, 1, 4, 0, 3], [42, 1, 2, 0, 5], [40, 1, 1, 0, 7]
#                 ]

# pluck_message = [
# #               [59, .1, 7, 0, 1], [61, .1, 7, 0, 2], [63, .1, 7, 0, 3], [65, .1, 7, 0, 4],
# #                [50, .1, 7, 0, 1],[50, .1, 7, 0, 1.5], [52, .1, .1, 0, 2], [54, .1, 7, 0, 3], [56, .1, 7, 0, 4], [56, .1, 7, 0, 4.5],
# #             [40, .1, 7, 0, 1], [42, .1, 7, 0, 2], [44, .1, 7, 0, 3], [46, .1, 7, 0, 4]
#                 ]

# # 3. Short Song
# , ["Dsus2", 5],["Cmaj7", 9],  ["Am", 13], ["On", 17]
# chords_message = [["On", 17]]
# strum_message =  [["UP", 0]]
# pluck_message = [
#                  [50, .5, 10, 0, 1.5], [50, .1, 1, 0, 2.5], [50, .1, 1, 0, 3],
#                  [50, .5, 10, 0, 3.5], [50, .1, 1, 0, 4.5], [50, .1, 1, 0, 5],
#                  [54, .5, 10, 0, 5.5], [54, .1, 1, 0, 6.5], [54, .1, 1, 0, 7],
#                  [54, .5, 10, 0, 7.5], [54, .1, 1, 0, 8.5], [54, .1, 1, 0, 9],
#                  # [50, .5, 10, 0, 9.5], [50, .1, 1, 0, 10.5], [50, .1, 1, 0, 11],
#                  # [52, .5, 10, 0, 11.5], [52, .1, 1, 0, 12.5], [52, .1, 1, 0, 13],
#                  [54, .5, 10, 0, 13.5], [54, .1, 1, 0, 14.5], [54, .1, 1, 0, 15],
#                  # [54, .5, 10, 0, 15.5], [54, .1, 1, 0, 16.5], [54, .1, 1, 0, 17],
#                  # # String seperator
#                  [62, .5, 10, 0, 1.5], [62, .6, 5, 0, 2], [62, 3, 5, 0, 3],
#                  # [66, 1, 10, 1, 5.2], [66, .6, 2, 1, 6.5], [66, .6, 2, 1, 7.5],
#                  [62, .5, 1, 0, 9.5], [62, .6, 1, 0, 10.5], [62, 1, 10, 0, 11.5],
#                  [66, 1, 10, 1, 13], [66, .6, 2, 1, 14], [66, .6, 2, 1, 15],
#                  # String seperator
#                  [43, .5, 10, 0, 1.5], [47, .6, 5, 0, 2], [43, 3, 5, 0, 3],
#                  [47, 1, 10, 1, 5.2], [42, .6, 2, 1, 6.5], [47, .6, 2, 1, 7.5],
#                  [43, .5, 1, 0, 9.5], [45, .6, 1, 0, 10.5], [43, 1, 10, 0, 11.5],
#                  [47, 1, 10, 1, 13], [42, .6, 2, 1, 14], [47, .6, 2, 1, 15]
#
#                  ]


# chords_message_2 = [["On", 11]]
# strum_message_2 = [["UP", 0.0]]
# pluck_message_2 = [[64, 1, 10, 0, 0], [55, 1, 10, 0, 0],
#                    # Phrase Smoothing
#                    [64, 2, 10, 0, .5], [67, 2, 5, 1, 2], [66, 1.5, 5, 0, 3],
#                    [64, 1, 5, 0, 5], [62, 1, 5, 0, 7], [62, 1, 5, 0, 8], [62, .6, 10, 0, 10],
#                    # String Seperator
#                    [55, 2, 10, 0, .5], [52, 2, 5, 1, 2], [54, 2, 2, 0, 4],
#                    [55, .5, 10, 1, 6], [50, 2, 3, 1, 7], [50, 1.5, 5, 0, 9],
#                    # String seperator
#                    [45, 2, 10, 0, .5], [48, 2, 5, 1, 2], [47, 1.5, 5, 0, 3],
#                    [45, 1, 5, 0, 5], [43, 1, 5, 0, 7], [43, 1, 5, 0, 8], [43, .6, 10, 0, 10],
#                     ]

# pluck_message = RandomNoteGenerator.generateSong()
# pluck_message = RandomNoteGenerator.generate_scale_progression(12)
# pluck_message = RandomNoteGenerator.sequential_Plucks(4)
# pluck_message = RandomNoteGenerator.generate_polyrhythms()
pluck_message = RandomNoteGenerator.generate_e_major_blues_progression()
# pluck_message = midi_to_pluck_messages("Test12.mid", 20)

E_notes = []
B_notes = []
D_notes = []
for message in pluck_message:
    if message[0] > 39 and message[0] < 50:
        E_notes.append(message)
    elif message[0] > 49 and message[0] < 60:
        D_notes.append(message)
    elif message[0] > 58 and message[0] < 69:
        B_notes.append(message)

print("E Notes: ", E_notes)
print("D Notes: ", D_notes)
print("B Notes: ", B_notes)

# Song Space, Spring 2026

# Pattern 1:

# pluck_message = [
#                [40, .3, 3, 0, 1], [40, .3, 3, 0, 2],
#                [50, .3, 3, 0, 1], [50, .3, 3, 0, 2],
#                [59, .3, 3, 0, 1], [59, .3, 3, 0, 2],
#                 ]
#
pluck_message = [
    # =================================================================
    # LOOP 1
    # =================================================================
    [45, 0.4, 3, 0, 1.0], [45, 0.5, 2, 0, 1.4], [45, 0.4, 3, 0, 2.4],
    [45, 0.4, 3, 0, 4.0], [45, 0.5, 1, 0, 4.4], [45, 0.4, 3, 0, 5.4],
    [45, 0.4, 3, 0, 7.0], [45, 0.5, 6, 0, 7.4], [45, 0.4, 3, 0, 8.4],
    [45, 0.4, 3, 0, 10.0], [45, 0.5, 3, 0, 10.4], [45, 0.4, 3, 0, 11.4],
    [45, 0.4, 3, 0, 13.0], [45, 0.5, 8, 0, 13.4], [45, 0.4, 3, 0, 14.4], [45, 1, 8, 0, 15.0],
    [45, 0.4, 3, 0, 16.0], [45, 0.5, 3, 0, 16.4], [45, 0.4, 3, 0, 17.4], [45, 0.5, 3, 0, 17.8], [45, 0.6, 6, 0, 18.3],
    [52, 0.4, 3, 0, 1.0], [52, 0.4, 3, 0, 4.0], [52, 0.4, 3, 0, 7.0], [52, 0.4, 3, 0, 10.0], [52, 0.4, 3, 0, 13.0], [52, 0.4, 3, 0, 16.0],
    [59, 0.4, 3, 0, 1.0], [59, 0.4, 3, 0, 4.0], [59, 0.4, 3, 0, 7.0], [59, 0.4, 3, 0, 10.0], [59, 0.4, 3, 0, 13.0], [59, 0.4, 3, 0, 16.0],

    # =================================================================
    # LOOP 2: Intro
    # =================================================================

    [45, 0.4, 3, 0, 19.0], [45, 0.5, 2, 0, 19.4], [45, 0.4, 3, 0, 20.4],
    [45, 0.4, 3, 0, 22.0], [45, 0.5, 1, 0, 22.4], [45, 0.4, 3, 0, 23.4],
    [45, 0.4, 3, 0, 25.0], [45, 0.5, 6, 0, 25.4], [45, 0.4, 3, 0, 26.4],
    [45, 0.4, 3, 0, 28.0], [45, 0.5, 3, 0, 28.4], [45, 0.4, 3, 0, 29.4],
    [45, 0.4, 3, 0, 31.0], [45, 0.5, 8, 0, 31.4], [45, 0.4, 3, 0, 32.4], [45, 1, 8, 0, 33.0],
    [45, 0.4, 3, 0, 34.0], [45, 0.5, 3, 0, 34.4], [45, 0.4, 3, 0, 35.4], [45, 0.5, 3, 0, 35.8], [45, 0.6, 6, 0, 36.3],
    [52, 0.4, 3, 0, 19.0], [52, 1.0, 3, 0, 21.0], [52, 0.4, 3, 0, 22.0], [52, 1.0, 6, 0, 24.0], [52, 0.4, 3, 0, 25.0], [52, 1.0, 3, 0, 27.0], [52, 0.4, 3, 0, 28.0], [52, 1.0, 7, 0, 30.0], [52, 0.4, 3, 0, 31.0], [52, 1.0, 3, 0, 33.0], [52, 0.4, 3, 0, 34.0], [52, 1.0, 9, 0, 36.0],
    [59, 1.0, 3, 0, 19.0], [59, 2.0, 4, 0, 22.0], [59, 1.0, 3, 0, 25.0], [59, 2.0, 6, 0, 28.0], [59, 1.0, 8, 0, 31.0], [59, 1.0, 5, 0, 33.0], [59, 2.0, 3, 0, 34.0], [59, 1.0, 10, 0, 33.0],

    # =================================================================
    # CHORUS LOOP 1
    # =================================================================

    # --- SECTION 1: Tension (37.0 - 43.0) ---
    [47, 4.0, 3, 0, 37.0], [47, 1.0, 3, 0, 41.0], [47, 1.0, 3, 0, 43.0],
    [57, 3.0, 3, 0, 38.0], [57, 1.0, 3, 0, 42.0],
    [64, 2.0, 3, 0, 39.0], [64, 1.0, 3, 0, 42.0],

    # --- MOTIF VARIATION 1: The Tease (44.0 - 45.0) ---
    # Rhythm: Straight triplets (44.0, 44.5, 45.0)
    [47, 0.4, 3, 0, 44.0], [57, 0.4, 3, 0, 44.0], [64, 0.4, 3, 0, 44.0],
    [47, 0.4, 3, 0, 44.5], [57, 0.4, 3, 0, 44.5], [64, 0.4, 3, 0, 44.5],
    [47, 0.4, 3, 0, 45.0], [57, 0.4, 3, 0, 45.0], [64, 0.4, 3, 0, 45.0],

    # --- SECTION 2: G Major Polyrhythm (46.0 - 50.0) ---
    [43, 0.4, 3, 0, 46.0], [43, 0.4, 3, 0, 47.0], [43, 0.4, 3, 0, 48.0], [43, 0.4, 3, 0, 49.0], [43, 0.4, 3, 0, 50.0],
    [50, 0.4, 5, 0, 46.0], [50, 0.4, 5, 0, 46.75], [50, 0.4, 5, 0, 47.5], [50, 0.4, 5, 0, 48.25], [50, 0.4, 5, 0, 49.0],
    [50, 0.4, 5, 0, 49.75],
    [59, 0.4, 8, 0, 46.0], [59, 0.6, 3, 0, 46.8], [59, 0.6, 8, 0, 47.6], [59, 0.7, 6, 0, 48.4], [59, 0.5, 8, 0, 49.2],
    [59, 0.6, 9, 0, 50.0],

    # --- MOTIF VARIATION 2: The Shift (50.5 - 51.5) ---
    # Rhythm: Your original (50.5, 51.5, 52.0)
    [43, 0.4, 3, 0, 50.5], [50, 0.4, 3, 0, 50.5], [59, 0.4, 3, 0, 50.5],
    [43, 0.4, 3, 0, 51.5], [50, 0.4, 3, 0, 51.5], [59, 0.4, 3, 0, 51.5],
    [43, 0.4, 3, 0, 52.0], [50, 0.4, 3, 0, 52.0], [59, 0.4, 3, 0, 52.0],

    # --- SECTION 3: F#sus4 Tri-Polyrhythm (53.0 - 57.0) ---
    [42, 0.4, 3, 0, 53.0], [42, 0.4, 3, 0, 54.0], [42, 0.4, 3, 0, 55.0], [42, 0.4, 3, 0, 56.0], [42, 0.4, 3, 0, 57.0],
    [54, 0.5, 3, 0, 53.0], [54, 0.4, 3, 0, 53.8], [54, 0.5, 5, 0, 54.6], [54, 0.4, 3, 0, 55.4], [54, 0.5, 6, 0, 56.2],
    [54, 0.5, 6, 0, 57.0],
    [59, 0.4, 3, 0, 53.0], [59, 0.5, 8, 0, 53.66], [59, 0.4, 3, 0, 54.33], [59, 0.5, 9, 0, 55.0],
    [59, 0.4, 3, 0, 55.66], [59, 0.5, 10, 0, 56.33], [59, 0.5, 10, 0, 57.0],

    # --- MOTIF VARIATION 3: The Crunch (57.5 - 58.5) ---
    # Rhythm: Accelerated (57.5, 57.75, 58.5)
    [42, 0.4, 3, 0, 57.5], [54, 0.4, 3, 0, 57.5], [59, 0.4, 3, 0, 57.5],
    [42, 0.4, 3, 0, 57.75], [54, 0.4, 3, 0, 57.75], [59, 0.4, 3, 0, 57.75],
    [42, 0.4, 3, 0, 58.5], [54, 0.4, 3, 0, 58.5], [59, 0.4, 3, 0, 58.5],

    # --- SECTION 4: THE WALLL (59.5 - 68.0) ---
    [40, 0.6, 3, 0, 59.5], [40, 0.6, 3, 0, 61.5], [40, 0.6, 3, 0, 63.5], [40, 0.6, 3, 0, 65.5], [40, 0.6, 3, 0, 67.5],
    [52, 0.6, 5, 0, 60.0], [52, 0.6, 5, 0, 62.0], [52, 0.6, 5, 0, 64.0], [52, 0.6, 5, 0, 66.0], [52, 0.6, 5, 0, 68.0],
    [64, 0.6, 7, 0, 59.5], [64, 0.6, 8, 0, 61.0], [64, 0.6, 9, 0, 62.5], [64, 0.6, 10, 0, 64.0], [64, 0.6, 10, 0, 65.5],
    [64, 0.6, 10, 0, 67.0],

    # --- SECTION 5: Asus2 Resolution (69.0 - 74.0) ---
    [45, 0.9, 4, 0, 69.0], [45, 0.9, 4, 0, 70.0], [45, 0.9, 4, 0, 71.0], [45, 0.9, 4, 0, 72.0],
    [52, 0.9, 7, 0, 69.0], [52, 0.9, 7, 0, 70.0], [52, 0.9, 7, 0, 71.0], [52, 0.9, 7, 0, 72.0],
    [59, 0.9, 10, 0, 69.0], [59, 0.9, 10, 0, 70.0], [59, 0.9, 10, 0, 71.0], [59, 0.9, 10, 0, 72.0],
    [45, 2.0, 5, 0, 73.0], [52, 2.0, 8, 0, 73.0], [59, 2.0, 10, 0, 73.0],

    # --- FINAL Chorus MOTIF: (75.5 - 77.0) ---
    [45, 0.4, 3, 0, 75.5], [52, 0.4, 3, 0, 75.5], [59, 0.4, 3, 0, 75.5],
    [45, 0.4, 3, 0, 76.5], [52, 0.4, 3, 0, 76.5], [59, 0.4, 3, 0, 76.5],
    [45, 0.4, 3, 0, 77.0], [52, 0.4, 3, 0, 77.0], [59, 0.4, 3, 0, 77.0]

    # =================================================================
    # Verse 1
    # =================================================================

    # =================================================================
    # The Anti-Christ I mean Anti-Chorus
    # =================================================================

    # =================================================================
    # Verse 2
    # =================================================================

    # =================================================================
    # Falling Action / Outro
    # =================================================================


]

import copy


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


intro_segment = get_pluck_segment(pluck_message, 1.0, 18.5)
chorus_segment = get_pluck_segment(pluck_message, 37.0, 80.0)
transition_segment = get_pluck_segment(pluck_message, 30.0, 45.0)

pluck_message = chorus_segment

# Print a few notes of the chorus segment to verify it starts at 1.0
print("First 3 notes of selected segment:")
for msg in chorus_segment[:3]:
    print(msg)


chords_message = [["On",41]]



def send_osc_message(client, address, data):
    print(f"Sending OSC message to {address}: {data}")
    client.send_message(address, data)

def main():
    # Create an OSC client
    client = SimpleUDPClient(UDP_IP, UDP_PORT)

    client = SimpleUDPClient(UDP_IP, UDP_PORT)
    print("sent")
    # send_osc_message(client, "/Chords", chords_message)
    #long_pluck_message_list = RandomNoteGenerator.generate_scale_progression(iterations=20)

    # 2. Call the new batch sender function
    # batch_send_pluck_messages(client, long_pluck_message_list, batch_size=60)
    send_osc_message(client, "/Chords", chords_message)

    # pluck_message = create_tremolo_message()
    send_osc_message(client, "/Pluck", pluck_message)
    time.sleep(1)

    counter = 0

    # while counter < 5:
    #     send_osc_message(client, "/Chords", chords_message)
    #     send_osc_message(client, "/Strum", strum_message)
    #     send_osc_message(client, "/Pluck", pluck_message)
    #     counter += 1
    #     time.sleep(1)


# def batch_send_pluck_messages(client, full_pluck_list, batch_size=60):
#     """
#     Splits the full pluck list into smaller batches and sends them sequentially.
#     """
#     total_messages = len(full_pluck_list)
#     print(f"Total pluck messages to send: {total_messages}")
#
#     for i in range(0, total_messages, batch_size):
#         # Get a batch of messages
#         batch = full_pluck_list[i:i + batch_size]
#
#         # The plucked notes are sent as a list of lists:
#         # e.g., [[note1, dur1, spd1, slide1, ts1], [note2, ...], ...]
#         send_osc_message(client, "/Pluck", batch)
#
#         # Add a short delay to ensure the receiver processes the batch
#         # before the next one arrives. 10ms is usually safe.
#
#     print("Finished sending all pluck batches.")

#----------#
# Saved Stuff #
# Good Random Gen
# [40, 0.49, 0, 0, 1.0]
# [56, 0.5, 2, 0, 1.0]
# [59, 0.5, 8, 0, 1.0]
# [59, 0.49, 0, 0, 1.75]
# [40, 0.49, 0, 0, 2.0]
# [56, 0.5, 1, 0, 2.5]
# [59, 0.49, 0, 0, 2.5]
# [40, 0.5, 5, 0, 3.0]
# [59, 0.49, 0, 0, 3.25]
# [40, 0.49, 0, 0, 4.0]
# [56, 0.49, 0, 0, 4.0]
# [59, 0.5, 7, 0, 4.0]
# [59, 0.49, 0, 0, 4.75]
# [40, 0.49, 0, 0, 5.0]
# [56, 0.49, 0, 0, 5.5]
# [59, 0.49, 0, 0, 5.5]
# [40, 0.49, 0, 0, 6.0]
# [59, 0.49, 0, 0, 6.25]
# [49, 0.5, 3, 0, 7.0]
# [56, 0.49, 0, 0, 7.0]
# [61, 0.5, 7, 0, 7.0]
# [56, 0.49, 0, 0, 7.6]
# [49, 0.49, 0, 0, 7.75]
# [61, 0.49, 0, 0, 8.0]
# [56, 0.5, 1, 0, 8.2]
# [49, 0.49, 0, 0, 8.5]
# [56, 0.49, 0, 0, 8.8]
# [61, 0.5, 6, 0, 9.0]
# [49, 0.49, 0, 0, 9.25]
# [56, 0.49, 0, 0, 9.4]
# [49, 0.49, 0, 0, 10.0]
# [56, 0.5, 1, 0, 10.0]
# [61, 0.5, 8, 0, 10.0]
# [56, 0.49, 0, 0, 10.6]
# [49, 0.49, 0, 0, 10.75]
# [61, 0.5, 9, 0, 11.0]
# [56, 0.5, 1, 0, 11.2]
# [49, 0.5, 2, 0, 11.5]
# [56, 0.5, 3, 0, 11.8]
# [61, 0.49, 0, 0, 12.0]
# [49, 0.49, 0, 0, 12.25]
# [56, 0.5, 3, 0, 12.4]
# [42, 0.49, 0, 0, 13.0]
# [57, 0.49, 0, 0, 13.0]
# [61, 0.49, 0, 0, 13.0]
# [57, 0.49, 0, 0, 13.75]
# [61, 0.49, 0, 0, 14.0]
# [42, 0.49, 0, 0, 14.5]
# [57, 0.49, 0, 0, 14.5]
# [61, 0.49, 0, 0, 15.0]
# [57, 0.49, 0, 0, 15.25]
# [42, 0.49, 0, 0, 16.0]
# [57, 0.49, 0, 0, 16.0]
# [61, 0.49, 0, 0, 16.0]
# [57, 0.49, 0, 0, 16.75]
# [61, 0.49, 0, 0, 17.0]
# [42, 0.5, 5, 0, 17.5]
# [57, 0.49, 0, 0, 17.5]
# [61, 0.5, 7, 0, 18.0]
# [57, 0.49, 0, 0, 18.25]
# [47, 0.5, 1, 0, 19.0]
# [59, 0.49, 0, 0, 19.0]
# [59, 0.5, 7, 0, 19.0]
# [47, 0.49, 0, 0, 19.6]
# [59, 0.5, 5, 0, 20.0]
# [47, 0.49, 0, 0, 20.2]
# [63, 0.49, 0, 0, 20.5]
# [47, 0.5, 2, 0, 20.8]
# [59, 0.5, 4, 0, 21.0]
# [47, 0.5, 5, 0, 21.4]
# [47, 0.49, 0, 0, 22.0]
# [59, 0.49, 0, 0, 22.0]
# [63, 0.49, 0, 0, 22.0]
# [47, 0.49, 0, 0, 22.6]
# [59, 0.49, 0, 0, 23.0]
# [47, 0.49, 0, 0, 23.2]
# [63, 0.5, 9, 0, 23.5]
# [47, 0.5, 1, 0, 23.8]
# [59, 0.49, 0, 0, 24.0]
# [47, 0.5, 3, 0, 24.4]
# [44, 0.49, 0, 0, 25.0]
# [52, 0.5, 3, 0, 25.0]
# [59, 0.49, 0, 0, 25.0]
# [52, 0.49, 0, 0, 25.75]
# [59, 0.49, 0, 0, 25.75]
# [44, 0.49, 0, 0, 26.0]
# [52, 0.49, 0, 0, 26.5]
# [59, 0.49, 0, 0, 26.5]
# [44, 0.5, 2, 0, 27.0]
# [52, 0.49, 0, 0, 27.25]
# [59, 0.49, 0, 0, 27.25]
# [44, 0.49, 0, 0, 28.0]
# [52, 0.49, 0, 0, 28.0]
# [59, 0.49, 0, 0, 28.0]
# [52, 0.49, 0, 0, 28.75]
# [59, 0.49, 0, 0, 28.75]
# [44, 0.5, 5, 0, 29.0]
# [52, 0.49, 0, 0, 29.5]
# [59, 0.49, 0, 0, 29.5]
# [44, 0.49, 0, 0, 30.0]
# [52, 0.49, 0, 0, 30.25]
# [59, 0.49, 0, 0, 30.25]


if __name__ == "__main__":
    main()