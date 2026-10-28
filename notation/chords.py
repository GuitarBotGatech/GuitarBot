"""Chord track → pinned plucks, so the planner only ever sees plucks."""

from __future__ import annotations

import bisect
from typing import Any
import numpy as np
import pandas as pd
from tuning import tune as tu

_ONE_CHAR_TYPES = {'m': "MINOR", '7': "DOMINANT", '9': "DOMINANT", '13': "DOMINANT", 'o': "HALF-DIM", '5': "FIFTH"}
_TWO_CHAR_TYPES = {"M6": "MAJOR6", "M7": "MAJOR7", "M9": "MAJOR9", "m6": "MINOR6", "m7": "MINOR7", "m9": "MINOR9"}
_LONG_TYPES = {"sus": "SUS4", "sus4": "SUS4", "sus2": "SUS2", "dim": "DIMINISHED", "dim7": "DIMINISHED"}

# Distance from the nut, in mm, for frets 0 through 10. Used only to score a shape change.
_FRET_LENGTHS_MM = [
    37.85201719088437, 35.63981144712466, 33.639502533759924,
    31.751462333006657, 29.96938968620543, 28.287337091556935,
    26.69969085488873, 25.201152354471787, 23.786720357363606,
    22.45167432825832, 21.191558675138026,
]


def chord_name(symbol: str) -> tuple[str, str]:
    """Chord symbol → (letter, type) as spelled in the voicing library, e.g. ``"F#m"`` → ``("F#", "MINOR")``.

    Flats may be written ``b`` (``Bb``) or ``f`` (``Bf``). Both use the library's ``f`` spelling.
    """
    accidental, chord_type, index = "n", "MAJOR", 1
    if len(symbol) > 1 and symbol[1] in "#bf":
        accidental = "#" if symbol[1] == "#" else "f"
        index = 2
    remaining = symbol[index:]
    if len(remaining) == 1:
        chord_type = _ONE_CHAR_TYPES.get(remaining, chord_type)
    elif len(remaining) == 2:
        chord_type = _TWO_CHAR_TYPES.get(remaining, chord_type)
    elif len(remaining) >= 3:
        chord_type = _LONG_TYPES.get(remaining, chord_type)
    return symbol[0].upper() + accidental, chord_type


def find_lowest_cost_chord(current_fret_positions, filepath, chord_letter, chord_type):
    """Frets of the library voicing closest to ``current_fret_positions``, or None."""
    easiest = None
    min_cost = float("inf")
    for voicing in _library_voicings(filepath, chord_letter, chord_type):
        cost = _transition_cost(current_fret_positions, voicing)
        if cost < min_cost:
            min_cost = cost
            easiest = voicing
    return easiest


def plan_parts(chord_rows: list[list[Any]], pluck_rows: list[list[Any]]):
    """Pluck rows, plus a mute for each string a chord damps.

    String-index plucks (note 0-5) become the pitch the active chord frets on that
    string, pinned so the planner honors them. Before the first chord the string
    plays open. A muted string is not plucked. The mute starts the usual prep
    window before the chord, and never earlier than the start of the song.
    """
    from control.actions import Mute

    frets = [0] * len(tu.STRING_MIDI_RANGES)
    # (time, frets) for the chords that resolved. Plucks look up the one active at their time.
    voiced: list[tuple[float, list[int]]] = []
    for symbol, timestamp in sorted(chord_rows, key=lambda row: float(row[1])):
        letter, chord_type = chord_name(str(symbol))
        voicing = find_lowest_cost_chord(frets, tu.CHORD_LIBRARY_FILE, letter, chord_type)
        if voicing is None:
            print(f"Warning: No voicing for chord {symbol} at {timestamp}, keeping the previous chord.")
            continue
        frets = [int(fret) for fret in voicing]
        voiced.append((float(timestamp), frets))

    times = [timestamp for timestamp, _frets in voiced]
    mutes = []
    prep = float(tu.LH_PREP_TIME_BEFORE_PICK)
    for timestamp, shape in voiced:
        start = max(0.0, float(timestamp) - prep)
        for string, fret in enumerate(shape):
            if int(fret) < 0:
                mutes.append(Mute(string, start, prep))

    rows = []
    for row in pluck_rows:
        note, timestamp = int(row[0]), float(row[-1])
        if not 0 <= note < len(tu.STRING_MIDI_RANGES):
            rows.append(list(row))
            continue

        active = bisect.bisect_right(times, timestamp) - 1
        fret = voiced[active][1][note] if active >= 0 else 0
        low, high, _direction = tu.STRING_MIDI_RANGES[note]
        if not 0 <= fret <= high - low:
            print(f"Skipping pluck on string {note} at {timestamp}: the chord mutes it or frets it out of reach.")
            continue
        duration, speed, slide = row[1], row[2], row[3]
        rows.append([low + fret, duration, speed, slide, note, timestamp])
    return rows, mutes


def _library_voicings(filepath, chord_letter, chord_type) -> list[list[int]]:
    """Contiguous rows of ``Alternate_Chords.csv`` for one letter and type. -1 is a muted string."""
    df_chords = pd.read_csv(filepath)
    voicings = []
    row = 0
    while row < 351 and not (df_chords.iloc[row].iloc[0] == chord_letter and df_chords.iloc[row].iloc[1] == chord_type):
        row += 1
    while row < 351 and df_chords.iloc[row].iloc[0] == chord_letter and df_chords.iloc[row].iloc[1] == chord_type:
        voicings.append(_frets_from_row(df_chords, row))
        row += 1
    return voicings


def _frets_from_row(df_chords, row) -> list[int]:
    frets = []
    for column in range(3, 9):
        try:
            frets.append(int(df_chords.iloc[row].iloc[column]))
        except (TypeError, ValueError):
            frets.append(-1)
    return frets


def _transition_cost(current, target, samples: int = 25) -> float:
    """Average per-string travel from ``current`` frets to ``target`` frets."""
    cost = 0.0
    for start, end in zip(current, target):
        if end == -1:
            y0 = y1 = _FRET_LENGTHS_MM[0]
        else:
            y0 = _FRET_LENGTHS_MM[start]
            y1 = _FRET_LENGTHS_MM[end]
        motion = _interp_with_bend(y0, y1, 25, 0.2)
        slope = abs(np.gradient(motion))
        midpoint = samples / 2
        cost += float(np.interp(midpoint, np.linspace(0, 1, samples), slope)) * 59.9406059
    return cost / 6


def _interp_with_bend(q0, qf, count, bend=0.2):
    """Blend into and out of a linear move. ``bend`` is the fraction of samples spent accelerating."""
    nb = int(bend * count)
    accel = 0.5 * (qf - q0) / (nb * (count - nb))
    curve = np.zeros(count, dtype=float)
    for i in range(nb):
        offset = accel * pow(i, 2)
        curve[i] = q0 + offset
        curve[count - i - 1] = qf - offset
    held = accel * pow(nb, 2)
    curve[nb: count - nb] = np.linspace(q0 + held, qf - held, count - (2 * nb))
    return curve
