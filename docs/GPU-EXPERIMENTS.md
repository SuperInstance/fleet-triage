# The experiment queue for a GPU agent

Everything below is a real experiment with a pre-registered prediction. The part that is
usually missing — and the part worth reading first — is **§2: what each result would mean.**

A GPU agent iterating on a number without knowing which outcomes would change the direction
is not doing science, it is hill-climbing with a loss curve. For every experiment here there
is a written branch: what a null means, what a win means, and what result would *retract*
something already published.

---

## 0. Read this first: the rules that make these numbers mean anything

These are not preferences. Each one is a rule that was learned by getting it wrong.

1. **State whether CUDA or CPU actually ran.** A CPU fallback reported as a GPU result is a
   fabricated measurement. Record the device string with the number.
2. **Report the variance, not just the mean.** If the measured quantity has `std == 0` over
   the sample, the result is **INCONCLUSIVE, never PASSED**. This is a hard rule: an earlier
   sharding experiment scored `PASSED` on the literal comparison `0 < 0`.
3. **The ground truth must be computed, not asserted.** Every game number below is exact.
   If a label is approximate, say by how much.
4. **Non-degeneracy is a precondition, not a result.** Assert that the data has variance
   *before* evaluating any relational claim about it.
5. **A control must vary the thing it audits, by a different path than the audited thing.**
   The most expensive mistake in this project's history: a control built from the same call
   path as the probes, which therefore confirmed a fault instead of auditing it.
6. **A ratio whose denominator can be zero is a construction, not a measurement.** It always
   produces a finding, and the finding is always false.
7. **Seed everything and record the seed.** Two runs of the same experiment that differ are
   a finding about the seed, not about the method.
8. **Cross-port arithmetic must preserve the reference loop/summation order.** Float addition
   is not associative; a port that vectorises changes the answer.

---

## 1. The experiments, ranked by expected value per GPU-hour

| # | experiment | repo | needs GPU? | status |
|---|---|---|---|---|
| 1 | Can a network absorb minimax with zero search? | `pie-minimax` | **yes, strongly** | part-done |
| 2 | The decision-tree ceiling on 3×3 | `pie-minimax` | no (CPU) | **DONE — VERIFIED multi-beam** (pie-minimax `CEILING-VERIFY.md`, wave-63) |
| 3 | Composition test, carried to 4×4 | `ga4444` | yes, moderately | **partition re-derived (wave-63: `ga4444/PARTITION-44.md`); GPU sweep must sample LATE boards — run.py's ply≤9 walk makes the composition class structurally empty** |
| 4 | Capacity vs representation on 4×4 | `ga4444` | **yes, strongly** | blocked on data |
| 5 | What is a discrete judge actually good at? | `selectlib` | no | done; extend |
| 6 | Glyph/braille as an agentic observation | `voxelglyph` | yes, moderately | inconclusive |
| 7 | Set-valued labels on a 7-wide move space | `connect4` | yes, strongly | unblocked (54,166 positions; digest 0x4ef8351a5c319637) |
| 8 | Cross-runtime conformance at scale | `xruntime-conformance` | yes, moderately | part-done |
| 9 | Self-play vs table lookup as ground truth | `ladder` | yes, strongly | not started |
| 10 | Critical mass in a cellular opinion system | `murmuration` | yes, moderately | running |
| 11 | **Transfer gap vs I/O determinacy (the Cog Thesis)** | `quilt-dba` + `exoj` | yes, moderately | **queued — highest novelty** |
| 12 | Faithfulness of a cell's I/O simulation | `quilt-dba` | no (CPU) | queued |

**The single highest-value item is #1, and #1 is nearly finished.** Everything else is a
scaling of it.

---

## 2. Decision trees — what each result *means*

This is the part to read twice.

### Experiment 1 — Can a network absorb minimax composition, with zero search?

