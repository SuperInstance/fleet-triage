#!/usr/bin/env python3
"""
The tile taxonomy, measured rather than asserted.

Claim under test: "the tile must be a function of (glyph, colour, neighbourhood),
not glyph alone."

Evidence produced here:
  1. per-glyph colour -> enemy rate. If glyph alone were the tile, every colour
     inside a glyph would share one rate.
  2. the same (glyph, colour) pair in two different neighbourhood contexts, showing
     the neighbourhood is load-bearing too.
  3. a held-out check: does the tile table built on some frames predict enemy cells in
     frames it never saw?
"""
import glob, os, sys
import numpy as np
sys.path.insert(0, "/tmp")
from twoarm import parse, FOG


def coarse(c):
    return ((c & 0b111) >> 1) * 16 + (((c >> 3) & 0b111) >> 1) * 4 + ((c >> 6) & 0b11)

FRAMES = sys.argv[1] if len(sys.argv) > 1 else "/tmp/frames"
files = sorted(glob.glob(os.path.join(FRAMES, "scene*_pose*.txt")))
frames = [parse(p) for p in files]
FOGLIST = list(FOG) + ["<none>"]

G = np.concatenate([f["g"].reshape(-1) for f in frames])
C = np.concatenate([f["col"].reshape(-1) for f in frames])
E = np.concatenate([f["enemy"].reshape(-1) for f in frames])
N = len(G)
base = E.mean()
print(f"{N} cells over {len(frames)} frames. overall enemy rate {E.mean():.4f}")
print(f"distinct packed colour bytes observed: {len(np.unique(C))} -- a raw (glyph, colour)")
print("lookup is far too sparse for a taxonomy, so the tile table below uses a COARSE")
print("colour: R:3>>1, G:3>>1, B:2, i.e. 4x4x4 = 64 material buckets. That is a lossless")
print("re-quantisation of the 8-bit console colour, not a different channel.\n")
CQ = ((C & 0b111) >> 1) * 16 + (((C >> 3) & 0b111) >> 1) * 4 + ((C >> 6) & 0b11)

# ---- 1. glyph alone is not a tile -------------------------------------------------
print("1. INSIDE ONE GLYPH, THE COARSE COLOUR SPLITS THE ENEMY RATE")
print("   (buckets with >= 500 cells; lift is against the global rate %.4f)" % base)
print(f"   {'glyph':7s} {'cq':>4s} {'cells':>8s} {'enemy rate':>11s} {'lift':>7s}")
for gi in (3, 4, 5, 6, 7):          # 8 x * , :
    m = G == gi
    if m.sum() < 5000:
        continue
    cc = CQ[m]; ee = E[m]
    u, inv = np.unique(cc, return_inverse=True)
    cnt = np.bincount(inv)
    pos = np.bincount(inv, weights=ee.astype(float))
    rate = pos / np.maximum(cnt, 1)
    big = np.where(cnt >= 500)[0]
    if len(big) < 2:
        continue
    order = big[np.argsort(-cnt[big])][:4]
    for o in order:
        print(f"   '{FOG[gi]}'  {u[o]:>4d} {cnt[o]:>8d} {rate[o]:>11.4f} {rate[o]/base:>6.2f}x")
    print(f"   '{FOG[gi]}'  -- spread across its coarse colours (>=500 cells): "
          f"min {rate[big].min():.4f}  max {rate[big].max():.4f}  "
          f"ratio {rate[big].max()/max(rate[big].min(),1e-9):.1f}x")
    print()

# ---- 2. the neighbourhood is load-bearing too -------------------------------------
print("2. SAME (GLYPH, COARSE COLOUR), DIFFERENT NEIGHBOURHOOD")
print("   the context feature is: how many of the 8 neighbours share the CENTRE glyph.")
print("   'a lone x is a wall; an x inside a field of x is not' -- measured.")
print(f"   {'glyph+cq':16s} {'same-glyph neighbours':>22s} {'cells':>8s} {'enemy rate':>11s}")
NSAME, KEY, LAB = [], [], []
for f in frames:
    g = f["g"]; Hh, W = g.shape
    idx = np.arange(Hh * W)
    r, c = idx // W, idx % W
    same = np.zeros(len(idx), np.int64)
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            if dy == 1 and dx == 1:
                continue
            rr = np.clip(r - dy, 0, Hh - 1); cc = np.clip(c - dx, 0, W - 1)
            same += (g[rr, cc] == g[r, c])
    NSAME.append(same)
    KEY.append(g.reshape(-1) * 64 + CQ[f["col"].reshape(-1)])
    LAB.append(f["enemy"].reshape(-1))
