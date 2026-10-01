#!/usr/bin/env python3
"""
PROJECTION-DOCTRINE EXPERIMENT
===============================
The fleet's standing doctrine says:

    "Every observation is a projection. Every projection is lossy.
     No downstream cleverness recovers what the looking never carried."

That sentence has never been measured. It is unfalsifiable as stated, which
makes it a slogan rather than a claim. This experiment makes it a number.

GROUND TRUTH
    SuperInstance/connect4, `c4_ground_truth.txt`, 54,166 positions, plies 1-6,
    full-depth minimax, value from p0's point of view. FNV-1a 64 digest
    0x4ef8351a5c319637. No draws in range, consistent with 7x6 Connect-4 being
    a proven second-player win: all 7 one-ply positions are losses for p0.

    Encoding: `mask pos value`, decimal. Bit = 7*col + row, row 0 is the
    bottom. Verified 54,166/54,166 gravity-valid under that mapping.

DESIGN
    Build a ladder of observations of the same position, from lossless to
    deliberately destructive, and measure how much of the exact minimax value a
    downstream learner can still recover from each.

    "Downstream cleverness" gets three separate learners, so the answer does
    not depend on one architecture being good or bad.

PRE-REGISTERED PREDICTIONS (written before running, not adjusted after)
    P1  L0 lossless (full colour board)      -> high recovery. If this fails the
                                                 LEARNER is the bottleneck, not
                                                 the projection: experiment void.
    P2  L1 colour-collapsed (occupancy only) -> CHANCE (~0.50). The label is
                                                 defined relative to p0, so
                                                 discarding ownership must
                                                 DESTROY the value, not blur it.
    P3  L3 colour-preserving but spatially    -> below L0, above chance.
        lossy (12 coarse blocks)                Minimax value is largely a
                                                 coarse threat property.
    P4  L4 irreversible 64-bit FNV-1a hash    -> at or below L1. A hash that
                                                 beats colour-collapse would mean
                                                 information leaks somewhere.
    P5  L5 stone count only (4 features)      -> poor, near chance.

SPLIT
    A random split leaks badly here: boards one move apart are near-identical,
    so random-split accuracy is inflated for reasons unrelated to the
    observation. Both are reported and the GAP measures the leakage.
      * random : 80/20 over all 54,166             -> optimistic
      * by-ply : train plies 1-4, test plies 5-6   -> honest

CONTROLS
    C1  label-shuffle on the same features and learner -> must land at chance.
        If not, there is leakage and every number here is void.
    C2  L0 must be high                               -> the learner's ceiling.
    C3  random-vs-by-ply gap                           -> measures the hidden
                                                        leakage.
"""
import numpy as np
from collections import Counter

GT = "/tmp/c4/c4_ground_truth.txt"
OUT = "/tmp/c4/results.npy"
RNG = np.random.default_rng(20261001)
W, H = 7, 6
NQ = W * H



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


def verify_encoding(mask, p0, val, ply):
    ok = True
    bad = 0
    for m in mask:
        for c in range(W):
            col = "".join("1" if (int(m) >> (7 * c + r)) & 1 else "0" for r in range(H))
            if "01" in col:
                bad += 1
                break
    print(f"  gravity violations            {bad} / {len(mask)}")
    ok &= bad == 0
    n0 = np.array([bin(int(x)).count("1") for x in p0])
    nt = np.array([bin(int(x)).count("1") for x in mask])
    d = np.abs(n0 - (nt - n0))
    print(f"  |p0|-|p1| out of range       {(d > 1).sum()}")
    ok &= bool((d <= 1).all())
    print(f"  p0 not a subset of mask       {sum(1 for m, p in zip(mask, p0) if int(p) & ~int(m))}")
    ok &= all(int(p) & ~int(m) == 0 for m, p in zip(mask, p0))
    one = val[ply == 1]
    print(f"  1-ply values                  {dict(Counter(one.tolist()))}  (expect all -1)")
    ok &= bool((one == -1).all())
    mx = int(max(n0))
    print(f"  max stones held by one player {mx}  (<4 required for 0 wins to be correct)")
    ok &= mx < 4
    return ok


