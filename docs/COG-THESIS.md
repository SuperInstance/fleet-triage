# The Cog Thesis — why a cellular system's parts are trainable on simulated data

**Status: a falsifiable hypothesis, not a result.** Nothing here has been measured. The
experiment that tests it is specified below and is the point of this document.

---

## 1. The thesis

> **A component inside a cellular system is learnable from simulated data when its role is
> computable from its own input/output contract, and the surrounding system provides enough
> filtering that a simulation of that I/O is faithful to the real distribution.**

The usual objection to synthetic data is that it is unfaithful to the real distribution.
That objection is correct *in general* and it is what makes distillation work hard. The
thesis says it does not apply here, for a structural reason:

**In a cellular system, a component's role is not a label someone assigned. It is a
consequence of what can enter it and what leaves it.** A sensor cell that is push-based and
returns a wrapped reading has almost no freedom. That constraint is not a designer's
intention — it is forced by the I/O. And because the cell sits inside a lattice, the
simulation of its inputs is already being filtered by every neighbouring cell before the
data reaches it.

So the faithfulness requirement is not "simulate reality perfectly." It is **"simulate the
I/O, which the system already constrains."** The cell is a definable cog, and a cog is
learnable from a simulation of its own socket.

## 2. Why this is worth testing rather than assuming

The thesis is attractive and it is also the kind of thing that is attractive *because* it
would justify a lot of work. It could be wrong for two opposite reasons:

1. **The I/O is looser than it looks.** A cell that accepts arbitrary values and emits
   arbitrary values has no computable role, whatever its documentation says.
2. **The simulation is unfaithful anyway.** The system's filtering is not enough to make a
   synthetic input distribution match the real one, and every conclusion drawn from
   simulated data is about the simulator.

Both failure modes are **measurable**, and that is what makes the thesis a research program
rather than a slogan.

## 3. The measurement: I/O determinacy

Define, for a cell `c` with input alphabet `I` and output alphabet `O`:

```
determinacy(c) = 1 - (observed output entropy under fixed input) / (log |O|)
```

Read it as: *given this input, how much freedom does the cell still have?*

- A **router** with 3 declared outputs and a fixed input distribution is near 1.0 — almost
  everything is determined.
- A **value** cell carrying arbitrary content is near 0 — the input does not constrain it.

The thesis makes a **quantitative, falsifiable prediction**:

> **The transfer gap — the performance difference between a component trained on simulated
> data and the same component trained on real data — should be a decreasing function of
> `determinacy`.** Cells with `determinacy → 1` should transfer nearly perfectly. Cells
> near 0 should transfer poorly, no matter how good the simulator.

**That correlation is the experiment.** It is the whole thing. If `determinacy` predicts the
transfer gap, the thesis holds and there is a principled way to decide which parts of a
cellular system can be trained synthetically and which cannot. If it does not, the thesis is
wrong and we have learned that something *other* than I/O structure governs transfer.

A negative result here is worth more than a positive one, because it would tell us the
determinant is elsewhere — and the list of candidates is short enough to check.

## 4. The experiment

**Cells in scope:** the nine in `quilt-dba/engine/cells/` — `ai`, `api`, `formula`, `io`,
`listener`, `program`, `router`, `sensor`, `value`. Each already declares a role and a
push/pull discipline in its own header, which is the documentary form of the thesis.

**For each cell, in both repositories:**

1. **Extract the I/O contract from the code, not the comments.** For every public function,
   record the declared input types, the declared output types, and the constraints that
   actually appear in the body (validation, defaults, throws). **If the code and the
   documentation disagree, that disagreement is a datum — report it.** In `quilt-dba` the
   sensor header says "push-based, not pull-based… by design," and that is a testable claim
   about the code, not a statement about the architecture.

2. **Measure `determinacy`** under a fixed, documented input distribution. Use at least
   three input distributions (uniform over the declared type, a realistic operational
   distribution, and a degenerate one) — **if the three disagree, the measure is not stable
   and that is the finding.**

3. **Train two identical models**: one on simulated data, one on real operational traces.
   Same architecture, same optimiser, same budget, same seeds. **Matched budget is not
   optional** — the earlier nonlinear-vs-linear comparison was inconclusive precisely because
   the optimiser budgets were not matched.

4. **Measure the transfer gap** and plot it against `determinacy`.

5. **Run the null control.** Train on simulated data from a *deliberately mismatched*
   simulator — one whose input distribution is wrong. If the transfer gap does not widen,
   **the original simulator was not carrying the signal, and the thesis is untested rather
   than supported.** A control that cannot widen the gap is not a control.

## 5. Decision tree

| Result | What it means |
|---|---|
| Transfer gap falls monotonically with `determinacy`; near-1 cells transfer almost exactly | **Thesis supported.** There is a principled, measurable criterion for which parts of a cellular system can be trained synthetically. Publish the criterion. |
| Gap is flat across `determinacy` | **Thesis wrong.** Something other than I/O structure governs transfer. Check the obvious candidates: simulator fidelity, data volume, or simply that all nine cells are near each other on the measure and the experiment lacks range. **A flat result over a narrow range of `determinacy` is an uninformative result — say so rather than reporting it as a refutation.** |
| Gap is *low* everywhere | Either the task is too easy to separate the conditions, or real data was not really held out. Verify the holdout before believing it. |
| Gap is *high* everywhere, including `determinacy → 1` | **The determinacy measure is wrong**, not the thesis. A cell can be structurally constrained and still depend on temporal context the I/O does not capture. That would be a genuinely interesting finding about the limits of a static I/O view. |
| The mismatched-simulator control does not widen the gap | **Nothing was tested.** Report as INCONCLUSIVE. This is the most likely result if the real and simulated distributions were too similar to distinguish. |
| `determinacy` is unstable across input distributions | The measure does not exist as stated. Report the instability — do not average it away. |

## 6. Rules

- **Do not use a decision tree as the ceiling here.** The nine cells are not a labelled
  classification problem with an exact answer; the goal is a *transfer* measurement.
- **Real operational traces must be genuinely held out** and the holdout must be verified
  before the gap is quoted. A gap measured against data the model saw is zero by
  construction.
- **`quilt-dba` already enforces this discipline.** Its charter requires decision rules as
  receipts **dated before the run that produced the numbers**, and `receipts_ed1.jsonl`
  carries `rules.R1`–`R5` alongside `findings.R1`. Follow that pattern: **write the
  decision rule down, commit it, then run.**
- **Report the variance.** If the transfer gap has `std == 0` over seeds, the result is
  INCONCLUSIVE, never a pass.
- **State whether CUDA or CPU ran.** A CPU result reported as a GPU result is a fabricated
  measurement.
- **A cell whose role is documented but whose I/O is unconstrained is a finding**, and the
  most likely one. "The documentation promises a constraint the code does not enforce" is a
  better result than a smooth correlation, because it is actionable.

## 7. Why these two repos are the right pair

`quilt-dba` is an implementation with nine named, documented, separately-testable cells and
an existing receipt chain. `exoj` is the formal structure — Field as a category, observers
as functors, deformations as natural transformations — that says what a "role" *is* in a way
that makes "computable from its I/O" a precise claim rather than an intuition.

The thesis needs both: the implementation to measure, and the formalism to say what the
measurement means. Neither alone can test it. `exoj` without `quilt-dba` is philosophy with
no numbers; `quilt-dba` without `exoj` is nine cells with no account of why their roles are
the kind of thing that transfers.
