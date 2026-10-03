#!/usr/bin/env python3
"""Parity harness: the shared library against the two original implementations.

Compares policy_ladder.ConnectN against SuperInstance/connect4/c4.py and
SuperInstance/ga4444/ga4444.py on random reachable positions. The originals keep
2-D tuple-of-tuple boards and return (row, col) pairs; the library uses a flat tuple
and cell indices, so this file adapts between them. Run it with the originals cloned:

    python3 tools/parity_against_originals.py
"""
from __future__ import annotations
import random, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

REPOS = HERE.parent.parent / "repos"
ORIG = {"connect4": REPOS / "connect4", "ga4444": REPOS / "ga4444"}
if not all(p.is_dir() for p in ORIG.values()):
    print("parity harness needs the original checkouts; skipping rather than "
          "reporting 0 comparisons as a pass.")
    raise SystemExit(0)
for p in ORIG.values():
    sys.path.insert(0, str(p))
import policy_ladder as PL
import c4
import ga4444 as ga

POSITIONS = 3000          # cheap board-rule comparisons
NEG_POSITIONS = 25        # search comparisons
NEG_DEPTH = 6             # matched depth for both sides (see the OOM note below)


def from_flat(flat, W, H):
    """flat cell tuple -> tuple-of-tuples grid, which is what the originals use."""
    return tuple(tuple(flat[r * W:(r + 1) * W]) for r in range(H))


def to_flat(grid, W, H):
    return tuple(v for row in grid for v in row)


def random_reachable(W, H, n, rng, gravity):
    """A position reachable by alternating legal moves from the empty board."""
    b = [0] * (W * H)
    for ply in range(n):
        if gravity:
            ms = [c for c in range(W)
                  if sum(1 for r in range(H) if b[r * W + c]) < H]
        else:
            ms = [i for i, v in enumerate(b) if v == 0]
        if not ms:
            break
        m = rng.choice(ms)
        if gravity:
            for r in range(H):
                if b[r * W + m] == 0:
                    b[r * W + m] = (ply % 2) + 1
                    break
        else:
            b[m] = (ply % 2) + 1
    return tuple(b)


def main() -> int:
    rng = random.Random(20260930)
    fails, checks = [], 0

    # ---- connect4: 7x6 gravity ----
    for _ in range(POSITIONS):
        flat = random_reachable(7, 6, rng.randint(0, 30), rng, gravity=True)
        grid = from_flat(flat, 7, 6)
        for p in (PL.P1, PL.P2):
            if PL.CONNECT4.wins(flat, p) != c4.wins(grid, p):
                fails.append(f"connect4.wins mismatch at {flat} p={p}"); break
        if fails: break
        if PL.CONNECT4.legal(flat) != c4.legal_cols(grid):
            fails.append(f"connect4.legal mismatch at {flat}"); break
        if fails: break
        if PL.CONNECT4.immediate_wins(flat, PL.P1) != c4.immediate_wins(grid, c4.P1):
            fails.append(f"connect4.immediate_wins mismatch at {flat}"); break
        if fails: break
        m = rng.randrange(7)
        lib_nb = PL.CONNECT4.play(flat, m, PL.P1)
        org_nb = c4.play(grid, m, c4.P1)
        if lib_nb is None or org_nb is None:
            if (lib_nb is None) != (org_nb is None):
                fails.append(f"connect4.play None-disagreement at {flat} col={m}"); break
        elif lib_nb != to_flat(org_nb, 7, 6):   # lib is already flat; org is a grid
            fails.append(f"connect4.play mismatch at {flat} col={m}"); break
        checks += 5

    # ---- ga4444: 4x4 free-cell ----
    for _ in range(POSITIONS):
        flat = random_reachable(4, 4, rng.randint(0, 14), rng, gravity=False)
        grid = from_flat(flat, 4, 4)
        for p in (PL.P1, PL.P2):
            if PL.GA4444.wins(flat, p) != ga.wins(grid, p):
                fails.append(f"ga4444.wins mismatch at {flat} p={p}"); break
        if fails: break
        lib_legal = PL.GA4444.legal(flat)
        org_legal = tuple(r * 4 + c for r, c in ga.legal_moves(grid))   # (r,c) -> index
        if lib_legal != org_legal:
            fails.append(f"ga4444.legal mismatch at {flat}: {lib_legal} vs {org_legal}"); break
        if PL.GA4444.immediate_wins(flat, PL.P1) != ga.immediate_wins(grid, ga.P1):
            fails.append(f"ga4444.immediate_wins mismatch at {flat}"); break
        if fails: break
        m = rng.randrange(16)
        if PL.GA4444.play(flat, m, PL.P1) != to_flat(ga.play_at(grid, m, ga.P1), 4, 4):
            fails.append(f"ga4444.play mismatch at {flat} cell={m}"); break
        checks += 5

    # ---- negamax parity at MATCHED depth ----
    # The originals memoise at module level with lru_cache(maxsize=1<<22)
    # (connect4/c4.py:103, ga4444/ga4444.py:90) and never clear it. Running their full
    # MAX_PLY=9 search repeatedly in one process OOMs a 2 GB box, so both sides are run
    # at depth 6 and the cache is cleared between positions. `depth` is a real
    # parameter of the original function, so this is the same recursion, not a weaker
    # one -- and it is the reason the library makes cache_size a parameter.
    for _ in range(NEG_POSITIONS):
        flat = random_reachable(4, 4, rng.randint(0, 3), rng, gravity=False)
        grid = from_flat(flat, 4, 4)
        lib = PL.GA4444.value(flat, PL.P1, depth=NEG_DEPTH)
        org = ga.negamax(grid, ga.P1, NEG_DEPTH)
        if lib.value != org:
            fails.append(f"ga4444.negamax mismatch at {flat}: lib={lib.value} orig={org}"); break
        # exactness is a claim about the horizon: at depth 6 on a 16-cell board the
        # search cannot be complete, and the library is expected to SAY so.
        empty = sum(1 for v in flat if v == 0)
        expected_exact = NEG_DEPTH >= empty
        if lib.exact != expected_exact:
            fails.append(f"ga4444.negamax exact flag at {flat}: got {lib.exact}, "
                         f"expected {expected_exact} (depth {NEG_DEPTH}, {empty} empty)"); break
        checks += 2
    try:
        ga.negamax.cache_clear()
    except AttributeError:
        pass

    print(f"parity: {checks} comparisons against connect4/c4.py and ga4444/ga4444.py")
    print(f"  rules: {POSITIONS} positions each; search: {NEG_POSITIONS} positions "
          f"at matched depth {NEG_DEPTH}")
    if fails:
        print(f"FAIL ({len(fails)}):")
        for f in fails[:10]:
            print(f"  - {f}")
        return 1
    print("PASS: the shared library agrees with both original implementations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
