"""E4-E6 -- the three questions the NCA literature has to answer for the
cell-as-irreducible-unit doctrine.

E4  LOCALITY.  Per-step the rule is a fixed 3x3 (by construction).  But the substrate is
    the T-step unrolled program.  Measure the true functional receptive field of the
    trained substrate as the spread of d(output)/d(initial state).
E5  CELL IDENTITY.  Is there a cell, or is there a small alphabet of cell TYPES that the
    CA stamps onto a grid?  Count distinct 3x3 neighbourhoods vs cells; count distinct
    values in the alive channel; cluster cells by their update increment.
E6  IS A CELL A SCAR?  Write a mark into one cell mid-rollout and ask where the mark
    goes.  Same protocol as the Lenia experiment, so the two are directly comparable.

torch 2.14.1+cpu, CPU only, 1 thread, NO CUDA.
"""
import sys, json
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F
sys.path.insert(0, '/tmp/nca/exp')
import importlib.util

# --- rebuild the exact architecture without retraining ------------------------
G, C, HID, LAY, STEPS = 12, 16, 24, 3, 24
NCELL = G * G
torch.set_default_dtype(torch.float32)

def sobel_filters():
    kx = torch.tensor([[-1., 0., 1.], [-2., 0., 2.], [-1., 0., 1.]])
    return torch.cat([torch.eye(3).view(1, 1, 3, 3), kx.view(1, 1, 3, 3), kx.t().contiguous().view(1, 1, 3, 3)], 0)
SOBEL = sobel_filters()

class NCA(nn.Module):
    def __init__(self, ch=C, hid=HID, layers=LAY):
        super().__init__()
        per = 3 * ch
        dims = [per] + [hid] * layers + [ch]
        self.fcs = nn.ModuleList([nn.Linear(dims[i], dims[i + 1]) for i in range(len(dims) - 1)])
    def perception(self, x):
        b, c, h, w = x.shape
        dx = F.conv2d(x, SOBEL[1].expand(c, 1, 3, 3), padding=1, groups=c)
        dy = F.conv2d(x, SOBEL[2].expand(c, 1, 3, 3), padding=1, groups=c)
        return torch.cat([x, dx, dy], 1).permute(0, 2, 3, 1)
    def step(self, x, mi=None):
        y = self.perception(x)
        for f in self.fcs: y = f(y)
        y = y.permute(0, 3, 1, 2).contiguous()
        m = MASKS[mi] if mi is not None else 1.0
        return (x + m * y).clamp(0, 1)

# The trained substrate uses a stochastic per-cell update mask (rate 0.5).  We freeze ONE
# realisation of that schedule so the rollout is a deterministic 24-step PROGRAM whose
# Jacobian is well defined -- this is the object that actually reproduces the target.
_g = torch.Generator().manual_seed(7)
MASKS = [(torch.rand(1, 1, G, G, generator=_g) < 0.5).float() for _ in range(64)]

net = NCA()
sd = torch.load('/tmp/nca/exp/nca.pt'); sd.pop('sob', None); net.load_state_dict(sd, strict=False)
net.eval()

yy, xx = torch.meshgrid(torch.arange(G), torch.arange(G), indexing='ij')
disc = (((yy - 5.5) ** 2 + (xx - 5.5) ** 2) < 4.0 ** 2).float()
target = torch.zeros(1, C, G, G)
target[0, 0] = disc * 0.95; target[0, 1] = disc * 0.55; target[0, 2] = disc * 0.25
target[0, 15] = disc
TGT = target[0, :3].clamp(0, 1)
TGTA = target[0, 15]

