# Treat the font as the tileset — the arithmetic, and the problem underneath it

Casey's suggestion, taken seriously enough to do the division.

> *"the shapes could be as many character variations as there are pixels for the tile. Think
> about the way Game Boy / Genesis / early Nintendo programmers used tiles and windows to
> create effects quickly. We could be doing that but treating font as our tile-set."*

---

## 1. What the alphabet is today, measured

`syzygy-lattice` is a **product alphabet**: band × class, 10 × 5.

```
flat  .:-=+*#%@      h   ▁▂▃▄▅▆▇█▰
v     ▏▎▍▌▋▊▉█▮     dp  ·:;/Xx%#@     dn  ·:\Xx%#&*
```

The ramps **overlap** — `.:;=+*#%@` and `·:;/Xx%#@` share six glyphs. So the real count is
**38 distinct glyphs, 5.25 bits per cell**, not 50 / 5.64.

Syzygy pools **2×4**, so a character cell stands for 8 source pixels = **64 bits at the
cell.** That makes the current scheme **12.2:1 lossy**.

| alphabet | glyphs | bits/cell | loss at the cell |
|---|---:|---:|---:|
| **syzygy-lattice today** | 38 | 5.25 | **12.2 : 1** |
| ASCII printable | 95 | 6.57 | 9.7 : 1 |
| Latin-1 + symbols | 224 | 7.81 | 8.2 : 1 |
| VGA 8×16 | 256 | 8.00 | 8.0 : 1 |
| a 3×5 cell at 2 levels | 32768 | 15.00 | 4.3 : 1 |

**A plain ASCII font is already 25% more alphabet than the entire band × class scheme.** The
suggestion is not a marginal improvement. It is strictly larger before a single glyph is
chosen well.

## 2. The flat class is the smoking gun

The luma collision lives in the flat class, because a flat region has no Sobel class to
carry. And the flat class is:

> **10 glyphs = 3.32 bits, spending 10 of the 32,768 possible 3×5 patterns — 0.031%.**

**A 15-pixel medium is being used to transmit 3.3 bits.** That is the waste, and it is exactly
where the provable collision sits. `voxelglyph` proved two colours 403 RGB units apart
collapse; the *reason they collapse* is that the encoder only has ten symbols to separate
them with.

## 3. Why the tile trick works, stated precisely

This is the part worth getting right, because it is counterintuitive.

**Game Boy tile:** 8×8 = 64 pixels, 2bpp, a palette of 4.

| | bits per 64-pixel tile | bits per pixel |
|---|---:|---:|
| encode by **palette** | 128 | 2.00 |
| encode by **tileset** (256 tiles) | 8 | 0.125 |

**The tileset carries 16× LESS information and looks dramatically better.** Not comparable —
better, by a wide margin, on the only axis that matters to a human looking at a screen.

**The codebook beats the scalar, and it is not close.** A scalar asks *"how bright is this
cell"* and gets one number. A codebook asks *"which of 256 prepared shapes best matches this
cell"* and gets one of 256. The second question has 256 answers and the first has 10, and the
answers are not equally spaced — they are *shaped*, so the error the eye notices is smaller
even though the number of options is smaller too.

That is the whole insight, and it is exactly what `chiaroscuro` meant by **"characters are
shapes, not pixels"** — the idea the lineage dropped when `syzygy-lattice` reduced it to
"orientation picks which brightness ramp you draw from," which is still a scalar with a
side-channel.

## 4. The window trick, and what survives of it in text

The Genesis **Composition Engine** shifts an entire layer by a *sub-tile* amount, per
scanline. The visible effect: the 8×8 grid dissolves, and a dither pattern made of
different tiles reads as a continuous gradient across tile boundaries.

**Text cannot shift a cell.** The grid is fixed by the terminal. So the window trick does not
transfer directly — and I think that is important, because it means the honest version of
Casey's idea stops at the tileset and does not get a second free win.

