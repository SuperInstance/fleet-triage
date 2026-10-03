"""Board rules shared by the policy-ladder rungs.

PROVENANCE. Written for policy-ladder-solver, replacing the win detector that was
independently implemented in two places:

  SuperInstance/connect4/c4.py:62-83   -- `wins()`, with the run length HARD-CODED to 4
  SuperInstance/ga4444/ga4444.py:44-63 -- `wins()`, with K as a module constant

Both are the same algorithm: scan each column top-to-bottom, each row left-to-right,
then both diagonals, counting a run and reporting a win at length K. `connect4`'s copy
wrote `n == 4` where `ga4444`'s wrote `n == K`, which is the only difference between
them -- and it is a difference that matters, because the hardcoded version silently
answers "no win" for every K other than 4. Here K is a parameter of the board.

A board is a flat tuple of ints: 0 empty, 1 first player, 2 second player. Winning is
"some line in `lines` is entirely `player`". That one definition covers both a 3x3
tic-tac-toe board (8 hand-written lines) and an RxC connect-N board (every straight run
of length K), which is the whole reason these two games could share a solver.
"""
from __future__ import annotations
from typing import Iterable, Sequence, Tuple

EMPTY, P1, P2 = 0, 1, 2
Board = Tuple[int, ...]

# The eight tic-tac-toe lines, as flat cell indices. Identical to the LINES tuple in
# SuperInstance/pie-minimax/minmax.py:24-29.
TIC_TAC_TOE_LINES: Tuple[Tuple[int, ...], ...] = (
    (0, 1, 2), (3, 4, 5), (6, 7, 8),      # rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),      # cols
    (0, 4, 8), (2, 4, 6),                  # diagonals
)


def generated_lines(width: int, height: int, k: int) -> Tuple[Tuple[int, ...], ...]:
    """Every straight run of `k` cells in a width x height board, 4 directions.

    A run only counts if it fits entirely on the board, so on a 4x4 board at k=4 there
    are 2 rows + 2 columns + 2 main diagonals and nothing else.
    """
    if k < 1:
        raise ValueError("k must be >= 1")
    if k > max(width, height):
        return ()
    out = []
    for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
        for r in range(height):
            for c in range(width):
                cells = tuple((r + i * dr) * width + (c + i * dc) for i in range(k))
                if all(0 <= (r + i * dr) < height and 0 <= (c + i * dc) < width
                       for i in range(k)):
                    out.append(cells)
    return tuple(out)


def player_wins(board: Board, lines: Sequence[Sequence[int]], player: int) -> bool:
    """True iff `player` occupies every cell of some line.

    This is the single win predicate for the whole ladder. It is the code that
    connect4/c4.py:62-83 and ga4444/ga4444.py:44-63 each wrote for themselves.
    """
    return any(all(board[i] == player for i in line) for line in lines)


def legal_moves_gravity(board: Board, width: int, height: int) -> Tuple[int, ...]:
    """Columns that are not yet full, in a gravity (connect-4) board.

    Same rule as connect4/c4.py:48-50 via heights(), and as ga4444/ga4444.py:31-32.
    """
    out = []
    for c in range(width):
        occupied = sum(1 for r in range(height) if board[r * width + c] != EMPTY)
        if occupied < height:
            out.append(c)
    return tuple(out)


def legal_moves_free(board: Board, width: int, height: int) -> Tuple[int, ...]:
    """Every empty cell, for a game that may place anywhere (4x4 with gaps).

    ga4444/ga4444.py:71-89 carries a comment saying a column-only enumeration would
    miss legal positions and quietly shrink the dataset. This is that enumeration.
    """
    return tuple(i for i, v in enumerate(board) if v == EMPTY)


def drop(board: Board, col: int, player: int, width: int, height: int) -> Board | None:
    """Place `player` at the lowest empty cell of `col`. None if the column is full."""
    out = list(board)
    for r in range(height):
        i = r * width + col
        if out[i] == EMPTY:
            out[i] = player
            return tuple(out)
    return None


def place(board: Board, cell: int, player: int) -> Board:
    out = list(board)
    out[cell] = player
    return tuple(out)