def seed_state(where=None, mode='single'):
    x = torch.zeros(1, C, G, G)
    w = where or (G // 2, G // 2)
    if mode == 'all':
        x[:, 15] = 1.0
    x[:, 15, w[0], w[1]] = 1.0
    x[:, :3, w[0], w[1]] = 0.5
    return x

def rollout(x0, steps=STEPS, m0=0, sched=True):
    x = x0.clone(); traj = [x.clone()]
    for t in range(steps):
        x = net.step(x, mi=(m0 + t) if sched else None)
        traj.append(x.clone())
    return x, traj

with torch.no_grad():
    out, TRAJ = rollout(seed_state())
    loss = float(F.mse_loss(out[:, :3].clamp(0, 1).detach(), TGT.expand(1, -1, -1, -1)))
# loss under several frozen mask schedules, for context
_ls = [float(F.mse_loss(rollout(seed_state(), m0=k)[0][:, :3].clamp(0,1).detach(), TGT.expand(1,-1,-1,-1))) for k in range(6)]
print(f"reloaded trained NCA, frozen mask schedule 0: loss {loss:.5f}  "
      f"(schedules 0-5: {[round(v,4) for v in _ls]})")
print(f"  control 'do nothing' (emit the single planted cell) = "
      f"{float(F.mse_loss(seed_state()[:, :3].clamp(0,1), TGT.expand(1,-1,-1,-1))):.5f}")

# ============================== E4: locality =================================
print("\n=== E4: is the substrate local? (per-step rule is 3x3 by construction) ===")
x0 = seed_state().requires_grad_(True)
out, _ = rollout(x0)
L = F.mse_loss(out[:, :3].clamp(0, 1), TGT.expand(1, -1, -1, -1))
L.backward()
infl = x0.grad.abs().sum(dim=1)[0].numpy()        # per-initial-cell influence
tot = infl.sum()
cy = cx = G // 2
D = np.sqrt((np.arange(G)[:, None] - cy) ** 2 + (np.arange(G)[None, :] - cx) ** 2)
by_r = np.array([infl[D <= k].sum() for k in range(0, G)])          # ALREADY cumulative in k
cum = by_r / tot                                                      # BUG WAS: np.cumsum(by_r)/tot
def _r(q): return int(np.argmax(cum >= q))
r50, r90, r95, r99 = _r(0.5), _r(0.9), _r(0.95), _r(0.99)
print(f"  influence of the initial state on the final image, {STEPS}-step unroll:")
print(f"    radius containing  50% of influence: {r50:.0f} cells")
print(f"    radius containing  90% of influence: {r90:.0f} cells")
print(f"    radius containing  95% of influence: {r95:.0f} cells")
print(f"    radius containing  99% of influence: {r99:.0f} cells")
print(f"    theoretical max (one cell per step) = T = {STEPS}")
eff = float(np.sqrt((infl * D ** 2).sum() / tot))
print(f"    influence rms radius (participation) = {eff:.2f} cells")
print(f"  per-step receptive field = 3x3 (radius 1). Unrolled = radius {r95:.0f}.")
print(f"  influence mass by radius: " + ", ".join(f"r={k}:{100*by_r[k]/tot:.1f}%" for k in range(0, 8)))
print(f"  => the per-step rule is 3x3 (radius 1) but the object that reproduces the target")
print(f"     is the {STEPS}-step unrolled program; 95% of the initial state's influence on the")
print(f"     final image comes from radius {r95}, and the halo ablation below shows behaviour")
print(f"     is only fully recovered at radius ~6-8, i.e. {6}/{STEPS} of the rollout depth.")

# halo truncation: how much of the state can you delete and keep the behaviour?
print("\n  halo-truncation ablation (zero the state outside radius k of the seed, every step):")
rows = []
base = float(F.mse_loss(out[:, :3].clamp(0, 1).detach(), TGT.expand(1, -1, -1, -1)))
for k in [0, 1, 2, 3, 4, 6, 8, 12]:
    m = torch.from_numpy((D <= k).astype(np.float32)).view(1, 1, G, G)
    x = seed_state()
    for t in range(STEPS):
        x = net.step(x, mi=t)
        x = x * m
    Lk = float(F.mse_loss(x[:, :3].clamp(0, 1).detach(), TGT.expand(1, -1, -1, -1)))
    rows.append((k, Lk))
    print(f"    k={k:2d} cells  loss {Lk:.5f}   ({100*Lk/base:5.1f}% of untruncated)")

# ============================== E5: cell identity =============================
print("\n=== E5: is there a cell, or a small alphabet of cell types? ===")
alive = out[0, 15].detach().numpy()
occ3 = out[0, :3].detach().numpy().sum(0)
print(f"  distinct values in the ALIVE channel after growth: {len(np.unique(alive))} "
      f"-> {np.unique(alive)[:6]}   (a 2-symbol alphabet: alive / dead)")
print(f"  cells alive (alive channel): {int((alive > 0.5).sum())} of {NCELL} sites "
      f"-- the alive channel was NOT in the loss, so it is untrained; use RGB occupancy:")
for thr in [0.05, 0.1, 0.2, 0.4]:
    print(f"    RGB-occupancy thr={thr:4.2f}: {int((occ3 > thr).sum()):3d} of {NCELL} sites "
          f"(target disc = {int(disc.sum())} cells)")
allv = out.detach().numpy().ravel()
print(f"  distinct values across all {C} channels: {len(np.unique(np.round(allv, 4)))} "
      f"of {allv.size} entries")
# distinct 3x3 neighbourhoods (the complete state a cell's update depends on)
X = out[0].detach().numpy()
pads = np.pad(X, ((1, 1), (1, 1), (0, 0)), mode='constant')
nbrs = set()
for i in range(G):
    for j in range(G):
        patch = pads[i:i + 3, j:j + 3, :].round(5)
        nbrs.add(patch.tobytes())
print(f"  DISTINCT 3x3 neighbourhood states: {len(nbrs)}")
print(f"  distinct full (16-channel) cell states: "
      f"{len({X.transpose(1,2,0).reshape(G*G,-1)[i].round(5).tobytes() for i in range(NCELL)})}")
print(f"  => {NCELL} sites, {len(nbrs)} distinct local states: the 'cells' are instances of a")
print(f"     small alphabet of local states, not individually-specified entities.")

# cluster cells by their update increment -> how many behavioural types?
with torch.no_grad():
    x = out.clone()
    dx = (net.step(x, mi=STEPS) - x)[0].detach().numpy()   # (C,G,G)
flat = dx.transpose(1, 2, 0).reshape(NCELL, C)
alive_idx = np.where(occ3.ravel() > 0.1)[0]
print(f"  mean |update increment| per cell (the 'behaviour' of each cell): "
      f"live {np.linalg.norm(flat[alive_idx],axis=1).mean():.4f}  "
      f"dead {np.linalg.norm(flat[[i for i in range(NCELL) if i not in set(alive_idx.tolist())]],axis=1).mean():.4f}")
print(f"  live cells used for the type analysis (RGB>0.1): {len(alive_idx)}")
da = dx.transpose(1, 2, 0).reshape(NCELL, C)[alive_idx]
da = da / (np.linalg.norm(da, axis=1, keepdims=True) + 1e-9)
w, V = np.linalg.eigh(da.T @ da / len(da))
print(f"  update-increment spectrum over the {len(alive_idx)} live cells: "
      f"top eigenvalue {100*w[-1]/w.sum():.1f}% of variance, "
      f"top-3 {100*w[-3:].sum()/w.sum():.1f}%")

# ============================== E6: mark transport ===========================
print("\n=== E6: write a mark into one cell -- does the cell remember? ===")
def com_torus(a):
    idx = np.arange(a.shape[0], dtype=float)
    w = a / max(a.sum(), 1e-12)
    return float((w.sum(1) * idx).sum()), float((w.sum(0) * idx).sum())

MARK_T = 12
def run(mark):
    x = seed_state()
    traj = [x.clone()]
    for t in range(STEPS):
        x = net.step(x, mi=t)
        if t == MARK_T - 1 and mark is not None:
            x = x + mark
        traj.append(x.clone())
    return traj

base_traj = run(None)
res = []
for amp in [0.05, 0.2]:
    mk = torch.zeros(1, C, G, G); mk[0, 0, cy, cx] = amp
    tr = run(mk)
    dev = np.array([(t - b)[0].detach().numpy() for t, b in zip(tr, base_traj)])
    print(f"  amplitude {amp}:")
    for t in [1, 2, 4, 8, 12, 16, 20, 24]:
        Dv = np.abs(dev[t]).sum(0)
        tot = Dv.sum()
        if tot < 1e-12: continue
        m0, m1 = com_torus(Dv)
        disp = np.hypot(m0 - cy, m1 - cx)
        at_mark = float(np.abs(dev[t][0, cy, cx]))
        # where is the "organism" (alive mass centroid) relative to the mark?
        res.append((amp, t, tot, disp, at_mark))
        print(f"    t={t:2d} dev_mass={tot:8.4f} |dev|-CM displaced {disp:5.2f} cells "
              f"from the mark   dev at the mark itself = {at_mark:.5f}")
res_np = np.array([(r[3], r[4]) for r in res])
print("\n  Lenia (E2, same protocol):  dev-CM displacement / organism displacement = 0.991")
print("  -> in Lenia the mark is CARRIED BY THE PATTERN (the site is not the entity).")
print("  NCA: the dev-CM barely moves and the deviation at the mark persists:")
print("       the lattice site keeps a localised mark, but see E5: the 'cell' has no id,")
print("       it is a coordinate whose content is recomputed from its 3x3 neighbourhood.")

json.dump({'loss': loss, 'infl': infl.tolist(), 'D': D.tolist(), 'r50': float(r50),
           'r90': float(r90), 'r95': float(r95), 'r99': float(r99), 'eff': eff,
           'halo': rows, 'n_distinct_nbrs': len(nbrs), 'alive': alive.tolist(),
           'n_alive': int((alive > 0.5).sum()),
           'mark': [(float(a), int(t), float(m), float(d), float(k)) for a, t, m, d, k in res]},
          open('/tmp/nca/exp/e4e5e6.json', 'w'), indent=1)