What *does* transfer is the reason the trick existed: **break the visible grid so the
codebook's discreteness stops reading as blocks.** The text equivalent is choosing among
glyphs that differ by a *sub-cell phase* — stipple patterns at different offsets, so
neighbouring cells interlock instead of tiling. Whether a given font contains such a family
is checkable, and is the experiment below.

## 5. The problem underneath, which is the real research question

Here is where I have to push back on my own enthusiasm, because the arithmetic does not
finish.

**A tileset is a vector quantizer.** To use a font as a tileset, each cell's local image
patch selects its nearest glyph. The best possible such set of N glyphs is the **vector
quantizer trained on the patch distribution** — LBG / k-means. So:

> **The optimal tileset is not the font. It is a codebook trained on the distribution of
> image patches. The font is a good starting point, because a typographer and a quantizer
> are solving the same problem — cover the space with shapes that are all distinguishable —
> but they are solving it over different distributions.**

Legibility is over *letterforms*. Coverage is over *image patches*. They are not the same
set, and where they disagree the font will be the wrong codebook.

**And the second problem, which is worse.** `voxelglyph`'s finding is about what a **machine**
can read through the text. A tileset chosen for human perception is chosen to make nearby
patches map to *similar* glyphs — that is the whole point of a codebook. **Similar glyphs are
exactly what a machine cannot tell apart.**

**So the two readers want opposite things from the same alphabet:**

- **Human reader** → want neighbouring patches to collide onto nearby glyphs. That is what
  makes it look smooth.
- **Machine reader** → want neighbouring patches to get *distinguishable* glyphs. That is
  what makes it readable.

**Casey's idea, taken all the way, is the question: can one glyph set be simultaneously
(a) legible to a human, (b) a good vector quantizer for image patches, and (c) injective
enough for a machine to round-trip what it sees?**

I do not know the answer. I know the three constraints are in tension, and I know which
direction each pulls. **That tension is the research problem, and it is a good one.**

## 6. What I will not claim

- **The font does not fix `voxelglyph`'s collision.** For a *uniform* patch, both colours are
  a uniform patch; a patch codebook maps them to the same uniform glyph, exactly as the band
  did. **The collision is a collision between the two colours' identities, and any codebook
  over patches inherits it.** What the tileset fixes is *perceptual* resolution, not
  *identity* resolution. Those are different problems and I nearly conflated them.
- **A tileset gets us from 5.25 to 8 bits, and we need 64.** Better by 2.3×, still 8:1 lossy.
  Anyone who says "use the font" has solved a fifth of the problem.
- I have not run a distortion experiment. Everything above is arithmetic over the existing
  alphabets, not a measurement of what they render like.

## 7. The experiment, and it is cheap

1. **Collect a patch distribution.** Real images, cropped to the cell. A webcam frame, a
   screenshot, a document scan — three sources, because the distributions differ and that
   matters.
2. **Fit the baseline.** Nearest-neighbour over the 38 current glyphs, using each glyph's
   actual pixel pattern. Measure distortion, per cell.
3. **Fit three challengers.** Nearest-neighbour over the font. Nearest-neighbour over a
   k-means/LBG codebook trained on the same patches. Nearest-neighbour over a *phase-shifted
   stipple family* if the font has one.
4. **The metric that decides it is not MSE.** It is: **at a fixed bit rate, which renders
   more recognisably like the source to a person?** Report both, and report them separately,
   because they will disagree — and where they disagree is the actual finding.
5. **The control that matters:** also report the machine round-trip. For each scheme, how
   many distinct source patches are distinguishable after the encode? **A scheme that wins on
   perception and loses on round-trip is not a win**, it is a trade, and the size of the trade
   is the number worth publishing.

## 8. Why this is the right shape of thing to build

`chiaroscuro` was for a person looking at a screen. `voxelglyph` was for an agent reading
through text. **`LINEAGE.md` recorded that those two never met.** Casey's suggestion is the
first thing in the chain that could make them meet — a single alphabet serving both readers,
with the tension between them made explicit and measured rather than discovered later by
whoever tries to use it.

📄 `syzygy-lattice/src/codec.mjs:72` for the band derivation this replaces.
