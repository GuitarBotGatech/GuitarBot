from pythonosc import dispatcher
from pythonosc import osc_server

def midi_handler(address, *args):
    print(f"Received MIDI: {args}")

disp = dispatcher.Dispatcher()
disp.map("/live/clip/get/*", midi_handler)

server = osc_server.ThreadingOSCUDPServer(("127.0.0.1", 11001), disp)
print("Listening for OSC messages on port 11001...")
server.serve_forever()