"""
ASCII frame substrate — a z-buffered rasterizer that reproduces the projection
math of Asciipocalypse's Rasterizer.cs.

PROVENANCE: RECONSTRUCTED, NOT EXTRACTED.
------------------------------------------------
The .NET runtime is not present in this sandbox (verified: no `dotnet`
executable, no libhostfxr.so, no libcoreclr.so anywhere on the filesystem), so
Rasterizer.Raster() could NOT be run against a live Scene.  Every frame below
is produced by this file's own rasterizer, in Python.

What IS faithful (transcribed line-for-line from the real source):
  * Rasterizer.cs:22   fogString = "@&#8x*,:. "
  * Rasterizer.cs:129  fogId = (z<0) ? 0
                             : min((int)(pow(z,10) * fogString.Length + offset[i,j]), 9)
  * Rasterizer.cs:36   offset[i,j] = (float)rand.NextDouble() - 0.5f,
                       computed ONCE in the constructor — a FIXED SPATIAL PATTERN
                       (the ASCII-CHARSELECTION.md retraction), seeded here.
  * Mathg.cs:69        ColorTo8Bit: r=clamp(X,0,0.9)*8, g=clamp(Y,0,0.9)*8,
                       b=clamp(Z,0,0.8)*4, packed r + (g<<3) + (b<<6)
  * Console.cs:31      reset: Data=' ', Color=255
  * Rasterizer.cs:124  EyeEasy branch (every cell '@', depth into brightness)

What is NOT faithful: the geometry, the scene graph, the textures and the
playthrough.  Those are synthesized by this file.  So the frames are
reconstructed at the level of the PROJECTION, and synthetic at the level of
the SCENE.  Both labels are asserted per-frame in Frame.provenance.
"""

import math
import random

FOG_STRING = "@&#8x*,:. "          # Rasterizer.cs:22
assert len(FOG_STRING) == 10

# ---------------------------------------------------------------- colour ----
def _clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def color_to_8bit(c):               # Mathg.cs:69
    r = int(_clamp(c[0], 0.0, 0.9) * 8)
    g = int(_clamp(c[1], 0.0, 0.9) * 8)
    b = int(_clamp(c[2], 0.0, 0.8) * 4)
    return r + (g << 3) + (b << 6)


def unpack_color(c8):               # inverse, for the absolute-state question
    return ((c8 & 0b111) / 8.0, ((c8 >> 3) & 0b111) / 8.0, ((c8 >> 5) & 0b110) / 4.0)


# ------------------------------------------------------------------ frame ----
class Frame:
    """Console.Data (char) + Console.Color (byte).  Console.cs is 55 lines and
    carries zero MonoGame references; both channels are kept, because
    ASCII-CHARSELECTION.md established that the char is DEPTH-AND-NOT-IDENTITY
    while the colour is IDENTITY.  A diff over chars alone is a diff over a
    channel that cannot tell you what anything is."""

    __slots__ = ("tick", "data", "color", "zbuf", "owner", "provenance",
                 "focal", "_w", "_h")

    def __init__(self, tick, w, h, focal):
        self.tick = tick
        self.focal = focal
        self._w, self._h = w, h
        # Console.cs uses char[width, height] indexed [i,j] with i = x, so the
        # faithful Python layout is w rows of h.
        self.data = [[" "] * h for _ in range(w)]
        self.color = [[255] * h for _ in range(w)]
        self.zbuf = [[1.0] * h for _ in range(w)]
        self.owner = [[None] * h for _ in range(w)]
        self.provenance = "reconstructed-projection/synthetic-scene"

    @property
    def w(self):
        return self._w

    @property
    def h(self):
        return self._h

    def page(self):
        """One 'page' of text, colour row included.  81 cells at the game default."""
        out = []
        for j in range(self.h):
            glyphs = "".join(self.data[i][j] for i in range(self.w))
            cols = " ".join("%02x" % self.color[i][j] for i in range(self.w))
            out.append("%s  |%s" % (glyphs, cols))
        return "\n".join(out)

    def owner_at(self, i, j):
        return self.owner[i][j]

    def owner_name(self, i, j):
        o = self.owner[i][j]
        return "none" if o is None else o["id"]

    def cell_count(self):
        return self.w * self.h

    def digest(self):
        """Content hash of BOTH channels.  Used to decide whether a diff is empty."""
        h = 2166136261
        for j in range(self.h):
            for i in range(self.w):
                h ^= ord(self.data[i][j]) & 0xFF
                h = (h * 16777619) & 0xFFFFFFFF
                h ^= self.color[i][j]
                h = (h * 16777619) & 0xFFFFFFFF
        return h


