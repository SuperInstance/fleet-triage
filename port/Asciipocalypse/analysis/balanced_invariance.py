#!/usr/bin/env python3
"""
RERENDER-BALANCED: is the re-projection collapse caused by the PROJECTION, or by the
CLASS IMBALANCE?

The first run answered "0.9856" on a scene that was 99.99% wall texture.  That number
measured frequency, not representation.  Here the two causes are separated by making
the class prior an INDEPENDENT, exactly-controlled variable:

  * six identities at MATCHED depth and matched quad size, in the game's own scene
    graph, rendered by the game's own Rasterizer (Headless/ProbeScene.cs)
  * the class prior is then set by SUBSAMPLING, so p = 0.50 and p = 0.95 are the same
    pixels wearing a different prior -- not two different renders

If the collapse shrinks roughly in proportion to the imbalance, the original 0.9856 was
a frequency result and there was never a projection result.  If the collapse is flat in
the prior, it is a projection result.  Both are reported, including a null.

Cell record stride 11, offsets read out of the writer in Program.cs:
    0 char | 1 color8 | 2..5 float z | 6..7 ushort owner | 8..9 tex | 10 hud
"""

import json, os, sys
import numpy as np

STRIDE = 11
ROOT = sys.argv[1] if len(sys.argv) > 1 else "/workspace/rr"
ARMS = {"L81_hard": (81, 45), "M162_hard": (162, 90), "H324_hard": (324, 180),
        "L81_easy": (81, 45), "H324_easy": (324, 180)}
HARD = ["L81_hard", "M162_hard", "H324_hard"]
NCLS = 6


def load(arm):
    arm = arm if arm.startswith("bal_") else "bal_" + arm
    W, H = ARMS[arm.replace("bal_", "")]
    n = os.path.getsize(f"{ROOT}/{arm}/frames.bin") // (STRIDE * W * H)
    r = np.fromfile(f"{ROOT}/{arm}/frames.bin", dtype=np.uint8).reshape(n, W * H, STRIDE)
    ch = r[:, :, 0].astype(np.int32)
    col = r[:, :, 1].astype(np.int32)
    own = r[:, :, 6].astype(np.int32) | (r[:, :, 7].astype(np.int32) << 8)
    return ch, col, own


def pick(own, prior, rng, budget=1800, floor=40):
    """Resample identified cells to a class prior, per frame.

    n1 is class 1's share; the other five split the remainder equally.  `floor` stops a
    minority class being starved to a handful of cells, whose centroid would then be
    noise that wins the argmin everywhere.
    """
    n1 = int(round(prior * budget))
    n_rest = max(floor, int(round((1 - prior) * budget / 5.0)))
    keep = []
    for f in range(own.shape[0]):
        idx = []
        for c in range(1, NCLS + 1):
            w = np.flatnonzero(own[f] == c)
            k = n1 if c == 1 else n_rest
            if k <= 0 or len(w) == 0:
                continue
            idx.append(w[rng.choice(len(w), min(k, len(w)), replace=False)])
        keep.append(np.concatenate(idx) if idx else np.array([], dtype=int))
    return keep


BALANCED = 1.0 / NCLS     # equal share for each of the six identities


def featurise(col, ch, quant):
    """(glyph, colour) -> a key.  'quant' snaps colour to 4 levels/channel so the
    hard and EyeEasy key spaces overlap at all; without that the transfer is a pure
    key-space miss and the number is not interpretable."""
    r = (col & 7) // 2
    g = ((col >> 3) & 7) // 2
    b = (col >> 6) & 3
    if quant == "both":
        return (ch.astype(np.int64) << 8) | (r * 16 + g * 4 + b)
    if quant == "colour":
        return col.astype(np.int64) * 8 + r * 2
    return (ch.astype(np.int64) << 8) | (r * 16 + g * 4 + b)


def vec(col, ch):
    """8-bit colour unpacked to (r,g,b) plus the glyph index: a point in a small,
    continuous space, so a learner can generalise to colours it never saw.
    Returns (n, 4) float."""
    r = (col & 7).astype(np.float64)
    g = ((col >> 3) & 7).astype(np.float64)
    b = ((col >> 6) & 3).astype(np.float64)
    return np.stack([r, g, b, (ch % 10).astype(np.float64)], axis=1)


