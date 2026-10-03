#!/usr/bin/env python3
"""
TWO-ARM TEST on frames EXTRACTED from SuperInstance/Asciipocalypse by executing the
game's own Rasterizer.Raster() (see Harness.cs; provenance is recorded in every frame file).

Prediction under test (ASCIIPOCALYPSE.md):
  "for this game, the char arm and the colour arm should be nearly equally informative,
   and collapsing to char-only should lose little."

Two tasks with computable ground truth, deliberately chosen to have OPPOSITE winners,
so the test can fail in both directions:

  TASK A -- IDENTITY  label = 1 iff the nearest surface at this cell is a living enemy.
                     Ground truth: a second rasterisation of the SAME scene with the SAME
                     camera in which every enemy triangle carries a flat marker texture.
                     Zones are untouched, so occlusion and the z-buffer are identical; only
                     the winning triangle's sampled colour changes.
  TASK B -- DEPTH     label = 1 iff the nearest surface is within 25 world units.
                     Distance is recovered from the game's own zBuffer through the game's
                     own projection matrix. Not estimated, not binned by hand.

Arms. Every arm sees the SAME 3x3 neighbourhood of the cell. Only the FIELDS differ.

  CHARS       Data only
  COLOURONLY  Color only
  BOTH        Data + Color                 <- the projection a player actually has
  CTRL_SHUF   Data, glyphs permuted        <- must sit at chance, else the test cannot fail
  CTRL_FLATC  Data + Color, colour zeroed  <- must destroy Task A only

Classifier: binary logistic regression, L2, full-batch gradient descent, deterministic.
Folds are grouped by SCENE, so no frame is scored against a model that saw its own level.
Colour vocabulary is fitted on the training scenes of each fold only.
"""
import glob, json, os, re, sys
import numpy as np

FRAMES = sys.argv[1] if len(sys.argv) > 1 else "/tmp/frames"
SEED = 20261002
NEAR, FAR = 0.5, 1000.0
_zc = (FAR + NEAR) / (FAR - NEAR)
_zn = 2 * FAR * NEAR / (FAR - NEAR)
FOG = "@&#8x*,:. "          # Rasterizer.cs:22
HDR = re.compile(r"^# scene (\d+) floor (\d+) pose (\d+) tag (\S+)")


def z_to_distance(z):
    with np.errstate(divide="ignore", invalid="ignore"):
        return _zn / (_zc - z)


def ramp_table():
    """Invert the fog ramp: at what metric distance does each glyph take over?"""
    rows = []
    for k in range(10):
        zk = ((k + 0.5) / 10.0) ** (1.0 / 10.0)     # fogId k  <=>  z^10*10 in [k,k+1)
        d = float(z_to_distance(np.array(zk)))
        rows.append((FOG[k], k, round(zk, 4), round(d, 2)))
    return rows


def parse(path):
    with open(path) as f:
        lines = f.read().split("\n")
    m = HDR.match(lines[1])
    W, H = 160, 90

    def block(header):
        i = next(k for k, l in enumerate(lines) if l.startswith(header))
        return lines[i + 1:i + 1 + n_of(header)]

    n_of = lambda h: 90
    data = np.array([list(r.ljust(W)[:W]) for r in block("# DATA --")])
    color = [r.ljust(2 * W)[:2 * W] for r in block("# COLOR --")]
    zt = [r.ljust(8 * W)[:8 * W] for r in block("# Z --")]
    enemy = [r.ljust(W)[:W] for r in block("# LABEL_ENEMY --")]

    g = np.full((H, W), 10, dtype=np.int64)
    for c in FOG:
        g[np.array([[ch == c for ch in r] for r in data])] = FOG.index(c)
    col = np.array([[int(color[j][2 * i], 16) * 16 + int(color[j][2 * i + 1], 16) for i in range(W)]
                    for j in range(H)], dtype=np.int64)
    zz = np.array([[0.0 if zt[j][8 * i:8 * i + 8].strip() == "---" else float(zt[j][8 * i:8 * i + 8])
                   for i in range(W)] for j in range(H)])
    zz = np.where(zz == 0.0, 1.0, zz)
    en = np.array([[ch == "1" for ch in r] for r in enemy])
    return dict(scene=int(m.group(1)), floor=int(m.group(2)), pose=int(m.group(3)), tag=m.group(4),
                g=g, col=col, z=zz, enemy=en, dist=z_to_distance(zz))


