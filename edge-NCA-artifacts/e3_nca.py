"""E3-E6 -- Neural Cellular Automata, the "cells that grow themselves" claim.

Architecture ported from arXiv:2103.08737 (Distelgo et al., "Growing 3D Artefacts and
Functional Machines with Neural Cellular Automata", v1 2021-03-15), which states:
  * 16-dim continuous state per cell (RGB + alive + hidden)
  * Sobel filters -> "perception vector" = cell state + its neighbourhood derivatives
  * neural layers SHARED across the whole CA
  * stochastic per-cell update mask; alive-masking so dead cells do not update
  * trained from a single living cell; MSE to a target image; sample pool to avoid
    catastrophic forgetting; last layer zero-initialised (identity at init)
Scaled down for a 1-core CPU box: 12x12 grid, 24 hidden, 3 layers, 16 steps, batch 4.
Absolute losses will not match the paper; the *structural* measurements are the point.

RUNS ON CPU ONLY (no CUDA in this sandbox). torch 2.14.1+cpu, numpy 2.4.6.
"""
import sys, json, math, time
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F

torch.manual_seed(0)
DEV = 'cpu'
torch.set_num_threads(1)

G, C, HID, LAY, STEPS, BATCH = 12, 16, 24, 3, 24, 4
NCELL = G * G
torch.set_default_dtype(torch.float32)

# ---------------- target: a hand-designed 12x12 pattern ------------------------
yy, xx = torch.meshgrid(torch.arange(G), torch.arange(G), indexing='ij')
target = torch.zeros(1, C, G, G)
disc = (((yy - 5.5) ** 2 + (xx - 5.5) ** 2) < 4.0 ** 2).float()   # r=4 disc, 49 cells
target[0, 0] = disc * 0.95
target[0, 1] = disc * 0.55
target[0, 2] = disc * 0.25
target[0, 15] = disc                                   # hand-supervised alive channel
TGT_ALIVE = disc.clone()
TGT_RGB = target[0, :3].clamp(0, 1).clone()
n_tgt_cells = int((disc > 0).sum())

# ---------------- Sobel perception (Mordvintsev-style) -------------------------
def sobel_filters():
    kx = torch.tensor([[-1., 0., 1.], [-2., 0., 2.], [-1., 0., 1.]])
    ky = kx.t().contiguous()
    ident = torch.eye(3).view(1, 1, 3, 3)
    return torch.cat([ident, kx.view(1, 1, 3, 3), ky.view(1, 1, 3, 3)], 0)   # 3 x (1,1,3,3)

SOBEL = sobel_filters()   # 3 hand-specified 3x3 filters (identity, d/dx, d/dy)

class NCA(nn.Module):
    def __init__(self, ch=C, hid=HID, layers=LAY, id_ch=0):
        super().__init__()
        self.id_ch = id_ch
        per = 3 * ch
        dims = [per] + [hid] * layers + [ch]
        self.fcs = nn.ModuleList([nn.Linear(dims[i], dims[i + 1]) for i in range(len(dims) - 1)])
        nn.init.zeros_(self.fcs[-1].weight); nn.init.zeros_(self.fcs[-1].bias)  # identity at init
        self.register_buffer('sob', SOBEL.repeat(ch, 1, 1, 1))                 # hand-designed

    def perception(self, x, ids=None):
        """Sobel perception (Distelgo 2103.08737): per-cell perception vector = the cell's
        own state concatenated with the two Sobel partial-derivative fields -> 3C channels."""
        b, c, h, w = x.shape
        dx = F.conv2d(x, SOBEL[1].expand(c, 1, 3, 3), padding=1, groups=c)
        dy = F.conv2d(x, SOBEL[2].expand(c, 1, 3, 3), padding=1, groups=c)
        parts = [x, dx, dy]
        if self.id_ch:
            parts.append(ids)
        return torch.cat(parts, 1).permute(0, 2, 3, 1)      # (B, H, W, 3C)

    def step(self, x, ids=None, mask=True, alive_mask=False, alive_idx=15):
        y = self.perception(x, ids)          # (B, H, W, 3C)
        for f in self.fcs: y = f(y)
        y = y.permute(0, 3, 1, 2).contiguous()   # -> (B, C, H, W)
        if mask:
            m = (torch.rand(x.shape[0], 1, x.shape[2], x.shape[3]) < 0.5).float()
        else:
            m = torch.ones(x.shape[0], 1, x.shape[2], x.shape[3])
        dx = x + m * y
        if alive_mask:
            alive = (x[:, alive_idx:alive_idx + 1] > 0.5).float()
            dx = x + m * y * alive
        return dx

