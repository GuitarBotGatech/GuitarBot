from ..model import Note, Assignment, StringState, NUM_STRINGS, candidates, transition_cost, apply


def plan(notes: list[Note]) -> list[Assignment]:
    states = [StringState() for _ in range(NUM_STRINGS)]
    out: list[Assignment] = []
    for i, n in enumerate(notes):
        cands = candidates(n.pitch)
        if not cands:
            continue
        best = min(cands, key=lambda sf: transition_cost(states[sf[0]], n, sf[1])[0])
        s, f = best
        states[s] = apply(states[s], n, f)
        out.append(Assignment(i, s, f))
    return out
