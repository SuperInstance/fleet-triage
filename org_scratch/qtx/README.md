# quilt-tools

Eleven working tools grown on the [Quilt](https://github.com/SuperInstance/quilt)
reactive spreadsheet engine, one shared harness, three GAN-bred bloodlines of
logic, and a lab where the receipts get to mutate the tools that print them.

**For the impatient:** everything here runs offline, grades its own homework,
and says so out loud. No engine build, no cloud, one dependency.

```bash
git clone https://github.com/SuperInstance/quilt-tools && cd quilt-tools
npm install                  # the only dep is yaml; the engine dist is vendored
node tools/fleet-pager.mjs   # expect: 7/7 checks green
npm run check                # syntax-check every tool and experiment
```

---

## The eleven tools

Each `tools/*.mjs` is self-contained — engine wiring, scenario, and a check
harness at the bottom. **94 self-checks across the set; green is the only
accepted color.** Each tool also has a claim card in [`cards/`](cards/) saying
what it is, who it's for, and where it came from.

| tool | checks | what it actually does |
|---|---|---|
| [`fleet-pager`](tools/fleet-pager.mjs) | 7/7 | SRE paging with hysteresis band discipline — no more page-flapping at 3 a.m. |
| [`ledger-seal`](tools/ledger-seal.mjs) | 6/6 | tamper-evident append-only witness ledger, fnv1a-chained |
| [`ocean-recall`](tools/ocean-recall.mjs) | 7/7 | vector-note recall with *honest* forget — absence says "forgot," never "found" |
| [`triagedesk`](tools/triagedesk.mjs) | 8/8 | support triage routing |
| [`budget-tide`](tools/budget-tide.mjs) | 8/8 | cash-flow envelopes with dry-envelope fences |
| [`home-ecos`](tools/home-ecos.mjs) | 6/6 | home ecosystem automation |
| [`driftwatch`](tools/driftwatch.mjs) | 7/7 | config drift detection |
| [`approvals`](tools/approvals.mjs) | 9/9 | spend approvals with tier-based routing |
| [`habit-atlas`](tools/habit-atlas.mjs) | 8/8 | habit streaks with momentum physics |
| [`pipeline-guard`](tools/pipeline-guard.mjs) | 9/9 | pipeline row validation + dead-letter replay |
| [`convergence-gauge`](tools/convergence-gauge.mjs) | 19/19 | training-curve convergence certification — flat-tail latch, CUSUM change-point scan, hysteresis on the stop button |

These are not demos wearing tool costumes. They are the smallest full
behaviors that still count: each one makes decisions, keeps receipts, and can
tell you why it decided what it decided.

```bash
for f in tools/*.mjs; do node $f >/dev/null 2>&1 \
  && echo "${f##*/}: green" || echo "${f##*/}: FAIL"; done
```

## The harness they stand on

[`src/toolkit.mjs`](src/toolkit.mjs) — `sheet()`, `check()`, `done()`, SysOne
heuristics, a deterministic embedder, witness-chain helpers. No laptop paths;
the engine dist resolves via [`vendor/quilt-core/`](vendor/quilt-core/) (the
exact upstream provenance is recorded in its own README there — vendored so
the tools run hermetically and the lab can mutate a copy without touching
upstream). Override with `QUILT_DIST=/path/to/dist`.

The fleet's honesty idiom for any claim is four verdicts:
**CONFIRMED** (re-executed and it holds) · **REFUTED** (re-executed and it fails) ·
**SIMULATED** (asserted, never executed — a model, not a measurement) ·
**MEASURED** (executed, nothing claimed). These tools already book their refusals as
receipts; coev's auditor names the other two dodges so no claim goes unlabeled.

## The lab — where tools meet live models

[`experiments/`](experiments/) is the springboard: studies that run the
heuristic tools against the fleet's typed live models and book whatever
happens, including the refusals. The house rule: **witness-booked, and REFUSED
rows are kept, never retried away.** Write-ups and receipts:

- [`experiments/README.md`](experiments/README.md) — the live-oracle studies
  (S1: triagedesk vs live jev — 12/12 live calls, honest score-gap reported).
- [`experiments/API_LIMITS_R1.md`](experiments/API_LIMITS_R1.md) — what the
  live models tolerate, measured not guessed.
- `e1-ordinal-not-interval.mjs`, `e2-receipts-change-credit.mjs` — instrument
  studies: how the *receipts themselves* bend the results (they do).
- `s2-driftwatch-jev.mjs`, `s3-quantum-tided-budget.mjs` — more live pairings.
- The fleet's newest instrument: [coev](https://github.com/SuperInstance/coev) —
  adversarial coevolution with a champion-integrity auditor. The gan-elites were
  bred by *divergence* (as different as possible, behaviorally exact); coev breeds
  by *rivalry* against a live champion and then audits the champion for hollowness.
  Sibling instruments, one honesty doctrine.

### The referral graph — the mesh answers as a distribution

Casey's 2026-09-25 mandate: *"not one thing but a distribution of intelligent
referrals."* [`src/referral_graph.mjs`](src/referral_graph.mjs) is the
substrate: ideas are nodes, referrals are hash-chained LINK rows (fnv1a-64,
the fleet receipt idiom), every edge carries the receipt that proves it —
or the falsification condition that would kill it. The answer to a question
is a ranked VIEW over modules, not a single confident pointer.

- [`experiments/REFERRAL_GRAPH.md`](experiments/REFERRAL_GRAPH.md) — the
  constitution: weight law (PENDING speculation weighs 0.05; VERIFIED merged
  provenance weighs 1.0), booking rules, kill switches.
- `referral_graph.seed.mjs` / `referral_graph.pins.mjs` — the real v1 graph
  and its pin suite (`--live` audits every provenance PR against GitHub;
  offline pins are labeled SKIPPED, never passed silently).

## The bloodlines — logic the loom bred

[`gan-elites/`](gan-elites/) holds crowned implementations bred by the
quilt-loom Divergence Foundry: a GAN that breeds logic **as different as
possible from every prior bloodline while staying behaviorally exact.** Each
directory carries a vendored oracle, a frozen 200-probe corpus, a provenance
banner (family, hash, novelty, voice), and a self-contained verifier:

```bash
node gan-elites/pager-band/verify.mjs      # 860/860 — divergent in form, exact in behavior
node gan-elites/witness-fnv/verify.mjs     # 832/832
node gan-elites/cosine-sparse/verify.mjs   # 828/828
```

Same animal, three skeletons. If you doubt equivalence, run the verifier —
that is what it's for.

## The site

[`site/index.html`](site/index.html) — a tool-picker UI over the ten. Open
it, click around, break it, file the receipt.

## Reading beyond this repo

- The engine: [SuperInstance/quilt](https://github.com/SuperInstance/quilt) —
  the reactive spreadsheet substrate everything here stands on.
- The judges: [jeviter](https://github.com/SuperInstance/jeviter) (typed
  model receipts) and [quilt-doctor](https://github.com/SuperInstance/quilt-doctor)
  (four diagnostic lenses over any quilt-shaped project — this repo is a
  patient).
- The canon: [AI-Writings](https://github.com/SuperInstance/AI-Writings) —
  the essays, including the ones about why tools must grade themselves.
- The face: [SuperInstance.github.io](https://superinstance.github.io/) —
  where the demos live.

## Lab mandate (Phase 2+)

These prototypes plus the vendored engine are the substrate for
JEV/MothQuantum experiments — instance-graph mutations as sheet diffs, midden
harvesting as cell provenance, ZPP certification runs as witness chains. Work
happens on branches; **`main` stays green.**

---

*A tool that can't check itself is a rumor with a README. Nothing here is a rumor.*
