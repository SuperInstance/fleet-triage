# EDGE-WATCH 2026-10-03F — post-14:37Z scan (snowball pulse 22:56 CST)

Scan window: commits after the 22:37 receipt's cutoff. READ-SIDE verified from source before writing.

## 1. quilt-gpu-lab — control-ladder tool (14:41Z, commit 0451e49) — DOCTRINE ADOPTION #5

`tools/control_ladder.py` (162 lines, stdlib): generic **POS + expect-red negative-control harness**, fail-closed, lifted from the lab's own PROVEN CAN-1 pattern (`tools/canary.py` control_ladder, G1-G4 booked PASS).

Semantics verified in source:
- green rung: check fires on clean input → FALSE-POSITIVE → FAIL
- red rung: check silent on tampered input → BLIND SPOT → FAIL
- check raising counts as FIRED (red) / FAIL (green) — an exception is a detection signal
- non-PASS exits 1 with a JSON receipt on stdout

This is our fleet-kit L9/L10 doctrine ("canary-that-cannot-fail is worse than none"; RED-demonstrated before trusted) made into a **generic, grabbable ladder** — the lab's README doctrine says "Grab = copy the file". Zero collision with anything we own (we have no generic ladder tool; our pins are per-repo shell suites). **Adoption posture: WATCH-and-lift** — if a future lane needs a generic two-rung harness, lift this file rather than re-derive; cite CAN-1 lineage. No hedge PR needed; this *is* the org running the doctrine.

## 2. mavis-workspace — COLOUR PROBE self-refutation (06:50Z) — receipts culture datapoint

Commit message verbatim: "the last claim, measured on real pixels — and it refutes me". A lane measuring its own claim on real pixels and publishing the refutation is the receipts-over-claims doctrine operating org-side without our involvement. Followed by "ENVIRONMENT: I wrote 'no C toolchain' from memory. gcc 12.2.0 was in the…" — second self-correction of a memory-claim in the same repo, same day. No action; noted as evidence the culture generalizes.

## 3. Stale-check + collision scan

- ZERO new repos post-08:24Z (workspace-rescue still tip, census re-verified).
- ZERO merges of ours since 22:37 receipt: fleet-triage #5-#12 (8), doubt-ledger #16/#18/#19/#20 (4), quilt-in-git #12 (1) = 17 open, all Casey-gated. Sibling: pong-quilt #103-105 open.
- gpu-lab SCOUT-32 slice (14:14Z) + edge-mine wave 9 (14:26Z): internal, zero collision.
- Collision scan: control-ladder cites CAN-1, not our repos — nearest neighbor remains receiptd (hedged, doubt-ledger#18). No new vocabulary emergency.

## Honest limits

- Shallow clone (depth 5) — commit messages read, full history not audited.
- gpu-lab self-test (`--selftest`) NOT executed here (GPU-lab repo, no GPU needed but out of scope for a docs scan); semantics verified by reading source only.
- mavis commits read by message only.
