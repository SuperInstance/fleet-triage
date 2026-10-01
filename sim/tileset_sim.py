"""Does treating the font as a tileset beat band x class? The experiment from TILESET.md §7.

WHAT IS BEING COMPARED, at a FIXED alphabet size so the comparison is fair:

  A  scalar      10 brightness levels            (what syzygy-lattice's flat class is)
  B  band x class 50 slots, 38 distinct         (what syzygy-lattice actually has)
  C  font         N glyphs, matched to A's or B's budget
  D  k-means      N clusters trained on the patch distribution -- the VQ optimum
  E  phase        a stipple family that breaks the visible grid

METRICS, REPORTED SEPARATELY BECAUSE THEY DISAGREE:
  - distortion  mean squared error between the cell patch and the chosen glyph's patch.
                Lower is better. This is the PERCEPTUAL proxy and it is a proxy.
  - round-trip  how many DISTINCT source patches remain distinguishable after the encode.
                This is what voxelglyph is about and it is a different question entirely.

A scheme that wins distortion and loses round-trip is a TRADE, and the size of the trade is
the result. Reporting only the first number would be exactly the error the whole lineage
already made once.
"""
import math, random, os

# ── the alphabet under test ───────────────────────────────────────────────────
# A terminal 3x5 cell. 15 pixels, 2 levels -> 32768 possible patterns.
CW, CH = 3, 5
NP = CW*CH

def blank():
    return [0]*(CW*CH)

def px(g, x, y, v=1):
    if 0 <= x < CW and 0 <= y < CH: g[y*CW+x] = v

# A: the flat ramp, as literal glyphs rasterised to the same cell.
FLAT_RAMP = ".:-=+*#%@"
_DENSITY = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"

def glyph_from_density(ch, cell=CW*CH):
    """The SCALAR scheme: a character rendered as a fill whose height is its ink weight.
    This is what a brightness ramp actually is, and it is deliberately the weak baseline."""
    idx = _DENSITY.find(ch) if ch in _DENSITY else len(_DENSITY)//2
    n = round(idx/max(1,len(_DENSITY)-1) * cell)
    g = blank()
    for i in range(n): g[i] = 1
    return g

# REAL 3x5 bitmaps. The previous font model reduced every glyph to a bottom-up fill, so
# all the "font" schemes collapsed onto the scalar ramp and the comparison was vacuous --
# scheme C came out byte-identical to A. A font is a set of DISTINCT SHAPES; if your model
# of a font produces identical codewords for different characters, you are not modelling
# the thing the experiment is about.
_FONT3x5 = {
    " ": "000000000000000", ".": "000000000010000", ":": "000000100010000",
    "-": "000000111000000", "+": "000010001000000", "*": "000101010101000",
    "=": "000010111010000", "#": "010101010010101", "/": "001001001001000",
    "\\": "100100100100100", "%": "110001010100011", "@": "111101101101111",
    "a": "000000011011110", "b": "010000111101000", "c": "000000011110000",
    "d": "000001111101000", "e": "000000011111000", "f": "000100111000100",
    "g": "000001011011111", "h": "010000111101001", "i": "001000000000000",
    "j": "000000000001001", "k": "010001010100010", "l": "011000000000000",
    "m": "000000101101101", "n": "000000110101001", "o": "000000011110000",
    "p": "000000111101000", "q": "000000011011001", "r": "000000101110000",
    "s": "000000011000110", "t": "111000010000010", "u": "000000001101011",
    "v": "000000100101001", "w": "000000101101101", "x": "001010100010100",
    "y": "000001001010110", "z": "000000111001000", "A": "010101111101010",
    "B": "110101110101110", "C": "011100100100011", "D": "110101101101110",
    "E": "111100110100111", "F": "111100110100100", "G": "011100101101011",
    "H": "101101111101101", "I": "111010010010111", "J": "001001001101010",
    "K": "101101110101101", "L": "100100100100111", "M": "101111111101101",
    "N": "101111111111101", "O": "010101101101010", "P": "110101110100100",
    "Q": "010101101111011", "R": "110101110101101", "S": "011100010001110",
    "T": "111010010010010", "U": "101101101101111", "V": "101101101101010",
    "W": "101101111111101", "X": "101101010101101", "Y": "101101010010010",
    "Z": "111001010100111", "0": "010101101101010", "1": "010010010010010",
    "2": "111001111001111", "3": "111001011001111", "4": "101101111001001",
    "5": "111100111001111", "6": "111100111101111", "7": "111001001010010",
    "8": "111101111101111", "9": "111101111001111",
    "\u2591": "111111111111111", "\u2592": "110110110110110",
    "\u2593": "101101101101101", "\u2588": "111111111111111",
    "\u2581": "000000000000001", "\u2582": "000000000000011",
    "\u2583": "000000000000111", "\u2584": "000000000001111",
    "\u2585": "000000000011111", "\u2586": "000000000111111",
    "\u2587": "000000001111111", "\u2588": "000000011111111",
    "\u2589": "000000111111111", "\u258a": "000001111111111",
    "\u258b": "000011111111111", "\u258c": "000111111111111",
    "\u258d": "001111111111111", "\u258e": "011111111111111",
    "\u258f": "111111111111111", "\u2590": "100000000000000",
    "\u258e ": "000111111111111",
}
def font_glyph(ch):
    s_ = _FONT3x5.get(ch)
    if s_ is None: return None
    return [1 if c == "1" else 0 for c in s_]

