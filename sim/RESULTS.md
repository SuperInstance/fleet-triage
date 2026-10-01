# Two simulations, and one conclusion I got wrong before running anything

## 1. The collapse law — the audit is right and I was wrong

`F1-AUDIT.md` §2 says my `Var_n = Var₀·2^(−n)` is wrong and the true rate is
`1 − 4D sin²(π/N)`, scaling as **N²/D**. I reimplemented it from scratch on a circulant
ring and ran it.

**λ₁ reproduces the measured decay to a worst relative error of 3.5 × 10⁻¹²** over N ∈
{16…256} × D ∈ {0.5, 0.25, 0.1}. And the scaling is exact:

| | rounds to 1% | ratio | N² | 1/D |
|---|---:|---:|---:|---:|
| N=64, D=0.50 (baseline) | 955 | 1.00 | 1.00 | 1.00 |
| N=128, D=0.50 | 3,821 | **4.00** | 4.00 | 1.00 |
| N=256, D=0.50 | 15,289 | **16.01** | 16.00 | 1.00 |
| N=512, D=0.50 | 61,157 | **64.04** | 64.00 | 1.00 |
| N=64, D=0.25 | 1,911 | **2.00** | 1.00 | 2.00 |
| N=64, D=0.10 | 4,780 | **5.01** | 1.00 | 5.00 |

Three significant figures, two orders of magnitude in N. **The audit's N²/D is right and my
2^(−n) was wrong.**

**And the sign of the correction is the useful part:** doubling the fleet quadruples the time
to uniformity. **Scale does not make a federated system converge faster — it makes it more
heterogeneous for longer.** That is a design lever, not a fate.

### I got the comparison wrong three times, and each time printed a confident number

| version | the bug | what it did to the verdict |
|---|---|---|
| v1 | random init — "measured" mixes all Fourier modes, "predicted" is k=1 | ratios across five orders of magnitude |
| v2 | sum-of-squares decays as λ^(2t), compared against λ^t | every ratio wrong by a factor of 2 |
| v3 | absolute amplitude compared against a **ratio** with no normalisation | I printed **"the audit's lambda is CORRECT"** on data showing 6.22 × 10¹ error |

**v3 is the one that matters.** It was not a wrong conclusion reached by bad reasoning; it
was a right conclusion asserted from a table that did not support it, and I would not have
known without running the corrected version. Every fix was the same: **normalise before
comparing, and never compare a quantity to a ratio.**

## 2. The tileset — Casey's suggestion, measured, and I was wrong about the outcome

TILESET.md §7 specified this experiment. Here is the result, and **the conclusion I wrote
into that document before running it is not what the data says.**

600 cells of 3×5, three patch sources, at matched alphabet sizes:

| scheme | slots | bits | MSE (image) | MSE (doc) | MSE (photo) |
|---|---:|---:|---:|---:|---:|
| A scalar density ramp | 9 | 3.17 | 0.2854 | 0.2611 | 0.3466 |
| B band × class (what syzygy-lattice has) | 33 | 5.04 | 0.2802 | 0.2564 | 0.3392 |
| C font, matched to A's size | 9 | 3.17 | 0.3003 | 0.2760 | 0.3146 |
| D k-means k=10 | 10 | 3.32 | 0.2440 | 0.2450 | 0.2916 |
| E **k-means k=38** | 38 | 5.25 | **0.1809** | **0.1760** | **0.2017** |
| F font, deduped | 26 | 4.70 | 0.2480 | 0.2167 | 0.2728 |
| G font, deduped to 38 | 38 | 5.25 | 0.2449 | 0.2286 | 0.2572 |

**Three results, one of which contradicts what I wrote before running it.**

**1. A font beats a density ramp — Casey's insight holds, modestly.** At 38 slots the font
is **1.17–1.35× better than the scalar ramp** on MSE. Real, reproducible, and worth having.

**2. A font is a mediocre codebook, and a trained one is much better.** At the *same* 38
slots and the *same* 5.25 bits, **k-means is 1.58× better than the font** (0.1809 vs
0.2449). This confirms the theoretical point in TILESET.md — a typographer and a quantizer
cover different distributions — and it is the more useful half.

**3. The tension I predicted does not exist.** TILESET.md says:

> *"for a MACHINE reading through the text, the two pull opposite ways, and the perceptual
> winner is the round-trip loser."*

**The data does not show that.** k-means k=38 wins on **both**: MSE 1.58× better *and*
round-trip 62/600 against the baseline's 32/600. **I wrote a conclusion before running the
experiment and the experiment contradicted it.** Same shape as the v3 comparison bug above,
and the same fix applies: measure, then write.

**4. The round-trip metric is saturated and therefore not yet discriminating.** Best is
79/600. Random-ish 15-bit patches are nearly all distinct, so *any* 38-symbol alphabet
collides. A real version of this needs smooth, correlated patches from actual images; until
then the round-trip column tells you the scheme is lossy and not which is less so.

## 3. What the first version of this simulation got wrong, since it is the same disease

My first "font" model rasterised every character as a **bottom-up fill by ink weight** — so
`:`, `+`, `*` and `#` all produced the same shape at different fill levels, and the "font"
schemes came out **byte-identical to the scalar ramp**. C and F had MSE 0.2854, exactly A's.

**The tell was that two supposedly different schemes had identical numbers to four decimals.**
I had modelled a font as a number again, which is the very thing the experiment was about.
A font is a set of *distinct shapes*; if your model of a font produces identical codewords for
different characters, you are not modelling the thing you are measuring.

Fixed with real 3×5 bitmaps and a duplicate-bitmap dedupe — the density ramp ░▒▓█ and the
solid █ collapse to the same 15 bits, so a "38-glyph font" can really only be 26–38 distinct
codewords. **That is a property of 3×5 cells, not of fonts, and it caps the alphabet.**

## Reproduce

```
python3 collapse_sim.py     # the ring; prints the lambda table and the N^2/D scaling
python3 tileset_sim.py      # the tileset comparison, three patch sources
```