# ------------------------------------------------------------- rasterizer ----
class Rasterizer:
    """Port of the parts of Rasterizer.cs that decide what a cell contains."""

    def __init__(self, w, h, dither_seed=777, eye_easy=False, gamma=0.0):
        self.w, self.h = w, h
        self.eye_easy = eye_easy
        self.gamma = gamma
        # Rasterizer.cs:36 — a FIXED SPATIAL PATTERN, drawn once, seeded.
        rng = random.Random(dither_seed)
        self.offset = [[rng.random() - 0.5 for _ in range(h)] for _ in range(w)]
        self.tri_count = 0

    def raster(self, tick, tris, cam, focal):
        f = Frame(tick, self.w, self.h, focal)
        # Rasterizer.cs:53-60 reset
        self.tri_count = 0
        cy, sy = cam[1], math.tan(cam[3] * 0.5)
        aspect = self.w / float(self.h)

        for tri in tris:
            self.tri_count += 1
            # camera transform: translate then yaw
            v = []
            for (x, y, z) in tri["v"]:
                dx, dz = x - cam[0], z - cam[2]
                ca, sa = math.cos(cam[4]), math.sin(cam[4])
                rx = dx * ca - dz * sa
                rz = dx * sa + dz * ca
                v.append((rx, y - cy, rz))
            if any(p[2] <= 0.05 for p in v):
                continue
            # z is normalized to [0,1] with 0 = NEAR, matching the game's
            # NDC convention: Rasterizer.cs:129 feeds z into pow(z,10) so that a
            # near cell lands on fogString[0] == '@'.  FAR is the corridor's end.
            FAR = 60.0
            # Y is negated, exactly as Rasterizer.cs does at its projection
            # (`new Vector2(v0.X, -v0.Y) / v0.W`) so +y world is UP on the page.
            p = [(focal * a / c, -focal * b / c, c / FAR) for (a, b, c) in v]
            sx = [(px + self.w * 0.5, py + self.h * 0.5) for (px, py, _pz) in p]

            (x0, y0), (x1, y1), (x2, y2) = sx
            minI = max(0, int(min(x0, x1, x2)))
            maxI = min(self.w - 1, int(max(x0, x1, x2)) + 1)
            minJ = max(0, int(min(y0, y1, y2)))
            maxJ = min(self.h - 1, int(max(y0, y1, y2)) + 1)
            if minI > maxI or minJ > maxJ:
                continue
            d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(d) < 1e-9:
                continue
            colr = tri["c"]
            owner = tri["o"]
            for i in range(minI, maxI + 1):
                for j in range(minJ, maxJ + 1):
                    px, py = float(i), float(j)
                    l0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / d
                    l1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / d
                    l2 = 1.0 - l0 - l1
                    if l0 < -0.01 or l1 < -0.01 or l2 < -0.01:
                        continue
                    z = l0 * p[0][2] + l1 * p[1][2] + l2 * p[2][2]
                    if 0.0 < z < 1.0 and z < f.zbuf[i][j]:
                        f.zbuf[i][j] = z
                        f.owner[i][j] = owner
        # Rasterizer.cs:118-140 shading
        for i in range(self.w):
            for j in range(self.h):
                ow = f.owner[i][j]
                if ow is None:
                    continue
                z = f.zbuf[i][j]
                base = ow["c"]
                if self.eye_easy:
                    dd = _clamp(1.0 - (z ** 25), 0.0, 1.0)
                    f.data[i][j] = "@"
                    f.color[i][j] = color_to_8bit(
                        (base[0] * dd, base[1] * dd, base[2] * dd))
                else:
                    off = self.offset[i][j]
                    fog = 0 if z < 0 else min(int((z ** 10) * 10 + off), 9)
                    f.data[i][j] = FOG_STRING[fog]
                    f.color[i][j] = color_to_8bit(base)
        return f


