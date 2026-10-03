# EDGE-WATCH 2026-10-04G — post-18:14Z window (snowball pulse 03:56 10/4)

Cutoff: previous receipt 02:56 10/4 (EDGE-WATCH-2026-10-04E, cutoff 18:08Z). Window scanned: 18:14Z → 20:00Z.

## 1. New repos: ONE — naDir (19:23Z, description-stage)

SuperInstance/naDir: initial commit is LICENSE only; assessment is from repo description + verified empty tree.

- **Collision scan**: vocabulary-level convergence with quilt-in-git (cells, ledger, time-travelable state), ZERO code collision — no README, no code, no pins. Not a rival to any shipped surface.
- **Watch points**: (a) "directory-native substrate — codebases as active, nested spreadsheets; data=folder cells" ≈ quilt-in-git's sheet-as-git-tree / cells/<alias>/dials layout — if it grows code, re-scan for pin-surface overlap; (b) "double-entry ledger" for async logic is accounting-shaped (debit/credit invariants), NOT an append-only receipt chain — doubt-ledger differentiator stays first-class; (c) "bugs = un-cleared cells lighting a spatial grid" is a *visualization* thesis, not a verification thesis — our emitted!=accepted moat law does not transfer.
- **Verdict**: WATCH only. No hedge PR warranted at description stage; hedge trigger = first code commit touching cell/ledger state or any test surface.

## 2. Corroboration: canons SCOUT-2026-10-03T1917Z (mutation-proven, SECOND instance)

quilt-research-canons tip 19:22Z, scout report read directly from commit message:

- **quilt-core-os**: injected `assert.equal(1,2)` test → `npm test` still exits 0, name never printed. Unfalsifiable gate MUTATION-PROVEN on a second, independent org repo (first was the echo-test npm suite, SCOUT-1320Z, already cross-referenced in fleet-triage#12).
- quilt-evolve: 13/13 → 12/13 → 13/13 mutation-verified (can fail — datapoint only).
- holodeck-zig: 45,931KB / 45,954KB committed is `.zig-cache`/`zig-out`; 0 tests vs a 40-test standard; census-truncation class again (size-discipline).
- quilt-metal / quilt-chapel: prose-only ports, badges linking nonexistent manifests (claims-over-receipts shape).
- census re-derived: 5161 repos / 52 pages, unique==rows PASS.

**Relation to our surfaces**: fleet-triage#12 (OPEN, cite-only antidote over SCOUT-1320Z) already names the doctrine target. This scout extends the finding set to new repos; it does not contradict or supersede #12. No new cross-ref doc needed; if #12 lands first, one follow-up line citing SCOUT-1917Z as second-instance corroboration is the post-merge adoption. Named-here-not-double-fixed.

## 3. Named-not-double-fixed (already covered by open receipts)

- gpu-lab QG7b (19:14–19:17Z): PRE-REG booked → ensemble correlation census → booked INTERMEDIATE rho 0.787, 4/5 reruns bit-identical, n_eff~2 threat carried from SCOUT-34 (02:56 receipt) + sibling fleet-triage#17. No action.
- fleet-triage sibling PR #20 (19:14Z): same-window edge-watch fallback unit; its "zero new repos post-18:08Z" claim is now stale (naDir 19:23Z) — corrected here, no clobber, disjoint-by-content (they did org-review, this doc does new-repo + scout scan).

## 4. Stale-fix / state of the world

- fleet-triage main: 47d3239 (unchanged since NEURO-QUILT doc 17:48Z; 19:14Z push event was a branch push, tip verified).
- Merges of ours since 18:14Z: ZERO. Open PRs fleet-triage: 15 (#5–#20), all Casey-gated.
- Zero other org pushes in window beyond the four listed.

## Honest limits

Read-side only this pulse (no code executed against foreign repos beyond clone/list); naDir assessment rests on description + empty-tree verification, not source. Window ends 20:00Z; anything after is next pulse's.
