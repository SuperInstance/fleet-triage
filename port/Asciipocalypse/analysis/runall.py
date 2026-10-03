#!/usr/bin/env python3
"""PROJECTION-LOSS measurements. Memory-frugal: one run in RAM at a time."""
import collections, glob, json, os, sys
import numpy as np
from frames import Frames

FOGCH = "@&#8x*,:. "                                # Rasterizer.cs:22
FOG = np.array([ord(c) for c in FOGCH])            # index 0 = nearest bucket
LUT = np.full(256, -1, np.int32)                    # char code -> fog bucket
for _i, _c in enumerate(FOGCH):
    LUT[ord(_c)] = _i
OBS = sorted(glob.glob('/tmp/fx/run_*'))
WALK = sorted(glob.glob('/tmp/fx/walk_*'))
EYE = sorted(glob.glob('/tmp/fx/eye_*'))
R = {}          # results


def sec(t):
    print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78, flush=True)


def cls_of(F):
    names = ["empty"]
    for o in F.owner_table:
        p = o.split("|")
        names.append(("obj:" + p[2] + "/" + p[3]) if p[0] == "obj" else ("arch:" + p[3]))
    return names


# ------------------------------------------------------------------ 0
def provenance():
    m = json.load(open(os.path.join(OBS[0], 'meta.json')))[0]
    R['meta'] = {k: m[k] for k in ("provenance", "source", "texture_path", "camera_placement",
                                   "eye_easy", "audio_calls_suppressed", "cell_stride_bytes")}
    R['meta']['textures_loaded'] = len(m['textures_loaded'])
    R['meta']['nonopaque_alpha_textures'] = m['nonopaque_alpha_textures']
    for k, v in R['meta'].items():
        print(f"  {k}: {v}")


# ------------------------------------------------------------------ 1+2
def collapse(paths, label, every=1):
    """scene entity -> cell, and the cells nothing won."""
    acc = collections.Counter()
    glyph = collections.defaultdict(lambda: [np.zeros(10), np.zeros(10)])   # cls -> per-bucket z sum,count
    nframes = 0
    per_class_cells = collections.Counter()
    per_class_inst = collections.Counter()
    per_class_med = collections.defaultdict(list)
    for p in paths:
        F = Frames(p)
        names = cls_of(F)
        for f in range(0, F.N, every):
            own = F.owner[f]
            m = (own > 0) & (F.hud[f] == 0)
            nframes += 1
            acc['cells_total'] += F.W * F.H
            acc['cells_3d'] += int(m.sum())
            acc['cells_hud'] += int((F.hud[f] == 1).sum())
            acc['cells_blank'] += int(((own == 0) & (F.hud[f] == 0)).sum())
            acc['scene_objects'] += F.gt[f]['n_objects']
            acc['scene_triangles'] += F.gt[f]['object_triangles'] + F.gt[f]['scene_triangles']
            acc['rendered_triangles'] += F.gt[f]['rendered_triangles']
            acc['clipped_triangles'] += F.gt[f]['clipped_triangles']
            tags, cnts = np.unique(own[m], return_counts=True)
            acc['distinct_entities'] += len(tags)
            for t, c in zip(tags.tolist(), cnts.tolist()):
                nm = names[t]
                if nm.startswith("obj:"):
                    acc['object_entities'] += 1
                    acc['object_cells'] += c
                    per_class_cells[nm] += c
                    per_class_inst[nm] += 1
                    per_class_med[nm].append(c)
                else:
                    acc['arch_entities'] += 1
                    acc['arch_cells'] += c
            # glyph ramp, vectorised over cells
            kidx = LUT[F.ch[f][m]]
            z = F.z[f][m]
            nam = np.array(names)
            cn = nam[own[m]]
            for nm in np.unique(cn):
                sm = cn == nm
                k = kidx[sm]
                zz = z[sm]
                good = k >= 0
                k = k[good]
                if len(k):
                    glyph[nm][0] += np.bincount(k, weights=zz[good], minlength=10)
                    glyph[nm][1] += np.bincount(k, minlength=10)
        del F
    out = {k: v / nframes for k, v in acc.items()}
    out['frames'] = nframes
    out['entity_collapse_ratio'] = out['scene_objects'] / out['distinct_entities']
    out['object_occlusion_rate'] = 1 - out['object_entities'] / out['scene_objects']
    out['object_cell_share'] = out['object_cells'] / out['cells_3d']
    R[label] = out
    R[label + '_per_class'] = {k: dict(instances=v, total_cells=per_class_cells[k],
                                        median_cells=float(np.median(per_class_med[k])))
                               for k, v in per_class_inst.most_common()}
    ramps = {}
    for nm, (zs, cs) in glyph.items():
        nz = cs > 0
        ramps[nm] = dict(cells=int(cs.sum()), distinct_glyphs=int(nz.sum()),
                         glyphs="".join(chr(FOG[i]) for i in range(10) if nz[i]),
                         mean_z={chr(FOG[i]): round(float(zs[i] / cs[i]), 5) for i in range(10) if nz[i]})
    R[label + '_ramps'] = dict(sorted(ramps.items(), key=lambda kv: -kv[1]['cells']))
    return out


