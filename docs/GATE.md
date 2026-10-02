# GATE.md — one gate, four discriminators

**Status: STUB. Rules 1 and 2 are live with green negative controls. Rules 3 and 4
are declared but return `unknown`.** Written at T+35min against a 10-minute stub
target; the overrun is mine and the reason is below.

Run it:

```bash
cd /workspace/projects/fleetlint
python3 -m fleetgate controls                    # the negative controls
python3 -m fleetgate records-a-failure   <repo>  # one rule
python3 -m fleetgate run                  <repo>  # all four, gated
python3 -m fleetgate explain             [rule]  # why it exists
```

Standard library only. No install, no model call, no network. If a rule costs a
model call to run it will not be run, and an instrument that is not run is the
subject of this fleet's entire problem.

---

## The finding all four rules encode

> The load-bearing element is always the boring one — the enumerator, the
> provenance, the record of the red, the metric with a denominator that exists —
> and the expensive impressive thing is decoration.

Each rule names one boring element and refuses to let decoration stand in for it.

**Three verdicts, not two.** `fail` / `ok` / `unknown`. `unknown` is not a softer
`ok`: a gate that quietly passes what it did not measure is the
`echo "No CI configured"` placeholder with better branding.

---

## Rule 1 — `records-a-failure`

**Discriminator.** A check whose only committed evidence is a green result
cannot be told apart from a check that does not run. The load-bearing element
is not the passing; it is a **committed record of the check having gone red**.

**Why it is not a filename match.** The signal is *content*: a committed
artifact containing a **verdict line**. A rule keyed on the literal word
`failfirst` would pass on these seven repos and prove nothing, because these
seven are the only seven in the corpus containing that word.

### The control is constructed, and it is the harder direction

| control | what it is | want | got |
|---|---|---|---|
| `r1_green_only` | suite + CI + a **green** receipt + a README that talks about failing constantly | `fail` | `fail` |
| `r1_with_red` | the *same repo, same prose*, plus one observed red in a file named `2026-09-30-run.txt` | `ok` | `ok` |
| `r1_no_apparatus` | prose, nothing that runs | `unknown` | `unknown` |

The red record in `r1_with_red` is in a file whose name has nothing to do with
the answer. A rule matching on names passes `r1_with_red` for the wrong reason
and is caught by the corpus, not by the control — so the control is where that
class of rule is supposed to die.

### Two defects the corpus found in my own rule, before it found anything in yours

**1. `0 checks fail` in a green summary.** The first pattern matched the word
`fail` anywhere, so a receipt reading `3/3 checks pass (3 checks pass, 0 checks
fail)` counted as a record of the red. It accepted every honest green receipt in
the fleet. Fixed by requiring a non-zero count and stripping green zero-count
clauses before matching.

**2. Prose about failure is not a record of failure.** This is the serious one.
Over the real corpus the word-list version returned **`ok` for `moth-ledger` and
`moth-corpus`** on the strength of these sentences:

```
A hunt that failed is data, never noise.
ok, errors = ledger.verify_chain()
fails loud, not silently stale
| `REFUSAL/v1` | hunt failure: budget exhausted, tool refused, cap hit |
```

A rule that cannot tell a description of a red from a red is not a
record-of-failure check; it is a grep, and it had quietly become the defect it
was written to catch. The fix is a **line-anchored verdict grammar** — a
non-pass verdict at the head or tail of a line, a non-zero fail tally, a
`k/n pass` ratio with `k < n`, or a structured verdict field. Every alternative
is anchored so that a sentence containing the word cannot match.

Both those prose lines are now **in the control**. The control got harder, not
softer.

### Result on the seven repos named in the finding

| repo | verdict | committed red? |
|---|---|---|
| `moth-ledger` | **fail** | none |
| `moth-corpus` | **fail** | none |
| `moth-cells` | **fail** | none |
| `moth-honest` | **fail** | none |
| `quilt-in-git` | ok | 8 verdict artifacts (`pins/failfirst*.log`) |
| `frozen-clock-lab` | ok | 1 (`FAIL-first: lab/ absent — No module named 'lab'`) |
| `doubt-ledger` | ok | 2 (`pins/failfirst*.log`, `pins/guardian-failfirst.log`) |

**7/7. Finding 1 reproduces, and the rule identified `moth-*` without being
fitted to it.** Controls 8/8.

---

## Rule 2 — `enumerates-from-own-state`

**The seam in one line.** If the enumeration takes anything the app did not
derive from its own state, the app is composed, and it will need a chooser to
exist.

**Why static.** A behavioural test needs a chooser to exist in order to observe
a seam, so a composed app is invisible to any test that runs it happily. Static
provenance of the iterable is the only thing available before the chooser is
written. Python goes through the real `ast`; other languages get a conservative
line scanner and report `unknown` rather than guessing.

Provenance resolution is one level deep: imports from outside the package are
foreign, literals and `self` are own, calls to a local function are resolved
through that function's return expressions, and a call whose dotted name or
arguments name the network, the filesystem, the environment or a model is
foreign.

### Controls

| control | want | got |
|---|---|---|
| `r2_enumerated_literal` — moves are a tuple literal | `ok` | `ok` |
| `r2_enumerated_own_state` — moves derived from `self` | `ok` | `ok` |
| `r2_composed_imported` — `from some_other_package.prior import MOVE_TABLE` | `fail` | `fail` |
| `r2_composed_fetched` — `for x in suggestions(state)` over `urlopen(...).read()` | `fail` | `fail` |
| `r2_composed_model` — `for c in client.chat.completions.create(...)` | `fail` | `fail` |

**8/8 controls.** The `_dotted` helper had to learn to see through a call on a
call (`urlopen(x).read()`); without it the fetch control fell through to
`unknown`, and an `unknown`-heavy rule gets switched off, which is the same
outcome as no rule.

---

## Rules 3 and 4 — declared, not yet live

Both currently return `unknown` for every path. They are wired into the CLI and
into `run` so the gate's shape is fixed, but a rule that returns `unknown` is not
a rule, and the gate reports that rather than pretending otherwise.

- **Rule 3 `metric-is-defined`** — refuse to report a number unless the metric is
  defined on every sampled position. Acceptance test: it must catch all three of
  the failed experiment metrics.
- **Rule 4 `provenance-before-embedding`** — the discipline from `res-CLUSTER` as
  something checkable: when a learned or embedding key makes a clustering,
  dedup or selection decision and an exact provenance key is available in the
  same data and unused, the embedder is decoration.

---

## What this gate is not yet

- The false-negative count. A lint rule's FN count is the more useful number and
  nobody ever reports it. It comes after rules 3 and 4 exist, over the fleet.
- The `got = expected` defeatability probe on `moth-honest`. The static half of
  rule 1 identifies the family; the *runtime* half — taint the comparison, re-run
  the canary, see whether it notices — is a separate executable probe and is not
  written yet. Until it is, rule 1 supports "these four commit only green" and
  does **not** yet support "theirs is the canary that survives `got = expected`".
  Those are two claims and only the first is currently backed.
