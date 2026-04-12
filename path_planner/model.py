"""Fretboard model and cost primitives for the path planner.

Constants are derived from tune.py so the planner and parser always agree
on string ranges and fret counts.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import tune as tu

# Build string model from tune.py
_RANGES = tu.STRING_MIDI_RANGES          # list of (low, high, direction)
NUM_STRINGS = len(_RANGES)
OPEN_PITCHES = [r[0] for r in _RANGES]  # lowest playable pitch = open string
MAX_FRETS = [r[1] - r[0] for r in _RANGES]  # per-string fret count

DAMPING_S = tu.SHORT_NOTE_DEFAULT_DURATION   # min gap between plucks on same string
V_MAX_FRETS_PER_S = 80.0                     # ballpark slider velocity cap
W_TRAVEL = 1.0
W_VIOLATION = 1000.0


@dataclass(frozen=True)
class Note:
    pitch: int
    t: float
    dur: float
    slide_in: bool = False
    forced_string: Optional[int] = None  # None = planner decides; int = hard pin


@dataclass(frozen=True)
class Assignment:
    note_idx: int
    string: int
    fret: int


@dataclass
class StringState:
    fret: int = 0
    last_pluck_t: float = -1e9


def candidates(note: Note) -> list[tuple[int, int]]:
    """All (string, fret) pairs that can sound this note's pitch."""
    if note.forced_string is not None:
        s = note.forced_string
        if 0 <= s < NUM_STRINGS:
            fret = note.pitch - OPEN_PITCHES[s]
            if 0 <= fret <= MAX_FRETS[s]:
                return [(s, fret)]
        return []
    out = []
    for s, (open_p, high, _) in enumerate(_RANGES):
        fret = note.pitch - open_p
        if 0 <= fret <= high - open_p:
            out.append((s, fret))
    return out


def violations(prev: StringState, note: Note, fret: int) -> list[str]:
    v = []
    if note.slide_in and fret == 0:
        v.append("slide_into_open")
    dt = note.t - prev.last_pluck_t
    if 0 < dt < DAMPING_S:
        v.append("pluck_conflict")
    travel = abs(fret - prev.fret)
    if dt > 0 and travel / dt > V_MAX_FRETS_PER_S:
        v.append("over_velocity")
    return v


def transition_cost(prev: StringState, note: Note, fret: int) -> tuple[float, int]:
    vs = violations(prev, note, fret)
    travel = abs(fret - prev.fret)
    return W_TRAVEL * travel + W_VIOLATION * len(vs), len(vs)