def focal_for(w, fov=1.05):
    """Pinhole focal length in pixels for a given horizontal field of view.
    fov=1.05 rad ~ 60 deg, the usual corridor-game horizontal FOV."""
    return (w / 2.0) / math.tan(fov * 0.5)


# ------------------------------------------------------------------ scene ----
# Corridor + hostiles.  Geometry is SYNTHETIC (this file's own); only the
# projection is transcribed.  The corridor runs +Z from the camera.
FLOOR_C = (0.30, 0.28, 0.26)
WALL_C = (0.55, 0.35, 0.30)
CEIL_C = (0.25, 0.24, 0.28)
MONSTER_C = (0.75, 0.15, 0.20)     # red-ish: the identity colour
ITEM_C = (0.20, 0.70, 0.35)        # green-ish


def _quad(a, b, c, d, col, owner):
    """One planar quad -> two triangles.  (a,b,c) + (a,c,d)."""
    return [
        {"v": [a, b, c], "c": col, "o": owner},
        {"v": [a, c, d], "c": col, "o": owner},
    ]


HOSTILES = [(14.0, 2.6, 2.2, 0.0), (26.0, 3.1, 2.4, 1.1), (40.0, 2.2, 2.0, 2.3)]


def hostile_pose(t, k):
    """Ground truth for hostile k's transform at time t.  This is the SCENE
    GRAPH, not a projection of it -- so it is what a trigger's ASSUMPTION is
    actually about."""
    z0, spd, amp, ph = HOSTILES[k]
    return {"x": amp * math.sin(spd * t + ph),
            "y": 1.2 + 0.25 * math.sin(spd * t * 1.7 + ph),
            "z": z0}


def build_scene(t, dt=1.0 / 60.0):
    """Deterministic world at simulation time t (seconds).  Same t -> same scene,
    which is what makes the 'hold the scene still' test a real test."""
    trig = []
    # CORRIDOR WALLS  (fixed identity, so they are the 'static' content)
    trig += _quad((-5, 0, 1), (-5, 3, 1), (-5, 3, 60), (-5, 0, 60), WALL_C, {"id": "wall_L", "c": WALL_C})
    trig += _quad((5, 0, 1), (5, 3, 1), (5, 3, 60), (5, 0, 60), WALL_C, {"id": "wall_R", "c": WALL_C})
    trig += _quad((-5, 3, 1), (5, 3, 1), (5, 3, 60), (-5, 3, 60), CEIL_C, {"id": "ceiling", "c": CEIL_C})
    trig += _quad((-5, 0, 1), (5, 0, 1), (5, 0, 60), (-5, 0, 60), FLOOR_C, {"id": "floor", "c": FLOOR_C})
    # THREE HOSTILES, each oscillating across the corridor on its own phase.
    # This is the "fast-moving content" that the sample rate either catches or not.
    for k, (z0, spd, amp, ph) in enumerate(HOSTILES):
        x = amp * math.sin(spd * t + ph)
        s = 0.9
        y = 1.2 + 0.25 * math.sin(spd * t * 1.7 + ph)
        c = MONSTER_C
        o = {"id": "hostile_%d" % k, "c": c}
        base = z0
        trig += _quad((x - s, y - s, base - s), (x + s, y - s, base - s),
                      (x + s, y + s, base - s), (x - s, y + s, base - s), c, o)
        trig += _quad((x - s, y - s, base + s), (x + s, y - s, base + s),
                      (x + s, y + s, base + s), (x - s, y + s, base + s), c, o)
    return trig
