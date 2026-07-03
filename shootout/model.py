"""Core shootout model: notes, fretboard, state, constraints, cost."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

NUM_STRINGS = 6
OPEN_PITCHES = [40, 45, 50, 55, 59, 64]  # E A D G B E (low to high)
MAX_FRET = 20

DAMPING_S = 0.08           # min seconds between plucks on same string
V_MAX_FRETS_PER_S = 120.0  # ballpark slide velocity cap
BIG_PENALTY = 1e6          # soft penalty for violations in cost

W_TRAVEL = 1.0
W_VIOLATION = 1000.0


@dataclass(frozen=True)
class Note:
    pitch: int
    t: float
    dur: float
    slide_in: bool = False


@dataclass(frozen=True)
class Assignment:
    note_idx: int
    string: int
    fret: int


@dataclass
class StringState:
    fret: int = 0
    last_pluck_t: float = -1e9


def candidates(pitch: int) -> list[tuple[int, int]]:
    """All (string, fret) pairs that can sound `pitch`."""
    out = []
    for s, open_p in enumerate(OPEN_PITCHES):
        fret = pitch - open_p
        if 0 <= fret <= MAX_FRET:
            out.append((s, fret))
    return out


def violations(prev: StringState, note: Note, fret: int) -> list[str]:
    """Return list of violation tags for assigning `note` to this string."""
    v = []
    if note.slide_in and fret == 0:
        v.append("slide_into_open")
    dt = note.t - prev.last_pluck_t
    if dt <= 0:
        v.append("time_order")
    elif dt < DAMPING_S:
        v.append("pluck_conflict")
    travel = abs(fret - prev.fret)
    if dt > 0 and travel / max(dt, 1e-9) > V_MAX_FRETS_PER_S:
        v.append("over_velocity")
    return v


def transition_cost(prev: StringState, note: Note, fret: int) -> tuple[float, int]:
    """(cost, violation_count) for this transition."""
    travel = abs(fret - prev.fret)
    vs = violations(prev, note, fret)
    return W_TRAVEL * travel + W_VIOLATION * len(vs), len(vs)


def apply(prev: StringState, note: Note, fret: int) -> StringState:
    return StringState(fret=fret, last_pluck_t=note.t)


@dataclass
class PlanResult:
    assignments: list[Assignment]
    total_travel: float = 0.0
    violations: int = 0
    peak_velocity: float = 0.0

    @classmethod
    def from_plan(cls, notes: list[Note], assignments: list[Assignment]) -> "PlanResult":
        states = [StringState() for _ in range(NUM_STRINGS)]
        travel = 0.0
        viols = 0
        peak_v = 0.0
        for a in assignments:
            n = notes[a.note_idx]
            prev = states[a.string]
            dt = n.t - prev.last_pluck_t
            d = abs(a.fret - prev.fret)
            travel += d
            if dt > 0:
                peak_v = max(peak_v, d / dt)
            viols += len(violations(prev, n, a.fret))
            states[a.string] = apply(prev, n, a.fret)
        return cls(assignments, travel, viols, peak_v)
