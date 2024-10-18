from mido import Message
import time
import rtmidi

# NOTE: Designed to integrate with GarageBand.

PORT_NAME = 'GarageBand Virtual Out'

# open virtual midi port
midiout = rtmidi.MidiOut()
# ports = midiout.get_ports()
# print(ports)
midiout.open_virtual_port(PORT_NAME)

with midiout:
    channel = 0
    root = 48
    third_offset = 4 # 4 = major, 3 = minor
    fifth_offset = 7
    octave_offset = 12

    time.sleep(1) # must have this for the note_on message to send (TODO: maybe a better fix out there?)

    # send messages to adjust settings
    midiout.send_message(Message(type='note_on', note=85, channel=channel, velocity=1).bytes()) # strum mode off
    midiout.send_message(Message(type='note_on', note=92, channel=channel, velocity=1).bytes()) # open string first mode off

    # play C major chord
    root = 48

    # TODO: delay between notes for more realistic strumming? May not be needed
    midiout.send_message(Message(type='note_on', note=root, channel=channel, velocity=64).bytes())
    midiout.send_message(Message(type='note_on', note=root + third_offset, channel=channel, velocity=64).bytes())
    midiout.send_message(Message(type='note_on', note=root + fifth_offset, channel=channel, velocity=64).bytes())
    midiout.send_message(Message(type='note_on', note=root + octave_offset, channel=channel, velocity=64).bytes())
    midiout.send_message(Message(type='note_on', note=root + octave_offset + third_offset, channel=channel, velocity=64).bytes())

    # pause for chord duration
    time.sleep(3)

    # stop chord
    midiout.send_message(Message(type='note_off',  note=root, channel=channel).bytes())
    midiout.send_message(Message(type='note_off', note=root + third_offset, channel=channel).bytes())
    midiout.send_message(Message(type='note_off', note=root + fifth_offset, channel=channel).bytes())
    midiout.send_message(Message(type='note_off', note=root + octave_offset, channel=channel).bytes())
    midiout.send_message(Message(type='note_off', note=root + octave_offset + third_offset, channel=channel).bytes())

    # play D major chord
    root = 50

    # TODO: delay between notes for more realistic strumming? May not be needed
    midiout.send_message(Message(type='note_on', note=root, channel=channel, velocity=64).bytes())
    midiout.send_message(Message(type='note_on', note=root + third_offset, channel=channel, velocity=64).bytes())
    midiout.send_message(Message(type='note_on', note=root + fifth_offset, channel=channel, velocity=64).bytes())
    midiout.send_message(Message(type='note_on', note=root + octave_offset, channel=channel, velocity=64).bytes())
    midiout.send_message(Message(type='note_on', note=root + octave_offset + third_offset, channel=channel, velocity=64).bytes())

    # pause for chord duration
    time.sleep(3)

    # stop chord
    midiout.send_message(Message(type='note_off',  note=root, channel=channel).bytes())
    midiout.send_message(Message(type='note_off', note=root + third_offset, channel=channel).bytes())
    midiout.send_message(Message(type='note_off', note=root + fifth_offset, channel=channel).bytes())
    midiout.send_message(Message(type='note_off', note=root + octave_offset, channel=channel).bytes())
    midiout.send_message(Message(type='note_off', note=root + octave_offset + third_offset, channel=channel).bytes())

    # send note_off's for settings messages
    midiout.send_message(Message(type='note_off', note=85, channel=channel, velocity=1).bytes())
    midiout.send_message(Message(type='note_off', note=92, channel=channel, velocity=1).bytes())