"""Connect-4 ground truth loader + exact labels, SET-VALUED.

The dataset: /workspace/c4gt/c4_ground_truth.txt, 54,166 rows, plies 1..6,
FNV-1a-64 digest 0x4ef8351a5c319637 (REPRODUCED HERE, not copied from the doc).

Row shape, read off ctool.c:337 `emit(mask, pos, value)` and normalised at
ctool.c:378-383 to PLAYER ZERO:

    col0 mask   column occupancy incl. sentinel bits
    col1 pos    P0's stones only
    col2 value  the FULL-SOLVE game value from P0's point of view, +1/0/-1

THE LABEL IS A SET, NOT A MOVE. A move is correct iff the value of the position
it produces equals the value of the best position available. Every move that
preserves the value is in the optimal set, and at plies 1..6 that set routinely
has more than one member. Scoring against one arbitrary "best" move is the bug
this module exists to prevent.
"""
from __future__ import annotations

import functools
import os
import sys

W, H, STRIDE = 7, 6, 7
COL_PLAY = tuple((0x3F << (c * STRIDE)) for c in range(W))
# ctool.c:96  static const Board BOTTOM_BITS = 0x0002040810204081  bits 0,7,14,21,28,35,42
# I first typed 0x0102040810204081 -- one digit short. Every bit below 42 was correct and
# the three above were garbage, so top_mask() carried into the wrong columns, a "move"
# could leave the mask unchanged, and the search recursed forever. No crash, no wrong
# answer: just no answer. Same shape as the two traps ctool.c documents in its own header.
BOTTOM = 0x0002040810204081
FULL49 = 0x1FF_FFFF_FFFF_FFFF

sys.setrecursionlimit(20000)

GT_PATH = "/workspace/c4gt/c4_ground_truth.txt"
GT_DIGEST = 0x4EF8351A5C319637
GT_ROWS = 54166


