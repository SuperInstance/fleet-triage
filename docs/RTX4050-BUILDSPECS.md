# pie-minimax A1 build spec — the one-evening closure (RTX 4050 worklist)

Facts below are from the verified `SuperInstance/pie-minimax` README
(org-survey deep-read, 2026-10-01). Items tagged INFERRED must be confirmed
against the repo on first clone — the spec is written so the evening is not
spent reverse-engineering.

## What exists (FOUND)
- Question: can a local rule reproduce a global optimum? Tic-tac-toe, where the
  optimal policy is **computed**, not learned.
- Model: linear 9→9, **81 parameters**.
- Result: top-1 accuracy **0.1807** vs multi-optimal floor **0.1431** on
  **180,361** exact game states.
- **14.7%** of states have multiple optimal moves (that's why the floor is
  0.1431, not 0).
- Prior receipts establish a defensible lower bound, but can't distinguish
  "need nonlinear" from "need completely different parameterization."
- The pre-registered partition test (SIMPLE vs COMPOSED) is named in the
  fleet's GPU-EXPERIMENTS queue as #1, "nearly finished," ranked highest value
  per GPU-hour.

## The pre-registered prediction (carry forward, do not soften)
- Train the smallest nonlinear student (MLP 9→64→9, ~1.3k params) on the same
  180,361 exact labels, CUDA, pinned seeds.
- Partition states: **COMPOSED** = boards where ≥2 distinct immediate wins are
  simultaneously present (fork states). Count them first.
- P1: global top-1 lands in **[0.25, 0.40]** — closure far above linear, far
  below 1.0.
- P2: accuracy on COMPOSED states is **<70% of global** (local voting cannot
  count two threats at once).
- P1∧P2 → the "local-voting ceiling" explanation carries; the next rung
  (pairwise features) is motivated by a receipt, not a hunch.
- P1 fails high (>0.6) → nonlinear closure is closer than believed; the
  composition thesis weakens. Report either way — the receipt is the point.

## Smallest build (one evening, in order)
1. Clone; confirm label artifact location/format (INFERRED: 180,361-row
   board→optimal-moves table), the linear baseline harness entry point, and
   how 0.1807 was computed. **Reproduce the linear number first** — if your
   harness doesn't print 0.1807 on the baseline, stop; the port has a defect
   (rule: reproduce before extending).
