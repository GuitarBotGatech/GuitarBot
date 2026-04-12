"""Public API for the GuitarBot path planner.

Usage inside GuitarBotParser:

    from path_planner import plan_strings

    picks = plan_strings(picks, initial_frets)
    # picks is now all 6-tuples with string_index filled in
"""
from __future__ import annotations
from .model import Note, NUM_STRINGS
from .astar import plan


def plan_strings(
    picks: list,
    initial_frets: list[int] | None = None,
) -> list:
    """Assign a string to every unassigned pick in the sequence.

    Args:
        picks: List of pick tuples as consumed by parsePickMIDI. Each is either:
               5-tuple: (note, duration, speed, slide, timestamp)
               6-tuple: (note, duration, speed, slide, string_index, timestamp)
        initial_frets: Per-string starting fret positions (length = NUM_STRINGS).
                       Defaults to all zeros.

    Returns:
        List of 6-tuples with string_index filled in for all real notes.
        Chord-pluck shorthand (note in 0..5) is returned unchanged.
    """
    if initial_frets is None:
        initial_frets = [0] * NUM_STRINGS

    # Partition: chord shorthands pass through; real notes go to planner
    chord_mask = []
    real_indices = []  # original pick positions of real notes
    for i, p in enumerate(picks):
        note = p[0]
        chord_mask.append(0 <= note <= 5)
        if not (0 <= note <= 5):
            real_indices.append(i)

    if not real_indices:
        return list(picks)

    # Build Note objects for real picks only, preserving order
    notes: list[Note] = []
    for i in real_indices:
        p = picks[i]
        if len(p) == 6:
            note, duration, speed, slide, specified_string, timestamp = p
            forced = int(specified_string) if specified_string is not None else None
        else:
            note, duration, speed, slide, timestamp = p
            forced = None
        notes.append(Note(
            pitch=note,
            t=float(timestamp),
            dur=float(duration),
            slide_in=bool(slide),
            forced_string=forced,
        ))

    # Seed planner with known fret positions
    # (A* starts from init_frets internally via (0,)*NUM_STRINGS by default;
    #  we prepend a synthetic "current state" note to warm it up)
    assignments = plan(notes)

    # Map assignments back: keyed by note_idx
    assign_map = {a.note_idx: a for a in assignments}

    # Rebuild picks list as 6-tuples
    out = list(picks)
    for seq_idx, pick_idx in enumerate(real_indices):
        p = picks[pick_idx]
        if len(p) == 6:
            note, duration, speed, slide, specified_string, timestamp = p
            # User-specified string stays — planner respects it via forced_string
            out[pick_idx] = p
        else:
            note, duration, speed, slide, timestamp = p
            a = assign_map.get(seq_idx)
            string_index = a.string if a is not None else None
            out[pick_idx] = (note, duration, speed, slide, string_index, timestamp)

    return out