def fnv1a64(b: bytes) -> int:
    h = 0xCBF29CE484222325
    for x in b:
        h = ((h ^ x) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def top_mask(mask: int) -> int:
    """ctool.c:99 -- top_mask(b) = b + BOTTOM_BITS. NOT (b+BOTTOM)&b; the AND version
    returns the empty square of an empty column as "no move", and the empty board is
    the position you are most often asked about."""
    return mask + BOTTOM


def drop_bit(mask: int, c: int) -> int:
    """The single empty square at the top of column `c`. 0 if that column is full.

    ctool.c:103  top(b,c) = b + (1 << (c*STRIDE + height_of(b,c))).
    NOT top_mask(b), which is all seven column tops at once -- using it here made the
    FIRST move drop seven stones, which then won instantly, which made solve(0,0)
    return +1 and would have made the whole harness agree with a wrong ground truth.
    """
    if not can_play(mask, c):
        return 0
    return (mask + (1 << (c * STRIDE + height_of(mask, c)))) & ~mask & FULL49


def height_of(mask: int, c: int) -> int:
    return bin((mask >> (c * STRIDE)) & 0x3F).count("1")


def is_playable(mask: int, c: int) -> bool:
    return not (mask & (1 << (c * STRIDE + H)))


def can_play(mask: int, c: int) -> bool:
    return (mask & COL_PLAY[c]) != COL_PLAY[c]


def has_won(pos: int, mask: int) -> bool:
    """Four in a row: horizontal, vertical, two diagonals. Sentinel-safe.

    The 4-in-a-row detector is a fixed function of the opponent's stone set. It
    is CROSS-CHECKED against /workspace/c4gt/c4.py `wins()` (a completely
    different representation -- tuple of tuples, brute-force scan) on every
    position the harness plays, by selftest.py. A bitboard win check that is
    wrong in a direction which never fires produces a metric that never fires,
    and that is indistinguishable from a good one at the console.
    """
    for d in (1, STRIDE, STRIDE + 1, STRIDE - 1):
        q = pos & (pos >> d) & (pos >> (2 * d)) & (pos >> (3 * d))
        while q:
            low = q & -q
            q ^= low
            anchor = low.bit_length() - 1          # lowest set bit = start of the run
            for k in range(4):
                bit = anchor + k * d
                if bit < 0 or bit > 48:
                    break
                if not (mask >> bit) & 1:         # a non-playable cell -> vertical wrap
                    break
            else:
                return True
    return False


def nstones(mask: int) -> int:
    """Occupied cells, sentinels excluded. `bin(mask).count('1')` is WRONG here."""
    return sum(bin((mask >> (c * STRIDE)) & 0x3F).count("1") for c in range(W))


def p0_to_move(mask: int, pos: int) -> bool:
    return nstones(mask) == bin(pos).count("1")


def legal_cols(mask: int) -> tuple:
    return tuple(c for c in range(W) if can_play(mask, c))


def play(mask: int, pos: int, c: int) -> tuple:
    """Play a stone of the side to move. `pos` is the MOVER's stone set for this call.

    ctool.c keeps (mask, pos) in "opponent of the mover" convention inside the search
    and only normalises to P0 at export time. The harness uses the same convention:
    solve() takes the stones of the side to move. One convention, stated once, so the
    normalisation bug ctool.c:358-383 documents cannot be reintroduced downstream.
    """
    t = drop_bit(mask, c)
    if not t:
        return (mask, pos)
    return (mask | t, pos | t)


@functools.lru_cache(maxsize=1 << 20)
def solve(mask: int, pos: int, depth: int = 0) -> int:
    """Full-depth exact value for the side to move. +1 win, 0 draw, -1 loss."""
    opp = mask ^ pos
    if has_won(opp, mask):
        return -1
    if not legal_cols(mask):
        return 0
    best = -1
    for c in (3, 2, 4, 1, 5, 0, 6):
        if not can_play(mask, c):
            continue
        t = drop_bit(mask, c)
        if not t:
            continue
        m2 = mask | t
        if has_won(pos | t, m2):
            return 1
        v = -solve(m2, opp, depth + 1)
        if v > best:
            best = v
            if best == 1:
                return 1
    return best


@functools.lru_cache(maxsize=1)
def load_gt(path: str = GT_PATH) -> dict:
    """(mask,pos) -> P0-perspective exact value, plus the digest proof."""
    with open(path, "rb") as fh:
        raw = fh.read()
    digest = fnv1a64(raw)
    table = {}
    n = 0
    for line in raw.decode().splitlines():
        if not line.strip():
            continue
        a, b, v = line.split()
        table[(int(a), int(b))] = int(v)
        n += 1
    return {
        "table": table,
        "digest": digest,
        "digest_ok": digest == GT_DIGEST,
        "rows": n,
        "rows_ok": n == GT_ROWS,
    }


def value_p0(mask: int, pos: int, gt: dict) -> int:
    """Exact value for P0 in this position.

    GT table first (plies 1..6, full solve). Beyond ply 6 the table does not
    reach, so we fall back to the in-process exact solver and SAY SO -- the
    caller records which instrument produced the number.
    """
    v = gt["table"].get((mask, pos))
    if v is not None:
        return v, "gt-table"
    return solve(mask, pos), "live-solver"


def optimal_set(mask: int, pos: int, gt: dict) -> tuple:
    """THE SET of moves that do not lose value. This is the label.

    A move is in the set iff value(child) == value(parent) from the mover's
    point of view. Ties are members, not errors. The size of this set is the
    number the "did it play well" metric has to be normalised by.
    """
    v, src = value_p0(mask, pos, gt)
    turn = p0_to_move(mask, pos)
    best = v if turn else -v                 # value for the side to move
    keep = []
    for c in legal_cols(mask):
        m2, p2 = play(mask, pos, c)
        if turn:
            w, _ = value_p0(m2, p2, gt)
        else:
            # P1 moved. The child is stored P0-normalised with pos2 = p2' = m2 ^ p1.
            w, _ = value_p0(m2, m2 ^ p2, gt)
            w = -w
        if w == best:
            keep.append(c)
    return tuple(keep), best, src
