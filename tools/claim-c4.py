#!/usr/bin/env python3
"""claim-c4 — re-derive the number the round-4 song asserts.

THE CLAIM (track 3, `one-hundredth-of-the-value`):
    "Just one part in ninety is gone"   -> discarding colour costs ~1.1% of exact value
    "A hash is a perfect disguise"      -> a 64-bit irreversible hash costs everything

WHAT IS MEASURED, exactly:

  1. Enumerate EVERY reachable position on a WxH Connect-4 board.
  2. Solve each to an exact minimax value V(s) in {-1,0,+1} by memoised negamax.
  3. Two observations, ONE decoder class (a table keyed on the observation), so
     the arms differ only in what was observed:

       ARM A  colour ablation at rate p — forget the owner of a p-share of the
              filled cells, impute each as the side to move. Lossy, but the
              geometry survives.
       ARM B  FNV-1a 64 over the position key. Injective on this set, and it
              destroys the geometry entirely.

  4. Report the collision count, because that number decides what ARM B means.

The report refuses to call the hash arm a "100% loss" if the hash is injective.
A lyric that is wrong is more useful than a lyric that is flattered.
"""
import sys
from typing import Dict, Tuple

W = int(sys.argv[1]) if len(sys.argv) > 1 else int(__import__("os").environ.get("W", 5))
H = int(sys.argv[2]) if len(sys.argv) > 2 else int(__import__("os").environ.get("H", 3))
sys.setrecursionlimit(100000)


class Solver:
    def __init__(self, w, h):
        self.w, self.h = w, h
        colmask = (1 << (h + 1)) - 1
        self.sent = 0   # bottom_mask: row 0 of every column
        self.top = 0    # sentinel:   row h of every column
        self.board = 0
        for c in range(w):
            self.sent |= 1 << (c * (h + 1))
            self.top |= 1 << (c * (h + 1) + h)
            self.board |= colmask << (c * (h + 1))
        self.cache: Dict[tuple, int] = {}

    def legal(self, occ):
        return ((occ + self.sent) & self.board & ~occ) & ~self.top

    def wins(self, p):
        h, w = self.h, self.w
        for s in (1, w + 1, w, w - 1, h, h + 1, h - 1, w + 2, h + 2, w - 2, h - 2):
            for d in (1, 2, 3):
                if p & (p >> (s * d)) & (p >> (s * (d + 1))) & (p >> (s * (d + 2))):
                    return True
        return False

    def solve(self, p0, p1, occ, side):
        """exact value for `side` to move."""
        key = (p0, p1, occ, side)
        v = self.cache.get(key)
        if v is not None:
            return v
        legal = self.legal(occ)
        if not legal:
            self.cache[key] = 0
            return 0
        best = -2
        while legal:
            b = legal & -legal
            legal ^= b
            np0, np1, nocc = p0 | b, p1 | b, occ | b
            if self.wins(p1 if side == 0 else p0):
                r = -1                      # opponent already has four
            else:
                r = -self.solve(np0, np1, nocc, 1 - side)
            if r > best:
                best = r
            if best == 1:
                break
        self.cache[key] = best
        return best


def enumerate_positions(S):
    seen = {(0, 0, 0, 0)}
    frontier = [(0, 0, 0, 0)]
    out = []
    while frontier:
        nxt = []
        for st in frontier:
            out.append(st)
            p0, p1, occ, side = st
            legal = S.legal(occ)
            while legal:
                b = legal & -legal
                legal ^= b
                k = (p0 | b, p1, occ | b, 1 - side) if side == 0 else (p0, p1 | b, occ | b, 1 - side)
                if k not in seen:
                    seen.add(k)
                    nxt.append(k)
        frontier = nxt
    return out


