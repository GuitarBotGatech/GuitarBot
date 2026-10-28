"""Fretboard model and cost primitives for the path planner."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from tuning import tune as tu
from control.actions import fret_to_encoder

_RANGES = tu.STRING_MIDI_RANGES
NUM_STRINGS = len(_RANGES)
OPEN_PITCHES = [r[0] for r in _RANGES]
MAX_FRETS = [r[1] - r[0] for r in _RANGES]

# A slider cannot usefully cross more than this many frets per second.
_MAX_FRETS_PER_S = 80.0
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
        string = note.forced_string
        if 0 <= string < NUM_STRINGS:
            fret = note.pitch - OPEN_PITCHES[string]
            if 0 <= fret <= MAX_FRETS[string]:
                return [(string, fret)]
        return []
    found = []
    for string, (open_pitch, high) in enumerate(_RANGES):
        fret = note.pitch - open_pitch
        if 0 <= fret <= high - open_pitch:
            found.append((string, fret))
    return found


def fret_from_slider(string, encoder):
    """Fret the slider is sitting on. Home (0) and the stay sentinel (-1) are open."""
    if encoder == -1:
        return 0
    best_fret = 0
    best_dist = abs(float(encoder))
    for fret in range(1, MAX_FRETS[string] + 1):
        dist = abs(float(encoder) - fret_to_encoder(string, fret))
        if dist < best_dist:
            best_dist = dist
            best_fret = fret
    return best_fret


def slider_frets(encoders):
    frets = []
    for string in range(NUM_STRINGS):
        encoder = encoders[string] if encoders is not None and string < len(encoders) else 0
        frets.append(fret_from_slider(string, encoder))
    return frets


def viable(prev: StringState, note: Note, fret: int) -> bool:
    """The slider can be on `fret` by the pluck, given where it is and when it is free.

    A slider already on that fret does not need the prep window. Any other move
    needs ``LH_PREP_TIME_BEFORE_PICK`` after the string is free, and the travel
    has to fit in the time since it was last free.
    """
    if prev.fret == fret and not note.slide_in:
        return note.t + 1e-9 >= prev.last_pluck_t
    prep = float(tu.LH_PREP_TIME_BEFORE_PICK)
    if note.t - prep + 1e-9 < prev.last_pluck_t:
        return False
    dt = note.t - prev.last_pluck_t
    travel = abs(fret - prev.fret)
    if travel and (dt <= 0 or travel / dt > _MAX_FRETS_PER_S):
        return False
    return True


def violations(prev: StringState, note: Note, fret: int) -> list[str]:
    v = []
    if note.slide_in and fret == 0:
        v.append("slide_into_open")
    return v


def transition_cost(prev: StringState, note: Note, fret: int) -> tuple[float, int]:
    vs = violations(prev, note, fret)
    travel = abs(fret - prev.fret)
    return W_TRAVEL * travel + W_VIOLATION * len(vs), len(vs)
