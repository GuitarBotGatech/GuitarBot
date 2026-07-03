from .greedy import plan as greedy
from .lookahead import plan as lookahead
from .viterbi import plan as viterbi
from .beam import plan as beam
from .astar import plan as astar

ALL = {
    "greedy": greedy,
    "lookahead3": lookahead,
    "viterbi": viterbi,
    "beam32": beam,
    "astar": astar,
}