def arm_maps(fr, arm, rng):
    g, col = fr["g"].copy(), fr["col"].copy()
    if arm == "CTRL_SHUF":
        m = g < 10
        g[m] = rng.permutation(10)[g[m]]
    if arm == "CTRL_FLATC":
        col = np.full_like(col, 255)
    if arm in ("CHARS", "CTRL_SHUF"):
        return g
    if arm == "COLOURONLY":
        return col
    return np.stack([g, col], -1)          # BOTH


def patch(a, size=3):
    """size x size neighbourhood, row-major from top-left, edge-clamped."""
    H, W = a.shape[0], a.shape[1]
    d = 1 if a.ndim == 2 else a.shape[2]
    out = np.zeros((H * W, size * size * d), dtype=np.int64)
    n = 0
    for dy in range(size):
        for dx in range(size):
            ys = np.clip(np.arange(H) - dy, 0, H - 1)
            xs = np.clip(np.arange(W) - dx, 0, W - 1)
            sub = a[np.ix_(ys, xs)]
            out[:, n * d:(n + 1) * d] = sub.reshape(H * W, d)
            n += 1
    return out


def fit(X, y, l2=1e-4, iters=250, lr=1.0):
    n, d = X.shape
    Xb = np.hstack([X, np.ones((n, 1), np.float32)]).astype(np.float32)
    w = np.zeros((d + 1,), dtype=np.float32)
    yf = y.astype(np.float32)
    for _ in range(iters):
        z = Xb @ w
        np.clip(z, -30, 30, out=z)
        p = 1.0 / (1.0 + np.exp(-z))
        g = Xb.T @ (p - yf) / n
        g[:-1] += l2 * w[:-1]
        w -= (lr * g).astype(np.float32)
    return w


def scores(X, w):
    z = np.hstack([X, np.ones((len(X), 1), np.float32)]).astype(np.float32) @ w
    return (z > 0).astype(np.int64)


def bal(y, p):
    tpr = float((p[y == 1] == 1).mean()) if (y == 1).any() else np.nan
    tnr = float((p[y == 0] == 0).mean()) if (y == 0).any() else np.nan
    return 0.5 * (tpr + tnr), tpr, tnr