**Repo:** `pie-minimax` · **Ground truth:** exact, 180,361 reachable our-turn states
**Result so far:** a 9→9 linear model, 81 parameters, top-1 **0.1807**. Random floor
**0.1431**. Set-recall 0.1748. **14.7% of states (26,505) have multiple optimal moves.**

The linear model beats chance by 0.037. That is a small, real, *uninteresting* margin.

| Result | What it means |
|---|---|
| Linear stays ≈ 0.18 after any fix | **The representation cannot express minimax.** Minimax is a composition of local threats; a sum of local terms has no way to represent "two simultaneous wins" because that is a *count*, not a sum. This is a strong, publishable negative. |
| Nonlinear closes a *little* (0.25–0.40) | Capacity helps a bit; representation is still the binding constraint. Report the gap to the decision-tree ceiling — **the number that matters is the ratio to that ceiling, not the raw accuracy.** |
| Nonlinear approaches the tree ceiling | Minimax composition is learnable by a small net. Surprising, and a real result. |
| **Any model beats the decision-tree ceiling** | **Stop. Something is wrong with the labels, not the model.** The tree is an exact computation. Beating it means the evaluation leaked. This branch is the most important one. |
| Accuracy collapses on COMPOSED states (≥2 simultaneous wins) | **The prediction carried forward from 3×3 holds.** You have isolated the mechanism: local voting handles single threats, fails on threat *counts*. This is the cleanest result available in the whole queue. ⚠️ *Wave-63 correction: at 3×3 this row could not be executed as pre-registered — the corrected threat definition (blocked lines excluded) leaves n=22 trivial COMPOSED single-optimal boards (`pie-minimax/CEILING-VERIFY.md` M2/M3). Re-derive the partition on 4×4 before relying on it.* |

**Pre-registered test, carried forward:** partition states into **SIMPLE** (0 or 1 immediate
win available — expressible by one linear term) and **COMPOSED** (≥2 simultaneous wins —
requires counting). If accuracy collapses on COMPOSED, you have found the mechanism, not
just a number.

### Experiment 2 — The decision-tree ceiling

**Not started, and it gates Experiment 1.** No conclusion about neural capacity is valid
without it. Fit a decision tree to the same 180,361 states and measure its top-1. A shallow
tree, if it beats the linear model substantially, says the task is *nonlinearly separable but
shallowly structured* — a different and more actionable claim than "neural nets are bad at
this." A deep tree matching the linear model says minimax is not a simple function of local
structure at all.

**Without this, Experiment 1's numbers are uninterpretable.** Do this first. It is CPU work.

> **RESULT (wave-63, VERIFIED multi-beam — `pie-minimax/CEILING-VERIFY.md` + receipts).** On the 2,423 distinct our-turn boards: custom Gini tree-16 **0.7879 ± 0.0224**, custom linear **0.7148 ± 0.0170** (re-run reproduces the committed numbers exactly); independent sklearn beams **0.7907 ± 0.0313 / 0.6888 ± 0.0119** pass the registered bands — after an empty-cell-aware scoring fix (argmax over all 9 classes auto-misses occupied-cell picks; below-floor artifact receipted). Floor 0.5753. Landed branch: **nonlinearly separable but shallowly structured**; the tree saturates by depth 12; linear fills ~0.84–0.91 of the tree depending on column. Two corrections travel with it: (1) `is_simple()` counts BLOCKED lines as threats — under the fixed definition the COMPOSED class nearly vanishes on single-optimal (n=22, all trivial), so Experiment 1's COMPOSED-collapse test is **not executable as pre-registered at 3×3** and the 4×4 rung must re-derive the partition before consuming it; (2) the partition contrast is training-protocol-sensitive (class-internal vs full-train booked; tree shows no composition penalty in all three beams, the linear penalty deflates from 43% to small-or-absent). Dataset canon now pinned: `receipts/exp2-distinct-boards.txt` (sha256 `ae19d8ad…`, FNV `0x65a75b94d9804cfd`).

### Experiment 3 — Composition test on 4×4 four-in-a-row

**Blocked on data** (a C bitboard solver is being written). `ga4444`.

