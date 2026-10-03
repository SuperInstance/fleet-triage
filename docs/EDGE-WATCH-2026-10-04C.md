# EDGE-WATCH 2026-10-04C (post-17:15Z scan, 01:56 CST pulse)

Cutoff: prior pulse (04B) scanned through 17:12Z. This scan covers 17:13Z → 17:56Z.

## ZERO new repos
workspace-rescue (2026-10-03T08:24Z) still the newest repo. Zero collisions with our
ledger/verification surfaces; nearest rival remains receiptd (hedged, doubt-ledger#18).

## MERGE / MAIN STATE — one move, zero of ours
- fleet-triage MAIN MOVED: b04b1e6 → 47d3239 (sibling push, 17:48Z, direct to main).
- ZERO merges of our PRs. Open count UNCHANGED at 17: fleet-triage #5-#16 (12),
  doubt-ledger #16/#18/#19/#20 (4), quilt-in-git #12 (1). ALL Casey-gated.
- Our 04B branch (PR #16) stacks cleanly on new main by construction (branched 04C
  off 47d3239; #16 was off b04b1e6 — GitHub will confirm mergeability, content is
  one disjoint file).

## FRESH ORG SIGNALS (receipts-verified read-side before writing)

### 1. spec_sha-bound pre-registration — TWO repos in the same hour
- unspoken-resonance 3ad67d4 (17:45Z): spec/invariants.json committed BEFORE
  implementation. 48dcd93 (17:50Z): implements exactly those invariants and cites
  the spec_sha (7d77ff51…b07) in the commit message; --check mode ships.
- madlibs-jev ee7b73a (17:38Z): same prereg pattern. 9baec4f (17:44Z): spec_sha IN
  THE COMPILE LOOP — breach refuses to canonize (INDETERMINATE receipt), missing
  spec refuses to compile; learnedBands law: an INDETERMINATE receipt's bands never
  feed learned bands (the seal's missing half, flagged at 68-b1).
- This is receipts-culture convergence #7/#8 with a mechanism we have NOT built:
  hash-binding the expectation document to the check that consumes it. Our FAIL-first
  pins seal RED→GREEN in one suite; theirs makes the spec a runtime dependency of
  canonization. ADOPTION CANDIDATE (cite-only, consume-don't-rival): a spec_sha
  header line in our pin receipts would give our canaries the same
  expectation-binding without changing pin grammar.

### 2. gpu-lab: dead-metric self-declaration, second instance
- be08bb3 (17:27Z) gate-loop-v3: "edge-IoU instrument SATURATED (~0.95 all arms) —
  dead metric at this operating point, differential metric needed." Same shape as
  the VSB-1 census catching its own nested-vendor strip fix: the instrument that
  cannot discriminate is NAMED as such in the receipt. Canary-that-cannot-fail
  doctrine, org-side, applied to metrics not just gates.
- e001fb3 (17:44Z): tools/holdout_gate.py — held-out prediction gate with G1
  coverage + G2 non-vacuous checks (verified present in tree). Held-out +
  non-vacuity = the exact antidote our unfalsifiable-gates doc (fleet-triage#12)
  prescribes; now a grabbable generic tool org-side. WATCH-and-lift.

### 3. NEURO-QUILT on main (47d3239) — two doctrines restated by a brain
Sibling's assembloid digest lands three transfers, all vocabulary-level convergent
with our surfaces, zero collision:
- ROTTED CITE named as a failure mode: "the claim was true, the work was real, and
  the receipt no longer resolves" = our stale-claim correction practice (we
  receipt two stale fixes per pulse) made a named org doctrine by the wardroom's
  bobbin. Receipts must resolve, not just exist.
- FlyWire ships a STATED NOISE FLOOR for its own ground truth ("30% edge-weight
  differences may be entirely technical noise… should not be overinterpreted").
  "Declare what it cannot be trusted for" = our honest-limits sections, now cited
  as the standard every artifact should meet.
- Sufficiency/necessity BY DELETION (build without a structure to test necessity) =
  canary doctrine's RED-demonstration generalized: you prove the gate matters by
  removing it and watching the signature die.

### 4. Control-ladder hardening continues
- purpose-loops 954ab7a (17:24Z): flat control rung now EXECUTABLE in CI ("the flat
  control rung is executable, the rite documented") — the wave-68 fleet rule went
  from receipted rung to enforced gate within ~10h.
- quilt-whitepapers c68ede6 (17:08Z): standing rule — every paper ships a flat
  control rung (receipted) and a playable twin where feasible.
- AI-Writings c1f941e (16:53Z): System-2-closer harvest wave (creative) — zero
  collision.

## STALE-CHECK
- pong-quilt 17:13Z push: tag-touch class (verified in 04B pulse, unchanged tip #100).
- Zero merges of ours (see above). Disk 57%.

## Posture
No hedge PRs needed (zero collisions). Optional small follow-on: spec_sha citation
line in a future doubt-ledger export note (post-merge #18) referencing the
unspoken-resonance/madlibs-jev mechanism as prior art — adoption-not-rivalry.
