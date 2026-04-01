#!/usr/bin/env python3
"""Launch the GuitarBot web UI, song server, and receiver together."""

import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

from pythonosc.udp_client import SimpleUDPClient

ROOT = Path(__file__).parent

COMPONENTS = [
    {
        "name": "receiver",
        "label": "[RECEIVER]",
        "cmd": [sys.executable, str(ROOT / "OSC_Message_Receiver.py")],
        "color": "\033[36m",  # cyan
    },
    {
        "name": "song-server",
        "label": "[SONG-SRV]",
        "cmd": [sys.executable, str(ROOT / "send_song_arrangement.py"), "--serve"],
        "color": "\033[33m",  # yellow
    },
    {
        "name": "web-ui",
        "label": "[WEB-UI  ]",
        "cmd": [sys.executable, str(ROOT / "web_dev_server.py"), "--port", "8000", "--directory", str(ROOT / "web")],
        "color": "\033[32m",  # green
    },
]

RESET = "\033[0m"
WEB_URL = "http://127.0.0.1:8000/index.html"
OSC_RESET_IP = "127.0.0.1"
OSC_RESET_PORT = 12000
UPLOAD_SERVER_RESET_URL = "http://127.0.0.1:8765/Reset"


def stream_output(proc, label, color):
    for line in proc.stdout:
        print(f"{color}{label}{RESET} {line}", end="", flush=True)


def send_reset_on_interrupt() -> None:
    """Attempt to send /Reset to the receiver before shutdown."""
    try:
        client = SimpleUDPClient(OSC_RESET_IP, OSC_RESET_PORT)
        # Send a few times to reduce packet-loss/timing races.
        for _ in range(3):
            client.send_message("/Reset", [1])
            time.sleep(0.08)
        print("Sent /Reset before shutdown.")
    except Exception as exc:
        print(f"Warning: failed to send /Reset before shutdown: {exc}")


def send_reset_via_upload_server() -> bool:
    """Use the same /Reset endpoint as the UI for reliable reset behavior."""
    req = urlrequest.Request(
        UPLOAD_SERVER_RESET_URL,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=1.5) as resp:
            ok = 200 <= int(resp.status) < 300
        if ok:
            print("Sent reset via upload server /Reset endpoint.")
            return True
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        print(f"Warning: /Reset endpoint call failed: {exc}")
    return False


def main():
    print(f"Starting GuitarBot...\n")

    procs = []
    threads = []

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    for comp in COMPONENTS:
        proc = subprocess.Popen(
            comp["cmd"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            cwd=ROOT,
            env=env,
            start_new_session=True,
        )
        procs.append(proc)

        t = threading.Thread(
            target=stream_output,
            args=(proc, comp["label"], comp["color"]),
            daemon=True,
        )
        t.start()
        threads.append(t)
        print(f"{comp['color']}{comp['label']}{RESET} started (pid {proc.pid})")

    print(f"\nWeb UI: {WEB_URL}")
    print("Press Ctrl+C to stop all components.\n")

    time.sleep(1.5)
    webbrowser.open(WEB_URL)

    reported = set()
    try:
        while True:
            for i, (proc, comp) in enumerate(zip(procs, COMPONENTS)):
                if i not in reported and proc.poll() is not None:
                    reported.add(i)
                    print(
                        f"\n{comp['color']}{comp['label']}{RESET} exited with code {proc.returncode}"
                    )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")

        receiver_idx = next((i for i, comp in enumerate(COMPONENTS) if comp["name"] == "receiver"), None)

        # Use the same reset path as UI first; fall back to direct UDP /Reset.
        reset_sent = send_reset_via_upload_server()
        if not reset_sent:
            send_reset_on_interrupt()

        # Small grace period so receiver can enqueue reset before service teardown.
        time.sleep(0.15)

        # Stop non-receiver services first so receiver remains available for /Reset.
        for i, (proc, comp) in enumerate(zip(procs, COMPONENTS)):
            if i == receiver_idx:
                continue
            if proc.poll() is None:
                proc.terminate()

        # Prefer receiver's own Ctrl+C path, which runs cleanup_and_reset().
        if receiver_idx is not None:
            receiver_proc = procs[receiver_idx]
            if receiver_proc.poll() is None:
                try:
                    os.kill(receiver_proc.pid, signal.SIGINT)
                    print("Sent SIGINT to receiver for internal cleanup_and_reset().")
                except Exception as exc:
                    print(f"Warning: failed to signal receiver with SIGINT: {exc}")

        # Give receiver time to run its own reset trajectory.
        time.sleep(1.25)

        # If receiver is still alive, ask it to exit.
        if receiver_idx is not None:
            receiver_proc = procs[receiver_idx]
            if receiver_proc.poll() is None:
                receiver_proc.terminate()

        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("All components stopped.")


if __name__ == "__main__":
    main()
