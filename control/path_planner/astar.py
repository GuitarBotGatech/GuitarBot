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
    candidates, transition_cost, viable, W_TRAVEL,
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


def plan(
    notes: list[Note],
    initial_frets: list[int] | tuple[int, ...] | None = None,
    free_at: list[float] | tuple[float, ...] | None = None,
) -> list[Assignment]:
    N = len(notes)
    if N == 0:
        return []

    if initial_frets is None:
        init_frets = (0,) * NUM_STRINGS
    else:
        frets_list = list(initial_frets) + [0] * NUM_STRINGS
        init_frets = tuple(int(frets_list[i]) for i in range(NUM_STRINGS))

    # Free before the song, so a note at t=0 still has its prep window.
    if free_at is None:
        init_last_pluck = (-0.5,) * NUM_STRINGS
    else:
        free = list(free_at) + [-0.5] * NUM_STRINGS
        init_last_pluck = tuple(float(free[i]) for i in range(NUM_STRINGS))
    counter = [0]

    def push(f_score, g, i, frets, last_pluck, path):
        counter[0] += 1
        heapq.heappush(
            open_h,
            (f_score, counter[0], g, i, frets, last_pluck, path),
        )

    open_h = []
    push(
        _heuristic(notes, 0, init_frets),
        0.0,
        0,
        init_frets,
        init_last_pluck,
        (),
    )

    best_goal = None
    expanded = 0

    while open_h and expanded < NODE_BUDGET:
        f_score, _, g, i, frets, last_pluck, path = heapq.heappop(open_h)

        if i == N:
            if best_goal is None or g < best_goal[0]:
                best_goal = (g, path)
            break

        expanded += 1
        n = notes[i]
        # Drop frets the slider cannot reach in time, then rank the rest by travel.
        playable = []
        for s, fr in candidates(n):
            st = StringState(frets[s], last_pluck[s])
            if viable(st, n, fr):
                playable.append((transition_cost(st, n, fr)[0], s, fr))
        playable.sort()

        if not playable:
            push(
                g + _heuristic(notes, i + 1, frets),
                g,
                i + 1,
                frets,
                last_pluck,
                path,
            )
            continue

        for _cost, s, fr in playable:
            st = StringState(frets[s], last_pluck[s])
            c, _ = transition_cost(st, n, fr)
            new_frets = tuple(fr if k == s else frets[k] for k in range(NUM_STRINGS))
            new_last_pluck = tuple(n.t if k == s else last_pluck[k] for k in range(NUM_STRINGS))
            new_g = g + c
            h = _heuristic(notes, i + 1, new_frets)
            push(
                new_g + h,
                new_g,
                i + 1,
                new_frets,
                new_last_pluck,
                path + (Assignment(i, s, fr),),
            )

    if best_goal is None:
        # Budget exhausted — return best partial plan found
        if not open_h:
            return []
        # Tuple layout: f, counter, g, i, frets, last_pluck, path
        best = min(open_h, key=lambda e: (-e[3], e[2]))
        return list(best[6])

    return list(best_goal[1])
