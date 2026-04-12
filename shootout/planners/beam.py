"""Beam search over joint 6-string state; small fixed width."""
from ..model import (
    Note, Assignment, StringState, NUM_STRINGS,
    candidates, transition_cost,
)

BEAM_WIDTH = 32


def plan(notes: list[Note]) -> list[Assignment]:
    N = len(notes)
    if N == 0:
        return []
    init_frets = (0,) * NUM_STRINGS
    init_lastt = (-1e9,) * NUM_STRINGS
    # beam entry: (cost, frets, lastt, path_list)
    beam = [(0.0, init_frets, init_lastt, [])]

    for i, n in enumerate(notes):
        cands = candidates(n.pitch)
        next_beam = []
        for cost, frets, lastt, path in beam:
            if not cands:
                next_beam.append((cost, frets, lastt, path))
                continue
            for s, f in cands:
                st = StringState(frets[s], lastt[s])
                c, _ = transition_cost(st, n, f)
                new_frets = tuple(f if k == s else frets[k] for k in range(NUM_STRINGS))
                new_lastt = tuple(n.t if k == s else lastt[k] for k in range(NUM_STRINGS))
                next_beam.append((cost + c, new_frets, new_lastt, path + [Assignment(i, s, f)]))
        next_beam.sort(key=lambda e: e[0])
        beam = next_beam[:BEAM_WIDTH]

    return beam[0][3] if beam else []
