"""A* string assignment over joint 6-string fret state.

Copied from shootout/planners/astar.py and adapted to use path_planner.model,
which drives constants from tune.py. Forced strings (user pins) are handled
transparently via Note.forced_string — candidates() returns only the pinned
(string, fret) pair for those notes, so A* treats them as single-candidate
steps at full cost accuracy.
"""
import heapq
from .model import (
    Note, Assignment, StringState, NUM_STRINGS,
    candidates, transition_cost, W_TRAVEL,
)

NODE_BUDGET = 20_000


def _heuristic(notes: list[Note], from_idx: int, frets: tuple) -> float:
    """Admissible lower bound: for each remaining note, cheapest reachable fret."""
    h = 0.0
    for k in range(from_idx, len(notes)):
        cands = candidates(notes[k])
        if cands:
            h += W_TRAVEL * min(abs(f - frets[s]) for s, f in cands)
    return h


def plan(notes: list[Note]) -> list[Assignment]:
    N = len(notes)
    if N == 0:
        return []

    init_frets = (0,) * NUM_STRINGS
    init_lastt = (-1e9,) * NUM_STRINGS
    counter = [0]

    def push(f_score, g, i, frets, lastt, path):
        counter[0] += 1
        heapq.heappush(open_h, (f_score, counter[0], g, i, frets, lastt, path))

    open_h = []
    push(_heuristic(notes, 0, init_frets), 0.0, 0, init_frets, init_lastt, ())

    best_goal = None
    expanded = 0

    while open_h and expanded < NODE_BUDGET:
        f_score, _, g, i, frets, lastt, path = heapq.heappop(open_h)

        if i == N:
            if best_goal is None or g < best_goal[0]:
                best_goal = (g, path)
            break

        expanded += 1
        n = notes[i]
        cands = candidates(n)

        if not cands:
            # Note unplayable on any string — skip it
            push(g + _heuristic(notes, i + 1, frets), g, i + 1, frets, lastt, path)
            continue

        for s, fr in cands:
            st = StringState(frets[s], lastt[s])
            c, _ = transition_cost(st, n, fr)
            new_frets = tuple(fr if k == s else frets[k] for k in range(NUM_STRINGS))
            new_lastt = tuple(n.t if k == s else lastt[k] for k in range(NUM_STRINGS))
            new_g = g + c
            h = _heuristic(notes, i + 1, new_frets)
            push(new_g + h, new_g, i + 1, new_frets, new_lastt, path + (Assignment(i, s, fr),))

    if best_goal is None:
        # Budget exhausted — return best partial plan found
        if not open_h:
            return []
        best = min(open_h, key=lambda e: (-e[3], e[2]))
        return list(best[6])

    return list(best_goal[1])
