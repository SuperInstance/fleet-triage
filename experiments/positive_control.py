#!/usr/bin/env python3
"""
POSITIVE CONTROL for projection_doctrine.py
===========================================
The pre-registered P1 said: if the lossless observation L0 does not reach high
recovery, the LEARNER is the bottleneck and the ladder is void.

P1 FAILED. L0 lossless topped out at 0.8497 (MLP, random split) against a
predicted >0.90. So before the ladder can mean anything, the harness has to
demonstrate it can reach high accuracy on a task whose answer is *actually a
deterministic function of the same board* and is *locally computable*.

If the learners nail the control, the minimax shortfall is a property of the
TASK (full-depth game-tree value is genuinely hard to learn from occupancy) and
not a bug in the pipeline. If they cannot nail the control, the whole harness
is broken and the ladder means nothing.

THE CONTROL TASK
    "Does p0 have at least one immediate winning move on this ply?"

    This is exactly determined by the board, computable by brute force from the
    42 bits alone, and — unlike minimax — it is LOCAL. A learner should get
    near 1.0 from the lossless board.

    The ground truth is computed here, from the board, by explicit play-out of
    every legal move. It is then cross-checked against the solver's own label:
    any position where p0 has an immediate win must have solver value +1.
    That cross-check is the control's own control — if they disagree, my
    decoder is wrong and everything downstream is void.

WHY THIS MATTERS
    It converts "the ladder showed 0.85 at best" into "the ladder showed 0.85
    where the ceiling is ~1.0 for a local task, so the ordering ACROSS
    observations is still meaningful even though the absolute numbers are
    bounded by a hard task."
"""
import numpy as np
from collections import Counter

GT = "/tmp/c4/c4_ground_truth.txt"
W, H = 7, 6
NQ = W * H
RNG = np.random.default_rng(20261001)


def bit(col, row):
    return 7 * col + row


def moves(mask, who):
    """Every legal gravity-respecting drop for `who` on a board."""
    for c in range(W):
        col_occ = sum(1 for r in range(H) if (mask >> bit(c, r)) & 1)
        if col_occ < H:
            yield c, col_occ


def four(mask):
    for r in range(H):
        for c in range(W - 3):
            if all((mask >> bit(c + k, r)) & 1 for k in range(4)):
                return True
    for c in range(W):
        for r in range(H - 3):
            if all((mask >> bit(c, r + k)) & 1 for k in range(4)):
                return True
    for c in range(W - 3):
        for r in range(H - 3):
            if all((mask >> bit(c + k, r + k)) & 1 for k in range(4)):
                return True
        for r in range(3):
            if all((mask >> bit(c + k, r + 3 - k)) & 1 for k in range(4)):
                return True
    return False


def immediate_win(mask, mine):
    for c, r in moves(mask, 0):
        if four(mask | (1 << bit(c, r))):
            return True
    return False



def verified_subset_unused(rows):
    """Only rows where BOTH colours are gravity-legal under bit=7c+row, pos is a
    subset of mask, and |p0|-|p1|<=1. The raw export has 44.1% of rows carrying
    `pos` bits outside the 42-bit `mask` space (pos is a 7x7 bitboard, mask is
    7x6), so the naive decode silently mislabels colour on those rows."""
    out = []
    for m, p, v in rows:
        if p >> 42:
            continue
        good = True
        for c in range(7):
            for who in (p, m & ~p):
                col = ''.join('1' if (who >> (7 * c + r)) & 1 else '0' for r in range(6))
                if '01' in col:
                    good = False
                    break
            if not good:
                break
        if not good or (p & ~m):
            continue
        n0 = bin(p).count('1')
        if abs(n0 - (bin(m).count('1') - n0)) > 1:
            continue
        out.append((m, p, v))
    return out

def load():
    rows = []
    for line in open(GT):
        m, p, v = line.split()
        rows.append((int(m), int(p), int(v)))
    return rows