def learn_centroid(Xtr, ytr, Xte, randomise_colour=False, seed=0):
    """Nearest class centroid in (r,g,b,glyph) space.

    A 1-NN over exact keys is a MEMORISER: each class spans a cloud of texture colours,
    it memorises the few it saw and is wrong on the rest, and its accuracy is then just
    the class prior.  The centroid reads the cloud instead, so in-projection accuracy
    measures whether identity is recoverable at all, independently of frequency.
    """
    Xtr = Xtr.copy()
    if randomise_colour:
        rng = np.random.default_rng(seed)
        Xte = Xte.copy()
        Xte[:, :3] = rng.integers(0, 8, size=(Xte.shape[0], 3))
    cents, labs = [], []
    for c in np.unique(ytr):
        m = ytr == c
        cents.append(Xtr[m].mean(axis=0))
        labs.append(c)
    C = np.stack(cents)
    # squared distance to every centroid
    d = ((Xte[:, None, :] - C[None, :, :]) ** 2).sum(axis=2)
    return np.array(labs)[d.argmin(axis=1)]


def learn(Xtr, ytr, Xte, randomise_colour=False, seed=0):
    if randomise_colour:
        # control: keep the glyph, destroy the colour channel's identity
        rng = np.random.default_rng(seed)
        Xte = Xte ^ rng.integers(1, 7, size=Xte.shape).astype(Xte.dtype)
    order = np.argsort(Xtr, kind="stable")
    Xs, ys = Xtr[order], ytr[order]
    uniq, start = np.unique(Xs, return_index=True)
    pos = np.searchsorted(uniq, Xte)
    hit = (pos < uniq.size) & (uniq[np.minimum(pos, uniq.size - 1)] == Xte)
    out = np.full(Xte.shape, -1, dtype=np.int32)
    out[hit] = ys[start[pos[hit]]]
    return out


def run(tr_arm, te_arm, prior, quant="both", mode="real", seed=0, budget=1800):
    gtr, ctr, otr = load(tr_arm)
    gte, cte, ote = load(te_arm)
    rng = np.random.default_rng(seed)
    # TRAIN on the requested prior; always TEST balanced.  A balanced test set is what
    # makes chance = 1/6: if the test set carried the same skew, a classifier that just
    # predicts the majority class would score the prior and look like a real learner.
    keep_tr = [k for i, k in enumerate(pick(otr, prior, rng)) if i % 2 == 0]
    keep_te = [k for i, k in enumerate(pick(ote, BALANCED, rng)) if i % 2 == 1]

    Xa, ya = [], []
    for f, idx in enumerate(keep_tr):
        Xa.append(vec(ctr[f][idx], gtr[f][idx]))
        ya.append(otr[f][idx])
    Xa, ya = np.concatenate(Xa), np.concatenate(ya)

    Xb, yb = [], []
    for f, idx in enumerate(keep_te):
        Xb.append(vec(cte[f][idx], gte[f][idx]))
        yb.append(ote[f][idx])
    Xb, yb = np.concatenate(Xb), np.concatenate(yb)
    if mode == "shuffle":
        # break the feature->label association.  Shuffling the INDEX LIST is not a
        # control: it moves features and labels together and changes nothing.
        rng.shuffle(yb)
    pred = learn_centroid(Xa, ya, Xb, randomise_colour=(mode == "colour"), seed=seed)
    return float((pred == yb).mean())


