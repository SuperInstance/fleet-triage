"""policy-ladder-solver -- one solver for the SuperInstance policy ladder.

Extracted from three repos that each wrote their own minimax:

  SuperInstance/connect4/c4.py        negamax over a 7x6 gravity board
  SuperInstance/ga4444/ga4444.py      negamax over a 4x4 free-cell board
  SuperInstance/pie-minimax/minmax.py exact minmax over 3x3 tic-tac-toe

See README.md for the extraction record and the tests that fail without it.
"""
from .connectn import CONNECT4, GA4444, GRAVITY, FREE, ConnectN
from .negamax import SearchResult, negamax, negamax_with_horizon
from .rules import (
    EMPTY, P1, P2, TIC_TAC_TOE_LINES, drop, generated_lines, legal_moves_free,
    legal_moves_gravity, place, player_wins,
)
from .tictactoe import enumerate_reachable, optimal, random_optimal_position, value, winner

__all__ = [
    "ConnectN", "CONNECT4", "GA4444", "GRAVITY", "FREE",
    "SearchResult", "negamax", "negamax_with_horizon",
    "EMPTY", "P1", "P2", "TIC_TAC_TOE_LINES", "generated_lines", "player_wins",
    "legal_moves_free", "legal_moves_gravity", "drop", "place",
    "winner", "value", "optimal", "enumerate_reachable", "random_optimal_position",
]
__version__ = "0.1.0"
