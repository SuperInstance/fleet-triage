"""Exact tic-tac-toe as data, not as a model. The first rung of the policy ladder.

PROVENANCE. Ported from SuperInstance/pie-minimax/minmax.py. The win detector and the
legal-move enumeration are now the shared ones in `rules`; the search below is
pie-minimax's, kept in pie-minimax's sign convention.

NOTE THE SIGN CONVENTION, which differs from ConnectN and is not an oversight.
pie-minimax encodes a board as (-1 them, 0 empty, +1 us) and its `value()` is from
US's perspective on a position where it is our move. ConnectN encodes (0, 1, 2) and
`value()` is from the SIDE TO MOVE. Mixing the two silently inverts every published
number, so they are kept apart, and the shared piece is exactly the part that has no
sign convention in it: `player_wins` and the empty-cell enumeration.

Two bugs from the original are preserved as comments because they are the reason this
file is worth reading: an `respond(play(b, m), m)` that let the opponent overwrite our
own cell, and an `enumerate_reachable` that only ever played as us, so it returned
exactly one state while reporting no error.
"""
from __future__ import annotations

import random
from functools import lru_cache
from typing import Callable, List, Optional, Tuple

from .rules import TIC_TAC_TOE_LINES, legal_moves_free, player_wins

Board = Tuple[int, ...]          # -1 them, 0 empty, +1 us
US, EMPTY = 1, 0

def new_board() -> Board:
    """The empty 3x3. Nine empty cells, us-to-move."""
    return tuple([0] * 9)


def winner(b: Board) -> int:
    """+1 if we have a line, -1 if they do, 0 otherwise. Shared win predicate."""
    if player_wins(b, TIC_TAC_TOE_LINES, 1):
        return 1
    if player_wins(b, TIC_TAC_TOE_LINES, -1):
        return -1
    return 0


def moves(b: Board) -> Tuple[int, ...]:
    """Shared empty-cell enumeration, identical to ga4444's legal_moves in rules.py."""
    return legal_moves_free(b, 3, 3)


def play(b: Board, mv: int) -> Board:
    out = list(b)
    out[mv] = 1
    return tuple(out)


def respond(b: Board, mv: int) -> Board:
    out = list(b)
    out[mv] = -1
    return tuple(out)


def _opponent_best_after(b: Board, m: int) -> int:
    """After WE play m, the opponent takes their best reply. Their best is our worst."""
    if winner(b) == 1:
        return 1
    replies = moves(b)
    if not replies:
        return 0
    return min(value(respond(b, r)) for r in replies)


@lru_cache(maxsize=None)
def value(b: Board) -> int:
    """+1 we win with perfect play, 0 draw, -1 we lose. Exact, and it is OUR turn.

    The first version of this had `respond(play(b, m), m)` -- which let the opponent
    replay OUR OWN cell and overwrite our move. It returned -1 for the empty board, which
    is the classic tic-tac-toe draw, and would have poisoned every number measured against
    it. The ground truth has to be right or the whole exercise is measuring my typo.
    """
    w = winner(b)
    if w:
        return w
    legal = moves(b)
    if not legal:
        return 0
    return max(_opponent_best_after(play(b, m), m) for m in legal)


@lru_cache(maxsize=None)
def optimal(b: Board) -> Tuple[int, ...]:
    """The set of optimal moves -- a SET, not a choice.

    Several moves are frequently equally correct. A training set that picks one of them
    relabels the others as mistakes, and then you spend your budget teaching a model to
    avoid correct play.
    """
    w = winner(b)
    if w or not moves(b):
        return ()
    vals = {m: _opponent_best_after(play(b, m), m) for m in moves(b)}
    best = max(vals.values())
    return tuple(m for m, v in vals.items() if v == best)


def board_our_turn(b: Board) -> bool:
    """Only positions where it is our move -- the states a model would ever be asked about."""
    return bool(moves(b)) and b.count(1) == b.count(-1)


def enumerate_reachable(max_plies: int = 9) -> List[Tuple[Board, Tuple[int, ...]]]:
    """Every position reachable with US to move, together with its exact optimal set.

    The walk alternates players. The first version only ever played as us, which filled
    the board with +1s, meant it was never our turn past the opening, and returned exactly
    one state -- the empty board -- while reporting no error. A walk that only explores
    one side of the tree is not a smaller result, it is a wrong one.
    """
    out: List[Tuple[Board, Tuple[int, ...]]] = []

    def walk(b: Board, plies: int, our_turn: bool) -> None:
        if plies > max_plies:
            return
        if winner(b) or not moves(b):
            return
        if our_turn:
            opt = optimal(b)
            if opt:
                out.append((b, opt))
        step = play if our_turn else respond
        for m in moves(b):
            walk(step(b, m), plies + 1, not our_turn)

    walk(tuple([0] * 9), 0, True)
    return out


def random_optimal_position(rng: Optional[random.Random] = None) -> Tuple[Board, Tuple[int, ...]]:
    """Sample a position we can actually face, with its optimal set."""
    rng = rng or random.Random()
    pos = enumerate_reachable()
    return pos[rng.randrange(len(pos))]


LADDER = [
    ("rung 1", "pie-minimax",  "tic-tac-toe", "exact policy computed by minmax"),
    ("rung 2", "connect4",     "connect 4 on 7x6", "exact to the search horizon"),
    ("rung 3", "ga4444",       "connect 4 on 4x4", "complete ground truth, free-cell"),
    ("rung 4", "ladder",       "the ladder itself", "adversarial reading of the rungs"),
]
