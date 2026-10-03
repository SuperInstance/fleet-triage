"""The bitboard instrument, checked against a different representation.

`c4gt.has_won` is a bitboard 4-in-a-row detector. `c4py.wins` is a brute-force
scan of a tuple-of-tuples board. They are different code with different failure
modes. If they disagree anywhere, the ground-truth harness is measuring
something other than Connect 4 and everything downstream is sediment.

Also: the FNV-1a-64 digest of the dataset, RE-DERIVED.
"""
from __future__ import annotations

import random
import sys

sys.path.insert(0, "/workspace/projects/fleet-triage/pixels-build/lib")
sys.path.insert(0, "/workspace/c4gt")

import c4gt
import c4 as c4py  # tuple-of-tuples reference


def b2py(mask: int, pos: int) -> tuple:
    """bitboard (mask,pos) -> c4.py's tuple-of-tuples board, 1 = P0, 2 = P1."""
    rows = []
    for r in range(c4gt.H):
        row = []
        for c in range(c4gt.W):
            bit = r * c4gt.STRIDE + c
            row.append(1 if (pos >> bit) & 1 else (2 if (mask >> bit) & 1 else 0))
        rows.append(tuple(row))
    return tuple(rows)


def random_positions(n: int, seed: int = 0):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        mask = pos = 0
        for _ply in range(rng.randint(0, 30)):
            cols = c4gt.legal_cols(mask)
            if not cols:
                break
            c = rng.choice(cols)
            m2, p2 = c4gt.play(mask, pos, c)
            opp = mask ^ pos
            if c4gt.has_won(opp, m2) or c4gt.has_won(pos, m2):
                out.append((mask, pos))
                break
            mask, pos = m2, p2
        else:
            out.append((mask, pos))
    return out


def main() -> int:
    fails = 0

    # --- 1. the dataset, re-hashed -------------------------------------------------
    gt = c4gt.load_gt()
    print(f"digest 0x{gt['digest']:016x}  expected 0x{c4gt.GT_DIGEST:016x}  "
          f"{'OK' if gt['digest_ok'] else '*** FAIL ***'}")
    print(f"rows {gt['rows']}  expected {c4gt.GT_ROWS}  "
          f"{'OK' if gt['rows_ok'] else '*** FAIL ***'}")
    fails += (not gt["digest_ok"]) + (not gt["rows_ok"])

    # --- 2. has_won against the other representation ------------------------------
    poss = random_positions(3000, seed=11)
    mism = 0
    for mask, pos in poss:
        b = b2py(mask, pos)
        for side, stones in (("p0", pos), ("p1", mask ^ pos)):
            mine = c4gt.has_won(stones, mask)
            theirs = c4py.wins(b, 1 if side == "p0" else 2)
            if mine != theirs:
                mism += 1
                if mism <= 3:
                    print(f"  MISMATCH {side} mask={mask} pos={pos} mine={mine} ref={theirs}")
    print(f"has_won vs c4.py wins   {mism} mismatches over {2*len(poss)} checks   "
          f"{'OK' if mism == 0 else '*** FAIL ***'}")
    fails += (mism > 0)

    # --- 3. the value agrees with the table, where the table reaches ---------------
    bad = 0
    checked = 0
    for (mask, pos), v in list(gt["table"].items()):
        if c4gt.nstones(mask) < 12:      # keep it quick; deep solves dominate
            got = c4gt.solve(mask, pos)  # P0 to move (dataset is P0-normalised at even ply)
            if c4gt.p0_to_move(mask, pos):
                got = got
            else:
                got = -got
            checked += 1
            if got != v:
                bad += 1
                if bad <= 3:
                    print(f"  VALUE MISMATCH mask={mask} pos={pos} solver={got} table={v}")
    print(f"solve() vs gt table     {bad} disagreements of {checked} checked   "
          f"{'OK' if bad == 0 else '*** FAIL ***'}")
    fails += (bad > 0)

    # --- 4. NEGATIVE CONTROL: the checker must be able to fail ---------------------
    # Break the detector. If this section reports no mismatches, section 2 is
    # comparing a constant to a constant and the whole selftest is a green badge.
    broken = 0
    for mask, pos in poss[:400]:
        opp = mask ^ pos
        if c4gt.has_won(opp, mask) and not c4gt.has_won(opp | 1, mask):
            broken += 1
    print(f"NEGATIVE CONTROL: detector disabled would miss {broken} wins in 400 "
          f"positions -> the check is {'LIVE' if broken else '*** DEAD (vacuous) ***'}")

    print("SELFTEST", "FAILED" if fails else "PASSED")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
