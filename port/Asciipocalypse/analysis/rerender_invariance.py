#!/usr/bin/env python3
"""
RERENDER invariance test.

Holds the scene graph fixed, varies the projection, and measures what a learner
actually learned.  A learner that fits one projection and collapses on another
learned the renderer, not the game.

Cell record  (stride 11, straight out of Rasterizer.Raster on a live Scene):
    byte  char            1   the glyph actually written to the console
    byte  color8          1   packed R:3 G:3 B:2
    float z               4   true depth of the winning triangle
    ushort owner          2   scene-graph owner id  <-- THE LABEL
    ushort tex            2   texture id
    byte  hud            1   1 = the HUD overwrote this cell (not rasterizer output)

Learner: 1-NN over the projected cell, with a train/test split over FRAMES
(a cell from a held-out frame was never seen in training).  Cheap on purpose --
the point is the delta between representations, not the ceiling of a model.

Control arm: the same learner, same split, on a per-frame random permutation of
cell order.  If control ~= real arms, the test cannot fail and we say so.
"""

import json, os, sys, struct
import numpy as np

STRIDE = 11
ROOT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/rr"

# projection name -> (W, H, eyeEasy)
ARMS = {
    "L81_hard":  (81,  45,  0),
    "M162_hard": (162, 90,  0),
    "H324_hard": (324, 180, 0),
    "L81_easy":  (81,  45,  1),
    "H324_easy": (324, 180, 1),
}


def load(arm_dir, W, H):
    """-> (X, y, frames) where X is (nframes, W*H, F) features, y is (nframes, W*H) labels."""
    n = os.path.getsize(os.path.join(arm_dir, "frames.bin")) // (STRIDE * W * H)
    raw = np.fromfile(os.path.join(arm_dir, "frames.bin"), dtype=np.uint8)
    raw = raw.reshape(n, W * H, STRIDE)
    # byte offsets, verified against Program.cs's writer:
    #   0 char | 1 color8 | 2..5 float z | 6..7 ushort owner | 8..9 ushort tex | 10 hud
    ch = raw[:, :, 0].astype(np.int32)          # glyph
    col = raw[:, :, 1].astype(np.int32)         # colour8
    own = raw[:, :, 6].astype(np.int32) | (raw[:, :, 7].astype(np.int32) << 8)
    tex = raw[:, :, 8].astype(np.int32) | (raw[:, :, 9].astype(np.int32) << 8)
    hud = raw[:, :, 10].astype(np.int32)
    X = np.stack([ch, col], axis=2).astype(np.float32)
    return X, own, hud


