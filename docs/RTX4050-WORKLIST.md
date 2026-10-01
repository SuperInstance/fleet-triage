# RTX 4050 WORKLIST — experimental gains only your GPU can buy

> For the fleet agent with an RTX 4050 (6 GB VRAM, CUDA). Sized to that card on
> purpose: everything below fits in a laptop GPU or honestly says it doesn't.
> Culture: receipts over claims, pre-registration before measured runs, seeds
> pinned, device string recorded with every number. The eight measurement rules
> in `docs/GPU-EXPERIMENTS.md` §0 are **learned by getting it wrong** — adopt
> them before your first experiment, especially: std==0 → INCONCLUSIVE never
> PASSED; a CPU fallback reported as GPU is fabrication; controls must vary the
> audited thing by a different path.

## A. NEEDS a real GPU to refine — blocked or part-done without you

| # | item | repo | what exists | what only you unlock | smallest first build |
|---|---|---|---|---|---|
| A1 | **pie-minimax closure** (queue #1, nearly finished) | `pie-minimax` | 9→9 linear, 81 params, top-1 0.1807 vs floor 0.1431 on 180,361 exact states; 14.7% of states have multiple optimal moves | the pre-registered **SIMPLE-vs-COMPOSED partition test**: if nonlinear closes a little (0.25–0.40) and collapses on ≥2-simultaneous-win states, the "local voting can't count threats" prediction carries — the cleanest result in the whole queue | tiny MLP (9→64→9), exact labels, CUDA, one evening |
| A2 | **4×4 composition + capacity** (queue #3/#4) | `ga4444` | "the rung with complete ground truth", blocked on data | GPU data generation + training at 4×4; the 3×3 finding either scales (composition ceiling) or breaks (surprising, publishable either way) | write the parallel data-gen harness first; train second evening |
| A3 | **connect4 set-valued labels** (queue #7) | `connect4` | blocked on data | GPU rollouts producing set-valued move labels on the 7-wide space | data-gen PoC with seeded rollouts |
| A4 | **xruntime-conformance at scale + the DETERMINISM LAB** | `xruntime-conformance` | 23/23 per-cell digests across two runtimes that never shared source | (a) scale the census; (b) **pre-register the fleet's first where-does-GPU-parallelism-break-bit-determinism study** — atomics, fp-reorder, atomics in reductions — with chained fnv1a-64 receipts (kit exists in `quilt-arcade` `shared/kit.mjs`: in-cell canon sort, GENESIS-chained rows, `verifyChain`) as the detector. Null result = canon rule candidate | rerun the 23 digests under CUDA tile orders; diff receipts |
| A5 | **quilt-mojo-lab consumer-GPU parity node** | `quilt-mojo-lab` | wave-73 runtime #9 CuPy: bit-parity 0.0 @16/512/1024², 3.10G cells/s (datacenter silicon) | the parity receipt on consumer silicon is NEW information; your box becomes the fleet's standing consumer-GPU conformance node | run their parity script; receipt the 4050 numbers next to theirs |
| A6 | **murmuration critical-mass ensembles** (queue #10, running) | `murmuration` | swarm consensus by local deference; running | seeded ensemble sweeps (1000 worlds) are embarrassingly parallel; critical-mass curves with real variance | batched world runner |

## B. TRAINABLE on 6 GB — proof-of-concepts with exact receipts

| # | item | repo | why the receipts are exact | smallest build |
|---|---|---|---|---|
| B1 | **Policy distillation of the pong derived law** | `pong-quilt` + `quilt-arcade` (`games/pong`) | the derived law is an EXACT teacher — receipts are h2h win-rate + per-tick action agreement vs the law, not loss curves | tiny MLP ← law traces, 3 seeds; report agreement to 100% or the gap |
| B2 | **C1 population-eval batching** | `pong-quilt` | the R68 finding (seed variance dominates at 40 gens at EVERY population; long arm 96×160 rises) needs the blocked 320+-gen × many-seed horizon arms | batch pop rollouts on CUDA; wall-clock receipt vs CPU with the speedup>1.0 gate; then run ONE 320-gen arm overnight |
| B3 | **MiniMoth→CUDA statevector** | `MicroMoth-quilt` | bit-exact vs MicroMoth ≤ n=10 is a CHECK, not a hope; then receipts per n as you scale — the "PROOF statevector witness cell" was named for n=4+; take it to n=16–20 (fits: 2²⁰ amplitudes × 16 B = 16 MB) | ~300-line CuPy statevector; first receipt = bit-parity at n=4 vs sealed exp008 |
| B4 | **voxelglyph observation encoder** | `voxelglyph` | a rank-one luma ceiling is already PROVEN — train the sub-ceiling encoder and verify it saturates at the proof. Training against a theorem is a luxury most labs never get | small conv encoder; receipt = measured rank vs proven ceiling |
| B5 | **ladder rung 9** (queue #9, not started) | `ladder` | self-play vs table-lookup ground truth; tiny net, exact labels | one evening |
| B6 | **selectlib extension** (queue #5, done-extend) | `selectlib` | "controls run before any number is presented" — your extensions inherit the control harness | CPU-fine on your box; the GPU sits idle honestly |

## C. PLAY-TEST — your card runs quantized 3–7 B models; put one to work

| # | item | what exists | smallest build |
|---|---|---|---|
| C1 | **The Local Playtester** | `quilt-arcade` engine API + 6 games + 67-check gate; `quilt-playtest` patch culture (12 engine patches, z-machine paths) | Qwen2.5-3B/7B-Q4 on the 4050 plays all 6 games via the engine API, temperature-seeded; session receipts = moves, outcomes, crashes, rule-violation probes. Pre-reg example (falsifiable both ways): the derived law beats the 7B at pong in ≥90% h2h matches |
| C2 | **C1 champion tournaments** | `pong-quilt` Round 69 sChamp lane on main | trained champions vs the derived law, h2h receipts — makes "fitness" honest against the exact policy |
| C3 | **chiaroscuro dial sweeps at scale** | video→ascii porter on main, 5 engines, 56 dials | batch a video corpus through the dial space on GPU; receipted montage grids = aesthetic QA that used to cost a day per video |
| C4 | **Adversarial PR playtesting** | fleet PRs pile up Casey-gated (`chiaroscuro` #1–#13 today) | cold-start playtest every new fleet PR with the local model; friction logs as receipts (pattern proven by the quilt-studio adversarial scouts) |

## D. THINK BIG — the three that change what the fleet can do

- **D1 · GPU-native quilt cell runtime.** Cells as CUDA kernels: 100–1000× tick
  rate unlocks long-horizon censuses (C1 at 10k gens), population-scale sweeps,
  and a successor class to the closed `quilt-arcade` predictive-paddle lane: a
  **wall-time-aged sparse-sensor estimator** — the contract that lane's third
  strike proved is the right one (exact cues + per-wall-tick certainty decay;
  the receipts are already written).
- **D2 · The Cog Thesis (queue #11, highest novelty).** Transfer gap vs I/O
  determinacy across `quilt-dba` + `exoj`. `quilt-dba`'s own E-D1 caveat names
  your job: "arms are deterministic, so cross-seed variance is vacuous by
  construction; next wave adds stochastic worlds." You are the stochastic-world
  engine: 1000 seeded worlds, JEV-gated growth receipts, transfer-gap measured.
- **D3 · The Determinism Canon.** A4's lab, written up as a fleet canon entry:
  *where parallelism breaks receipts, and how chained hashing detects it* —
  candidate for GPU-EXPERIMENTS §0 rule 9, learned the same way rules 1–8 were:
  by running the experiment, not by argument.

## Suggested first two weeks

1. **C1 + B1 (warm-up):** both small, receipt-heavy, immediately useful — a
   local playtester and a distilled policy with exact agreement receipts.
2. **A1 (first flagship):** pie-minimax closure — the queue's own ranking says
   it's the highest value per GPU-hour and it's nearly finished.
3. Then pick by appetite: B3 (quantum receipts) for spectacle with rigor, A4/D3
   (determinism lab) for canon impact, D2 for novelty.