def seed_state(batch, where=None, mode='single'):
    """mode='single' : exactly ONE living cell (Distelgo 2103.08737: 'a single living cell')
       mode='all'    : the whole grid marked alive (a control, NOT the paper's setup)"""
    x = torch.zeros(batch, C, G, G)
    if mode == 'all':
        x[:, 15] = 1.0
        where = where or (G // 2, G // 2)
    else:
        where = where or (G // 2, G // 2)
        x[:, 15, where[0], where[1]] = 1.0
    x[:, :3, where[0], where[1]] = 0.5
    return x

def rgb(x):
    return x[:, :3].clamp(0, 1)

def loss_of(x):
    return F.mse_loss(rgb(x), TGT_RGB.expand(x.shape[0], -1, -1, -1))

def rollout(net, batch=BATCH, steps=STEPS, seed_where=None, ids=None,
            mask=True, alive_mask=False, seed=True, ret_traj=False, seed_mode='single'):
    x = seed_state(batch, seed_where, seed_mode) if seed else torch.zeros(batch, C, G, G)
    traj = [x]
    for _ in range(steps):
        x = net.step(x, ids, mask=mask, alive_mask=alive_mask)
        x = x.clamp(0, 1)
        if ret_traj: traj.append(x)
    return (x, traj) if ret_traj else x

# =========================== E3: train =======================================
net = NCA()
ITERS = 2000
opt = torch.optim.Adam(net.parameters(), lr=4e-3)
sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=ITERS)
pool = [seed_state(1) for _ in range(8)]
t_start = time.time()
log = []
for it in range(ITERS):
    idx = [np.random.randint(len(pool)) for _ in range(BATCH)]
    x0 = torch.cat([pool[i] for i in idx], 0)
    out = rollout(net, batch=BATCH)
    L = loss_of(out)
    opt.zero_grad(); L.backward(); torch.nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step(); sched.step()
    with torch.no_grad():
        L1 = loss_of(rollout(net, batch=1))
    log.append((it, float(L), float(L1)))
    if it % 250 == 0 or it == ITERS - 1:
        print(f"  it {it:3d}  batch_loss {float(L):.5f}  single {float(L1):.5f}  "
              f"({time.time()-t_start:.0f}s)")
with torch.no_grad():
    do_nothing = float(loss_of(seed_state(8)))   # control: emit the seed unchanged
trained_loss = float(loss_of(rollout(net, batch=8, mask=False)))
print(f"TRAINING DONE  batch(8) loss (deterministic) = {trained_loss:.5f}   "
      f"CONTROL 'do nothing' (emit seed) = {do_nothing:.5f}   "
      f"[{time.time()-t_start:.0f}s, CPU 1 thread, NO CUDA]")

# =========================== E3b: parameter census ===========================
learned = sum(p.numel() for p in net.parameters())
hand = {
    'Sobel kernels (3x3, hand-specified)': int(SOBEL.numel()),
    'perception width (features per cell)': 3 * C,
    'grid size G': G, 'channels C': C, 'hidden H': HID, 'layers L': LAY,
    'rollout steps T': STEPS, 'stochastic update rate': 0.5,
    'alive channel index': 15, 'zero-init of last layer': 'yes',
    'seed: single cell at': (G // 2, G // 2),
    'seed values (alive=1, rgb=0.5)': 4,
    'target image pixels (hand-drawn)': C * G * G,
    'padding mode': 'zero', 'loss': 'MSE(rgb, target)',
}
print("\n=== E3b: what is learned vs hand-designed ===")
print(f"  LEARNED parameters (the entire learned content of the substrate): {learned}")
print(f"  hand-designed target image: {C*G*G} values that define what is being grown")
print(f"  hand-designed structural constants: {len(hand)} items, incl. "
      f"{SOBEL.numel()} Sobel coefficients, seed values, step count, mask rate")
print(f"  ratio learned-params : target-pixels = 1 : {C*G*G/learned:.1f}")

# =========================== E3c: mutation tests =============================
print("\n=== E3c: mutation tests -- how much does the substrate need the learned weights? ===")
def m_eval(tag, **kw):
    with torch.no_grad():
        out = rollout(net, **kw)
        L = float(loss_of(out))
    print(f"  {tag:52s} loss {L:.5f}")
    return L
res = {}
print(f"  {'CONTROL: do nothing (seed emitted unchanged)':52s} loss {do_nothing:.5f}")
res['CONTROL do nothing'] = do_nothing
res['trained (stochastic mask on)'] = m_eval('trained, full architecture', batch=16)
res['trained, no stochastic mask'] = m_eval('trained, no stochastic per-cell mask', batch=16, mask=False)
res['trained, + alive-masking ON'] = m_eval('trained, + alive-masking ON (dead cells frozen)', batch=16, alive_mask=True)
res['trained, no seed (all-dead init)'] = m_eval('trained, NO SEED (start from empty grid)', batch=16, seed=False)
res['trained, seed at wrong corner'] = m_eval('trained, seed at corner (2,2) not centre', batch=16, seed_where=(2, 2))
res['trained, WHOLE GRID alive at t=0'] = m_eval('trained, whole grid alive at t=0', batch=16, seed_mode='all')
res['trained, no stochastic mask, all alive'] = m_eval('trained, no stochastic mask + all alive', batch=16, mask=False, seed_mode='all')
# M1: zero the learned weights
saved = {k: v.clone() for k, v in net.state_dict().items()}
with torch.no_grad():
    for p in net.parameters(): p.zero_()
res['ALL learned weights zeroed'] = m_eval('ALL LEARNED WEIGHTS = 0 (identity rule)', batch=16)
with torch.no_grad():
    for k, v in net.state_dict().items(): v.copy_(saved[k])
res['restored'] = m_eval('restored', batch=16)

json.dump({'do_nothing': do_nothing, 'trained_loss': trained_loss, 'learned_params': learned, 'hand': {k: str(v) for k, v in hand.items()},
           'target_cells': n_tgt_cells, 'mutations': res,
           'log': log[-10:]}, open('/tmp/nca/exp/e3_nca.json', 'w'), indent=1)
torch.save(net.state_dict(), '/tmp/nca/exp/nca.pt')
print(f"\n  target has {n_tgt_cells} non-empty cells out of {NCELL} sites")
