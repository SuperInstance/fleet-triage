"""E7 -- how much of Lenia is hand-tuned? Perturb the Orbium's published (m, s) and ask
how big the basin of the hand-tuned creature is. Verified port (bit-exact vs Chan's code).
"""
import sys, json
sys.path.insert(0, '/tmp/nca/exp')
import numpy as np
import chan_ref as C

S, R, T, B = 128, 13, 10, (1.0,)
A0 = np.load('/tmp/nca/exp/orbium.npy')
M0, S0 = 0.15, 0.015
STEPS = 250


def run(m, s, steps=STEPS):
    A = np.zeros((S, S)); o = S // 2 - A0.shape[0] // 2
    A[o:o + 20, o:o + 20] = A0
    Kg = C.make_kernel(R, B, G=S, centred=True)
    FK = np.fft.fftn(Kg); dt = 1.0 / T
    tr = [A.copy()]
    for _ in range(steps):
        U = np.fft.fftshift(np.real(np.fft.ifftn(np.fft.fftn(A) * FK)))
        A = np.clip(A + dt * C.growth_func1(U, m, s), 0.0, 1.0)
        tr.append(A.copy())
    return tr


def classify(tr):
    M0_ = tr[0].sum(); MT = tr[-1].sum()
    idx = np.arange(S, dtype=float)
    cs = []
    prev = None
    for f in (tr[100], tr[200], tr[-1]):
        w = f / max(f.sum(), 1e-12)
        c = (float((w.sum(1) * idx).sum()), float((w.sum(0) * idx).sum()))
        if prev is not None:
            c = (c[0] + S * round((prev[0] - c[0]) / S), c[1] + S * round((prev[1] - c[1]) / S))
        prev = c; cs.append(c)
    speed = np.hypot(cs[-1][0] - cs[0][0], cs[-1][1] - cs[0][1]) / 200
    n0, nT = int((tr[0] > 1 / 255).sum()), int((tr[-1] > 1 / 255).sum())
    alive = 0.85 * M0_ < MT < 1.15 * M0_ and nT > 0.5 * n0
    glide = alive and speed > 0.05
    return dict(mass_ratio=MT / M0_, speed=float(speed), n0=n0, nT=nT,
                alive=bool(alive), glide=bool(glide))


rows = []
for dm in [-0.030, -0.020, -0.012, -0.006, -0.003, 0.0, 0.003, 0.006, 0.012, 0.020, 0.030]:
    for dms in [-0.006, -0.004, -0.002, -0.001, 0.0, 0.001, 0.002, 0.004, 0.006]:
        for ds in [-0.006, -0.004, -0.002, -0.001, 0.0, 0.001, 0.002, 0.004, 0.006]:
            m, s = M0 + dm, S0 + ds
            c = classify(run(m, s))
            c.update(m=m, s=s, dm=dm, ds=ds); rows.append(c)
alive = [r for r in rows if r['alive']]
glide = [r for r in rows if r['glide']]
print(f"LENIA PARAMETER SENSITIVITY around Orbium unicaudatus (m={M0}, s={S0}), {len(rows)} probes")
print(f"  survived (mass +-15%, >=half the cells): {len(alive)}/{len(rows)} = {100*len(alive)/len(rows):.0f}%")
print(f"  glided   (survived AND |v|>0.05 cells/step): {len(glide)}/{len(rows)} = {100*len(glide)/len(rows):.0f}%")
print(f"  published point (m=0.150,s=0.015): {classify(run(M0,S0))}")
print("\n  the surviving/gliding set (m, s and |m-0.15|, |s-0.015|):")
for r in sorted(rows, key=lambda r: (abs(r['dm']), abs(r['ds'])))[:8]:
    print(f"    m={r['m']:.4f} s={r['s']:.4f} | dm|={abs(r['dm']):.4f} | ds|={abs(r['ds']):.4f}  "
          f"mass_ratio={r['mass_ratio']:.3f} speed={r['speed']:.4f} glide={r['glide']}")
json.dump(rows, open('/tmp/nca/exp/e7_lenia_sensitivity.json', 'w'), indent=1)