def main():
    files = sorted(glob.glob(os.path.join(FRAMES, "scene*_pose*.txt")))
    frames = [parse(p) for p in files]
    print(f"frames: {len(files)}  scenes: {len({f['scene'] for f in frames})}  "
          f"cells/frame: {frames[0]['g'].size}")

    PER = 250
    rng = np.random.default_rng(SEED)
    idx = [rng.choice(frames[0]["g"].size, PER, replace=False) for _ in frames]
    labA = np.array([f["enemy"].reshape(-1)[i] for f, i in zip(frames, idx)]).astype(np.int64)
    dist = np.array([f["dist"].reshape(-1)[i] for f, i in zip(frames, idx)])
    labB = (dist <= 25.0).astype(np.int64)

    print("\n-- decoded fog ramp (Rasterizer.cs:22 + the game's own projection matrix) --")
    for c, k, z, d in ramp_table():
        print(f"   '{c}'  fogId {k}   z>={z:<8} distance >= {d:>8.2f} world units")
    print(f"   ' '  no surface (zBuffer == 1, no triangle won this cell)")

    print("\n-- direct evidence: glyph distribution on enemy vs non-enemy cells --")
    tot_e = int(sum(int(f["enemy"].sum()) for f in frames))
    tot_n = int(sum(int((~f["enemy"]).sum()) for f in frames))
    print(f"   enemy cells {tot_e}, other cells {tot_n}")
    print(f"   {'glyph':7s} {'share of ENEMY cells':>22s} {'share of OTHER cells':>22s}")
    for k, c in enumerate(list(FOG) + ["<none>"]):
        a = int(sum(int((f["g"] == k)[f["enemy"]].sum()) for f in frames))
        b = int(sum(int((f["g"] == k)[~f["enemy"]].sum()) for f in frames))
        lbl = f"'{c}'" if k < 10 else "no surface"
        print(f"   {lbl:7s} {a:>10d} ({a/tot_e:.4f}) {b:>12d} ({b/tot_n:.4f})")

    scenes = sorted({f["scene"] for f in frames})
    fold_of = {s: i % 5 for i, s in enumerate(scenes)}
    ARMS = ["CHARS", "COLOURONLY", "BOTH", "CTRL_SHUF", "CTRL_FLATC"]
    out = {"frames": len(files), "scenes": len(scenes), "per_frame_cells": PER,
           "positive_rate": {"A_IDENTITY": float(labA.mean()), "B_DEPTH": float(labB.mean())},
           "folds": {}}

    for arm in ARMS:
        r2 = np.random.default_rng(SEED + 1)
        P = [patch(arm_maps(f, arm, r2)) for f in frames]
        P = [p[i] for p, i in zip(P, idx)]
        for TASK, Y in (("A_IDENTITY", labA), ("B_DEPTH", labB)):
            fold_rows = []
            for fold in range(5):
                tr = [k for k, f in enumerate(frames) if fold_of[f["scene"]] != fold]
                te = [k for k, f in enumerate(frames) if fold_of[f["scene"]] == fold]
                # feature layout: (glyph channels, colour channels) per arm
                n_g, n_c = {"CHARS": (1, 0), "CTRL_SHUF": (1, 0),
                            "COLOURONLY": (0, 1), "BOTH": (1, 1), "CTRL_FLATC": (1, 1)}[arm]
                card_g = 12
                card_c, gmap = 0, None
                if n_c:
                    seen = np.unique(np.concatenate([P[k][:, 1::2] if n_g else P[k] for k in tr]))
                    gmap = {int(v): i for i, v in enumerate(seen)}
                    card_c = len(seen) + 1        # +1 UNK bucket

                def enc(k, rows):
                    a = P[k][rows]
                    n, ncol = len(a), a.shape[1]
                    per = ncol // 9
                    outm = np.zeros((n, n_g * 9 * card_g + n_c * 9 * card_c), np.float32)
                    ar = np.arange(n)
                    for j in range(ncol):
                        chan = j % per                       # which arm field this column is
                        pos = j // per                       # which of the 9 neighbourhood slots
                        if chan < n_g:
                            outm[ar, chan * 9 * card_g + pos * card_g + a[:, j]] = 1.0
                        else:
                            v = np.array([gmap.get(int(x), len(gmap)) for x in a[:, j]])
                            base = n_g * 9 * card_g + (chan - n_g) * 9 * card_c + pos * card_c
                            outm[ar, base + v] = 1.0
                    return outm

                allrows = np.arange(PER)
                Xtr = np.vstack([enc(k, allrows) for k in tr])
                ytr = np.concatenate([Y[k] for k in tr])
                Xte = np.vstack([enc(k, allrows) for k in te])
                yte = np.concatenate([Y[k] for k in te])
                w = fit(Xtr, ytr)
                p = scores(Xte, w)
                ba, tpr, tnr = bal(yte, p)
                fold_rows.append(dict(bal_acc=ba, tpr=tpr, tnr=tnr,
                                      pos_rate=float(yte.mean()), n=int(len(yte))))
            a = np.array([r["bal_acc"] for r in fold_rows])
            out["folds"][f"{arm}|{TASK}"] = fold_rows
            print(f"{arm:11s} {TASK:10s} bal_acc mean={a.mean():.4f} sd={a.std(ddof=1):.4f} "
                  f"range=[{a.min():.4f},{a.max():.4f}]  TPR={np.mean([r['tpr'] for r in fold_rows]):.4f} "
                  f"TNR={np.mean([r['tnr'] for r in fold_rows]):.4f}")
            out["folds"][f"{arm}|{TASK}|summary"] = dict(
                mean=float(a.mean()), sd=float(a.std(ddof=1)), lo=float(a.min()), hi=float(a.max()))

    with open("/tmp/twoarm_results.json", "w") as fh:
        json.dump(out, fh, indent=1)
    print("\nwrote /tmp/twoarm_results.json")


if __name__ == "__main__":
    main()