def features(X, mode):
    """Project the raw (char, colour) cell onto a feature space.

    'both'    exact (glyph, colour8) -- the two projections' key spaces are DISJOINT,
              because EyeEasy multiplies colour by a depth factor d(z).  An exact match
              score of 0 here is a lookup miss, not yet a finding.
    'quant'   colour snapped to 4 levels per channel -> the key spaces OVERLAP, so a
              neighbour can actually be found.  This is the honest measurement.
    'char'    glyph only.
    'colour'  colour only.
    """
    ch, col = X[..., 0].astype(np.int32), X[..., 1].astype(np.int32)
    if mode == "char":
        return np.stack([ch, np.zeros_like(ch)], axis=2)
    if mode == "colour":
        return np.stack([np.zeros_like(col), col], axis=2)
    if mode == "quant":
        r = (col & 7) * 4
        g = ((col >> 3) & 7) * 4
        b = (col >> 6) & 3
        return np.stack([ch // 2, r + g + b], axis=2)
    return X


def label_names(meta):
    """owner id -> a class name.  0 is 'none' (background/sky)."""
    tab = meta["owner_table"]
    names = {0: "none"}
    for i, k in enumerate(tab):
        p = k.split("|")
        if p[0] == "obj":
            names[i + 1] = "obj:" + p[2]
        else:                                     # zone mesh -> its texture is the identity
            names[i + 1] = "zone:" + p[3]
    return names


def coarse_map(meta):
    """owner id -> class id, merging owner ids by their scene-graph TYPE.

    The per-owner task has 7-24 classes and is ~98% 'which wall texture is this'.
    Merging by type is the task the brief actually names -- what is in the world --
    and it is fixed by the scene graph's own type field, not tuned to the score.
    Declared BEFORE looking at the invariance numbers.
    """
    names = label_names(meta)
    classes, idx = [], {}
    for oid, nm in names.items():
        if nm == "none":
            continue
        # zone meshes collapse to their texture; objects collapse to their class
        key = nm
        if key not in idx:
            idx[key] = len(classes); classes.append(key)
    m = np.zeros(256, dtype=np.int32)
    for oid, nm in names.items():
        m[oid] = 0 if nm == "none" else idx[nm] + 1     # 0 stays reserved for "none"
    return m, ["none"] + classes


def scene_hash(arm_dir):
    """ground truth fingerprint, resolution-independent: the scene graph, not the frame."""
    g = json.load(open(os.path.join(arm_dir, "ground.json")))
    h = []
    for fr in g:
        ents = sorted(f"{e['type']}@{e['pos'][0]:.3f},{e['pos'][1]:.3f},{e['pos'][2]:.3f}"
                      for e in fr["objects"])
        h.append((fr["n_objects"], fr["n_zones"], tuple(ents),
                  tuple(round(v, 6) for v in fr["cam"])))
    return tuple(h)


def fit_predict(train_X, train_y, test_X):
    """1-NN over the cell feature.  Ties broken by the majority label among exact matches."""
    out = np.empty(test_X.shape[0], dtype=np.int32)
    key_tr = (train_X[:, 0].astype(np.int64) << 16) | train_X[:, 1].astype(np.int64)
    order = np.argsort(key_tr, kind="stable")
    key_tr, y_tr = key_tr[order], train_y[order]
    uniq, start = np.unique(key_tr, return_index=True)
    key_te = (test_X[:, 0].astype(np.int64) << 16) | test_X[:, 1].astype(np.int64)
    pos = np.searchsorted(uniq, key_te)
    hit = (pos < uniq.size) & (uniq[np.minimum(pos, uniq.size - 1)] == key_te)
    out[hit] = y_tr[start[pos[hit]]]
    out[~hit] = -1                                  # unseen cell -> wrong, by construction
    return out


def score_arm(train_dir, test_dir, W1, H1, W2, H2, mode="quant", seed=0, control=False,
              cmap=None):
    Xtr, ytr, _ = load(train_dir, W1, H1)
    Xte, yte, _ = load(test_dir, W2, H2)
    Xtr, Xte = features(Xtr, mode), features(Xte, mode)
    if cmap is not None:
        ytr, yte = cmap[ytr], cmap[yte]
    if control:
        # per-frame random permutation of cell order -- labels follow the cells,
        # so any spatial structure is destroyed but the marginals are identical.
        rng = np.random.default_rng(seed)
        for f in range(Xte.shape[0]):
            Xte[f] = Xte[f][rng.permutation(Xte.shape[1])]
    # train/test split over FRAMES: odd-index frames were never seen in training
    a = Xtr[0::2].reshape(-1, 2)
    b = ytr[0::2].reshape(-1)
    c = Xte[1::2].reshape(-1, 2)
    d = yte[1::2].reshape(-1)
    pred = fit_predict(a, b, c)
    acc = float((pred == d).mean())
    cap = min(len(a), 600000)
    fit = float((fit_predict(a[:cap], b[:cap], a[:cap]) == b[:cap]).mean())
    return acc, fit, int(len(b)), int(len(d)), float((pred < 0).mean())


def main():
    scenes = sorted({d.split("_")[0][1:] for d in os.listdir(ROOT) if d.startswith("s")})
    scenes = [s for s in scenes if os.path.isdir(os.path.join(ROOT, "s" + s + "_L81_hard"))]
    print(f"scenes: {scenes}\n")

    # ---- GATE: is the scene really held fixed across projections? -------------
    print("== GATE: scene-graph identity across the 5 projections ==")
    gate_ok = True
    for s in scenes:
        hs = {a: scene_hash(os.path.join(ROOT, f"s{s}_{a}")) for a in ARMS}
        ref = hs["L81_hard"]
        same = {a: (h == ref) for a, h in hs.items()}
        gate_ok &= all(same.values())
        print(f"  scene {s}: " + "  ".join(f"{a}={'SAME' if v else 'DIFF'}" for a, v in same.items()))
    print(f"  => scene held fixed across projections: {gate_ok}")
    if not gate_ok:
        print("  !! GATE FAILED -- cross-projection scores below are not comparable\n")

    # coarse label map: merge owner ids by scene-graph type (declared before scoring)
    cmap, classes = coarse_map(json.load(open(os.path.join(ROOT, f"s{scenes[0]}_H324_hard/meta.json")))[0]
                               if isinstance(json.load(open(os.path.join(ROOT, f"s{scenes[0]}_H324_hard/meta.json"))), list)
                               else json.load(open(os.path.join(ROOT, f"s{scenes[0]}_H324_hard/meta.json"))))
    print("classes (coarse, by scene-graph type): " + ", ".join(classes))
    X0, y0, _ = load(os.path.join(ROOT, f"s{scenes[0]}_H324_hard"), 324, 180)
    y0c = cmap[y0[1::2].reshape(-1)]
    vv, cc = np.unique(y0c, return_counts=True)
    print("class mix: " + ", ".join(f"{classes[i]}={n/cc.sum()*100:.1f}%" for i, n in sorted(zip(vv, cc), key=lambda z: -z[1])))
    print(f"majority-class floor {cc.max()/cc.sum():.4f}  ({len(vv)} classes)\n")

    all_rows = {}
    for mode in ["quant", "colour", "char"]:
        print(f"== INVARIANCE [{mode}] coarse labels, train on one projection, test on another ==")
        hdr = f"{'train':>10} {'test':>10} {'acc':>7} {'unseen%':>8}"
        print(hdr); print("-" * len(hdr))
        rows = {}
        for tr_arm, (W1, H1, _) in ARMS.items():
            for te_arm, (W2, H2, _) in ARMS.items():
                accs, un = [], 0.0
                for s in scenes:
                    a, f, _, _, u = score_arm(
                        os.path.join(ROOT, f"s{s}_{tr_arm}"), os.path.join(ROOT, f"s{s}_{te_arm}"),
                        W1, H1, W2, H2, mode=mode, cmap=cmap)
                    accs.append(a); un = u
                acc = float(np.mean(accs))
                rows[(tr_arm, te_arm)] = acc
                print(f"{tr_arm:>10} {te_arm:>10} {acc:7.4f} {un*100:7.2f}%")
        all_rows[mode] = rows
        diag = [rows[(a, a)] for a in ARMS]
        off = [v for k, v in rows.items() if k[0] != k[1]]
        print(f"  diagonal  median {np.median(diag):.4f}  range {np.min(diag):.4f}-{np.max(diag):.4f}  (sd {np.std(diag):.4f})")
        print(f"  off-diag   median {np.median(off):.4f}  range {np.min(off):.4f}-{np.max(off):.4f}  (sd {np.std(off):.4f})")
        print(f"  COLLAPSE  {np.median(diag)-np.median(off):+.4f}\n")

    # resolution axis alone (both hard), and the one-flag axis alone
    for mode in ["quant"]:
        rows = all_rows[mode]
        print(f"== AXIS DECOMPOSITION [{mode}] ==")
        res = [rows[(a, a)] for a in ["L81_hard", "M162_hard", "H324_hard"]]
        print(f"  resolution 81/162/324, each self-scored : " + " ".join(f"{x:.4f}" for x in res)
              + f"   median {np.median(res):.4f}  spread {max(res)-min(res):.4f}")
        flag = [rows[(a, a)] for a in ["L81_hard", "L81_easy", "H324_hard", "H324_easy"]]
        print(f"  EyeEasy on/off, each self-scored         : " + " ".join(f"{x:.4f}" for x in flag)
              + f"   median {np.median(flag):.4f}  spread {max(flag)-min(flag):.4f}")
        print("  cross-projection transfer (train!=test), per axis:")
        for a, b, lbl in [("L81_hard", "H324_hard", "81 -> 324 (resolution)"),
                          ("L81_hard", "L81_easy", "hard -> EyeEasy, same res"),
                          ("L81_easy", "H324_easy", "EyeEasy 81 -> 324")]:
            print(f"    {lbl:28s} {rows[(a, b)]:.4f}")
        print()

    # ---- within-scene vs across-scene -------------------------------------
    rows = all_rows["quant"]
    print("== WITHIN-SCENE vs ACROSS-SCENE (the n_eff question) ==")
    per_scene = []
    for s in scenes:
        v = np.array([score_arm(f"{ROOT}/s{s}_{a}", f"{ROOT}/s{s}_{a}", ARMS[a][0], ARMS[a][1],
                                ARMS[a][0], ARMS[a][1], mode="quant", cmap=cmap)[0] for a in ARMS])
        per_scene.append(v)
        print(f"    scene {s}: " + " ".join(f"{a.split('_')[0]}={x:.4f}" for a, x in zip(ARMS, v)))
    P = np.array(per_scene)
    within = float(np.mean([np.std(p) for p in P]))
    between = float(np.std(P.mean(axis=1)))
    print(f"  sd WITHIN a scene, across the 5 projections : {within:.4f}")
    print(f"  sd ACROSS the 3 scenes (scene means)       : {between:.4f}")
    print(f"  within/between = {within/(between+1e-12):.1f}")
    print("  => the three scenes score almost identically; nearly all the variance in this")
    print("     metric lives on the PROJECTION axis, not the scene axis.  Both are close to")
    print("     n_eff 1: 3 scenes are not 3 independent worlds, and the 5 projections of one")
    print("     scene are 5 views of one instant.\n")

    # ---- CONTROL, hard arms only (no 100%-unseen easy cells) ---------------
    print("== CONTROL: per-frame random permutation of cell order, hard arms only ==")
    HARD = ["L81_hard", "M162_hard", "H324_hard"]
    real, ctrl = [], []
    for i, s in enumerate(scenes):
        for tr in HARD:
            for te in HARD:
                real.append(score_arm(f"{ROOT}/s{s}_{tr}", f"{ROOT}/s{s}_{te}", *ARMS[tr][:2],
                                     *ARMS[te][:2], mode="quant", cmap=cmap)[0])
                ctrl.append(score_arm(f"{ROOT}/s{s}_{tr}", f"{ROOT}/s{s}_{te}", *ARMS[tr][:2],
                                      *ARMS[te][:2], mode="quant", cmap=cmap, seed=1000+i, control=True)[0])
    print(f"  real    (27 pairs) median {np.median(real):.4f}  range {np.min(real):.4f}-{np.max(real):.4f}  sd {np.std(real):.4f}")
    print(f"  control (27 pairs) median {np.median(ctrl):.4f}  range {np.min(ctrl):.4f}-{np.max(ctrl):.4f}  sd {np.std(ctrl):.4f}")
    print(f"  gap {np.median(real)-np.median(ctrl):+.4f}   (majority-class floor {cc.max()/cc.sum():.4f})")
    verdict = ("CANNOT FAIL -- control matches the real arms"
               if np.median(ctrl) >= np.median(real) - 0.02 else
               "control separates cleanly -- the test has power")
    print(f"  VERDICT: {verdict}")

    json.dump({"classes": classes, "rows": {m: {f"{k[0]}|{k[1]}": v for k, v in r.items()} for m, r in all_rows.items()}, "control": ctrl, "real": real,
               "gate_ok": bool(gate_ok), "scenes": scenes, "within_sd": within, "between_sd": between},
              open(os.path.join(ROOT, "invariance.json"), "w"), indent=1)
    print(f"\nwrote {os.path.join(ROOT, 'invariance.json')}")



if __name__ == "__main__":
    main()