def fnv1a64(data: bytes) -> int:
    h = 0xCBF29CE484222325
    for b in data:
        h ^= b
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


def observations(mask, p0):
    mask, p0 = mask.astype(np.int64), p0.astype(np.int64)
    p1 = mask & ~p0
    n = len(mask)

    L0 = np.stack([((p0 >> b) & 1) for b in range(NQ)] +
                  [((p1 >> b) & 1) for b in range(NQ)], axis=1).astype(np.float32)

    L1 = np.stack([((mask >> b) & 1) for b in range(NQ)], axis=1).astype(np.float32)

    blocks = []
    for bc in range(0, 7, 2):
        for br in range(0, 6, 2):
            occ = np.zeros(n, np.float32)
            a = np.zeros(n, np.float32)
            for dc in range(2):
                for dr in range(2):
                    c, r = bc + dc, br + dr
                    if c >= W or r >= H:
                        continue
                    bit = 7 * c + r
                    occ += ((mask >> bit) & 1)
                    a += ((p0 >> bit) & 1)
            blocks += [occ, a, occ - a]
    L3 = np.stack(blocks, axis=1).astype(np.float32)

    L4 = np.zeros((n, 64), np.float32)
    for i in range(n):
        h = fnv1a64(int(mask[i]).to_bytes(8, "little") + int(p0[i]).to_bytes(8, "little"))
        for b in range(64):
            L4[i, b] = (h >> b) & 1
    L4 /= 64.0

    n0 = np.array([bin(int(x)).count("1") for x in p0], np.float32)
    nt = np.array([bin(int(x)).count("1") for x in mask], np.float32)
    L5 = np.stack([n0, nt - n0, nt, (nt % 2).astype(np.float32)], axis=1)

    return {"L0 lossless": L0, "L1 colour-collapsed": L1,
            "L3 coarse colour-preserving": L3, "L4 hash64 irreversible": L4,
            "L5 stone count only": L5}


def fit_logreg(X, y, epochs=400, lr=0.4, l2=1e-3):
    n = len(X)
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = np.hstack([np.ones((n, 1), np.float32), (X - mu) / sd]).astype(np.float64)
    w = np.zeros(Z.shape[1])
    yy = (y > 0).astype(np.float64)
    for _ in range(epochs):
        p = 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30)))
        g = Z.T @ (p - yy) / n
        g[1:] += l2 * w[1:]
        w -= lr * g
    return (w, mu, sd)


def predict_logreg(model, X):
    w, mu, sd = model
    Z = np.hstack([np.ones((len(X), 1), np.float32), (X - mu) / sd]).astype(np.float64)
    return np.where(Z @ w > 0, 1, -1)


def knn(Xtr, ytr, Xte, k=25, chunk=256):
    """Squared distance via matmul. The broadcast form allocated ~7 GB and was
    OOM-killed; this is 256 x ntrain, ~44 MB per chunk."""
    out = np.empty(len(Xte), np.int64)
    tr2 = (Xtr.astype(np.float32) ** 2).sum(1)
    for i in range(0, len(Xte), chunk):
        b = Xte[i:i + chunk].astype(np.float32)
        d = (b ** 2).sum(1)[:, None] + tr2[None, :] - 2.0 * (b @ Xtr.astype(np.float32).T)
        idx = np.argpartition(d, k, axis=1)[:, :k]
        out[i:i + chunk] = np.where(ytr[idx].mean(1) > 0, 1, -1)
    return out


