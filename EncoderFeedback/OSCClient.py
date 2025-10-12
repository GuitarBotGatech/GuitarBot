"""
OSCClient.py

Small utility for sending OSC messages to arm_list_recieverNN.py.
Default target: 127.0.0.1:12000

Supported helpers:
- send_dyn([mnn1, mnn2, ...]) -> sends /Dyn with list of MIDI note numbers
- send_fret(midi_note, [presser_force], [timestamp]) -> sends /Fret for LeftHandParser
- send_raw(address, args) -> send any address/args quickly

Usage from CLI:
    python -m EncoderFeedback.OSCClient --address /Dyn --args 40 45 50
    python -m EncoderFeedback.OSCClient --preset dyn --args 40 45 50
    python -m EncoderFeedback.OSCClient --preset fret --args 45 0.8 0.5

Note: Keep arm_list_recieverNN.py running to receive messages.
"""
from __future__ import annotations
import argparse
from typing import List, Sequence, Any

from pythonosc.udp_client import SimpleUDPClient

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 12000


class GuitarBotOSCClient:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self.client = SimpleUDPClient(self.host, self.port)

    def send_raw(self, address: str, args: Sequence[Any] | None = None):
        if args is None:
            args = []
        self.client.send_message(address, list(args))

    def send_dyn(self, midi_notes: List[int]):
        """Send /Dyn with a list of MIDI note numbers."""
        self.send_raw("/Dyn", midi_notes)

    def send_fret(self, midi_note: int, presser_force: float | None = None, timestamp: float | None = None):
        """
        Send /Fret according to LeftHandParser.parse_fret_message:
        args: [midi_note_number, presser_force?, timestamp?]
        - midi_note: required (e.g., 45)
        - presser_force: optional 0.0-1.0
        - timestamp: optional seconds (float)
        """
        args: list[Any] = [int(midi_note)]
        if presser_force is not None:
            args.append(float(presser_force))
        if timestamp is not None:
            args.append(float(timestamp))
        self.send_raw("/Fret", args)


def main():
    parser = argparse.ArgumentParser(description="Send OSC messages to GuitarBot receiver")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--address", help="OSC address to send (e.g., /Dyn, /Fret)")
    parser.add_argument("--preset", choices=["dyn", "fret"], help="Preset helpers")
    parser.add_argument("--args", nargs=argparse.REMAINDER, help="Arguments to send after --args")

    args = parser.parse_args()
    client = GuitarBotOSCClient(args.host, args.port)

    payload: List[Any] = []
    if args.args:
        # Try to cast ints when possible, else leave as strings
        for a in args.args:
            try:
                payload.append(int(a))
            except ValueError:
                try:
                    payload.append(float(a))
                except ValueError:
                    payload.append(a)

    if args.preset == "dyn":
        client.send_dyn([int(x) for x in payload])
    elif args.preset == "fret":
        # Expect payload like: midi_note [presser_force] [timestamp]
        if not payload:
            parser.error("--preset fret requires at least a MIDI note argument")
        midi_note = int(payload[0])
        presser_force = float(payload[1]) if len(payload) > 1 else None
        timestamp = float(payload[2]) if len(payload) > 2 else None
        client.send_fret(midi_note, presser_force, timestamp)
    elif args.address:
        client.send_raw(args.address, payload)
    else:
        parser.error("Provide either --preset or --address")


if __name__ == "__main__":
    main()
