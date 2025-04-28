from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

# This will handle incoming OSC messages
def osc_message_handler(address, *args):
    print(f"Received {address}: {args}")

# Create the dispatcher
dispatcher = Dispatcher()
dispatcher.map("/live/clip/notes", osc_message_handler)  # Listen to everything, or use specific paths like '/live/clip/notes'

# Create the server
ip = "127.0.0.1"  # localhost
port = 11000      # Match the AbletonOSC sending port
server = BlockingOSCUDPServer((ip, port), dispatcher)

print(f"Listening for OSC on {ip}:{port}...")
server.serve_forever()