def main():
    meta = json.load(open(f"{ROOT}/bal_H324_hard/meta.json"))
    meta = meta[0] if isinstance(meta, list) else meta
    print("provenance:", meta["provenance"])
    print("identities:", ", ".join(s.split("/")[-1] for s in meta["identities"]))
    print(f"matched depth = {meta['matched_depth']}, matched quad = {meta['matched_quad_size']}, "
          f"dither seed = {meta['raster_dither_seed']}\n")

    col, own = load("H324_hard")[1], load("H324_hard")[2]
    v, c = np.unique(own.reshape(-1)[own.reshape(-1) > 0], return_counts=True)
    print(f"rendered mix among identified cells: " +
          ", ".join(f"c{int(k)}={n/c.sum()*100:.1f}%" for k, n in sorted(zip(v, c), key=lambda z: -z[1])))
    print(f"chance = 1/{NCLS} = {1/NCLS:.4f}\n")

    print("=" * 78)
    print("A. THE CONFOUND: collapse vs class prior.  Resolution arm (81 -> 324).")
    print("=" * 78)
    print(f"{'prior':>7} {'in-proj':>8} {'re-proj':>8} {'collapse':>9} {'control':>9}")
    res_rows = []
    for p in [0.167, 0.25, 0.35, 0.50, 0.65, 0.80]:
        a = run("L81_hard", "L81_hard", p, seed=1)
        b = run("L81_hard", "H324_hard", p, seed=1)
        ctl = run("L81_hard", "H324_hard", p, mode="shuffle", seed=1)
        res_rows.append((p, a, b, a - b, ctl))
        print(f"{p:7.2f} {a:8.4f} {b:8.4f} {a-b:+9.4f} {ctl:9.4f}")

    print("\n" + "=" * 78)
    print("B. THE CONFOUND: collapse vs class prior.  PROJECTION arm (EyeEasy off -> on).")
    print("=" * 78)
    print(f"{'prior':>7} {'in-proj':>8} {'re-proj':>8} {'collapse':>9} {'control':>9}")
    flag_rows = []
    for p in [0.167, 0.25, 0.35, 0.50, 0.65, 0.80]:
        a = run("L81_hard", "L81_hard", p, seed=1)
        b = run("L81_hard", "L81_easy", p, seed=1)
        ctl = run("L81_hard", "L81_easy", p, mode="colour", seed=1)
        flag_rows.append((p, a, b, a - b, ctl))
        print(f"{p:7.2f} {a:8.4f} {b:8.4f} {a-b:+9.4f} {ctl:9.4f}")

    print("\n" + "=" * 78)
    print("C. Is the collapse a projection effect or a frequency effect?")
    print("=" * 78)
    for name, rows, ctrlname in [("resolution 81->324", res_rows, "shuffled cells"),
                                 ("projection hard->EyeEasy", flag_rows, "colour randomised")]:
        pr = np.array([r[0] for r in rows]); co = np.array([r[3] for r in rows])
        # a frequency story predicts the collapse tracks the prior;
        # a projection story predicts it is flat.
        r_prior = np.corrcoef(pr, co)[0, 1]
        print(f"  {name}:")
        print(f"    collapse at prior 0.167: {co[0]:+.4f}")
        print(f"    collapse at prior 0.80 : {co[-1]:+.4f}")
        print(f"    ratio (balanced / skewed) = {co[0]/co[-1] if co[-1] else float('nan'):.2f}")
        print(f"    corr(prior, collapse)   = {r_prior:+.3f}")
        print(f"    control ({ctrlname}) median = {np.median([r[4] for r in rows]):.4f} "
              f"(chance {1/NCLS:.4f})")

    print("\n" + "=" * 78)
    print("D. Does the re-projection arm stay above chance once balanced?")
    print("=" * 78)
    for p in [0.167, 0.50, 0.80]:
        for tr, te, lbl in [("L81_hard", "H324_hard", "resolution 81->324"),
                            ("M162_hard", "H324_hard", "resolution 162->324"),
                            ("L81_hard", "L81_easy", "hard->EyeEasy 81"),
                            ("H324_hard", "H324_easy", "hard->EyeEasy 324"),
                            ("L81_easy", "H324_easy", "EyeEasy 81->324")]:
            print(f"  prior {p:.2f}  {lbl:24s} {run(tr, te, p, seed=1):.4f}")

    json.dump({"resolution": res_rows, "projection": flag_rows, "n_classes": NCLS,
               "chance": 1.0 / NCLS},
              open(f"{ROOT}/balanced.json", "w"), indent=1)
    print(f"\nwrote {ROOT}/balanced.json")


if __name__ == "__main__":
    main()