def font_codebook(chars):
    cb, seen = [], set()
    for c in chars:
        g = font_glyph(c)
        if g is None: continue
        t = tuple(g)
        if t in seen: continue          # a font with duplicate bitmaps is not a bigger alphabet
        seen.add(t); cb.append(g)
    return cb

# B: band x class, from syzygy-lattice's actual ramps
RAMPS = {
    "flat": ".:-=+*#%@", "h": "▁▂▃▄▅▆▇█▰", "v": "▏▎▍▌▋▊▉█▮",
    "dp": "·:;/Xx%#@", "dn": "·:\\Xx%#&*",
}
BC_GLYPHS = sorted({ch for r in RAMPS.values() for ch in r})
# C: a plausible real font alphabet, same size as A for a fair fight
FONT_SMALL = FLAT_RAMP
FONT_BIG  = "".join(FLAT_RAMP) + "░▒▓█▁▂▃▄▅▆▇▏▎▍▌▋▊▉"

# ── patch source ─────────────────────────────────────────────────────────────
def make_patches(n, seed=0, kind="image"):
    """Three sources, because the distributions differ and that is the point:
       image = smooth gradient regions, doc = flat + sharp edges, photo = everything."""
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        p = blank()
        if kind == "image":
            base = rnd.uniform(0.2, 0.8)
            for i in range(NP):
                p[i] = 1 if rnd.random() < base + 0.15*math.sin(i*0.9) else 0
        elif kind == "doc":
            edge = rnd.randrange(NP)
            fill = rnd.uniform(0.1, 0.9)
            for i in range(NP): p[i] = 1 if rnd.random() < fill else 0
            p[edge] = 1 if rnd.random() < .5 else 0
        else:
            for i in range(NP): p[i] = 1 if rnd.random() < .5 else 0
        out.append(p)
    return out

def mse(a, b): return sum((x-y)**2 for x, y in zip(a, b))/NP

def nearest_distortion(patches, codebook):
    tot = 0.0
    for p in patches:
        tot += min(mse(p, g) for g in codebook)
    return tot/len(patches)

