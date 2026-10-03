#!/usr/bin/env python3
"""
PROJECTION LOSS, measured.

Five questions, five instruments:

  1. correspondence   which 3D entity won which cell (from the z-buffer)
  2. collapse         how many distinct entities land on how many distinct cells
  3. glyph stability  the same entity's glyph as a function of depth
  4. two arms         Data (chars) vs Data+Color, scored against the scene graph
  5. controls         shuffled chars, random colour -- if these score the same,
                      the test cannot fail and the ranking is void
"""
import collections, glob, json, os, random, sys
import numpy as np
from frames import Frames

FOGSTRING = "@&#8x*,:. "          # Rasterizer.cs:22


def load(paths):
    return [Frames(p) for p in paths]


def class_table(F):
    names = ["empty"]
    for o in F.owner_table:
        p = o.split("|")
        names.append(("obj:" + p[2] + "/" + p[3]) if p[0] == "obj" else ("arch:" + p[3]))
    return np.array(names)


# ---------------------------------------------------------------- 1 + 2
def correspondence(Fs, per_frame_rows=0, show=1):
    """scene entity -> cell, and how much of the scene the frame keeps."""
    out = []
    for F in Fs:
        cls = class_table(F)
        for f in range(F.N):
            own = F.owner[f]
            nz = own > 0
            cnt = collections.Counter(own[nz].tolist())
            g = F.gt[f]
            obj_tags = {k: v for k, v in cnt.items() if cls[k].startswith("obj:")}
            out.append(dict(
                set=os.path.basename(F.d), frame=f, n_scene_objects=g["n_objects"],
                n_distinct_entities_in_frame=len(cnt), n_object_entities=len(obj_tags),
                n_arch_entities=len(cnt) - len(obj_tags),
                cells_total=F.W * F.H, cells_written=int(nz.sum()),
                cells_empty=int((~nz).sum()), object_cells=sum(obj_tags.values()),
                object_entities_lost=g["n_objects"] - len(obj_tags),
                scene_triangles=g["object_triangles"] + g["scene_triangles"],
                rendered=g["rendered_triangles"], clipped=g["clipped_triangles"],
            ))
    return out


def per_entity_table(Fs, limit=40):
    """THE artifact: one row per (run, frame, 3D entity) -> cells it won."""
    rows = []
    for F in Fs:
        cls = class_table(F)
        for f in range(0, F.N, 5):
            own = F.owner[f]
            cnt = collections.Counter(own[own > 0].tolist())
            g = F.gt[f]
            objs = g["objects"]
            for tag, cells in cnt.items():
                p = F.owner_table[tag - 1].split("|")
                if p[0] == "obj":
                    idx = int(p[1])
                    pos = objs[idx]["pos"] if idx < len(objs) else [0, 0, 0]
                    cam = g["cam"]
                    dist = float(np.hypot(pos[0] - cam[0], pos[2] - cam[2]))
                    rows.append(dict(run=os.path.basename(F.d), frame=f, kind="object",
                                     cls=p[2], tex=p[3], pos=pos, cells=cells, dist=dist,
                                     zmin=float(F.z[f][own == tag].min()),
                                     zmax=float(F.z[f][own == tag].max())))
                else:
                    rows.append(dict(run=os.path.basename(F.d), frame=f, kind="zone",
                                     cls="zone", tex=p[3], pos=None, cells=cells, dist=None,
                                     zmin=float(F.z[f][own == tag].min()),
                                     zmax=float(F.z[f][own == tag].max())))
    return rows


# ---------------------------------------------------------------- 3
def glyph_stability(Fs, max_classes=8):
    """Distinct glyphs the SAME entity class shows, as a function of depth."""
    # collect (class, z, glyph) for every written cell
    data = collections.defaultdict(list)   # class -> list of (z, glyph)
    for F in Fs:
        cls = class_table(F)
        for f in range(F.N):
            own = F.owner[f]
            m = own > 0
            for c in np.unique(own[m]):
                k = (c.item() if hasattr(c, "item") else c)
                sel = m & (own == k)
                name = cls[k]
                zs = F.z[f][sel]
                gs = F.ch[f][sel]
                for z, g in zip(zs.tolist(), gs.tolist()):
                    data[name].append((z, chr(g)))
    out = []
    for name, pts in data.items():
        glyphs = sorted({g for _, g in pts})
        zs = np.array([z for z, _ in pts])
        per_glyph = {g: (round(float(zs[[g == x[1] for x in pts]].mean()), 4), int(sum(1 for x in pts if x[1] == g)))
                     for g in glyphs}
        out.append(dict(cls=name, n_cells=len(pts), n_distinct_glyphs=len(glyphs), glyphs="".join(glyphs),
                        z_range=(round(float(zs.min()), 4), round(float(zs.max()), 4)),
                        per_glyph_z=per_glyph))
    out.sort(key=lambda r: -r["n_cells"])
    return out, data


# ---------------------------------------------------------------- 4 + 5
def label_matrix(Fs):
    """(features..., label) for every cell of every frame, labels from the scene graph."""
    X, Y, G = [], [], []
    for gi, F in enumerate(Fs):
        cls = class_table(F)
        for f in range(F.N):
            own = F.owner[f]
            m = own > 0
            X.append((F.ch[f][m], F.col[f][m], F.z[f][m], gi, f))
            Y.append(cls[own[m]])
    return X, Y