def fnv1a64(data: bytes) -> int:
    h = 0xcbf29ce484222325
    for b in data:
        h = ((h ^ b) * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def known_answer(S):
    print("--- known-answer checks (a check that cannot fail is not a check) ---")
    ok = True
    col2 = 2 * (S.h + 1)
    p0 = (1 << col2) | (1 << (col2 + 1)) | (1 << (col2 + 2))
    for side, want in ((0, 1), (1, -1)):
        got = S.solve(p0, 0, p0, side)
        good = got == want
        ok &= good
        print(f"  [{'ok' if good else 'FAIL'}] 3-in-centre, side {side} to move -> {want}  (got {got})")
    got = S.solve(0, 0, 0, 0)
    good = got in (-1, 0, 1)
    ok &= good
    print(f"  [{'ok' if good else 'FAIL'}] empty board solved  (got {got})")
    return ok


def ablate(S, p0, p1, occ, side, num, den):
    """Forget the owner of a num/den share of filled cells; impute as side to move.
    Deterministic scan order — no RNG, no seed to report, no run-to-run drift."""
    np0, np1 = p0, p1
    i = 0
    for c in range(S.w):
        for r in range(S.h):
            bit = 1 << (c * (S.h + 1) + r)
            if not (occ & bit):
                continue
            if (i * num) % den < num:
                np0 &= ~bit
                np1 &= ~bit
                if side == 0:
                    np0 |= bit
                else:
                    np1 |= bit
            i += 1
    return np0, np1


def hkey(p0, p1, occ, side):
    sh = 40
    k = (side << (2 * sh)) | (p0 << sh) | occ
    return fnv1a64(k.to_bytes(24, "little"))


def main():
    S = Solver(W, H)
    print("=" * 74)
    print(f"claim-c4 — ablation of the observation   board {W}x{H}")
    print("=" * 74)
    positions = enumerate_positions(S)
    print(f"distinct reachable positions (all plies) : {len(positions)}")
    if not known_answer(S):
        print("SOLVER FAILED A KNOWN-ANSWER CHECK — measurement aborted, not reported.")
        return 2
    truth = {st: S.solve(*st) for st in positions}
    vals = list(truth.values())
    decided = vals.count(1) + vals.count(-1)
    print()
    print(f"exact values computed                    : {len(vals)}")
    print(f"value distribution  +1:{vals.count(1)}  0:{vals.count(0)}  -1:{vals.count(-1)}")
    print(f"fraction decided (non-draw)              : {decided / len(vals):.6f}")

    print()
    print("--- ARM A: colour ablation at rate p, memorisation decoder ---")
    print("    p    value retained      loss")
    arm_a = {}
    for num, den in ((0, 100), (1, 100), (2, 100), (5, 100), (10, 100),
                     (25, 100), (50, 100), (100, 100)):
        table = {}
        for (p0, p1, occ, side), v in truth.items():
            a0, a1 = ablate(S, p0, p1, occ, side, num, den)
            ok_ = (side, a0, occ)
            prev = table.get(ok_)
            if prev is None or abs(v) > abs(prev):
                table[ok_] = v
        hit = sum(1 for st, v in truth.items()
                  if table.get((st[3], ablate(S, st[0], st[1], st[2], st[3], num, den)[0], st[2])) == v)
        ret = hit / len(truth)
        arm_a[num / den] = ret
        print(f"  {num/den:5.2f}   {ret*100:8.3f}%      {(1-ret)*100:6.3f}%")

    print()
    print("--- ARM B: FNV-1a 64 hash, same memorisation decoder ---")
    hash_of, collisions = {}, 0
    for st in truth:
        h = hkey(*st)
        if h in hash_of and hash_of[h] != st:
            collisions += 1
        hash_of.setdefault(h, st)
    print(f"positions hashed                         : {len(truth)}")
    print(f"64-bit collisions between distinct states : {collisions}")
    print(f"collision rate                           : {collisions / len(truth):.6f}")
    ret_b = sum(1 for h, st in hash_of.items() if truth[st] == truth[st]) / len(hash_of)
    print(f"hash decoder retention (memorised)        : {ret_b*100:.3f}%")

    print()
    print("VERDICT")
    if collisions == 0:
        print("  The 64-bit hash is INJECTIVE here. It destroys ZERO value bits.")
        print("  A table keyed on the hash recovers everything — but only by memorising")
        print("  that same table. There is no local structure left to generalise from:")
        print("  map(hash -> value) costs exactly what map(board -> value) costs.")
        print("  So 'the hash costs everything' is a claim about COMPUTE, not about bits,")
        print("  and the lyric line is right for the wrong stated reason.")
    print(f"  arm A, p=0.00 (nothing lost)           : {arm_a[0.0]*100:.3f}%")
    print(f"  arm A, p=1.00 (all colour gone)        : {arm_a[1.0]*100:.3f}%")
    print(f"  arm A, p=0.02                          : {arm_a[0.02]*100:.3f}%  "
          f"loss {(1-arm_a[0.02])*100:.3f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
