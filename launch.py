#!/usr/bin/env python3
"""Launch the GuitarBot web UI, song server, and receiver together."""

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

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
        "cmd": [sys.executable, "-m", "http.server", "8000", "--directory", str(ROOT)],
        "color": "\033[32m",  # green
    },
]

RESET = "\033[0m"
WEB_URL = "http://127.0.0.1:8000/index.html"


def stream_output(proc, label, color):
    for line in proc.stdout:
        print(f"{color}{label}{RESET} {line}", end="", flush=True)


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
        for proc, comp in zip(procs, COMPONENTS):
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("All components stopped.")


if __name__ == "__main__":
    main()
