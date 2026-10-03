#!/usr/bin/env python3
"""What the renderer discarded: scene-entity -> cell correspondences, measured."""
import collections, json, os, sys
import numpy as np
from frames import Frames

def owner_class_table(F):
    names = ["empty"]
    for o in F.owner_table:
        p = o.split("|")
        names.append("obj:" + p[2] + "/" + p[3] if p[0] == "obj" else "arch:" + p[3])
    return np.array(names)

def summarise(paths, verbose=True):
    rows = []
    for path in paths:
        F = Frames(path)
        cls = owner_class_table(F)
        for f in range(F.N):
            own = F.owner[f]
            nz = own > 0
            cnt = collections.Counter(own[nz].tolist())
            classes = set(cls[list(cnt.keys())].tolist()) if cnt else set()
            g = F.gt[f]
            n_ent_scene = g["n_objects"] * len(F.gt[0]["objects"]) / max(1, g["n_objects"])  # placeholder
            rows.append(dict(
                path=os.path.basename(path), frame=f,
                n_objects_scene=g["n_objects"],
                n_owner_tags=len(cnt),
                n_obj_tags=sum(1 for k in cnt if cls[k].startswith("obj:")),
                n_arch_tags=sum(1 for k in cnt if cls[k].startswith("arch:")),
                cells_written=int(nz.sum()),
                cells_empty=int((~nz).sum()),
                obj_cells=int(sum(v for k, v in cnt.items() if cls[k].startswith("obj:"))),
                scene_triangles=g["object_triangles"] + g["scene_triangles"],
                rendered=g["rendered_triangles"], clipped=g["clipped_triangles"],
                zones=g["zones_rendered"],
                classes=classes,
            ))
    if verbose:
        print(f"{'set':>8} {'frame':>5} {'scn_obj':>7} {'tags':>5} {'objtags':>7} {'cells':>6} {'objcells':>8} {'empty':>6} {'clipped':>7}")
        for r in rows[:6] + rows[-6:]:
            print(f"{r['path'][:8]:>8} {r['frame']:>5} {r['n_objects_scene']:>7} {r['n_owner_tags']:>5} "
                  f"{r['n_obj_tags']:>7} {r['cells_written']:>6} {r['obj_cells']:>8} {r['cells_empty']:>6} {r['clipped']:>7}")
        n_with_obj = sum(1 for r in rows if r["obj_cells"] > 0)
        print(f"\nframes with >=1 scene-object cell: {n_with_obj}/{len(rows)}")
        print("distinct object classes ever visible:",
              sorted({c for r in rows for c in r["classes"] if c.startswith("obj:")}))
        print("mean cells per visible object tag:",
              round(np.mean([r["obj_cells"] / r["n_obj_tags"] for r in rows if r["n_obj_tags"]]), 2) if any(r["n_obj_tags"] for r in rows) else 0)
    return rows

if __name__ == "__main__":
    summarise(sys.argv[1:])