def fit_mlp(X, y, hidden=256, epochs=300, lr=0.08, l2=1e-4, seed=0):
    """Two-layer ReLU MLP, full-batch Adam. Needed because the minimax value
    is a deep game-tree property, not a linear function of occupancy."""
    rng = np.random.default_rng(seed)
    n, d = X.shape
    mu, sd = X.mean(0), X.std(0) + 1e-6
    Z = ((X - mu) / sd).astype(np.float32)
    yy = (y > 0).astype(np.float32) * 2 - 1
    W1 = rng.normal(0, np.sqrt(2 / d), (d, hidden)).astype(np.float32)
    b1 = np.zeros(hidden, np.float32)
    W2 = rng.normal(0, np.sqrt(2 / hidden), (hidden, 1)).astype(np.float32)
    b2 = np.zeros(1, np.float32)
    ps = [W1, b1, W2, b2]
    ms = [np.zeros_like(p) for p in ps]
    vs = [np.zeros_like(p) for p in ps]
    lrT = lr * np.sqrt(1 - 0.999 ** np.arange(1, epochs + 1))
    for t in range(epochs):
        a1 = np.maximum(0, Z @ W1 + b1)
        o = (a1 @ W2 + b2).ravel()
        p1 = 1 / (1 + np.exp(-np.clip(o * 8, -30, 30)))
        err = (p1 - (yy * .5 + .5)) / n
        gW2 = a1.T @ err[:, None] + l2 * W2
        gb2 = np.array([err.sum()])
        da1 = (err[:, None] * W2.T) * (a1 > 0)
        gW1 = Z.T @ da1 + l2 * W1
        gb1 = da1.sum(0)
        for i, g in enumerate([gW1, gb1, gW2, gb2]):
            ms[i] = .9 * ms[i] + .1 * g
            vs[i] = .999 * vs[i] + .001 * g * g
            ps[i] -= lrT[t] * (ms[i] / (1 - .9 ** (t + 1))) / (np.sqrt(vs[i] / (1 - .999 ** (t + 1))) + 1e-8)
    return (ps, mu, sd)


def predict_mlp(model, X):
    (W1, b1, W2, b2), mu, sd = model
    Z = ((X - mu) / sd).astype(np.float32)
    return np.where((np.maximum(0, Z @ W1 + b1) @ W2 + b2).ravel() > 0, 1, -1)


def rf(X, D, seed):
    rng = np.random.default_rng(seed)
    R = rng.normal(0, 1 / np.sqrt(X.shape[1]), (X.shape[1], D)).astype(np.float32)
    return np.cosh(X @ R).astype(np.float32)


def bal_acc(y, p):
    pos, neg = y > 0, y < 0
    if pos.sum() == 0 or neg.sum() == 0:
        return float("nan")
    return 0.5 * (float((p[pos] == y[pos]).mean()) + float((p[neg] == y[neg]).mean()))


