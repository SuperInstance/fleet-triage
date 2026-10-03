"""Connect-N boards: gravity (7x6) or free-cell (4x4), with K as a real parameter.

PROVENANCE. Replaces the board + win + search layer of both
SuperInstance/connect4/c4.py and SuperInstance/ga4444/ga4444.py.

The parameterisation is the point. connect4/c4.py:62-83 tested `n == 4` inline, so its
wins() could only ever be right about four-in-a-row; ga4444/ga4444.py:44-63 tested
`n == K`, which is right but where K was still a module constant, so the two files
could not be reconciled without editing one of them. `ConnectN` takes K per instance.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple

from .negamax import SearchResult, negamax_with_horizon
from .rules import Board, EMPTY, P1, P2, drop, generated_lines, legal_moves_free, legal_moves_gravity, place, player_wins

GRAVITY, FREE = "gravity", "free"


@dataclass(frozen=True)
class ConnectN:
    width: int
    height: int
    k: int = 4
    mode: str = GRAVITY

    def __post_init__(self):
        if self.mode not in (GRAVITY, FREE):
            raise ValueError(f"mode must be GRAVITY or FREE, got {self.mode!r}")
        if min(self.width, self.height, self.k) < 1:
            raise ValueError("width, height and k must all be >= 1")

    @property
    def lines(self) -> Tuple[Tuple[int, ...], ...]:
        return generated_lines(self.width, self.height, self.k)

    def new_board(self) -> Board:
        return tuple([EMPTY] * (self.width * self.height))

    def legal(self, board: Board) -> Tuple[int, ...]:
        if self.mode == GRAVITY:
            return legal_moves_gravity(board, self.width, self.height)
        return legal_moves_free(board, self.width, self.height)

    def play(self, board: Board, move: int, player: int) -> Optional[Board]:
        if self.mode == GRAVITY:
            return drop(board, move, player, self.width, self.height)
        return place(board, move, player)

    def wins(self, board: Board, player: int) -> bool:
        return player_wins(board, self.lines, player)

    def immediate_wins(self, board: Board, player: int) -> Tuple[int, ...]:
        """Every move that wins outright right now."""
        return tuple(m for m in self.legal(board)
                     if (nb := self.play(board, m, player)) is not None and self.wins(nb, player))

    def value(self, board: Board, turn: int = P1, depth: int = 12) -> SearchResult:
        return negamax_with_horizon(board, self.lines, self.legal, self.play, turn, depth)

    def value_for_p1(self, board: Board, depth: int = 12) -> SearchResult:
        return self.value(board, P1, depth)

    def to_grid(self, board: Board) -> Tuple[Tuple[int, ...], ...]:
        return tuple(tuple(board[r * self.width:(r + 1) * self.width])
                     for r in range(self.height))


# The two boards this library was extracted from, as named instances.
CONNECT4 = ConnectN(7, 6, 4, GRAVITY)      # SuperInstance/connect4
GA4444 = ConnectN(4, 4, 4, FREE)          # SuperInstance/ga4444
