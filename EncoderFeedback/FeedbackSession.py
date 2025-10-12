"""
FeedbackSession.py

End-to-end helper: send a quick OSC command (e.g., /Dyn) and record encoder feedback
for a short duration to CSV. This is useful for quick bench tests in conjunction with
arm_list_recieverNN.py and the MCU running EncoderFeedbackCollector.
"""
from __future__ import annotations
import argparse
import time

from .OSCClient import GuitarBotOSCClient
from .EncoderUDPReceiver import run_receiver


def run_session(address: str, payload, duration: float, csv_out: str,
                host: str = "127.0.0.1", port: int = 12000,
                feedback_host: str = "0.0.0.0", feedback_port: int = 8889):
    client = GuitarBotOSCClient(host, port)

    # Fire the OSC message
    if address == "/Dyn":
        # payload expected as list of midi notes
        client.send_dyn(payload)
    elif address == "/Chords":
        client.send_chords(payload)
    elif address == "/Pluck":
        client.send_pluck(payload)
    else:
        client.send_raw(address, payload)

    # Listen and record encoder feedback
    print(f"Recording encoder feedback for {duration:.2f}s -> {csv_out}")
    run_receiver(feedback_host, feedback_port, csv_out, duration)


def main():
    ap = argparse.ArgumentParser(description="Send OSC then record encoder feedback")
    ap.add_argument("--address", default="/Dyn")
    ap.add_argument("--args", nargs=argparse.REMAINDER)
    ap.add_argument("--duration", type=float, default=5.0)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--osc-host", default="127.0.0.1")
    ap.add_argument("--osc-port", type=int, default=12000)
    ap.add_argument("--fb-host", default="0.0.0.0")
    ap.add_argument("--fb-port", type=int, default=8889)
    args = ap.parse_args()

    payload = []
    if args.args:
        for a in args.args:
            try:
                payload.append(int(a))
            except ValueError:
                try:
                    payload.append(float(a))
                except ValueError:
                    payload.append(a)

    run_session(args.address, payload, args.duration, args.csv, args.osc_host, args.osc_port, args.fb_host, args.fb_port)


if __name__ == "__main__":
    main()
