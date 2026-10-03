# EDGE-WATCH 2026-10-04H — 20:00Z→20:11Z tail + census stale-fix (snowball pulse 04:11 10/4)

Cutoff: sibling EDGE-WATCH-2026-10-04G (window ended 20:00Z). This doc covers only the 11-minute tail plus one verified correction to 04G's state-of-world section. Read-side only.

## 1. Tail window 20:00Z → 20:11Z: ONE push

- **superinstance-advisor `bafe759` (20:10Z)** — "taps: 72nd-wipe hand-fallback round". Creative taps ledger, zero collision with any shipped surface. Repo is a live Cloudflare-Worker cell (5-min cron heartbeat, KV witness log with Merkle root) — org-side receipts culture generalizing again, datapoint only; the witness log is a *root-of-roots*, not an append-only per-event chain, so doubt-ledger / receiptd differentiators stay first-class. No action.
- No other org pushes in the tail (GraphQL repo-list sweep `pushedAt > 2026-10-03T19:59:00Z` = advisor only).

## 2. Stale-fix on 04G — open-PR census was 17, not 15

04G §4 records "fleet-triage: 15 (#5–#20), all Casey-gated". Verified live at 20:11Z: **fleet-triage has 17 open PRs (#5–#21)** — #21 (`edge-watch-2026-10-04g`) was opened inside 04G's own window but after its census snapshot. Not a content error, a snapshot-timing gap; corrected here per stale-claim practice, no clobber, disjoint-by-content.

Full verified census at 20:11Z (all Casey-gated, ZERO merges of ours in the tail):
- fleet-triage: 17 (#5–#21, incl. ours #5–#19 and sibling #20/#21)
- doubt-ledger: 4 (#16, #18, #19, #20) — #19 (`adjudication-receiptd-consistency-note`, opened 05:16Z) is a sibling consistency-review over our #16/#18, named-not-double-fixed
- quilt-in-git: 1 (#12, ours)
- pong-quilt: 5 (#102–#106, sibling R80–R84 rounds, all pre-17:14Z, zero collision)
- **Fleet-side total: 27 open, zero merges since the 10/2 Casey wave.**

Main tips verified unchanged: fleet-triage `47d3239`, quilt-in-git `61a71393` (matches 04G).

## Honest limits

11-minute window; tail assessment of advisor rests on README + commit message, not source execution. If a longer window had been available the queue's top item (exoj deep survey, epic, 18th skip per rule) would still exceed the 15-minute budget.
