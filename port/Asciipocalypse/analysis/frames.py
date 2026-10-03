#!/usr/bin/env python3
"""Read the headless extractor output: frames.bin + ground.json + meta.json."""
import json, struct, sys, os
import numpy as np

class Frames:
    def __init__(self, d):
        self.d = d
        self.meta = json.load(open(os.path.join(d, "meta.json")))[0]
        self.gt = json.load(open(os.path.join(d, "ground.json")))
        m = self.meta
        self.W, self.H, self.N = m["width"], m["height"], m["frames"]
        self.stride = m["cell_stride_bytes"]
        raw = np.fromfile(os.path.join(d, "frames.bin"), dtype=np.uint8)
        rec = self.W * self.H * self.stride
        assert raw.size == rec * self.N, (raw.size, rec * self.N)
        # the extractor writes cells column-major (i-major: index = i*H + j), so the
        # (i, j) axes come back as (col, row) and must be transposed to (y, x)
        b = raw.reshape(self.N, self.W, self.H, self.stride).transpose(0, 2, 1, 3)
        self.ch = b[:, :, :, 0]
        self.col = b[:, :, :, 1]
        # float32 z, little-endian
        z = b[:, :, :, 2:6].copy().view(np.float32).reshape(self.N, self.H, self.W)
        self.z = z
        self.owner = b[:, :, :, 6:8].copy().view(np.uint16).reshape(self.N, self.H, self.W)
        self.tex = b[:, :, :, 8:10].copy().view(np.uint16).reshape(self.N, self.H, self.W)
        self.hud = b[:, :, :, 10]
        self.owner_table = m["owner_table"]
        self.tex_table = m["tex_table"]
        self.own = np.array(self.owner_table + [""])           # idx 0 == empty cell

    def text(self, f, i=None, j=None):
        ch = self.ch[f]
        if i is None: return "\n".join("".join(chr(c) for c in row) for row in ch)
        return "".join(chr(ch[j, k]) for k in range(i, i + 80))

    def owner_class(self):
        """vectorised: per cell, the ground-truth class of the triangle that won it"""
        names = []
        for o in self.owner_table:
            parts = o.split("|")
            if parts[0] == "obj":
                names.append("obj:" + parts[2] + "/" + parts[3])
            elif parts[0] == "zone":
                names.append("arch:" + parts[3])
            else:
                names.append("empty")
        names = ["empty"] + names
        return np.array(names)

def argmax_report(path, frame=0):
    F = Frames(path)
    cls = F.owner_class()
    ch = F.ch[frame]
    print(f"--- frame {frame}: distinct chars {sorted(set(chr(c) for c in ch.flatten()))}")
    print(f"--- distinct owner classes in frame: ")
    import collections
    cc = collections.Counter(cls[F.owner[frame].flatten()])
    for k, v in cc.most_common(30):
        print(f"    {k:55s} {v:6d} cells")
    print(F.text(frame))
    return F

if __name__ == "__main__":
    argmax_report(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 0)