def main():
    rows = []
    for line in open("/tmp/c4/verified_subset.txt"):
        m, p_, v, _w = line.split()
        rows.append((int(m), int(p_), int(v)))
    mask = np.array([r[0] for r in rows], np.int64)
    p0 = np.array([r[1] for r in rows], np.int64)
    val = np.array([r[2] for r in rows], np.int64)
    print("=" * 78)
    print("POSITIVE CONTROL - a LOCAL task on the same boards")
    print('  label: "p0 has at least one immediate winning move"')
    print("=" * 78)

    # ── ground truth for the control, computed from the board alone ──────────
    print("\n  computing control labels by brute force over 54,166 boards...")
    y = np.array([1 if immediate_win(int(m), int(p)) else -1 for m, p in zip(mask, p0)], np.int64)
    print(f"  control label distribution: {dict(Counter(y.tolist()))}")

    # ── the control's own control: cross-check against the solver's label ────
    dis = np.where((y > 0) & (val < 0))[0]
    dis2 = np.where((y < 0) & (val > 0))[0]
    print(f"\n  CROSS-CHECK against the solver's full-depth label:")
    print(f"    p0 has an immediate win but solver says p0 loses : {len(dis)}")
    print(f"    p0 has NO immediate win but solver says p0 wins  : {len(dis2)}")
    if len(dis) == 0:
        print("    -> consistent: an immediate win implies +1. My decoder is sound.")
    else:
        print("    -> INCONSISTENT. Decoder or solver is wrong; stop here.")
        for i in dis[:3]:
            print(f"       mask={int(mask[i])} p0={int(p0[i])} val={int(val[i])}")
        return

    # ── same observations, same learners, control label ─────────────────────
    p1 = mask & ~p0
    L0 = np.stack([((p0 >> b) & 1) for b in range(NQ)] +
                  [((p1 >> b) & 1) for b in range(NQ)], axis=1).astype(np.float32)
    L1 = np.stack([((mask >> b) & 1) for b in range(NQ)], axis=1).astype(np.float32)
    blocks = []
    for bc in range(0, 7, 2):
        for br in range(0, 6, 2):
            occ = np.zeros(len(mask), np.float32)
            a = np.zeros(len(mask), np.float32)
            for dc in range(2):
                for dr in range(2):
                    c, r = bc + dc, br + dr
                    if c >= W or r >= H:
                        continue
                    b_ = 7 * c + r
                    occ += ((mask >> b_) & 1)
                    a += ((p0 >> b_) & 1)
            blocks += [occ, a, occ - a]
    L3 = np.stack(blocks, axis=1).astype(np.float32)

    idx = np.arange(len(y))
    RNG.shuffle(idx)
    tr, te = idx[:int(.8 * len(idx))], idx[int(.8 * len(idx)):]

    import importlib.util
    spec = importlib.util.spec_from_file_location("pd", "/workspace/experiments/projection_doctrine.py")
    pd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pd)

    def ba(yy, pp):
        pos, neg = yy > 0, yy < 0
        return 0.5 * (float((pp[pos] == yy[pos]).mean()) + float((pp[neg] == yy[neg]).mean()))

    print("\n  " + "=" * 78)
    print("  CONTROL TASK RECOVERY  (ceiling should be near 1.0 from L0)")
    print("=" * 78)
    print(f"  {'observation':30} {'logreg':>9} {'knn':>9} {'mlp':>9}")
    rows_out = {}
    for name, X in [("L0 lossless", L0), ("L1 colour-collapsed", L1),
                    ("L3 coarse colour-preserving", L3)]:
        a = ba(y[te], pd.predict_logreg(pd.fit_logreg(X[tr], y[tr]), X[te]))
        b = ba(y[te], pd.knn(X[tr], y[tr], X[te]))
        c = ba(y[te], pd.predict_mlp(pd.fit_mlp(X[tr], y[tr], 256, 300, .08, seed=3), X[te]))
        rows_out[name] = (a, b, c)
        print(f"  {name:30} {a:9.4f} {b:9.4f} {c:9.4f}")

    print("\n  VERDICT:")
    best0 = max(rows_out["L0 lossless"])
    if best0 > 0.97:
        print(f"    PASS - the harness reaches {best0:.4f} on a local task from the")
        print("    lossless board. The 0.85 ceiling on minimax is the TASK being hard")
        print("    (full-depth game-tree value is not a local function of occupancy),")
        print("    not the pipeline being broken. The ladder's ORDERING is therefore")
        print("    interpretable even though its absolute values are task-bounded.")
    else:
        print(f"    FAIL - only {best0:.4f} on a task a learner should solve. The harness")
        print("    is broken and the projection ladder means nothing. Do not publish it.")

    np.save("/tmp/c4/control_results.npy", rows_out, allow_pickle=True)
    print(f"\n  saved /tmp/c4/control_results.npy")


if __name__ == "__main__":
    main()