def main():
    print("=" * 78)
    print("PROJECTION-DOCTRINE EXPERIMENT")
    print("=" * 78)
    rows = []
    for line in open("/tmp/c4/verified_subset.txt"):
        m, p_, v, _w = line.split()
        rows.append((int(m), int(p_), int(v)))
    mask = np.array([r[0] for r in rows], np.int64)
    p0 = np.array([r[1] for r in rows], np.int64)
    val = np.array([r[2] for r in rows], np.int64)
    ply = np.array([bin(int(m)).count("1") for m in mask])
    print(f"\n  ground truth {len(val)} positions, plies {ply.min()}-{ply.max()}")
    print(f"  value distribution {dict(Counter(val.tolist()))}")

    print("\n  --- encoding verification (a wrong decode poisons everything) ---")
    if not verify_encoding(mask, p0, val, ply):
        print("  ABORT: encoding checks failed")
        return

    obs = observations(mask, p0)
    print("\n  --- observation ladder ---")
    for k, v in obs.items():
        print(f"    {k:30} {v.shape[1]:4d} cols")

    idx = np.arange(len(val))
    RNG.shuffle(idx)
    rtr, rte = idx[:int(.8 * len(idx))], idx[int(.8 * len(idx)):]
    dtr, dte = np.where(ply <= 4)[0], np.where(ply >= 5)[0]
    print(f"\n  random  train {len(rtr)} / test {len(rte)}")
    print(f"  by-ply  train {len(dtr)} (plies 1-4) / test {len(dte)} (plies 5-6)")

    results = {}
    print("\n" + "=" * 78)
    print("  OBSERVATION                  LEARNER     random     by-ply     gap")
    print("=" * 78)
    for name, X in obs.items():
        pr = bal_acc(val[rte], predict_logreg(fit_logreg(X[rtr], val[rtr]), X[rte]))
        pd = bal_acc(val[dte], predict_logreg(fit_logreg(X[dtr], val[dtr]), X[dte]))
        results[(name, "logreg")] = (pr, pd)
        print(f"  {name:27} logreg    {pr:.4f}      {pd:.4f}     {pr-pd:+.4f}")

        if X.shape[1] <= 128:
            a = bal_acc(val[rte], knn(X[rtr], val[rtr], X[rte]))
            b = bal_acc(val[dte], knn(X[dtr], val[dtr], X[dte]))
            results[(name, "knn")] = (a, b)
            print(f"  {'':27} knn       {a:.4f}      {b:.4f}     {a-b:+.4f}")

        ml = fit_mlp(X[rtr], val[rtr], 256, 300, 0.08, seed=3)
        c = bal_acc(val[rte], predict_mlp(ml, X[rte]))
        md_ = fit_mlp(X[dtr], val[dtr], 256, 300, 0.08, seed=4)
        e = bal_acc(val[dte], predict_mlp(md_, X[dte]))
        results[(name, "mlp")] = (c, e)
        print(f"  {'':27} mlp       {c:.4f}      {e:.4f}     {c-e:+.4f}")

        a = bal_acc(val[rte], predict_logreg(
            fit_logreg(rf(X[rtr], 3000, 1), val[rtr], 300, .5), rf(X[rte], 3000, 1)))
        b = bal_acc(val[dte], predict_logreg(
            fit_logreg(rf(X[dtr], 3000, 2), val[dtr], 300, .5), rf(X[dte], 3000, 2)))
        results[(name, "rf-logreg")] = (a, b)
        print(f"  {'':27} rf-logreg {a:.4f}      {b:.4f}     {a-b:+.4f}")

    print("\n  " + "-" * 78)
    print("  CONTROL C1 - shuffled labels, same features, same learner")
    X0 = obs["L0 lossless"]
    m = fit_logreg(X0[rtr], RNG.permutation(val[rtr]))
    c1 = bal_acc(val[rte], predict_logreg(m, X0[rte]))
    print(f"    logreg on L0, shuffled labels      {c1:.4f}   (must be ~0.50)")

    def best(name):
        v = [r for (n, _), r in results.items() if n == name]
        return max(v) if v else float("nan")

    print("\n" + "=" * 78)
    print("  PRE-REGISTERED PREDICTION VERDICTS")
    print("=" * 78)
    b0, b1, b3, b4, b5 = (best("L0 lossless"), best("L1 colour-collapsed"),
                          best("L3 coarse colour-preserving"),
                          best("L4 hash64 irreversible"), best("L5 stone count only"))
    checks = [
        ("P1 L0 lossless is high", b0 > 0.90, f"{b0:.4f}"),
        ("P2 L1 colour-collapsed ~ chance", abs(b1 - .5) < .06, f"{b1:.4f}"),
        ("P3 L3 below L0 and above chance", b3 < b0 - .02 and b3 > .52, f"{b3:.4f}"),
        ("P4 L4 hash <= L1", b4 <= b1 + .01, f"{b4:.4f} vs L1 {b1:.4f}"),
        ("P5 L5 near chance", abs(b5 - .5) < .10, f"{b5:.4f}"),
    ]
    for name, ok, vv in checks:
        print(f"    {'HOLDS ' if ok else 'FAILS '} {name:36} {vv}")
    np.save(OUT, results, allow_pickle=True)
    print(f"\n  saved {OUT}")


if __name__ == "__main__":
    main()
