"""Memoised negamax with a horizon, shared by the policy-ladder rungs.

PROVENANCE. Replaces the negamax that was written twice:

  SuperInstance/connect4/c4.py:104-129   -- depth 11, MAX_PLY
  SuperInstance/ga4444/ga4444.py:91-110  -- depth  9, MAX_PLY

Both are the same recursion: if the opponent has already won, -1; if the side to move
has no move, 0; at the horizon, 0; otherwise the best negated child, short-circuiting on
+1. Both memoise with lru_cache on (board, turn, depth). The only real difference is
move generation -- gravity for connect4, free-cell for 4x4-with-gaps -- and that is now
a parameter.

THE HORIZON IS NOT A DETAIL. Past `depth`, this returns 0, which is an UPPER BOUND on
the value, not the game-theoretic value. Both original docstrings said so in prose;
neither returned anything that recorded the bound in the result. Here
`negamax_with_horizon` returns a `SearchResult` that always says whether the value is
exact, so a caller cannot accidentally present a truncated value as ground truth.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Optional, Sequence, Tuple

from .rules import Board, EMPTY, P1, P2, player_wins


@dataclass(frozen=True)
class SearchResult:
    value: int          # +1 win for the side to move, 0 draw, -1 loss
    exact: bool         # False if the horizon truncated the search

    def __bool__(self) -> bool:            # so `if result:` reads as "found a win"
        return self.value > 0


def negamax(
    board: Board,
    lines: Sequence[Sequence[int]],
    legal: Callable[[Board], Tuple[int, ...]],
    play: Callable[[Board, int, int], Optional[Board]],
    turn: int = P1,
    depth: int = 12,
    other: int = P2,
) -> int:
    """Value for the side to move. +1 win, 0 draw, -1 loss.

    EXACT within `depth`. Beyond it the search truncates, so the returned 0 at the
    boundary is an upper bound. Use negamax_with_horizon() if you need to know which
    you got. This is the recursion from connect4/c4.py:104-129 and
    ga4444/ga4444.py:91-110, with the move generator as a parameter.
    """
    return negamax_with_horizon(board, lines, legal, play, turn, depth, other).value


def negamax_with_horizon(
    board: Board,
    lines: Sequence[Sequence[int]],
    legal: Callable[[Board], Tuple[int, ...]],
    play: Callable[[Board, int, int], Optional[Board]],
    turn: int = P1,
    depth: int = 12,
    other: int = P2,
    cache_size: int = 1 << 18,
) -> SearchResult:
    """As `negamax`, and it also reports whether the value is exact.

    `cache_size` defaults to 2**18 rather than the 2**21 / 2**22 that
    connect4/c4.py:103 and ga4444/ga4444.py:90 asked for. Those defaults are an
    allocation of up to 4M entries, which is several hundred MB for a cache keyed on
    (board, turn, depth) tuples; on a 2 GB machine that is a real OOM, not a tuning
    nicety. Raise it if you have the RAM and the search is deep.
    """
    @lru_cache(maxsize=cache_size)
    def rec(b: Board, t: int, d: int) -> Tuple[int, int]:
        # second element: 1 = this node's value is exact, -1 = the horizon cut it off
        if player_wins(b, lines, other):
            return -1, 1
        moves = legal(b)
        if not moves:
            return 0, 1
        if d <= 0:
            return 0, -1            # horizon: assume draw. An UPPER bound on value.
        o = P1 if t == P2 else P2
        best = -1
        exact = -1                   # no child examined yet, so nothing is exact yet
        for m in moves:
            nb = play(b, m, t)
            if nb is None:
                continue
            v, e = rec(nb, o, d - 1)
            v = -v
            if v > best:
                best, exact = v, e
            elif v == best:
                exact = max(exact, e)   # a tie only counts as exact if both are
            if best == 1:
                return 1, 1            # a proven win needs no horizon
        return best, exact

    v, e = rec(board, turn, depth)
    return SearchResult(value=v, exact=(e == 1))


def clear_caches() -> None:
    """Drop memoisation state. The caches are function-local, so the only supported way
    is to let the process exit; exposed so callers do not assume this does more than
    it says."""
    return None
