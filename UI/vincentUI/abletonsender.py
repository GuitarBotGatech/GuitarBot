import rtmidi

def list_ports():
    midi_in = rtmidi.MidiIn()
    ports = midi_in.get_ports()
    for i, port in enumerate(ports):
        print(f"{i}: {port}")

def listen_to_midi(port_index=0):
    midi_in = rtmidi.MidiIn()
    midi_in.open_port(port_index)
    print("Listening for MIDI... Press Ctrl+C to stop.")
    try:
        while True:
            msg = midi_in.get_message()
            if msg:
                message, delta = msg
                print(f"MIDI message: {message} | Time delta: {delta}")
    except KeyboardInterrupt:
        print("Stopping.")
    finally:
        midi_in.close_port()

# List available ports first
list_ports()

# Then listen on the correct one
listen_to_midi(port_index=0)