2. Compute the COMPOSED mask from labels (one pass; record the count).
3. Train MLP, 3 pinned seeds, until plateau. Record device string, seeds, and
   the split protocol (INFERRED: match the README's; verify).
4. Emit the receipt JSON below.
5. Verdict vs P1/P2 written down before the run executes.

## Receipt format
```json
{
  "experiment": "pie-minimax-closure-mlp",
  "pre_registered": "<date>",
  "predictions": {"P1": "global top-1 in [0.25,0.40]", "P2": "composed < 70% of global"},
  "device": "cuda:0 (RTX 4050, 6GB)",
  "seeds": [1, 2, 3],
  "results": {"linear_top1": 0.1807, "mlp_top1_global": null,
              "mlp_top1_composed": null, "composed_share": null},
  "verdict": {"P1": "TBD", "P2": "TBD"}
}
```

## Do NOT
- Train past the plateau to chase the floor — goalpost migration.
- Report composed accuracy without the share (a 12-state subset is not a
  partition result).
- Claim closure from one seed (seed everything; report all).
# Determinism Lab — pre-registration skeleton (worklist A4/D3)

The fleet's first study of **where GPU parallelism breaks bit-determinism, and
whether chained hashing detects it**. This is a TEMPLATE for the GPU agent to
seal — fill brackets, commit the prereg BEFORE any measured run.

## Background (verified facts)
- `SuperInstance/xruntime-conformance`: two runtimes that never shared source
  agree on **23/23 per-cell digests** — the cell convention cross-runtime
  contract exists and passes today (CPU-side).
- `SuperInstance/quilt-arcade` `shared/kit.mjs` receipt culture: in-cell canon
  sort, fnv1a-64 row hashes chained from GENESIS_PREV, `verifyChain()` —
  tamper-evidence by construction (used across all my sealed receipts).
- `SuperInstance/quilt-mojo-lab` wave-73: runtime #9 CuPy substrate with a
  sealed **bit-parity 0.0** receipt vs the C reference @16/512/1024² —
  GPU CAN be bit-deterministic on that path; the lab's job is to find where
  that breaks, not to assume it holds.

## Hypotheses (pre-registered)
- **H1 atomics**: cell-state updates using atomic adds produce digest
  divergence across runs of the SAME config on identical input. Prediction:
  FAILS to diverge below [N_min] concurrent updates; diverges above.
- **H2 fp-reorder**: reductions whose summation order varies (tile-size /
  block-dim sweep) produce fp32 digest divergence where fp64 does not.
  Prediction: divergence appears for fp32 when |values| dynamic range > [D],
  absent for fp64.
- **H3 canon-safety**: in-cell canon sort (kit.mjs culture) makes digests
  invariant to cell visitation order even under H1/H2 divergence in raw state.
  Prediction: canon digests match across all H1/H2 divergent configs.

## Controls (rule §0.5: vary by a DIFFERENT path)
- Same kernel, ordered reduction (single-thread reference) — the known-
  deterministic CPU/GPU-serial path. If the detector disagrees with THIS
  reference, the instrument is at fault, not the substrate (instrument-fault
  branch).
- fp64 shadow of every fp32 config (isolation of precision vs ordering).

## Procedure
1. Substrate: quilt-mojo-lab CuPy cell runtime; N=[8,16,64] cells; T=[1k,10k]
   ticks; sweep tile/block configs; [40] total configs.
2. Every run emits (a) raw state stream, (b) canon-sorted receipt chain per
   kit.mjs conventions.
3. Compare: raw-stream digests across configs (H1/H2), canon-chain digests
   across configs (H3), serial-reference chain vs all (control).

## Branch table
- **NULL**: no canon-chain divergence across all configs → publish as
  "GPU determinism holds to N cells on this substrate" + candidate canon rule
  (GPU-EXPERIMENTS §0 rule 9): "receipt chains over canon-sorted cell states
  are device-order-invariant."
- **FINDING**: specific config class diverges; report threshold (cell count,
   atomics pressure, dynamic range) + minimal repro + the divergence
  localized to [which stage] via chain-diff position.
- **INSTRUMENT-FAULT**: detector disagrees with serial reference on a known-
  deterministic path → retract detector design first; the lab result is
  about the KIT, not the GPU.

## Receipt (sealed per run)
```json
{
  "experiment": "determinism-lab-wave1",
  "prereg_commit": "<commit-hash-sealed-before-runs>",
  "substrate": {"repo": "quilt-mojo-lab", "runtime": "#9-cupy",
                "device": "cuda:0 (RTX 4050, 6GB)"},
  "configs_run": null, "h1": null, "h2": null, "h3": null,
  "control_match": null, "verdict": "TBD"
}
```
# Entry specs: quilt-dba stochastic worlds (D2) + MiniMoth→CUDA (B3)

Two entry points for the RTX-4050 agent, from verified org-survey facts
(2026-10-01). INFERRED items need first-clone confirmation.

## PART 1 — quilt-dba stochastic worlds (the Cog Thesis engine)

### What exists (FOUND)
- `SuperInstance/quilt-dba`: "developmental agent as a sheet." A 12-cell seed
  sheet; cells named, each hosting small primitives; a conservation law
  (γ+η ≤ C = log₂3 ≈ 1.585, scaled 1585); growth = cell addition.
- E-D1 results: **R1 GROWTH CONFIRMED**, **R2 JEV-GATE CONFIRMED** — the agent
  grows and its gate blocks growth when the world's surprise is too low to be
  worth it.
- E-D1 caveat (quote from fleet survey): the arms are **deterministic**, so
  cross-seed variance is **vacuous by construction**; the "next wave adds
  stochastic worlds" is named as the follow-on.
- Snowball-pulse verification (00:45 CST 10/2): `world.surprise` is a pure
  per-eval function of live state (stateless recompute); `state.stage` gain
  additive clamped [0,10]/eval; `memory.decayTick` ages on a driver-owned
  eval counter (checkpoint-consistent, rewind-invertible per E-D4). The
  contract avoids the predictive-paddle v3 pinning trap by construction;
  referral edges filed both directions (quilt-arcade 33ca652, quilt-dba
  referral-predictive-paddle-pinning @e82bc26, PR quilt-dba#1 open).

### ExoJ (FOUND, one paragraph)
`SuperInstance/exoj`: "external non-collapsing vectorized scratch-paper —
Field primary, quilt the projection." A scratch representation outside the
quilt's collapse-to-cell structure: an external field agents write to and
read from, projected onto quilt cells only at boundaries. The Cog Thesis
(GPU-EXPERIMENTS queue #11) asks whether transfer between quilt and ExoJ
carries a gap that scales with I/O determinacy — determinism of the
interface vs learnability of the transferred content.

### Smallest stochastic-world build (one evening + one overnight)
1. Wrap quilt-dba's world driver with a seeded noise source: per-eval Gaussian
   jitter on observed state (σ pinned per arm), plus per-episode world
   resampling from a seeded family (what varies per world: [initial cell
   masses / law constants / observation noise σ] — pick ONE axis first).
2. Arms: 3 σ levels × 1000 seeded worlds each; deterministic arm retained as
   control (variance must collapse to 0 there — rule: std==0 over identical
   seeds is expected, over DIFFERENT seeds is INCONCLUSIVE, never PASSED).
3. Receipts per world: growth event count, gate-blocked count, final mass,
   surprise trajectory digest. JEV-gate receipts: does the gate's block rate
   track noise-adjusted surprise?
4. Transfer-gap leg (week 2): train on quilt-dba worlds, eval zero-shot on
   ExoJ-projected versions of the same worlds; gap vs the I/O determinacy
   axis of the projection. That's the Cog Thesis measurement.

## PART 2 — MiniMoth→CUDA (B3)

### What exists (FOUND)
- `SuperInstance/MicroMoth-quilt`: MicroMoth quantum receipts as quilt PRs.
  exp008 sealed the n=4 GHZ balance-scale test as PR #13 (branch
  exp008-ghz4-scale-receipt) — the "PROOF statevector witness cell's named
  n=4+ target."
- Culture (verified across the fleet): sealed receipt JSONs carry prereg,
  seeds, device string, results, verdict; PRs reference receipts; FAIL-first
  pins (RED on pristine main before the experiment lands).

### First receipt (the bit-parity gate at n=4)
- Implement a ~300-line CuPy statevector simulator applying the SAME gate
  order and summation order as MicroMoth's reference (GPU-EXPERIMENTS rule 8:
  preserve reference loop/summation order in ports — fp addition is not
  associative; bit-parity means bitwise-identical amplitudes, which is only
  achievable if every op sequence matches; if bitwise fails, fall back to
  amplitude-distance ≤1e-12 AND identical measurement distributions over
  [10k] sampled shots — declare which parity standard the receipt seals).
- Receipt content: device string, seed, n=4 circuit (GHZ prep), amplitude
  vector hash vs MicroMoth reference hash, shot-distribution χ² or exact
  match, PASS/FAIL.
- Then scale: n=8, 12, 16, 20 (memory: 2^n × 16 B complex128 → 16 MB at n=20 —
  fits 6GB easily; throughput receipt = states/s vs CPU MicroMoth).

### Traps
- Gate application order must match the reference EXACTLY (matmul chaining
  order changes low bits).
- cuBLAS/cuSPARSE defaults may use TF32 on Ampere+ — pin fp64 (the 4050 is
  slow at fp64 but correct; this is a parity study, not a speed study until
  parity holds).
- Seeded shot sampling: match the RNG algorithm, or compare distributions,
  not samples.
