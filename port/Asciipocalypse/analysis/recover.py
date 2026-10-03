#!/usr/bin/env python3
"""
RECOVERABILITY PROBE -- what a downstream reader can still get out of the frame.

Three quantities, all measured against the scene graph, none of them from the frame:

  1. localisation   projected true position vs the centroid of the cells the entity won
  2. depth          the depth the GLYPH encodes vs the depth in the z-buffer
  3. existence      scene entities that win zero cells (no information at all)

Camera math is transcribed from Camera.cs / Mathg.cs; the transcription is verified
against the data before anything is reported (see verify_projection).
"""
import glob, json, os, sys
import numpy as np
from frames import Frames

FOG = "@&#8x*,:. "
NEAR, FAR = 0.5, 1000.0
FOV = np.pi / 2.5
ASPECT = 16 / 9


def rot(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, -s], [0, 1, 0], [s, 0, c]])


def project(p, cam_pos, cam_rot, W, H):
    """world -> (cell_i, cell_j, ndc_z), transcribed from Rasterizer.RenderTriangles"""
    v = rot(-cam_rot) @ (np.asarray(p) - np.asarray(cam_pos))
    nw = 2 * NEAR * np.tan(FOV / 2)
    nh = nw / ASPECT
    w = v[2]                                  # w_clip = z_cam in this projection
    i = ((2 * NEAR / nw) * v[0] / w + 1) * 0.5 * W
    j = (-(2 * NEAR / nh) * v[1] / w + 1) * 0.5 * H
    z = (FAR + NEAR) / (FAR - NEAR) + (-2 * FAR * NEAR / (FAR - NEAR)) / w
    return i, j, z


def verify_projection(F, n=400):
    """the transcription is right iff the projected true position lands on a cell the
    entity actually won.  Report the hit rate rather than asserting it."""
    hits = tot = 0
    for f in range(0, F.N, max(1, F.N // 8)):
        own = F.owner[f]
        g = F.gt[f]
        cam = g["cam"]
        masks = {}
        ys, xs = np.nonzero(own)
        for y, x in zip(ys.tolist(), xs.tolist()):
            masks.setdefault(int(own[y, x]), []).append((x, y))
        for t, cells in masks.items():
            key = F.owner_table[t - 1].split("|")
            if key[0] != "obj":
                continue
            idx = int(key[1])
            if idx >= len(g["objects"]):
                continue
            p = g["objects"][idx]["pos"]
            i, j, z = project(p, cam[:3], cam[3], F.W, F.H)
            ii, jj = int(round(i)), int(round(j))
            tot += 1
            if 0 <= ii < F.W and 0 <= jj < F.H and (int(own[jj, ii]) == t):
                hits += 1
    return hits, tot


def probe(paths, verbose=True):
    depth_err, depth_err_avg, loc_err, loc_hit, lost, cells_per_obj = [], [], [], [], [], []
    n_obj_vis, n_obj_scene, n_cells3d, n_cells_hud, n_cells_empty = 0, 0, 0, 0, 0
    for p in paths:
        F = Frames(p)
        bp = json.load(open(os.path.join(F.d, "backproj.json")))
        bp = {b["frame"]: b["objects"] for b in bp}
        for f in range(F.N):
            own = F.owner[f]
            m = (own > 0) & (F.hud[f] == 0)
            n_cells3d += int(m.sum())
            n_cells_hud += int((F.hud[f] == 1).sum())
            n_cells_empty += int(((own == 0) & (F.hud[f] == 0)).sum())
            g = F.gt[f]
            n_obj_scene += g["n_objects"]
            cam = g["cam"]

            # --- per-cell glyph depth, against the z-buffer ---
            ch = F.ch[f][m]
            zt = F.z[f][m]
            kidx = np.array([FOG.index(chr(c)) if chr(c) in FOG else -1 for c in ch])
            good = kidx >= 0
            if good.any():
                zg = ((kidx[good] + 0.5) / 10.0) ** 0.1
                depth_err.append(np.abs(zg - zt[good]))

            # --- per-entity ---
            for t in np.unique(own[m]):
                t = int(t)
                key = F.owner_table[t - 1].split("|")
                if key[0] != "obj":
                    continue
                idx = int(key[1])
                n_obj_vis += 1
                sel = m & (own == t)
                n = int(sel.sum())
                cells_per_obj.append(n)
                ys, xs = np.nonzero(sel)
                ci, cj = xs.mean(), ys.mean()
                kk = np.array([FOG.index(chr(c)) for c in F.ch[f][sel]])
                kk = kk[kk >= 0]
                if len(kk):
                    depth_err_avg.append(abs(float((((kk + 0.5) / 10.0) ** 0.1).mean() - F.z[f][sel].mean())))
                if idx < len(g["objects"]):
                    ti, tj, tz = project(g["objects"][idx]["pos"], cam[:3], cam[3], F.W, F.H)
                    loc_err.append(np.hypot(ti - ci, tj - cj))
                    loc_hit.append(int(round(ti)) == int(round(ci)) and int(round(tj)) == int(round(cj)))
            lost.append(g["n_objects"] - n_obj_vis if f == 0 else None)
    depth_err = np.concatenate(depth_err) if depth_err else np.array([])
    depth_err_avg = np.array(depth_err_avg)
    loc_err = np.array(loc_err)
    out = dict(
        n_cells_3d=n_cells3d, n_cells_hud=n_cells_hud, n_cells_blank=n_cells_empty,
        depth_err_ndc=dict(n=int(depth_err.size), median=float(np.median(depth_err)) if depth_err.size else 0,
                           p90=float(np.percentile(depth_err, 90)) if depth_err.size else 0,
                           p99=float(np.percentile(depth_err, 99)) if depth_err.size else 0),
        depth_err_per_entity=dict(n=int(depth_err_avg.size), median=float(np.median(depth_err_avg)) if depth_err_avg.size else 0,
                                  p90=float(np.percentile(depth_err_avg, 90)) if depth_err_avg.size else 0),
        loc_err_cells=dict(n=int(loc_err.size), median=float(np.median(loc_err)) if loc_err.size else 0,
                           p90=float(np.percentile(loc_err, 90)) if loc_err.size else 0,
                           hit_exact=float(np.mean(loc_hit)) if loc_hit else 0),
        cells_per_entity=dict(n=len(cells_per_obj), median=float(np.median(cells_per_obj)),
                              p10=float(np.percentile(cells_per_obj, 10)), p90=float(np.percentile(cells_per_obj, 90))),
    )
    if verbose:
        print(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    ps = sorted(glob.glob(sys.argv[1]))
    print("runs:", [os.path.basename(p) for p in ps])
    F = Frames(ps[0])
    h, t = verify_projection(F)
    print(f"projection transcription check on run 0: {h}/{t} projected true positions land on a cell the entity won")
    probe(ps)