# ------------------------------------------------------------------ 3
def recoverability(paths):
    eg, eo, dd, nc, loc = [], [], [], [], []
    for p in paths:
        bp = json.load(open(os.path.join(p, 'backproj.json')))
        for b in bp:
            for o in b['objects']:
                if not np.isnan(o['err_glyph']):
                    eg.append(o['err_glyph'])
                eo.append(o['err_oracle_depth']); dd.append(o['true_dist']); nc.append(o['cells'])
                loc.append(np.hypot(o['true_i'] - o['centroid_i'], o['true_j'] - o['centroid_j']))
    eg, eo, dd, nc, loc = map(np.array, (eg, eo, dd, nc, loc))
    R['recover'] = dict(
        n=len(dd),
        err_glyph=dict(median=float(np.median(eg)), p90=float(np.percentile(eg, 90))),
        err_oracle=dict(median=float(np.median(eo)), p90=float(np.percentile(eo, 90))),
        dist=dict(median=float(np.median(dd)), p90=float(np.percentile(dd, 90))),
        loc_cells=dict(median=float(np.median(loc)), p90=float(np.percentile(loc, 90)),
                       exact=float(np.mean(loc < 0.5))),
        by_size=[])
    for lo, hi in ((1, 4), (4, 20), (20, 100), (100, 10 ** 9)):
        m = (nc >= lo) & (nc < hi)
        if m.sum() > 3:
            R['recover']['by_size'].append(dict(lo=lo, hi=(None if hi > 10 ** 8 else hi), n=int(m.sum()),
                                                dist=float(np.median(dd[m])),
                                                err_glyph=float(np.median(eg[m])),
                                                err_oracle=float(np.median(eo[m]))))