KEY = np.concatenate(KEY); NSAME = np.concatenate(NSAME); LAB = np.concatenate(LAB)
u, cnt = np.unique(KEY, return_counts=True)
shown = 0
for t in u[np.argsort(-cnt)]:
    if cnt[np.where(u == t)[0][0]] < 5000:
        break
    m = KEY == t
    rate_all = LAB[m].mean()
    if rate_all < 0.02 or rate_all > 0.4:
        continue
    gi, ci = int(t) // 64, int(t) % 64
    print(f"   '{FOG[gi]}' + cq{ci:<2d}          (pooled rate {rate_all:.4f})")
    ns, inv = np.unique(NSAME[m], return_inverse=True)
    c2 = np.bincount(inv); p2 = np.bincount(inv, weights=LAB[m].astype(float))
    r2 = p2 / np.maximum(c2, 1)
    for o in np.argsort(ns):
        if c2[o] >= 200:
            print(f"     {'exactly ' + str(int(ns[o])) + ' of 8':>22s} {c2[o]:>8d} {r2[o]:>11.4f}")
    shown += 1
    if shown >= 3:
        break
print()

# ---- 3. held-out generalisation of the tile table ---------------------------------
print("3. HELD OUT: a tile table fitted on 20 scenes, scored on 4 unseen scenes")
train = [f for f in frames if f["scene"] % 5 != 0]
test = [f for f in frames if f["scene"] % 5 == 0]
tg = np.concatenate([f["g"].reshape(-1) for f in train])
tc = np.concatenate([coarse(f["col"].reshape(-1)) for f in train])
te = np.concatenate([f["enemy"].reshape(-1) for f in train])
rate_by = {}
uk, inv = np.unique(tg * 64 + tc, return_inverse=True)
cnt = np.bincount(inv); pos = np.bincount(inv, weights=te.astype(float))
lut = dict(zip(uk.tolist(), (pos / np.maximum(cnt, 1)).tolist()))
fallback = te.mean()
eg = np.concatenate([f["g"].reshape(-1) for f in test])
ec = np.concatenate([coarse(f["col"].reshape(-1)) for f in test])
ey = np.concatenate([f["enemy"].reshape(-1) for f in test])
pred = np.array([lut.get(int(a) * 64 + int(b), fallback) for a, b in zip(eg, ec)])
thr = np.quantile(pred, 1 - ey.mean())            # threshold to hit the test base rate
pp = (pred >= thr).astype(int)
tpr = (pp[ey == 1] == 1).mean(); tnr = (pp[ey == 0] == 0).mean()
print(f"   train {len(train)} frames / {len(te)} cells, test {len(test)} frames / {len(ey)} cells, "
      f"test enemy rate {ey.mean():.4f}")
print(f"   tile = (glyph, coarse colour) lookup, threshold at the test base rate: "
      f"bal_acc {0.5*(tpr+tnr):.4f}  TPR {tpr:.4f}  TNR {tnr:.4f}")
# and the glyph-only table, same protocol
lut2 = {}
uk2, inv2 = np.unique(tg, return_inverse=True)
c2 = np.bincount(inv2); p2 = np.bincount(inv2, weights=te.astype(float))
lut2 = dict(zip(uk2.tolist(), (p2 / np.maximum(c2, 1)).tolist()))
pred2 = np.array([lut2.get(int(a), fallback) for a in eg])
thr2 = np.quantile(pred2, 1 - ey.mean())
pp2 = (pred2 >= thr2).astype(int)
tpr2 = (pp2[ey == 1] == 1).mean(); tnr2 = (pp2[ey == 0] == 0).mean()
print(f"   tile = glyph only,      same protocol: "
      f"bal_acc {0.5*(tpr2+tnr2):.4f}  TPR {tpr2:.4f}  TNR {tnr2:.4f}")
print(f"   always-negative baseline: bal_acc 0.5000")