4×4 is a better rung than 5×5 or Connect 4 for the *first real* measurement, for a reason
that is easy to get backwards: **once a lookup table is impossible, you no longer know whether
your model is reasoning or memorising.** 4×4 has complete ground truth *small enough to
generate in a session*.

| Result | What it means |
|---|---|
| The 3×3 composition effect **replicates** | You have a result that survives a board-size increase. The single most valuable outcome in the queue. |
| It **does not replicate** | The 3×3 result was about board *size*, not about *composition*. Both readings are publishable; the second one is a correction and must be recorded as one. |
| The effect strengthens with size | Composition cost grows with depth. Predict and test: does it scale with the number of *simultaneous* threats rather than with ply count? |
| The effect vanishes | Either the labels are set-valued and you are being scored wrong, or linear voting is sufficient up to 4×4. **Check the label construction before believing this.** |

### Experiment 4 — Capacity vs representation on 4×4

With ground truth in hand, sweep width and depth and plot accuracy against the
decision-tree ceiling, not against 0.25 or 1.0. **A curve that is still rising at your
largest model is the interesting one** — it says the experiment is compute-limited rather
than representation-limited, and that is a completely different conclusion from a flat curve.

Report the plateau, and state explicitly whether the plateau is a property of the
representation or of the model you happened to pick.

### Experiment 5 — What a discrete judge is good at

**Repo:** `selectlib`, `jev-fusion`. **Result: settled, and it is a negative result.**

Measured: a real Jev judge **beats a blind local-noise statistic on cross-seam structure**
(`blind_split`: −0.0052, −0.0050, −0.0111 across three budgets) and **ties exactly on
same-error structure** (`blind_uniform`: +0.0000 at every budget). 288 model calls per field.

**What it means:** discrete judges are **coarse structural instruments** — useful for
boundaries and regions, not for fine per-cell selection. A judge that gates a whole region's
work is earning its cost. A judge that picks which of 400 individual cells to fix is not.

The GPU-relevant extension: if the judge is useful at *coarse* selection, the interesting
question becomes whether a **learned** coarse selector — trained on the judge's region-level
labels — can replace 288 API calls with one forward pass. That is a legitimate distillation
experiment, and its ground truth is already collected.

| Result | What it means |
|---|---|
| Student matches the judge on held-out fields | **The judge is compressible.** One forward pass replaces 288 calls. This is a real win and it is publishable. |
| Student matches only on `blind_split` | The judge encodes something about *error structure* that a local loss does not capture. Then the label set must carry cross-cell information — which the sparse-signal objection says it probably does not. |
| Student fails on both | The judge is not a function of the local representation at all. Report that plainly; it is a statement about the information content of the observation. |

### Experiment 6 — Glyph and braille as an agentic observation

**Repo:** `voxelglyph`. **Result: exp1 is solid, exp2 is INCONCLUSIVE, exp3 is at chance.**

The proven fact: Syzygy's luma is a rank-1 projection, so `(0,240,0)` and `(255,60,255)` are
**403 RGB units apart and both luma 140**. A rank-one luma ceiling means a genuine
aliasing collision, not a near-miss.

exp2 (distillation into a linear model) is **inconclusive after four corrections**: degenerate
labels, unequal input widths, a falsely described linear model, and palette/material
collinearity. exp3 (minimal encoding) is **at chance for every brightness alphabet** —
alphabet *alignment*, not alphabet size, controls collisions.

**There is no authorised claim of successful agentic distillation.** Do not report one.

| Result | What it means |
|---|---|
| A non-linear model beats the linear one on the same corrected setup | The corrected null was a real null and the function is genuinely nonlinear. Report it as a new result, not as a reversal. |
| The linear model still ties | **Alignment, not capacity, is the binding constraint.** Any encoder that does not canonicalise the palette first is measuring nothing. This is the more interesting claim and it is already supported by exp3. |
| A canonicalising encoder (map each glyph to its byte) succeeds | Trivially true and **not a result** — it is a lookup table. Say so if you find yourself reporting it. |