def run_arms(Fs, seed=0, holdout=0.5, shuffle_ctrl=True, verbose=True):
    """
    Arms.  A reader sees one frame at a time and must name, for every cell, the class
    of the 3D entity that the z-buffer says won it.  1-NN over training frames, on
    discretised features.  Ground truth is the scene graph, never the frame.

      A  Data          : glyph only
      B  Data+Color    : glyph + packed 8-bit colour
      C  Color only    : colour alone (upper bound on what colour carries)
      D  z only        : depth alone (the channel the glyph is a function of)
      CTRL-a  shuffled glyphs   (permutation of the glyph field within each frame)
      CTRL-b  random colour     (uniform over the 256 codes)
      CTRL-c  random everything  (glyph + colour randomised)
      BASE    majority class     (the floor any arm has to beat)
    """
    X, Y = label_matrix(Fs)
    nF = [len(x[4]) for x in X]
    offs = np.cumsum([0] + nF)
    total = offs[-1]
    cut = int(total * holdout)

    rng = np.random.default_rng(seed)

    ch = np.concatenate([x[0] for x in X])
    col = np.concatenate([x[1] for x in X])
    yy = np.concatenate([np.array(y) for y in Y])
    fidx = np.concatenate([np.full(len(y), i, dtype=np.int32) for i, y in enumerate(Y)])

    variants = {}
    variants["A:Data"] = ch
    variants["B:Data+Color"] = (ch.astype(np.int32) * 256 + col.astype(np.int32))
    variants["C:Color"] = col
    variants["D:z"] = np.digitize(np.concatenate([x[2] for x in X]), np.linspace(0, 1, 33)[1:-1]).astype(np.int32)
    if shuffle_ctrl:
        s = np.array([rng.permutation(x[0]) for x in X], dtype=object)
        variants["CTRL-shuffled-glyph"] = np.concatenate(list(s)).astype(np.int32)
        variants["CTRL-random-colour"] = rng.integers(0, 256, size=total, dtype=np.int32)
        variants["CTRL-both-random"] = (rng.integers(0, 11, size=total, dtype=np.int32) * 256
                                        + rng.integers(0, 256, size=total, dtype=np.int32))

    classes, cls_idx = np.unique(yy, return_inverse=True)
    majority = np.bincount(cls_idx, minlength=len(classes)).argmax()

    # train/val split by FRAME, so no cell from a test frame is in the training set
    train_mask = np.zeros(total, bool)
    for i in range(len(X)):
        train_mask[offs[i]:offs[i + 1]] = offs[i] < cut

    results = {}
    for name, feat in variants.items():
        # 1-NN on a hashed feature table, fitted on the training half
        key = feat.astype(np.int64)
        # bucket identical training features, take the majority label of each bucket
        order = np.argsort(key[train_mask], kind="stable")
        ktr = key[train_mask][order]
        ltr = cls_idx[train_mask][order]
        uniq, start = np.unique(ktr, return_index=True)
        # majority label per feature bucket (vectorised-ish: counts via bincount trick)
        bucket_lab = np.zeros(len(uniq), dtype=np.int64)
        pos = np.searchsorted(uniq, ktr)
        order2 = np.argsort(pos, kind="stable")
        pos_s, lab_s = pos[order2], ltr[order2]
        bounds = np.searchsorted(pos_s, np.arange(len(uniq) + 1))
        for b in range(len(uniq)):
            seg = lab_s[bounds[b]:bounds[b + 1]]
            bucket_lab[b] = np.bincount(seg, minlength=len(classes)).argmax()
        test = ~train_mask
        pred = bucket_lab[np.searchsorted(uniq, key[test])]
        truth = cls_idx[test]
        res = score(truth, pred, classes, len(classes), cls_idx[test])
        res["coverage"] = float((np.searchsorted(uniq, key[test]) < len(uniq)).mean())
        results[name] = res

    # majority-class baseline on the test half
    pred = np.full(truth.shape, majority)
    results["BASE-majority"] = score(truth, pred, classes, len(classes), truth)

    if verbose:
        hdr = f"{'arm':>20} {'macroF1':>8} {'microF1':>8} {'acc':>7} {'enemyF1':>8} {'enemyP':>7} {'enemyR':>7} {'cover':>6}"
        print(hdr)
        print("-" * len(hdr))
        for k, v in results.items():
            print(f"{k:>20} {v['macroF1']:>8.4f} {v['microF1']:>8.4f} {v['acc']:>7.4f} "
                  f"{v['enemyF1']:>8.4f} {v['enemyP']:>7.4f} {v['enemyR']:>7.4f} {v['coverage']:>6.3f}")
        print("\nclasses:", ", ".join(f"{i}:{c}" for i, c in enumerate(classes)))
    return results, classes


def score(truth, pred, classes, K, _=None):
    tp = np.zeros(K); fp = np.zeros(K); fn = np.zeros(K)
    for k in range(K):
        tp[k] = np.sum((pred == k) & (truth == k))
        fp[k] = np.sum((pred == k) & (truth != k))
        fn[k] = np.sum((pred != k) & (truth == k))
    f1 = np.where(2 * tp + fp + fn > 0, 2 * tp / np.maximum(2 * tp + fp + fn, 1), 0.0)
    pres = np.where(tp + fp > 0, tp / np.maximum(tp + fp, 1), 0.0)
    recs = np.where(tp + fn > 0, tp / np.maximum(tp + fn, 1), 0.0)
    present = (tp + fn) > 0
    enemy = np.array([i for i, c in enumerate(classes) if c.startswith("obj:")])
    em = present[enemy] if len(enemy) else np.array([], bool)
    return dict(macroF1=float(f1[present].mean()), microF1=float(f1[present].sum() / present.sum()),
                acc=float((pred == truth).mean()),
                enemyF1=float(f1[enemy][em].mean()) if em.any() else 0.0,
                enemyP=float(pres[enemy][em].mean()) if em.any() else 0.0,
                enemyR=float(recs[enemy][em].mean()) if em.any() else 0.0,
                per_class={classes[i]: round(float(f1[i]), 4) for i in range(K) if present[i]})
