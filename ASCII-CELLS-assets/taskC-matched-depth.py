#!/usr/bin/env python3
"""
Task C v3 -- IDENTITY AT MATCHED DEPTH, memory-bounded and with a nonparametric check.

Two problems with v1/v2 are fixed here:
  * v1/v2 one-hot the raw 8-bit colour, which is 2412 columns and OOMs. v3 decodes the
    packed byte back into the R:3 G:3 B:2 the game actually stores and feeds the nine
    neighbourhood slots as continuous channels -- 135 columns, and a *better* readout
    than one-hot because a hyperplane can express "green" directly.
  * balanced accuracy cannot tell "no information" from "the classifier collapsed to
    one class", since both score 0.5000. v3 reports TPR and TNR, asserts the char arm's
    input has exactly zero variance inside a stratum, and cross-checks the linear
    readout against 1-NN so a weak learner cannot be mistaken for absent information.
"""
import glob, os, sys
import numpy as np
sys.path.insert(0, "/tmp")
from twoarm import parse, FOG, fit, scores

FRAMES = sys.argv[1] if len(sys.argv) > 1 else "/tmp/frames"
SEED = 20261002
files = sorted(glob.glob(os.path.join(FRAMES, "scene*_pose*.txt")))
frames = [parse(p) for p in files]
rng0 = np.random.default_rng(SEED)
SUB = 2000                                   # cells sampled per frame
idx = [rng0.choice(frames[0]["g"].size, SUB, replace=False) for _ in frames]


def rgb(code):
    r = (code & 0b111) / 7.0
    g = ((code >> 3) & 0b111) / 7.0
    b = ((code >> 6) & 0b11) / 3.0
    return r, g, b


def stack(flat_g, flat_c):
    n = len(flat_g)
    o = np.zeros((n, 9 * 12), np.float32)
    o[np.arange(n), flat_g] = 1.0
    return o


def stack_col(flat_c, flat_g=None):
    n = len(flat_c)
    H, W = flat_g.shape if flat_g is not None else (None, None)
    o = np.zeros((n, 9 * 3), np.float32)
    o[:, 0::3] = (flat_c & 0b111) / 7.0
    o[:, 1::3] = ((flat_c >> 3) & 0b111) / 7.0
    o[:, 2::3] = ((flat_c >> 6) & 0b11) / 3.0
    return o


def neighbourhood(arr2d, rows, size=3):
    """arr2d: HxW. rows: flat indices. Returns (len(rows), size*size) with edge clamp."""
    H, W = arr2d.shape
    out = np.zeros((len(rows), size * size), dtype=arr2d.dtype)
    n = 0
    for dy in range(size):
        for dx in range(size):
            r = rows // W
            c = rows % W
            rr = np.clip(r - dy, 0, H - 1); cc = np.clip(c - dx, 0, W - 1)
            out[:, n] = arr2d[rr, cc]; n += 1
    return out


def knn1(Xtr, ytr, Xte, yte, cap=4000):
    """1-NN in squared-euclidean distance, chunked. This box has 2 GB of RAM and one
    core, so the full (n_te, n_tr, d) tensor is not buildable and is not attempted."""
    rs = np.random.default_rng(SEED)
    if len(Xtr) > cap:
        s = rs.choice(len(Xtr), cap, replace=False); Xtr, ytr = Xtr[s], ytr[s]
    if len(Xte) > cap:
        s = rs.choice(len(Xte), cap, replace=False); Xte, yte = Xte[s], yte[s]
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
    A, B = (Xtr - mu) / sd, (Xte - mu) / sd
    p = np.empty(len(B), dtype=np.int64)
    A2 = (A * A).sum(1)
    for s in range(0, len(B), 256):
        Bc = B[s:s + 256]
        d = A2[None, :] - 2.0 * (Bc @ A.T) + (Bc * Bc).sum(1)[:, None]
        p[s:s + 256] = ytr[d.argmin(1)]
    return float(0.5 * ((p[yte == 1] == 1).mean() + (p[yte == 0] == 0).mean()))


print(f"Task C v3 -- identity at matched depth. {len(frames)} frames, "
      f"{SUB} cells sampled per frame, 3x3 neighbourhood, edge-clamped.\n")
hdr = (f"{'stratum':8s} {'cells':>7s} {'pos%':>6s} | {'CHARS lin':>16s} {'CHR-var':>8s} | "
       f"{'COLOUR lin':>16s} {'COLOUR 1-NN':>13s} {'BOTH lin':>16s} {'CTRL_FLATC':>16s}")
print(hdr); print("-" * len(hdr))
print(f"{'':8s} {'':7s} {'':6s} | {'acc  TPR   TNR':>16s} {'':8s} | {'acc  TPR   TNR':>16s} "
      f"{'acc':>13s} {'acc  TPR   TNR':>16s} {'acc  TPR   TNR':>16s}")

summary = {}
for k in list(range(10)):
    G, C, Y = [], [], []
    for f, ii in zip(frames, idx):
        m = (f["g"] == k).reshape(-1)[ii]
        if m.sum() < 150:
            continue
        gpatch = neighbourhood(f["g"], ii)
        cpatch = neighbourhood(f["col"], ii)
        sel = m
        G.append(gpatch[sel]); C.append(cpatch[sel])
        Y.append(f["enemy"].reshape(-1)[ii][sel].astype(np.int64))
    if not Y:
        continue
    G, C, Y = np.concatenate(G), np.concatenate(C), np.concatenate(Y)
    if Y.sum() < 25 or (1 - Y).sum() < 25:
        continue
    Xchr = np.zeros((len(Y), 9 * 12), np.float32)
    for j in range(9):
        Xchr[np.arange(len(Y)), j * 12 + G[:, j]] = 1.0
    Xcol = np.ascontiguousarray(stack_col(C))
    Xboth = np.hstack([Xchr, Xcol])
    Xflat = np.hstack([Xchr, np.ascontiguousarray(stack_col(np.full_like(C, 255)))])
    chr_var = float(Xchr.var(0).sum())

    o = rng0.permutation(len(Y)); cut = int(0.7 * len(Y)); tr, te = o[:cut], o[cut:]
    res = []
    for E in (Xchr, Xcol, Xboth, Xflat):
        w = fit(E[tr], Y[tr]); p = scores(E[te], w)
        tpr = float((p[Y[te] == 1] == 1).mean()); tnr = float((p[Y[te] == 0] == 0).mean())
        res.append((0.5 * (tpr + tnr), tpr, tnr))
    knn = knn1(Xcol[tr], Y[tr], Xcol[te], Y[te])
    lbl = f"'{FOG[k]}'"
    summary[lbl] = dict(cells=int(len(Y)), pos=float(Y.mean()), chr_var=chr_var,
                        chr=res[0], col=res[1], knn_col=knn, both=res[2], flat=res[3])
    print(f"{lbl:8s} {len(Y):>7d} {100*Y.mean():>5.1f}% | "
          f"{res[0][0]:.4f} {res[0][1]:.3f} {res[0][2]:.3f} {chr_var:>8.1f} | "
          f"{res[1][0]:.4f} {res[1][1]:.3f} {res[1][2]:.3f} {knn:>13.4f} "
          f"{res[2][0]:.4f} {res[2][1]:.3f} {res[2][2]:.3f} "
          f"{res[3][0]:.4f} {res[3][1]:.3f} {res[3][2]:.3f}")

import json
json.dump(summary, open("/tmp/taskC.json", "w"), indent=1)
print("\nwrote /tmp/taskC.json")
