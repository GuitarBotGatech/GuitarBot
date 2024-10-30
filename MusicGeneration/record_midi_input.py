import mido
import time
from mido import MidiFile, MidiTrack, Message
import sys

def get_input(gbot_preview_mode=False):
    input_port = None
    while input_port is None:
        try:
            input_port = mido.open_input()
        except Exception as e:
            time.sleep(0.1)

    output_file = MidiFile()
    track = MidiTrack()
    output_file.tracks.append(track)

    last_message_time = None
    recording = False
    start_time = None

    print("Monitoring MIDI input. Play a note to start recording. The script will stop after saving the file.")

    try:
        while True:
            for msg in input_port.iter_pending():
                current_time = time.time()

                if not recording:
                    recording = True
                    start_time = current_time
                    last_message_time = current_time
                    print("Recording started...")

                if last_message_time is not None:
                    delta_time = current_time - last_message_time
                else:
                    delta_time = 0
                last_message_time = current_time

                # Convert time to MIDI ticks (assuming 480 ticks per quarter note at 120 BPM)
                ticks_per_second = 480 * 120 / 60
                midi_time = int(delta_time * ticks_per_second)

                new_msg = msg.copy(time=midi_time)

                # NOTE: This is put in 
                if gbot_preview_mode and (new_msg.note != 85 and new_msg.note != 92):
                    track.append(new_msg)

            if recording and last_message_time is not None and time.time() - last_message_time > 5:
                # feel free to change file name definition here
                # timestamp = time.strftime("%Y%m%d-%H%M%S")
                # filename = f"recorded_midi_{timestamp}.mid"
                # output_file.save(filename)
                # print(f"Recording saved as {filename}")
                print("Midi File Generated.")
                break

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
    finally:
        input_port.close()
        return output_file

# sys.exit(0)

midifile = get_input(gbot_preview_mode=True)
# midifile.tracks[0].insert(0, mido.Message('program_change', program=25, channel=0))
midifile.save('inputs/latest_recording.mid')