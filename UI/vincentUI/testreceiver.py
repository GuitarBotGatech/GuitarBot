import asyncio
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import AsyncIOOSCUDPServer

# Define handlers for incoming messages
def handle_hello(address, *args):
    print(f"Received {address}: {args}")

def handle_number(address, *args):
    print(f"Received {address}: {args}")

def handle_start(address, *args):
    print(f"Received {address}: {args}")

def handle_chord(address, *args):
    print(f"Received {address}: {args}")

def handle_strum(address, *args):
    print(f"Received {address}: {args}")

def handle_pluck(address, *args):
    print(f"Received {address}: {args}")
    
# Create dispatcher and map OSC addresses
dispatcher = Dispatcher()
dispatcher.map("/hello", handle_hello)
dispatcher.map("/number", handle_number)
dispatcher.map("/number", handle_number)
dispatcher.map("/Chords", handle_chord)
dispatcher.map("/Strum", handle_strum)
dispatcher.map("/Pluck", handle_pluck)

# Set up async OSC server
async def main():
    ip = "127.0.0.1"
    port = 5005

    server = AsyncIOOSCUDPServer((ip, port), dispatcher, asyncio.get_event_loop())
    transport, protocol = await server.create_serve_endpoint()
    print(f"Listening on {ip}:{port}...")

    # Keep running
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
    transport.close()

# Run the server
if __name__ == "__main__":
    asyncio.run(main())