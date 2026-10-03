"""E1+E2 -- the flagship Lenia creature, measured.

E1  Is there an intrinsic cell count?  Sweep the occupancy threshold and time.
E2  Is a cell a scar?  Write a mark into one cell, then track where the mark goes.
    If the mark is carried by the glider, the substrate has no fixed sites: the
    "cell" is a co-moving phase of the pattern, not a persistent entity.

Ground truth: dynamics verified bit-exact against Chakazul's own Automaton
(see e1d; kernel max|d|=3.9e-18, field max|d|=1.2e-15 after 5 steps).
All CPU / numpy.
"""
import sys, json
sys.path.insert(0, '/tmp/nca/exp')
import numpy as np
import chan_ref as C

S, R, T, M, SG, B = 192, 13, 10, 0.15, 0.015, (1.0,)
A0 = np.load('/tmp/nca/exp/orbium.npy')
STEPS = 400


def place(f, o=None):
    A = np.zeros((S, S))
    o = S // 2 - f.shape[0] // 2 if o is None else o
    A[o:o + f.shape[0], o:o + f.shape[1]] = f
    return A, o


# ============================ E1 =============================================
def rec(t, A):
    prev = getattr(rec, 'p', None)
    c = C.com(A)
    if prev is not None:
        c = C.com(A, wrapped=prev)
    rec.p = c
    _gyr = None
    Bm = np.where(A > 0.1, A, 0.0); idx = np.arange(S, dtype=np.float64)
    dy = (idx[:, None] - c[0] + S / 2) % S - S / 2
    dx = (idx[None, :] - c[1] + S / 2) % S - S / 2
    gyr = float(np.sqrt((Bm * (dy ** 2 + dx ** 2)).sum() / max(Bm.sum(), 1e-12)))
    return dict(t=t, mass=C.mass(A), cx=c[0], cy=c[1], gyr=gyr,
                **{f'n_{k}': C.support(A, v) for k, v in
                   {'001': 0.01, '005': 0.05, '010': 0.10, '020': 0.20, '050': 0.50}.items()})


def traj(A0f, steps=STEPS):
    """full field trajectory, bit-exact port"""
    Kg = C.make_kernel(R, B, G=S, centred=True); FK = np.fft.fftn(Kg)
    A = A0f.copy(); out = [A.copy()]; dt = 1.0 / T
    for _ in range(steps):
        U = np.fft.fftshift(np.real(np.fft.ifftn(np.fft.fftn(A) * FK)))
        A = np.clip(A + dt * C.growth_func1(U, M, SG), 0.0, 1.0)
        out.append(A.copy())
    return out


A_init, o = place(A0)
TR = traj(A_init); Af = TR[-1]
hist = [rec(t, TR[t]) for t in range(STEPS + 1)]
h0, hT = hist[0], hist[-1]
speed = np.hypot(hT['cx'] - h0['cx'], hT['cy'] - h0['cy']) / STEPS

print("=== E1: cell count of Orbium unicaudatus (R=13,T=10,m=0.15,s=0.015,b=1) ===")
print(f"  glide speed        : {speed:.4f} cells/step   ({speed*T:.3f} cells/unit-time)")
print(f"  mass  t=0 -> t={STEPS} : {h0['mass']:.3f} -> {hT['mass']:.3f}  "
      f"({100*(hT['mass']/h0['mass']-1):+.2f}%)")
print(f"  gyradius t=0 -> t={STEPS}: {h0['gyr']:.2f} -> {hT['gyr']:.2f}")
print("  occupancy vs THRESHOLD (t=0, and mean over the last 100 steps):")
for k in ['n_001', 'n_005', 'n_010', 'n_020', 'n_050']:
    v = np.array([x[k] for x in hist])
    thr = {'n_001': 0.01, 'n_005': 0.05, 'n_010': 0.10, 'n_020': 0.20, 'n_050': 0.50}[k]
    print(f"    thr={thr:4.2f}  n(t=0)={v[0]:4d}   n: min={v.min():4d} max={v.max():4d} "
          f"mean={v.mean():7.2f} std={v.std():6.2f} ({100*v.std()/v.mean():5.2f}%)  distinct={len(set(v.tolist())):3d}")
