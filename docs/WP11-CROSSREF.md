# WP-11 cross-ref — beyond-the-horizon bridges land on surfaces we already keep

Cite-only adoption note. Source: `SuperInstance/quilt-whitepapers`
`papers/WP-11-beyond-the-horizon.md` (committed 2026-10-03T08:14:35Z,
after this repo's last edge-watch scan cutoff). No code, no pins, no
rivalry — the whitepaper proposes bridges; this note records which fleet
surfaces already hold the load-bearing ends of each.

## Bridge 4 — cross-shape bone library ↔ doubt-ledger covered_by surface

WP-11's Bridge 4 ("a loop beginning a *new* shape can ask 'which existing
bones fit this fixture?'") is exactly a **coverage query** over a shared
bone economy. That query layer already exists as a design surface:
`SuperInstance/doubt-ledger` PR #20 (`docs/BONE-REGISTRY-REUSE-NOTE.md`,
branch `bone-registry-reuse-note`, commit 4cdf5dc) maps purpose-loops'
`costSaved`/reuse metric onto doubt-ledger's `covered_by` /
coverage-query surface (P5), with the boundary stated (no runtime, no
dependency). When Bridge 4 gets built, the bone library should answer
"which bones cover this shape" **through** that coverage-query grammar,
not invent a second one — one query language for covered-vs-uncovered,
whether the bones are task-shape lexicons or checked-claims.

## Bridge 5 — playable papers ("a demo is a claim you can perturb") ↔ FAIL-first canary pins

WP-11's method bridge — every white paper ships with its playable twin,
receipts bundled — is the paper-side statement of the fleet's pin-side
law: a claim is only a claim if its refusal is demonstrated. Our canary
doctrine (fleet-kit L9/L10; frozen-clock-lab#2 P6; quilt-in-git#6 P10)
requires every pin to show its RED before its GREEN. A playable paper is
the same object one layer up: the reader perturbs the demo the way the
pin-runner perturbs the fixture. Recommendation is vocabulary-level only:
when WP papers ship playable twins, twin receipts should record the
perturbation classes exercised (tamper/absent/mutant), matching the pin
receipts they cite.

## Bridges 1–2 — receipt-chain memory is already the house law

WP-11's quantized/warm-started memory bridges assume "the memory is
itself a receipt chain." That assumption needs no build: genesis-anchored
order-sensitive fnv1a-64 chains over every past beat are the fleet's
existing ledger grammar (doubt-ledger core, tidepool WAL row law #11,
quilt-tools referral weight law). Bridge work = indexing into that
grammar, not replacing it.

## Honest limits

- This note asserts nothing about WP-11's empirical claims (8×
  compression, pass curves) — uncited, unverified, not adopted.
- Cite-only: no dependency introduced, no vocabulary owned, no
  conformance claimed. WP-11 remains the source of record for the
  bridges; this file only names where their other ends are moored.
- If doubt-ledger#20 changes before merge, the Bridge 4 paragraph should
  be re-read against it (stale-premise hazard, same class as the
  quilt-in-git main-through-#11 correction of 10/3 11:20).