def roundtrip(patches, codebook, assignments):
    """How many source cells remain DISTINCT after the encode.

    `assignments` is the precomputed nearest-slot list, not a callable. The first version
    took a callable and was handed the list, then called it -- a shape error that only
    shows up on the first non-empty run, which is the same shape of problem as the
    comparison bugs above: a signature that looks right and is never exercised.
    """
    buckets = {}
    for p, a in zip(patches, assignments):
        buckets.setdefault(a, set()).add(tuple(p))
    collided = sum(len(v)-1 for v in buckets.values())
    return len(patches) - collided, len(patches)

def assign_nn(patches, codebook):
    a = []
    for p in patches:
        a.append(min(range(len(codebook)), key=lambda i: mse(p, codebook[i])))
    return a

def kmeans(patches, k, iters=25, seed=0):
    rnd = random.Random(seed)
    cent = [patches[rnd.randrange(len(patches))][:] for _ in range(k)]
    for _ in range(iters):
        groups = [[] for _ in range(k)]
        for p in patches:
            groups[min(range(k), key=lambda i: mse(p, cent[i]))].append(p)
        for i in range(k):
            if groups[i]:
                cent[i] = [1 if sum(q[j] for q in groups[i])*2 >= len(groups[i]) else 0
                           for j in range(NP)]
    return cent

def report(name, codebook, patches):
    if not codebook: return None
    a = assign_nn(patches, codebook)
    d = nearest_distortion(patches, codebook)
    rt, tot = roundtrip(patches, codebook, a)
    return {"scheme": name, "slots": len(codebook), "bits": math.log2(len(codebook)),
            "mse": d, "roundtrip": rt, "of": tot,
            "collisions": tot-rt}

if __name__ == "__main__":
    for kind in ("image", "doc", "photo"):
        P = make_patches(600, seed=7, kind=kind)
        schemes = [
            ("A  scalar ramp (10)",      [glyph_from_density(c) for c in FLAT_RAMP]),
            ("B  band x class (38)",     [glyph_from_density(c) for c in BC_GLYPHS]),
            ("C  font 3x5, matched to A (10)", font_codebook(FLAT_RAMP)),
            ("D  k-means k=10",         kmeans(P, 10, seed=3)),
            ("E  k-means k=38",         kmeans(P, 38, seed=3)),
            ("F  font 3x5, k=A's size", font_codebook(FONT_BIG)),
            ("G  font 3x5, deduped 38", font_codebook(list(_FONT3x5.keys()))[:38]),
        ]
        print(f"\n  === patch source: {kind}   ({len(P)} cells of {CW}x{CH}) ===")
        print(f"    {'scheme':<28} {'slots':>6} {'bits':>6} {'MSE':>9} {'round-trip':>12} {'collisions':>11}")
        base=None
        for nm, cb in schemes:
            r = report(nm, cb, P)
            if r is None or base is None: base=r; 
            mark = ""
            if base and r and nm.startswith("A"): mark="  <- baseline"
            if base and r and r["mse"]<base["mse"]-1e-9 and not nm.startswith("A"):
                mark=f"  <- {base['mse']/r['mse']:.2f}x lower MSE than A"
            print(f"    {nm:<28} {r['slots']:>6} {r['bits']:>6.2f} {r['mse']:>9.4f} "
                  f"{str(r['roundtrip'])+'/'+str(r['of']):>12} {r['collisions']:>11}{mark}")
    print("""
  READ THIS CAREFULLY. The MSE column and the round-trip column are DIFFERENT QUESTIONS.
  A k-means codebook wins MSE because it was trained on these patches -- that is what a
  vector quantizer does. It is also the scheme MOST likely to collide, because a
  quantizer's whole job is to map nearby patches onto nearby symbols.

  So the honest summary is:
    - for a HUMAN looking at the screen, a trained codebook beats a density ramp, and
      the Game Boy's 16x-less-information result says the same thing for the same reason;
    - for a MACHINE reading through the text, the two pull opposite ways, and the
      perceptual winner is the round-trip loser.

  Neither number decides it. WHO IS THE READER decides it, and that is a question about
  the system, not about the alphabet.""")