# ------------------------------------------------------------------ 4+5
def arms(paths, tag, stride=4, cap=900_000, seed=7):
    """
    A reader sees a frame and must name, for every cell, the class of the 3D entity the
    z-buffer says won it.  1-NN on the observed channels, fitted on the first half of the
    runs and tested on the rest.  Labels come from the scene graph, never from the frame.
    """
    rng = np.random.default_rng(seed)
    codes = {}          # class name -> code, grows across runs
    allnames = []
    feats = collections.defaultdict(list)
    labs = []
    run_of = []
    ntot = 0
    for ri, p in enumerate(paths):
        F = Frames(p)
        names = cls_of(F)
        for f in range(0, F.N, stride):
            own = F.owner[f]
            m = (own > 0) & (F.hud[f] == 0)
            n = int(m.sum())
            take = min(n, max(1, cap // (len(paths) * len(range(0, F.N, stride)))))
            idx = np.nonzero(m.ravel())[0]
            if len(idx) > take:
                idx = rng.choice(idx, take, replace=False)
            ch = F.ch[f].ravel()[idx].astype(np.int32)
            col = F.col[f].ravel()[idx].astype(np.int32)
            z = F.z[f].ravel()[idx]
            ownr = own.ravel()[idx]
            keep = ownr > 0
            ch, col, z, ownr = ch[keep], col[keep], z[keep], ownr[keep]
            for t in np.unique(ownr).tolist():
                nm = names[t]
                if nm not in codes:
                    codes[nm] = len(allnames)
                    allnames.append(nm)
            yy = np.fromiter((codes[names[t]] for t in ownr.tolist()), np.int32, len(ownr))
            labs.append(yy); run_of.append(np.full(len(yy), ri, np.int32))
            feats['A:Data'].append(ch)
            feats['B:Data+Color'].append(ch * 256 + col)
            feats['C:Color'].append(col)
            feats['D:depth-only'].append(np.digitize(z, np.linspace(-1, 1, 33)[1:-1]).astype(np.int32))
            feats['CTRL-shuffled-glyph'].append(rng.permutation(ch))
            feats['CTRL-random-colour'].append(rng.integers(0, 256, len(ch), dtype=np.int32))
            feats['CTRL-both-random'].append(rng.integers(0, 11, len(ch), dtype=np.int32) * 256
                                             + rng.integers(0, 256, len(ch), dtype=np.int32))
            ntot += len(yy)
        del F
    labs = np.concatenate(labs); run_of = np.concatenate(run_of)
    names = allnames
    # split WITHIN each level generator, never across it: floor 1 and floor 9 share no
    # texture at all, so a split across them would be testing "can you name a game you
    # have never seen", not "what does the channel carry".
    base = [os.path.basename(p) for p in paths]
    fam = {}
    for i, b in enumerate(base):
        fam.setdefault(b.split("_")[1][:1], []).append(i)
    tr = np.zeros(len(labs), bool)
    te = None
    for k, idxs in fam.items():
        half = len(idxs) // 2
        for i in idxs[:max(1, half)]:
            tr |= (run_of == i)
    te = ~tr
    K = len(names)
    maj = np.bincount(labs[tr], minlength=K).argmax()
    out = {}
    for name, chunks in feats.items():
        key = np.concatenate(chunks)
        ktr = key[tr]
        order = np.argsort(ktr, kind="stable")
        ktr_s, ltr_s = ktr[order], labs[tr][order]
        u, inv = np.unique(ktr_s, return_inverse=True)
        # majority label per bucket, vectorised via sorted grouping
        bounds = np.searchsorted(inv, np.arange(len(u) + 1))
        blab = np.zeros(len(u), np.int32)
        for b in range(len(u)):
            seg = ltr_s[bounds[b]:bounds[b + 1]]
            blab[b] = np.bincount(seg, minlength=K).argmax()
        pos = np.searchsorted(u, key[te])
        ok = pos < len(u)
        pred = np.full(int(te.sum()), maj, np.int32)
        pred[ok] = blab[pos[ok]]
        out[name] = score(labs[te], pred, names, K)
    pred = np.full(int(te.sum()), maj, np.int32)
    out['BASE-majority'] = score(labs[te], pred, names, K)
    out['_n'] = dict(train=int(tr.sum()), test=int(te.sum()), runs=len(paths),
                     runs_train=[base[i] for v in fam.values() for i in v[:max(1, len(v) // 2)]],
                     runs_test=[base[i] for v in fam.values() for i in v[max(1, len(v) // 2):]])
    R[tag] = out
    del feats, labs
    return out


def score(truth, pred, names, K):
    tp = np.bincount(truth[pred == truth], minlength=K).astype(float)
    pp = np.bincount(pred, minlength=K).astype(float)
    ap = np.bincount(truth, minlength=K).astype(float)
    f1 = np.where(2 * tp + pp + ap > 0, 2 * tp / np.maximum(2 * tp + pp + ap, 1), 0.0)
    pres = np.where(pp > 0, tp / np.maximum(pp, 1), 0.0)
    recs = np.where(ap > 0, tp / np.maximum(ap, 1), 0.0)
    present = ap > 0
    enemy = np.array([i for i, c in enumerate(names) if c.startswith("obj:")])
    em = present[enemy]
    return dict(macroF1=float(f1[present].mean()), microF1=float(f1[present].sum() / present.sum()),
                acc=float((pred == truth).mean()),
                enemyF1=float(f1[enemy][em].mean()) if em.any() else 0.0,
                enemyP=float(pres[enemy][em].mean()) if em.any() else 0.0,
                enemyR=float(recs[enemy][em].mean()) if em.any() else 0.0,

                per_class={names[i]: round(float(f1[i]), 4) for i in range(K) if present[i]})


def show(tag, title):
    o = R[tag]
    print(f"\n  {title}")
    print(f"  {'arm':>22} {'macroF1':>8} {'microF1':>8} {'acc':>7} {'enemyF1':>8} {'enemyP':>7} {'enemyR':>7}")
    print("  " + "-" * 72)
    order = ["A:Data", "B:Data+Color", "C:Color", "D:depth-only",
             "CTRL-shuffled-glyph", "CTRL-random-colour", "CTRL-both-random", "BASE-majority"]
    for k in order:
        if k not in o:
            continue
        v = o[k]
        print(f"  {k:>22} {v['macroF1']:>8.4f} {v['microF1']:>8.4f} {v['acc']:>7.4f} "
              f"{v['enemyF1']:>8.4f} {v['enemyP']:>7.4f} {v['enemyR']:>7.4f}")
    print(f"  (train cells {o['_n']['train']}, test cells {o['_n']['test']}, "
          f"train runs {o['_n']['runs_train']}, test runs {o['_n']['runs_test']})")


if __name__ == "__main__":
    sec("0. provenance")
    provenance()
    print(f"  runs: {len(OBS)} observe, {len(WALK)} walk, {len(EYE)} eyeeasy")

    sec("1+2. correspondence and collapse (scripted observer, 3D region only)")
    o = collapse(OBS, "observe", every=2)
    for k, v in o.items():
        print(f"  {k:26s} {v:12.2f}")
    print("\n  per class:")
    for k, v in R['observe_per_class'].items():
        print(f"    {k:46s} {v['instances']:6d} instances  median {v['median_cells']:7.1f} cells  total {v['total_cells']:10d}")

    sec("1b. the same, free walk (no scripted observer)")
    ow = collapse(WALK, "walk", every=4)
    for k in ("scene_objects", "distinct_entities", "entity_collapse_ratio", "object_entities",
              "object_entities" if False else "object_cells", "cells_3d", "object_cell_share",
              "object_occlusion_rate"):
        if k in ow:
            print(f"  {k:26s} {ow[k]:12.2f}")

    sec("3. the fog ramp, measured: distinct glyphs per 3D entity class")
    for nm, r in R['observe_ramps'].items():
        print(f"  {nm:46s} cells {r['cells']:9d}  distinct glyphs {r['distinct_glyphs']:3d}  {r['glyphs']!r}")
    mon = [k for k in R['observe_ramps'] if 'BasicMonster' in k or 'ShotgunDude' in k]
    for k in mon[:1]:
        print(f"\n  monster ramp for {k}  (glyph -> mean NDC z, measured from the z-buffer):")
        for g, z in R['observe_ramps'][k]['mean_z'].items():
            print(f"    {g!r:5s} z {z:.5f}")

    sec("4. recoverability: what a downstream reader still gets")
    recoverability(OBS)
    rc = R['recover']
    print(f"  instances: {rc['n']}")
    print(f"  world position from the glyph's depth : median {rc['err_glyph']['median']:.2f}  p90 {rc['err_glyph']['p90']:.2f} units")
    print(f"  world position with ORACLE depth       : median {rc['err_oracle']['median']:.2f}  p90 {rc['err_oracle']['p90']:.2f} units  <- pure raster loss")
    print(f"  true distance to the object            : median {rc['dist']['median']:.1f}  p90 {rc['dist']['p90']:.1f} units")
    print(f"  screen localisation error              : median {rc['loc_cells']['median']:.2f} cells, exact {rc['loc_cells']['exact']*100:.1f}%")
    for b in rc['by_size']:
        print(f"    size {b['lo']}-{b['hi']} cells  n={b['n']:6d}  dist {b['dist']:6.1f}  err_glyph {b['err_glyph']:7.2f}  err_oracle {b['err_oracle']:5.2f}")

    sec("5. the two arms and the controls")
    arms(OBS, "arms")
    show("arms", "normal projection (glyph = depth ramp, colour = texture identity)")
    arms(EYE, "arms_eye")
    show("arms_eye", "EyeEasy projection, same task (Rasterizer.cs:124: every cell '@', depth in brightness)")
    arms(OBS, "arms_ctrl2", seed=99)
    show("arms_ctrl2", "same, second seed -- the ranking must not depend on the 1-NN draw")

    json.dump(R, open('results.json', 'w'), indent=1, default=float)
    print("\nwrote results.json")