### Experiment 7 — Set-valued labels on a 7-wide move space

**Repo:** `connect4`. This is the **ladder-wide consequence**, and it gets worse, not
better, at each rung.

3×3 has 14.7% of states with multiple optimal moves. Connect 4 has a 7-wide move space and
common draws, so the multi-optimal fraction is far higher. A label set that assigns **one**
optimal move relabels every other optimal move as an error.

**This is the difference between training on truth and training on noise**, and it presents
as "the network is bad at Connect 4."

| Result | What it means |
|---|---|
| Set-recall stays high while top-1 drops | The network learned the value function and not a single arbitrary policy. **This is a success, and reporting only top-1 would call it a failure.** |
| Set-recall collapses too | The representation genuinely cannot represent "any of these are right". Then a set-aware loss is required and is a real contribution. |
| Adding a set-aware loss (`−log Σ_{m∈Opt} softmax(z)_m`) fixes it | Confirms the label-set diagnosis and gives a method. **The best available outcome on this rung.** |

**Report top-1 and set-recall together, always.** Reporting one alone is how a working model
gets described as broken.

### Experiment 8 — Cross-runtime conformance at scale

**Repo:** `xruntime-conformance`. FNV-1a 64 of `"café Δ 日本語"` = `0x24a555471370b18d`, the
substrate-wide canary. **BLAKE2b/SHA-256 is for integrity; FNV-1a 64 is for cross-port
conformance.** They are not interchangeable and a run that conflates them is not a test.

A real portability bug already lives here: the `scalarSha`/`lossSha` mismatch across runtimes,
caused by summation order.

| Result | What it means |
|---|---|
| All ports agree bit-for-bit on a wide sweep | Conformance holds at scale. Then the canary is worth promoting to a release gate. |
| Divergence appears only above a size threshold | A float-accumulation-order bug. Fix the loop order; **do not loosen the tolerance**, that hides the class. |
| Divergence is random per-run | Non-determinism (atomics, threading), not arithmetic. That is a different defect with a different fix. |

### Experiment 9 — When does ground truth stop being available?

**Repo:** `ladder`. Rung classification is settled: **too easy** (3×3, 4×4), **usable**
(5×5, Connect 4, single-deck blackjack), **uncheckable as proposed** (poker opponent
psychology).

The trap: once a lookup table is impossible, the only ground truth left is **self-play**, and
then every number is a statement about *your own search* rather than about the task.

| Result | What it means |
|---|---|
| A self-play model beats a table model on a table-checkable rung | **It is memorising, not reasoning.** This is the diagnostic experiment and it must be run before trusting any self-play number. |
| Self-play matches on checkable rungs | Self-play is a legitimate ground truth and the ladder can extend. |
| Both lose to the table on checkable rungs | Something is wrong with the search, not the model. Check the search first. |

**Do not model an opponent's hidden belief as ground truth.** Model observable action
distributions instead.

### Experiment 10 — Critical mass in a cellular opinion system

**Repo:** `murmuration`. **Provisional result:** 1-D corrected is bimodal, 2-D reliably
supports 3 communities, 3-D supports 4. The `d+1` law is **not yet established** — mechanism
and threshold sensitivity are under review.

**Known confound, already partly corrected:** the similarity radius was **0.20 in 2-D and
0.15 in 1-D**, and the geometry of a ball in a plane is not the geometry of an interval on a
line. **The d+1 law could be entirely a threshold artefact.**

| Result | What it means |
|---|---|
| Equalising thresholds changes the law | **It was an artefact. Retract the d+1 claim and report the threshold sensitivity as the finding.** This is the most likely outcome and it is not a failure. |
| The law survives equalised thresholds | The dimension effect is real and the threshold was not carrying it. Then the mechanism (dimension changes what "local agreement" means geometrically) is worth a real writeup. |
| Seed count matters more than dimension | The original seeding bug again. Fix and re-run before interpreting anything. |

---

