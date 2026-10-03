#!/usr/bin/env python3
"""Certify the correspondence table: every cell the z-buffer gave to an entity must
fall inside the box of that entity's OWN mesh vertices, projected with the game's own
matrices.  Any leak in the Tag propagation shows up here as a cell outside the box."""
import glob, json, sys
import numpy as np
n = ok = nbox = 0
worst = []
for p in sorted(glob.glob(sys.argv[1])):
    for b in json.load(open(p + "/backproj.json")):
        for o in b["objects"]:
            g = [round(x, 2) for x in o["geom_bbox"]]
            c = o["cells_bbox"]
            nbox += 1
            if c[0] > c[1]:
                n += 1
                continue
            good = (c[0] >= g[0] - 1.5 and c[1] <= g[1] + 1.5 and c[2] >= g[2] - 1.5 and c[3] <= g[3] + 1.5)
            n += 1
            ok += 1 if good else 0
            if not good and len(worst) < 8:
                worst.append((p, b["frame"], o["type"], o["cells"], g, c))
print(f"object-instances checked : {nbox}")
print(f"cells inside the object's own projected geometry: {ok} ({ok/nbox*100:.2f}%)")
for w in worst:
    print("  VIOLATION", w)
