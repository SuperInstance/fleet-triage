# API_LIMITS_R1 — high-level API experiments on the live oracles

Mandate: Casey 10:55 CST 2026-09-25 ("lanes for new experimentation with the
apis ... documenting successes and failures to shape limits and potentials").
Branch `api-lab-r1` on SuperInstance/quilt-tools. Each experiment:
hypothesis → protocol → receipts → finding. **Failures are findings.**

Wire baseline (verified live earlier today, S1/S2/S3):
`POST https://api.typesafe.ai/v1/systemone`, `Bearer $TYPESAFEAI_KEY`,
`{model:'jev-latest', state:<json-string>, questions:{name:{type,question,criteria,scale}}}`.
Score questions: `criteria` + `scale` label arrays, **10 levels max** (11+ → 400),
answer = normalized score with per-index `probabilities` (modal index → label).

---

## Experiment 1 — "ordinal, not interval", quantified (DONE)

Script: `experiments/e1-ordinal-not-interval.mjs` (7 pins).
Receipt: `experiments/out/e1-ordinal-not-interval.receipt.json` (witness chain,
18 rows).

**Hypotheses (pre-registered):**
- H1: mean modal score is strictly monotone across 6 claims on a known
  evidential-support continuum.
- H2: same-prompt rescoring (3×) mostly agrees at adjacent levels (ordinal
  noise, not signal).
- H3: adjacent continuum steps land unevenly on the scale (non-interval).

**Protocol:** 6 claims, decreasing support (crystals-cure → coffee-prevents-
Alzheimer's → fasting-extends-life → exercise-helps-cardiovascular → water-
boils-100°C → sky-is-blue), each scored on the 10..100 scale, 3 independent
rescoring rounds = 18 live calls, all witness-booked.

**Results (2 live runs):**
| claim | run 1 (3 rounds) | run 2 (3 rounds) |
|---|---|---|
| crystals cure chronic disease | 10,10,10 | 10,10,10 |
| coffee prevents Alzheimer's | 10,10,10 | 10,10,10 |
| fasting extends lifespan | **30,50,30** | 50,50,50 |
| exercise → cardiovascular | 100,100,100 | 100,100,100 |
| water boils at 100°C @sea level | 100,100,100 | 100,100,100 |
| daytime sky is blue | 100,100,100 | 100,100,100 |

**Findings:**
1. **H1 STRICT version FALSIFIED — floor/ceiling collapse.** A 6-point
   continuum compresses to 3 distinct values {10, 50, 100}: p1≡p2 at the floor,
   p4≡p5≡p6 at the ceiling. The scale has effectively ~3 usable rungs for
   real-world claims. Revised H1' (weak ordering, zero inversions) holds in
   both runs — the scale never inverts order, it saturates instead.
2. **H2 SUPPORTED, refined:** run 1 = 16/18 pairs within 1 level; run 2 = 18/18.
   But the refinement is the finding: **rescore noise exists ONLY at contested
   positions** (fasting: 30/50/30 in run 1). At floor/ceiling the oracle is
   perfectly repeatable. Noise is a boundary phenomenon, not general jitter.
3. **H3 SUPPORTED strongly:** adjacent continuum gaps = 0,4,5,0,0 levels
   (run 2). The middle gap (pseudoscience→contested = 4 levels,
   contested→established = 5 levels) vs zero gaps elsewhere = the scale
   measures "settled vs contested", not distance. **Ordinal, not interval —
   now with numbers.**
4. Practical consequence: with a 10-level fence that collapses to 3 usable
   rungs, downstream consumers should treat score deltas ≤1 level as ties and
   should expect no resolution at all between any two settled claims (both
   pin to 100) or any two refuted claims (both pin to 10). Comparative
   paired questions (S2/E4 style) are the only way to extract fine ordering —
   consistent with the E4 paired-gate result.

---

## Experiment 2 — receipts change credit (DONE)

Script: `experiments/e2-receipts-change-credit.mjs` (7 pins).
Receipt: `experiments/out/e2-receipts-change-credit.receipt.json` (witness
chain, 8 rows).

**Hypotheses (pre-registered):**
- H1 (S2 replication): bare-prompted, the oracle does NOT credit the shape
  detector on st02 (slow drift) even though replayed ground truth has shape
  firing at sample 10 and the 0.80 threshold at sample 18.
- H2 (thesis): adding the real witnessed firing events (hash-chained receipt
  rows built by the S2 replay math — never fabricated ticks) shifts credit
  toward the replayed ground truth.
- H3 (control): st08 cliff — measured, not presumed (replayed as a 1-tick
  race, shape@10 vs threshold@11).
- H4 (safety control): st01 healthy — no detector fires; receipts must not
  induce a false alarm.

**Protocol:** 4 S2 scenarios (st02 slow drift, st04 stuck, st08 cliff, st01
healthy) × 2 conditions (bare / receipts-inline), condition order
counterbalanced across scenarios (E4 position-bias lesson) = 8 live calls,
all witness-booked. Verdict = one choice question, options
shape / threshold / both_together / neither.

**Results (8/8 live, 7/7 pins, 2026-09-25 11:1x CST):**

| scenario | replayed ground truth | bare | receipts |
|---|---|---|---|
| st02 slow drift | shape@10 vs threshold@18 → shape | threshold ✗ | shape ✓ |
| st04 stuck (frozen exporter) | shape@10, threshold never → shape | neither ✗ | shape ✓ |
| st08 cliff | shape@10 vs threshold@11 → shape | threshold ✗ | shape ✓ |
| st01 healthy | neither fires → neither | neither ✓ | neither ✓ |

Ground-truth agreement: **bare 1/4, receipts 4/4.** Shift toward truth on
shape-first scenarios: 3/3, shift away: 0/3.

**Findings:**
1. **H1 REPLICATED cleanly:** bare, the oracle credits the 0.80 threshold on
   st02 exactly as S2 found (asserting "shape reads earlier" in prose does
   nothing).
2. **H2 SUPPORTED strongly — the thesis has API-layer numbers now:** the
   SAME question, with only the witnessed firing rows inline, moves credit
   to the true detector on all three problem scenarios (3/3 toward, 0/3
   away). Receipts are not decoration: they change what the oracle credits.
3. **H4 SAFETY side holds:** on the healthy stream the receipt chain is a
   genesis-only "no detector fired" row and the oracle still answers
   'neither' — witnessing did not manufacture an alarm.
4. **Boundary segment:** the effect is presentation-of-EVIDENCE, not
   persuasion wording — both conditions used identical question text;
   the only delta was the witnessed rows. But note what the receipts
   actually are: machine-verifiable hashes over replayed events. A
   fabricated receipt chain would be indistinguishable to the oracle —
   receipts change credit whether or not they are true. The consumer must
   verify the chain (verifyChain is 20 lines); trusting receipts by sight
   is the same wall as the ocean cache's 0.9520 injection hit: the channel
   is verified, the world is not.

---

## Experiment 3 — two-envelope entanglement (PENDING)

Two dry budget envelopes ENTANGLED to one coin-toss appeal; hypothesis: the
sheet enforces joint collapse; hard debt refuses. (S3 machinery reusable.)
