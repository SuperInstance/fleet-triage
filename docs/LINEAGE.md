# The chiaroscuro lineage, and the measurement that never went home

Four repos, one idea, and a gap that is now measured rather than suspected.

---

## 1. The lineage, established from commits and timestamps

| repo | first commit | commits | what it is |
|---|---|---|---|
| `chiaroscuro` | **09-27 10:05** | 11 | the root. *"Characters are shapes, not pixels."* Five doors, five engines, a 70-step tone ramp. |
| `voxelglyph` | **09-30 09:17** | 40 | the **measurement**. Proves Syzygy's observation is a rank-one projection R³→R with a provable collision. |
| `syzygy-lattice` | **09-30 10:59** | 3 | the **inheritor**. *"When a pixel becomes a character, what should the character know?"* Fuses Sobel orientation **into** the tone character. |
| `Projectionist` | **09-30 19:29** | 5 | the **stage**. Spawned from `Patchwork-experts`, not from `chiaroscuro`; side-by-side demo harness. |

`syzygy-lattice` names its parent explicitly: *"inheritor of chiaroscuro's question."* The
descent is clean and correctly attributed. `voxelglyph` names its target: *"What can a voxel
agent actually read through Syzygy's text encoding?"*

**The chain is: artifact → question → measurement.** And it stops there.

## 2. The gap, and it is not a missing link — it is a wrong direction

`syzygy-lattice` began at **10:59**. `voxelglyph`'s measurement landed at **09:17**, one
hour and forty minutes earlier, the same day.

**It could have known. It cites nothing.** Zero commit messages and zero files in
`chiaroscuro`, `syzygy-lattice`, or `Projectionist` mention `voxelglyph`, luma, rank-one, or
ceiling.

So the descent went artifact → question → measurement and **never came back up.** The
measurement was written down, published, and never reached the thing it was a measurement
*of*. `chiaroscuro` itself has commits on **10-01**, the day after, and still does not cite it.

## 3. What the measurement found, and what the inheritor built

`voxelglyph` proved: **Syzygy's entire observation is a rank-one linear projection** (BT.601
luma). Two colours **403 RGB units apart** land on the same luma, so to the encoder they are
one colour. That is a **provable** ceiling, not an empirical one.

`syzygy-lattice` built the right answer to a *different* question. It took the local Sobel
class and made it choose **which density ramp** the brightness draws from, so one glyph
carries **brightness band AND edge orientation**. The five ramps form a lattice where nearest
neighbours differ in exactly one coordinate. That is a genuinely good idea and it is the right
shape of answer.

**But the brightness channel was not touched.** `src/codec.mjs:72`:

```js
// cell class from the center pixel; band from mean luma
const band = Math.min(BANDS - 1, (mean * BANDS) >> 8);
```

**Still BT.601. Still rank-one. Still collides.** The lattice added a second dimension
alongside a first dimension that had already been measured as lossy, and **the pins verify
only the second dimension**: a golden lattice hash, h-bar and v-bar vote dominance, the
diamond's connected components. **Not one of them asks whether two different colours produce
the same cell.**

## 4. The loop, closed by measurement

I ran `voxelglyph`'s collision pair through `syzygy-lattice`'s own band and ramp logic:

```
A = rgb(0,240,0)      luma 140  band 5  class flat  ->  "+"
B = rgb(255,60,255)   luma 140  band 5  class flat  ->  "+"

distance in RGB: 403.1 units
identical glyph after the lattice's own encoding: YES
```

**Two colours 403 RGB units apart encode to the identical character, under the inheritor's
own code, on the inheritor's own arithmetic.** The orientation channel does not help, because
in a flat region there is no orientation to carry — the class is `flat` for both, and the
lattice is powerless along exactly the axis that collides.

**This is the same finding, third occurrence, in a new place:** the second channel makes the
system *look* higher-dimensional while the first channel's ceiling is untouched. A 5×10
alphabet that still loses what a rank-1 projection loses.

## 5. The fix is small and the design already implies it

`syzygy-lattice` has **five classes and ten bands per class = 50 symbols**, of which the flat
class uses ten. The flat class is the only place the collision can occur, and it is also the
class where a Sobel class carries **no information** — so the flat ramp is spending ten
symbols on what is, information-theoretically, one rank-one measurement.

**The obvious repair:** in the flat class, the ramp has nothing to disambiguate, so use the
budget differently. Options, cheapest first:

1. **Make the flat class chroma-keyed.** When the Sobel class is `flat`, choose among
   several ramp families by a second, non-rank-one statistic — hue, or chroma distance from
   the ramp's own neutral axis. `(0,240,0)` and `(255,60,255)` are 403 apart and differ
   enormously in chroma; this separates them at zero cost to the oriented classes, which
   have their own axis to spend.
2. **Report the collision as a receipt, not silence.** `syzygy-lattice` already has
   `src/receipts.mjs`. **A cell whose luma band is close to its neighbours' but whose chroma
   is not is exactly the signature of the rank-one ceiling**, and the encoder already has
   enough data to name it. That converts an invisible loss into a declared one.

Option 2 is the more interesting one, because it matches the project's own doctrine:
**the honest pause is the product.** A codec that names the cell it cannot resolve is worth
more than one that silently resolves it wrong.

## 6. What this lineage teaches that a single repo cannot

1. **The descent is attributed and the ascent is not.** `syzygy-lattice` says who its parent
   is. **No repo in the chain says who measured it.** The citation runs downward only.
   A lineage that can name its ancestors but not its measurements cannot close its own loops.
2. **Adding a channel is not the same as fixing the channel you have.** The lattice's
   alphabet is 5×10 and its effective brightness resolution is still ten steps of one
   rank-one projection. **The headline number went up; the ceiling did not move.**
3. **Pins verify what you built, not what broke.** The lattice's twelve pins are all
   structural. A pin that asked *"do two distinct colours share a cell?"* would have caught
   this in an afternoon. **That is the pin the lineage is missing, and it costs one line.**
4. **The stage is downstream of everything.** `Projectionist` came from `Patchwork-experts`
   and inherited neither the measurement nor the question. Demo stages are cheap to build and
   they are where the loop is least likely to close.

## 7. What I am not claiming

- I have not shown the collision *matters* for a real scene. It is a **provable ceiling on the
  encoding**, and how much it costs in practice on the images anyone actually points a camera
  at is a separate measurement that does not exist yet. **A provable loss is not yet a
  measured cost.**
- I have not read all 44 files of `chiaroscuro` or the five doors' implementations. The
  lineage claim rests on README claims, commit timestamps, and one executed test against
  `syzygy-lattice`'s own code.
- `chiaroscuro`'s Mirror is a 70-step ramp, not 10. I have only tested the *inheritor's*
  path. Whether the root has the same exposure is unmeasured.

---

**The one-line version:** the measurement landed at 09:17, the inheritor started at 10:59, and
after five weeks of citations running downward nobody has run the two numbers together. Now
someone has: **403 RGB units apart, identical glyph, `"+"`.**
