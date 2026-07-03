"""A* search over joint 6-string state with admissible travel heuristic.

For tractability we bound expansion by a node budget; falls back to best-so-far
if exhausted.
"""
import heapq
from ..model import (
    Note, Assignment, StringState, NUM_STRINGS,
    candidates, transition_cost, W_TRAVEL,
)

NODE_BUDGET = 20000


def _heuristic(notes, i, frets):
    """Lower bound on remaining travel: for each remaining note, min over
    candidates of |target_fret - current_fret_of_that_string| * W_TRAVEL.
    Admissible because it ignores interactions and violation penalties."""
    h = 0.0
    for k in range(i, len(notes)):
        cands = candidates(notes[k].pitch)
        if not cands:
            continue
        h += W_TRAVEL * min(abs(f - frets[s]) for s, f in cands)
    return h


def plan(notes: list[Note]) -> list[Assignment]:
    N = len(notes)
    if N == 0:
        return []
    init_frets = (0,) * NUM_STRINGS
    init_lastt = (-1e9,) * NUM_STRINGS
    start = (0.0, 0, init_frets, init_lastt, ())  # (g, i, frets, lastt, path)
    # open = priority queue with f = g + h
    open_h = []
    h0 = _heuristic(notes, 0, init_frets)
    counter = [0]
    def push(f, g, i, frets, lastt, path):
        counter[0] += 1
        heapq.heappush(open_h, (f, counter[0], g, i, frets, lastt, path))
    push(h0, 0.0, 0, init_frets, init_lastt, ())
    best_goal = None
    expanded = 0
    while open_h and expanded < NODE_BUDGET:
        f, _c, g, i, frets, lastt, path = heapq.heappop(open_h)
        if i == N:
            if best_goal is None or g < best_goal[0]:
                best_goal = (g, path)
            break
        expanded += 1
        n = notes[i]
        cands = candidates(n.pitch)
        if not cands:
            h = _heuristic(notes, i + 1, frets)
            push(g + h, g, i + 1, frets, lastt, path)
            continue
        for s, fr in cands:
            st = StringState(frets[s], lastt[s])
            c, _ = transition_cost(st, n, fr)
            new_frets = tuple(fr if k == s else frets[k] for k in range(NUM_STRINGS))
            new_lastt = tuple(n.t if k == s else lastt[k] for k in range(NUM_STRINGS))
            new_g = g + c
            h = _heuristic(notes, i + 1, new_frets)
            new_path = path + (Assignment(i, s, fr),)
            push(new_g + h, new_g, i + 1, new_frets, new_lastt, new_path)

    if best_goal is None:
        # fallback: pop best-g entry with largest i
        if not open_h:
            return []
        best = min(open_h, key=lambda e: (-e[3], e[2]))
        return list(best[6])
    return list(best_goal[1])
