"""Viterbi DP over joint per-string state, pruned to top-K per layer.

State = (frets: 6-tuple, last_t: 6-tuple-rounded). Transition cost uses the
real per-string last-pluck time. Pruning keeps best 128 unique states per note.
"""
from ..model import (
    Note, Assignment, StringState, NUM_STRINGS,
    candidates, transition_cost, apply,
)

TOPK = 128


def plan(notes: list[Note]) -> list[Assignment]:
    N = len(notes)
    if N == 0:
        return []

    # Each layer: list of (cost, frets_tuple, last_t_tuple, backpointer_index, assignment)
    init_frets = (0,) * NUM_STRINGS
    init_lastt = (-1e9,) * NUM_STRINGS
    layers: list[list[tuple]] = []

    # Layer 0
    n0 = notes[0]
    layer0 = []
    for s, f in candidates(n0.pitch) or [(None, None)]:
        if s is None:
            cost = 0.0
            frets = init_frets; lastt = init_lastt
            assign = None
        else:
            st = StringState(init_frets[s], init_lastt[s])
            c, _ = transition_cost(st, n0, f)
            cost = c
            frets = tuple(f if i == s else init_frets[i] for i in range(NUM_STRINGS))
            lastt = tuple(n0.t if i == s else init_lastt[i] for i in range(NUM_STRINGS))
            assign = Assignment(0, s, f)
        layer0.append((cost, frets, lastt, -1, assign))
    layers.append(_prune(layer0))

    for i in range(1, N):
        n = notes[i]
        cands = candidates(n.pitch)
        new_layer = []
        prev_layer = layers[-1]
        for pidx, (pcost, pfrets, plastt, _, _) in enumerate(prev_layer):
            if not cands:
                new_layer.append((pcost, pfrets, plastt, pidx, None))
                continue
            for s, f in cands:
                st = StringState(pfrets[s], plastt[s])
                c, _ = transition_cost(st, n, f)
                frets = tuple(f if k == s else pfrets[k] for k in range(NUM_STRINGS))
                lastt = tuple(n.t if k == s else plastt[k] for k in range(NUM_STRINGS))
                new_layer.append((pcost + c, frets, lastt, pidx, Assignment(i, s, f)))
        layers.append(_prune(new_layer))

    # Backtrack
    last = min(range(len(layers[-1])), key=lambda j: layers[-1][j][0])
    out: list[Assignment] = []
    i = len(layers) - 1
    idx = last
    while i >= 0:
        cost, frets, lastt, back, assign = layers[i][idx]
        if assign is not None:
            out.append(assign)
        idx = back
        i -= 1
        if idx < 0:
            break
    out.reverse()
    return out


def _prune(layer: list[tuple]) -> list[tuple]:
    # dedupe by (frets, lastt) keeping min cost, then keep top-K
    best = {}
    for entry in layer:
        key = (entry[1], entry[2])
        if key not in best or best[key][0] > entry[0]:
            best[key] = entry
    items = sorted(best.values(), key=lambda e: e[0])[:TOPK]
    return items
