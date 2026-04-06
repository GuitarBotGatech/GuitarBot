"""
OSC_PianoRoll_Parser.py — GuitarBot Piano Roll Bridge

Listens for Open Stage Control piano-roll OSC messages on LISTEN_PORT (default 9001)
and converts the grid state to GuitarBot /Pluck + /Chords messages forwarded to
GUITARBOT_PORT (default 12000).

Workflow
--------
1. Open `web/piano_roll.json` in Open Stage Control, set OSC output to 127.0.0.1:9001
2. Start GuitarBot: python OSC_Message_Receiver.py
3. Start this bridge: python OSC_PianoRoll_Parser.py

OSC addresses handled (from Open Stage Control)
------------------------------------------------
/piano_roll/grid        Full 29×32 matrix state (2D array, row 0 = MIDI 68 top)
/piano_roll/play        (momentary) Convert grid → /Pluck + /Chords → GuitarBot
/piano_roll/stop        (momentary) Send /Reset to GuitarBot
/piano_roll/clear       (momentary) Zero the local grid state
/piano_roll/bpm         float  40–240  (default 120)
/piano_roll/speed       int    1–10    (default 6, pluck speed)
/piano_roll/tremolo     int    0|1     (default 0, sets slide flag)
/piano_roll/step_size   float  0.125–2.0 beats per column (default 0.5)
/piano_roll/sustain     float  0.125–4.0 beats per note (default 1.0)

GuitarBot MIDI range
--------------------
String B (2):  MIDI 59–68  → matrix rows  0–9
String D (1):  MIDI 50–58  → matrix rows 10–18
String E (0):  MIDI 40–49  → matrix rows 19–28
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

# ── Constants ─────────────────────────────────────────────────────────────────

MIDI_MIN = 40
MIDI_MAX = 68
MIDI_ROWS = MIDI_MAX - MIDI_MIN + 1  # 29

DEFAULT_COLUMNS = 32
DEFAULT_BPM = 120.0
DEFAULT_SPEED = 6
DEFAULT_TREMOLO = 0
DEFAULT_STEP_BEATS = 0.5
DEFAULT_SUSTAIN_BEATS = 1.0

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 9001
GUITARBOT_IP = "127.0.0.1"
GUITARBOT_PORT = 12000

# Mirror send_song_arrangement.py's chunk limit so large grids don't exceed
# OSC_Message_Receiver's 8 KB UDP buffer.
MAX_EVENTS_PER_PACKET = 48

# Placeholder chord sent before /Pluck so song_creator() in
# OSC_Message_Receiver pairs them immediately (avoids 0.5 s auto-chord wait).
PLACEHOLDER_CHORD = "Em"


# ── State ─────────────────────────────────────────────────────────────────────

@dataclass
class PianoRollState:
    """Mutable UI state mirroring the Open Stage Control session."""
    columns: int = DEFAULT_COLUMNS
    bpm: float = DEFAULT_BPM
    speed: int = DEFAULT_SPEED
    tremolo: int = DEFAULT_TREMOLO
    step_beats: float = DEFAULT_STEP_BEATS
    sustain_beats: float = DEFAULT_SUSTAIN_BEATS
    grid: list[list[int]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.grid:
            self.grid = self._blank_grid()

    def _blank_grid(self) -> list[list[int]]:
        return [[0] * self.columns for _ in range(MIDI_ROWS)]

    def clear(self) -> None:
        self.grid = self._blank_grid()

    def midi_note_for_row(self, row: int) -> int:
        """Row 0 = MIDI_MAX (highest pitch), row 28 = MIDI_MIN (lowest pitch)."""
        return MIDI_MAX - row


# ── Converter ─────────────────────────────────────────────────────────────────

class PianoRollConverter:
    """Pure conversion logic — no OSC, no I/O. Easily unit-tested."""

    def grid_to_pluck_events(self, state: PianoRollState) -> list[list]:
        """
        Convert the active grid cells to a /Pluck payload.

        Each row in the returned list has the form expected by GuitarBot's
        song_creator / GuitarBotParser:
            [midi_note, duration_s, speed, slide, timestamp_s]

        Rows are sorted by timestamp_s, then by midi_note (ascending).
        """
        sps = self._seconds_per_step(state.bpm, state.step_beats)
        duration_s = state.sustain_beats * (60.0 / state.bpm)

        events: list[list] = []
        for row in range(MIDI_ROWS):
            midi_note = state.midi_note_for_row(row)
            for col in range(state.columns):
                if state.grid[row][col]:
                    timestamp_s = col * sps
                    slide_val = int(state.tremolo)
                    if slide_val == 1:
                        events.append([
                            midi_note,
                            round(duration_s, 4),
                            int(state.speed),
                            slide_val,
                            0.5, 0.5, # Default 2D control point for piano roll slides
                            round(timestamp_s, 4),
                        ])
                    else:
                        events.append([
                            midi_note,
                            round(duration_s, 4),
                            int(state.speed),
                            slide_val,
                            round(timestamp_s, 4),
                        ])

        events.sort(key=lambda e: (e[4], e[0]))
        return events

    def grid_to_chord_events(self, state: PianoRollState) -> list[list]:
        """
        Return a minimal /Chords payload with a placeholder chord at t=0.

        This satisfies the chord+pluck pairing in song_creator() so playback
        starts immediately rather than waiting for the 0.5 s auto-chord timeout.
        Returns an empty list if the grid is empty (nothing to play).
        """
        has_notes = any(
            state.grid[row][col]
            for row in range(MIDI_ROWS)
            for col in range(state.columns)
        )
        if not has_notes:
            return []
        return [[PLACEHOLDER_CHORD, 0.0]]

    @staticmethod
    def _seconds_per_step(bpm: float, step_beats: float) -> float:
        return step_beats * (60.0 / bpm)


# ── Bridge ────────────────────────────────────────────────────────────────────

class PianoRollBridge:
    """
    OSC server that receives piano-roll UI messages and forwards converted
    GuitarBot payloads to OSC_Message_Receiver.py.
    """

    def __init__(
        self,
        listen_host: str = LISTEN_HOST,
        listen_port: int = LISTEN_PORT,
        bot_ip: str = GUITARBOT_IP,
        bot_port: int = GUITARBOT_PORT,
    ) -> None:
        self._state = PianoRollState()
        self._converter = PianoRollConverter()
        self._client = SimpleUDPClient(bot_ip, bot_port)
        self._bot_addr = f"{bot_ip}:{bot_port}"

        dispatcher = Dispatcher()
        dispatcher.map("/piano_roll/grid",      self._on_grid)
        dispatcher.map("/piano_roll/play",      self._on_play)
        dispatcher.map("/piano_roll/stop",      self._on_stop)
        dispatcher.map("/piano_roll/clear",     self._on_clear)
        dispatcher.map("/piano_roll/bpm",       self._on_bpm)
        dispatcher.map("/piano_roll/speed",     self._on_speed)
        dispatcher.map("/piano_roll/tremolo",   self._on_tremolo)
        dispatcher.map("/piano_roll/step_size", self._on_step_size)
        dispatcher.map("/piano_roll/sustain",   self._on_sustain)

        self._server = BlockingOSCUDPServer((listen_host, listen_port), dispatcher)

    # ── OSC handlers ──────────────────────────────────────────────────────────

    def _on_grid(self, address: str, *args) -> None:
        """
        Receive the full matrix state from Open Stage Control.

        Open Stage Control sends the matrix value as OSC arrays. pythonosc
        decodes OSC arrays as Python lists, so args may arrive as:
          - 29 list args (one per row), each with 32 int values  ← nested
          - 928 flat int args (row-major)                         ← flat

        Both cases are handled.
        """
        cols = self._state.columns

        # Nested: each arg is a row list
        if args and isinstance(args[0], (list, tuple)):
            rows = [list(map(int, row)) for row in args]
            # Pad or trim to expected dimensions
            while len(rows) < MIDI_ROWS:
                rows.append([0] * cols)
            rows = rows[:MIDI_ROWS]
            for i in range(len(rows)):
                while len(rows[i]) < cols:
                    rows[i].append(0)
                rows[i] = rows[i][:cols]
            self._state.grid = rows
            return

        # Flat: 928 values row-major
        flat = list(map(int, args))
        expected = MIDI_ROWS * cols
        # Pad or trim
        if len(flat) < expected:
            flat.extend([0] * (expected - len(flat)))
        flat = flat[:expected]

        self._state.grid = [
            flat[r * cols: (r + 1) * cols]
            for r in range(MIDI_ROWS)
        ]

    def _on_play(self, address: str, *args) -> None:
        """Build /Chords + /Pluck payloads and send to GuitarBot."""
        pluck_payload = self._converter.grid_to_pluck_events(self._state)
        if not pluck_payload:
            print("[piano_roll] Grid is empty — nothing to send")
            return

        chord_payload = self._converter.grid_to_chord_events(self._state)
        if chord_payload:
            self._client.send_message("/Chords", chord_payload)
            print(f"[piano_roll] → /Chords ({len(chord_payload)} event(s)) to {self._bot_addr}")

        self._send_chunked("/Pluck", pluck_payload)

    def _on_stop(self, address: str, *args) -> None:
        self._client.send_message("/Reset", [])
        print(f"[piano_roll] → /Reset to {self._bot_addr}")

    def _on_clear(self, address: str, *args) -> None:
        self._state.clear()
        print("[piano_roll] Grid cleared")

    def _on_bpm(self, address: str, *args) -> None:
        if not args:
            return
        self._state.bpm = max(20.0, min(300.0, float(args[0])))
        print(f"[piano_roll] BPM = {self._state.bpm:.1f}")

    def _on_speed(self, address: str, *args) -> None:
        if not args:
            return
        self._state.speed = max(1, min(10, int(round(float(args[0])))))
        print(f"[piano_roll] Speed = {self._state.speed}")

    def _on_tremolo(self, address: str, *args) -> None:
        if not args:
            return
        self._state.tremolo = 1 if float(args[0]) > 0.5 else 0
        print(f"[piano_roll] Tremolo = {self._state.tremolo}")

    def _on_step_size(self, address: str, *args) -> None:
        if not args:
            return
        self._state.step_beats = max(0.125, min(4.0, float(args[0])))
        print(f"[piano_roll] Step size = {self._state.step_beats} beats")

    def _on_sustain(self, address: str, *args) -> None:
        if not args:
            return
        self._state.sustain_beats = max(0.125, min(8.0, float(args[0])))
        print(f"[piano_roll] Sustain = {self._state.sustain_beats} beats")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _send_chunked(self, osc_address: str, payload: list[list]) -> None:
        """Send a payload in MAX_EVENTS_PER_PACKET-sized chunks (mirrors send_song_arrangement.py)."""
        chunks = [
            payload[i: i + MAX_EVENTS_PER_PACKET]
            for i in range(0, len(payload), MAX_EVENTS_PER_PACKET)
        ]
        if len(chunks) == 1:
            self._client.send_message(osc_address, payload)
            print(f"[piano_roll] → {osc_address} ({len(payload)} event(s)) to {self._bot_addr}")
            return

        print(
            f"[piano_roll] → {osc_address} ({len(payload)} event(s) in "
            f"{len(chunks)} packets) to {self._bot_addr}"
        )
        for i, chunk in enumerate(chunks, 1):
            self._client.send_message(osc_address, chunk)
            print(f"  packet {i}/{len(chunks)}: {len(chunk)} event(s)")

    # ── Run ───────────────────────────────────────────────────────────────────

    def serve_forever(self) -> None:
        host, port = self._server.server_address
        print(f"[piano_roll] Listening on {host}:{port}")
        print(f"[piano_roll] Forwarding to GuitarBot at {self._bot_addr}")
        print(f"[piano_roll] Grid: {MIDI_ROWS} rows (MIDI {MIDI_MAX}→{MIDI_MIN}) × {self._state.columns} cols")
        self._server.serve_forever()


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="GuitarBot Piano Roll OSC bridge (Open Stage Control → GuitarBot)"
    )
    p.add_argument("--listen-port", type=int, default=LISTEN_PORT,
                   help=f"UDP port to receive OSC from Open Stage Control (default {LISTEN_PORT})")
    p.add_argument("--listen-host", default=LISTEN_HOST,
                   help=f"Bind address (default {LISTEN_HOST})")
    p.add_argument("--bot-ip", default=GUITARBOT_IP,
                   help=f"GuitarBot receiver IP (default {GUITARBOT_IP})")
    p.add_argument("--bot-port", type=int, default=GUITARBOT_PORT,
                   help=f"GuitarBot receiver UDP port (default {GUITARBOT_PORT})")
    p.add_argument("--columns", type=int, default=DEFAULT_COLUMNS,
                   help=f"Number of step columns in the grid (default {DEFAULT_COLUMNS})")
    return p


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()

    bridge = PianoRollBridge(
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        bot_ip=args.bot_ip,
        bot_port=args.bot_port,
    )
    bridge._state.columns = args.columns
    bridge._state.clear()  # reinit grid to match columns arg

    bridge.serve_forever()
