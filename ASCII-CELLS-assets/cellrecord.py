#!/usr/bin/env python3
"""
The cell record. 16 bytes, fixed width, little-endian.

  off  size  field      meaning
    0     1  glyph      ASCII code point of Console.Data[x,y]  (the 10-glyph fog ramp, or 0x20)
    1     1  rgb8       R:3 G:3 B:2 -- byte-for-byte Console.Color[x,y], as Mathg.ColorTo8Bit packs it
    2     2  x          uint16 LE, column
    4     2  y          uint16 LE, row
    6     1  fog_id     0..9 index into "@&#8x*,:. ", or 10 for "no surface" (zBuffer == 1)
    7     1  flags      bit0 = surface present; bit1 = interior (3x3 not edge-clamped); rest 0
    8     4  z_ndc      float32, the game's own Rasterizer zBuffer value, verbatim
   12     4  distance   float32, world distance recovered from z_ndc through the game's own projection

  16 bytes total. Row-major, y*width + x.

The ground-truth label is deliberately NOT in this record. A label inside the
observation record leaks the answer into the tile a learner is handed, which is the
error that makes an ablation look better than it is. Labels live in a parallel file:

  off  size  field
    0     1  enemy      1 if the nearest surface at this cell is a living enemy
    1     1  pad        0
"""
import glob, os, struct, sys
sys.path.insert(0, "/tmp")
import numpy as np
from twoarm import parse, FOG, _zc, _zn

REC = struct.Struct("<BBHHBBff")
assert REC.size == 16, REC.size
LAB = struct.Struct("<BB")
NEAR, FAR = 0.5, 1000.0

src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/frames"
dst = sys.argv[2] if len(sys.argv) > 2 else "/tmp/cells"
os.makedirs(dst, exist_ok=True)

files = sorted(glob.glob(os.path.join(src, "scene*_pose*.txt")))
print(f"packing {len(files)} frames -> {dst}")


def data_of(path, W, H):
    lines = open(path).read().split("\n")
    i0 = next(k for k, l in enumerate(lines) if l.startswith("# DATA --"))
    return np.array([list(r.ljust(W)[:W]) for r in lines[i0 + 1:i0 + 1 + H]])


for p in files:
    fr = parse(p)
    W, H = fr["g"].shape[1], fr["g"].shape[0]
    name = os.path.basename(p)[:-4]
    # original Data grid, needed to recover the glyph character
    data = data_of(p, W, H)
    gch = np.array([[ord(data[y][x]) for x in range(W)] for y in range(H)], np.uint8)
    rgb = fr["col"].astype(np.uint8)
    fog = fr["g"].astype(np.uint8)
    z = fr["z"].astype(np.float32)
    dist = (_zn / (_zc - fr["z"])).astype(np.float32)
    lab = fr["enemy"].astype(np.uint8)

    flags = np.zeros((H, W), np.uint8)
    flags[z < 1.0] |= 1                                    # surface present
    flags[1:H - 1, 1:W - 1] |= 2                            # interior

    with open(os.path.join(dst, name + ".cells"), "wb") as fh, \
         open(os.path.join(dst, name + ".label"), "wb") as lh:
        buf = bytearray()
        lbuf = bytearray()
        for y in range(H):
            for x in range(W):
                buf += REC.pack(int(gch[y, x]), int(rgb[y, x]), x, y, int(fog[y, x]),
                                int(flags[y, x]), float(z[y, x]), float(dist[y, x]))
                lbuf += LAB.pack(int(lab[y, x]), 0)
        fh.write(bytes(buf))
        lh.write(bytes(lbuf))

def data_of(path, W, H):
    lines = open(path).read().split("\n")
    i0 = next(k for k, l in enumerate(lines) if l.startswith("# DATA --"))
    return np.array([list(r.ljust(W)[:W]) for r in lines[i0 + 1:i0 + 1 + H]])


# --- round trip: read the binary back and rebuild the frame, compare to the source ---
print("\nround-trip verification (rebuild Data and Color from the binary and diff against the frame):")
bad = 0
for p in files[:8]:
    fr = parse(p)
    W, H = fr["g"].shape[1], fr["g"].shape[0]
    raw = open(os.path.join(dst, os.path.basename(p)[:-4] + ".cells"), "rb").read()
    assert len(raw) == W * H * 16, (len(raw), W * H * 16)
    arr = np.frombuffer(raw, dtype=np.dtype([
        ("glyph", "u1"), ("rgb", "u1"), ("x", "<u2"), ("y", "<u2"),
        ("fog", "u1"), ("flags", "u1"), ("z", "<f4"), ("d", "<f4")]))
    # x,y must be the row-major index
    ok_xy = np.array_equal(arr["x"], np.tile(np.arange(W, dtype=np.uint16), H)) and \
            np.array_equal(arr["y"], np.repeat(np.arange(H, dtype=np.uint16), W))
    ok_rgb = np.array_equal(arr["rgb"].reshape(H, W), fr["col"].astype(np.uint8))
    ok_fog = np.array_equal(arr["fog"].reshape(H, W), fr["g"].astype(np.uint8))
    ok_z = np.allclose(arr["z"].reshape(H, W), fr["z"].astype(np.float32), atol=1e-6)
    # glyph -> Data
    rebuilt = np.vectorize(chr)(arr["glyph"].reshape(H, W))
    ok_g = np.array_equal(rebuilt, data_of(p, W, H))
    good = ok_xy and ok_rgb and ok_fog and ok_z and ok_g
    bad += (not good)
    print(f"  {os.path.basename(p):24s} xy={ok_xy} colour={ok_rgb} fog={ok_fog} z={ok_z} glyph={ok_g}  "
          f"{'OK' if good else 'MISMATCH'}")
print(f"\n{'all round trips clean' if bad == 0 else str(bad) + ' MISMATCHES'}")