v10 = np.array([x['n_010'] for x in hist])
print(f"  at thr=0.10 the 'cell count' takes {len(set(v10.tolist()))} distinct values "
      f"over {STEPS} steps, range {v10.min()}..{v10.max()}")
print(f"  same creature, threshold 0.01 vs 0.50 at t=0: "
      f"{hist[0]['n_001']} vs {hist[0]['n_050']} cells  (ratio {hist[0]['n_001']/hist[0]['n_050']:.1f}x)")

# ============================ E2 =============================================
print("\n=== E2: write a mark into one cell -- does the cell remember? ===")
# reference trajectory
REF = traj(A_init)
# perturbed: a small bump written at one lattice site at t=0
pk = (S // 2 + 2, S // 2 - 3)
Apert = A_init.copy()
y, x = np.mgrid[0:S, 0:S]
Apert += 0.05 * np.exp(-((y - pk[0]) ** 2 + (x - pk[1]) ** 2) / (2 * 0.8 ** 2))
PERT = traj(Apert)
dev = np.abs(np.array(PERT) - np.array(REF))
rows = []
for t in [1, 2, 5, 10, 25, 50, 100, 200, 300, 400]:
    D = dev[t]
    tot = D.sum()
    if tot < 1e-9: continue
    idx = np.arange(S, dtype=np.float64)
    cy_ = float((D.sum(1) * idx).sum() / tot); cx_ = float((D.sum(0) * idx).sum() / tot)
    rows.append(dict(t=t, dev_mass=float(tot),
                     dev_at_mark=float(D[pk]),
                     dev_cm_displacement=float(np.hypot(cy_ - pk[0], cx_ - pk[1])),
                     mark_com_displacement=float(np.hypot(hist[t]['cx'] - h0['cx'],
                                                          hist[t]['cy'] - h0['cy'])),
                     n_sites_dev=float((D > 1e-6).sum())))
print("   t   dev_mass  dev_at_mark  |dev|-CM moved   organism moved   sites_dev")
for r in rows:
    print(f"  {r['t']:4d}  {r['dev_mass']:8.4f}  {r['dev_at_mark']:11.5f}  "
          f"{r['dev_cm_displacement']:13.2f}  {r['mark_com_displacement']:14.2f}  {r['n_sites_dev']:9.0f}")
r100 = [r for r in rows if r['t'] == 100][0]
print(f"\n  At t=100 the deviation's centre of mass has moved {r100['dev_cm_displacement']:.2f} cells "
      f"while the organism moved {r100['mark_com_displacement']:.2f} cells.")
print(f"  ratio dev-CM displacement / organism displacement = "
      f"{r100['dev_cm_displacement']/r100['mark_com_displacement']:.3f}")
print("  (ratio ~1 => the mark rides the pattern => sites are not the persistent entity;")
print("   ratio ~0 => the mark stays put => the site is a scar)")

# residency: how long does a given lattice site stay occupied (unwrapped frame)?
occ = np.array([(f > 0.1) for f in TR])
disp = np.array([[x['cx'], x['cy']] for x in hist])
res_t = []
site = (S // 2, S // 2)
frame = np.round(disp - disp[0]).astype(int)
for t in range(STEPS + 1):
    j = (site[0] + int(round(frame[t, 0]))) % S
    i = (site[1] + int(round(frame[t, 1]))) % S
    res_t.append(bool(occ[t, j, i]))
runs, cur = [], 0
for b in res_t:
    if b: cur += 1
    elif cur: runs.append(cur); cur = 0
if cur: runs.append(cur)
gyr_series = [h['gyr'] for h in hist]
print(f"  gyradius over the run: t=0 {gyr_series[0]:.2f}, t=100 {gyr_series[100]:.2f}, "
      f"t=200 {gyr_series[200]:.2f}, t=400 {gyr_series[400]:.2f}  "
      f"(min {min(gyr_series):.2f} max {max(gyr_series):.2f})")
print(f"\n  residency of the co-moving cell: consecutive occupied run = {runs} steps "
      f"(organism speed {speed:.4f} cells/step => a site is held ~{1/speed:.1f} steps at most")
print(f"  and the co-moving frame stays occupied for {sum(res_t)}/{STEPS+1} steps.")
json.dump({'E1': hist, 'E2': rows, 'speed': float(speed)}, open('/tmp/nca/exp/e1e2.json', 'w'), indent=1)
