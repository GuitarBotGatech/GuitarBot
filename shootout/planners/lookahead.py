from ..model import Note, Assignment, StringState, NUM_STRINGS, candidates, transition_cost, apply

K = 3


def _rollout_cost(states: list[StringState], notes: list[Note], start: int, depth: int) -> float:
    if depth == 0 or start >= len(notes):
        return 0.0
    n = notes[start]
    cands = candidates(n.pitch)
    if not cands:
        return _rollout_cost(states, notes, start + 1, depth - 1)
    best = float("inf")
    for s, f in cands:
        c, _ = transition_cost(states[s], n, f)
        new_states = list(states)
        new_states[s] = apply(states[s], n, f)
        total = c + _rollout_cost(new_states, notes, start + 1, depth - 1)
        if total < best:
            best = total
    return best


def plan(notes: list[Note]) -> list[Assignment]:
    states = [StringState() for _ in range(NUM_STRINGS)]
    out: list[Assignment] = []
    for i, n in enumerate(notes):
        cands = candidates(n.pitch)
        if not cands:
            continue
        best_choice = None
        best_cost = float("inf")
        for s, f in cands:
            c, _ = transition_cost(states[s], n, f)
            new_states = list(states)
            new_states[s] = apply(states[s], n, f)
            total = c + _rollout_cost(new_states, notes, i + 1, K - 1)
            if total < best_cost:
                best_cost = total
                best_choice = (s, f)
        s, f = best_choice
        states[s] = apply(states[s], n, f)
        out.append(Assignment(i, s, f))
    return out
