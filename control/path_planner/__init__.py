"""Assign each pluck to a string.

The algorithm is named in configs/default.yaml (`planner:`). Each one takes
the notes and the current slider frets and returns the strings it can play.
"""
from . import astar
from .model import Note, slider_frets

_ALGORITHMS = {"astar": astar.plan}


def assign(picks, sliders, algorithm="astar"):
    """String index for each pick, or None when no fret is reachable in time."""
    plan = _ALGORITHMS.get(algorithm)
    if plan is None:
        known = ", ".join(sorted(_ALGORITHMS))
        raise ValueError(f"Unknown planner '{algorithm}'. Known planners: {known}")
    if not picks:
        return []

    notes = []
    for pick in picks:
        if len(pick) == 6 and pick[4] is not None:
            note, duration, _speed, slide, specified, timestamp = pick
            forced = int(specified)
        elif len(pick) == 6:
            note, duration, _speed, slide, _specified, timestamp = pick
            forced = None
        else:
            note, duration, _speed, slide, timestamp = pick
            forced = None
        notes.append(Note(
            pitch=int(note),
            t=float(timestamp),
            dur=float(duration),
            slide_in=bool(slide),
            forced_string=forced,
        ))

    found = {a.note_idx: a.string for a in plan(notes, initial_frets=slider_frets(sliders))}
    return [found.get(i) for i in range(len(picks))]
