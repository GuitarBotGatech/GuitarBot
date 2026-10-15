"""A* string assignment over joint 6-string fret state.

Copied from shootout/planners/astar.py and adapted to use path_planner.model,
which drives constants from tune.py. Forced strings (user pins) are handled
transparently via Note.forced_string — candidates() returns only the pinned
(string, fret) pair for those notes, so A* treats them as single-candidate
steps at full cost accuracy.

When USE_EXPERIMENTAL_TRAJ is on, physically infeasible (string, fret) moves
are hard-filtered so A* never assigns a slam; notes with no feasible candidate
are skipped.
"""
import heapq
from .model import (
    Note, Assignment, StringState, NUM_STRINGS,
    candidates, transition_cost, is_physically_feasible, W_TRAVEL,
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
) -> list[Assignment]:
    N = len(notes)
    if N == 0:
        return []

    if initial_frets is None:
        init_frets = (0,) * NUM_STRINGS
    else:
        frets_list = list(initial_frets) + [0] * NUM_STRINGS
        init_frets = tuple(int(frets_list[i]) for i in range(NUM_STRINGS))

    init_last_pluck = (-1e9,) * NUM_STRINGS
    init_last_end = (-1e9,) * NUM_STRINGS
    counter = [0]

    def push(f_score, g, i, frets, last_pluck, last_end, path):
        counter[0] += 1
        heapq.heappush(
            open_h,
            (f_score, counter[0], g, i, frets, last_pluck, last_end, path),
        )

    open_h = []
    push(
        _heuristic(notes, 0, init_frets),
        0.0,
        0,
        init_frets,
        init_last_pluck,
        init_last_end,
        (),
    )

    best_goal = None
    expanded = 0

    while open_h and expanded < NODE_BUDGET:
        f_score, _, g, i, frets, last_pluck, last_end, path = heapq.heappop(open_h)

        if i == N:
            if best_goal is None or g < best_goal[0]:
                best_goal = (g, path)
            break

        expanded += 1
        n = notes[i]
        cands = candidates(n)

        # Hard-filter physics when experimental gap-fill is enabled.
        feasible = []
        for s, fr in cands:
            st = StringState(frets[s], last_pluck[s], last_end[s])
            if is_physically_feasible(st, n, fr):
                feasible.append((s, fr))

        if not feasible:
            # Note unplayable / physically impossible on every string — skip it.
            push(
                g + _heuristic(notes, i + 1, frets),
                g,
                i + 1,
                frets,
                last_pluck,
                last_end,
                path,
            )
            continue

        note_end = float(n.t) + max(0.0, float(n.dur))
        for s, fr in feasible:
            st = StringState(frets[s], last_pluck[s], last_end[s])
            c, _ = transition_cost(st, n, fr)
            new_frets = tuple(fr if k == s else frets[k] for k in range(NUM_STRINGS))
            new_last_pluck = tuple(n.t if k == s else last_pluck[k] for k in range(NUM_STRINGS))
            new_last_end = tuple(note_end if k == s else last_end[k] for k in range(NUM_STRINGS))
            new_g = g + c
            h = _heuristic(notes, i + 1, new_frets)
            push(
                new_g + h,
                new_g,
                i + 1,
                new_frets,
                new_last_pluck,
                new_last_end,
                path + (Assignment(i, s, fr),),
            )

    if best_goal is None:
        # Budget exhausted — return best partial plan found
        if not open_h:
            return []
        # Tuple layout: f, counter, g, i, frets, last_pluck, last_end, path
        best = min(open_h, key=lambda e: (-e[3], e[2]))
        return list(best[7])

    return list(best_goal[1])
