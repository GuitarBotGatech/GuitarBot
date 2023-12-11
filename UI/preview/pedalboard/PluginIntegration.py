from mido import Message
import time
import rtmidi

# NOTE: Designed to integrate with GarageBand. GarageBand must be running with an open software instrument track with the desired plugin loaded.
PORT_NAME = 'GarageBand Virtual Out'
midi_channel = 0

def play_midi_from_plugin(midi_chords: list):
    # open virtual midi port
    midiout = rtmidi.MidiOut()
    midiout.open_virtual_port(PORT_NAME)

    with midiout:
        time.sleep(1) # must have this for the first note_on message to send (TODO: maybe a better fix out there?)

        # send messages to adjust settings
        midiout.send_message(Message(type='note_on', note=85, channel=midi_channel, velocity=1).bytes()) # strum mode off
        midiout.send_message(Message(type='note_on', note=92, channel=midi_channel, velocity=1).bytes()) # open string first mode off

        # loop through midi messages and send to plugin
        # midi_chords is of format: [(note_on messages, note_off messages, duration), chord2, chord3, etc...]
        for chord in midi_chords:
            note_ons = chord[0]
            note_offs = chord[1]
            duration = chord[2]

            for msg in note_ons:
                midiout.send_message(msg) # make sure this is in bytes

            time.sleep(duration)
            
            for msg in note_offs:
                midiout.send_message(msg) # make sure this is in bytes

        # send note_off's for settings messages
        midiout.send_message(Message(type='note_off', note=85, channel=midi_channel, velocity=1).bytes())
        midiout.send_message(Message(type='note_off', note=92, channel=midi_channel, velocity=1).bytes())