## 2b. Experiments 11–12 — the Cog Thesis

> "A component inside a cellular system is learnable from simulated data when its role is
> computable from its own I/O contract, and the surrounding system filters enough that
> simulating the I/O is faithful."

**Why this is the most novel item in the queue.** Synthetic data is normally unfaithful to
the real distribution — that is the whole reason distillation is hard. This says the
objection does not apply inside a cellular system, for a structural reason: **a cell's role
is not a label someone assigned, it is a consequence of what can enter it and what leaves
it.** So faithfulness is available *by construction* rather than by luck.

**The measure.** `determinacy(c) = 1 - output entropy under fixed input`. How much freedom
does the cell still have given this input? A router with 3 declared outputs scores near 1.0.
A value cell carrying arbitrary content scores near 0.

**The prediction, which is the experiment:** the transfer gap between a simulated-trained and
a real-trained component should be a **decreasing function of `determinacy`**. That
correlation is the test. Nine cells in `quilt-dba/engine/cells/` — `ai api formula io
listener program router sensor value` — supply the range.

| Result | What it means |
|---|---|
| Gap falls monotonically with `determinacy` | **Thesis supported.** There is a principled, measurable criterion for which parts of a cellular system can be trained synthetically. That is a genuinely useful result. |
| Gap is flat across `determinacy` | Thesis wrong — but **check the range first.** A flat result where all nine cells sit close together is *uninformative*, not a refutation. Say which. |
| Gap high everywhere, including `determinacy → 1` | **The measure is wrong, not the thesis.** A cell can be structurally constrained and still depend on temporal context a static I/O view does not capture. That is an interesting finding about the limits of the I/O view. |
| `determinacy` unstable across input distributions | The measure does not exist as stated. **Report the instability; do not average it away.** |

**The control, and it is the thing most likely to invalidate this:** train on a
**deliberately mismatched** simulator — one whose input distribution is wrong. **If the
transfer gap does not widen, nothing was tested**, because the original simulator was not
carrying the signal in the first place. That is the most likely outcome, because real and
simulated distributions may simply be too similar to distinguish.

**GPU-specific:** the matched-budget rule is not optional here. Train both arms with the
same architecture, optimiser, budget, and seeds. The earlier nonlinear-vs-linear comparison
was inconclusive *precisely because* the budgets were not matched — do not repeat that.

**Full write-up:** [`fleet-triage/docs/COG-THESIS.md`](https://github.com/SuperInstance/fleet-triage/blob/main/docs/COG-THESIS.md)
(pushed to `quilt-dba/docs/` and `exoj/docs/` as well).

**Nothing here has been measured.** It is a hypothesis with a test.

---

## 3. The one thing to do before touching a GPU

**Run Experiment 2, the decision-tree ceiling, on CPU.** It is a few minutes of work and it
converts every neural number in this document from "an accuracy" into "a fraction of what is
achievable." Without it, Experiment 1's 0.1807 has no interpretation — 0.1807 could be 10% of
the ceiling or 90% of it, and those imply opposite conclusions.

**A number without a ceiling is not a result. It is a number.**

*(Wave-63 update: the ceiling exists now — see the RESULT block under Experiment 2. The GPU experiments should plot against tree-16 ≈ 0.79 on all boards and ≈ 0.68 on the single-optimal subset.)*

---

## 4. Reporting format

Every experiment reports, in this order:

1. **Device.** Did CUDA actually run? Paste the device string.
2. **Data provenance.** Which commit, which digest, how many states/positions, and the
   FNV-1a 64 of the input file.
3. **The ceiling.** What is perfect, and what did you get as a fraction of it.
4. **Variance.** Mean ± std over N seeds, with the seeds listed. **std == 0 means INCONCLUSIVE.**
5. **The branch.** Which row of which decision tree above you landed on, quoted.
6. **Controls.** What ran that could have failed. If nothing could have failed, say that —
   it is the finding.

No adjectives. A number, a ceiling, a variance, and a branch. Everything else is narrative.
