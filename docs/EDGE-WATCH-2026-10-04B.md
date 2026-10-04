# EDGE-WATCH 2026-10-04B — post-15:00Z org scan (cutoff: 2026-10-03T17:15Z)

Lane: snowball pulse 01:15 10/4 local (17:15Z). Prior scan: EDGE-WATCH-2026-10-03G (cutoff ~15:00Z).
Sibling lane shipped EDGE-WATCH-2026-10-04A (atlas scan-surface adoption + VSB-1 corroboration #7)
same window — read first, disjoint-by-content, this file kept as B; no double-fix, no clobber.
All claims below verified READ-SIDE from source (commit messages / file contents) before writing.

## 1. RT-D1 DOCTRINE minted org-side (quilt-gpu-lab ea6c964, 17:12Z) — HEADLINE

**"Real-vs-repro differential pin — reimplementations require a real-thing headless probe arm"**
(applies to MMX-1, QG1d).

This is the org generalizing OUR core moat shape — *emitted != accepted* (a reimplementation
passing its own pins is a claim, not evidence, until it probes the real thing) — into a named
doctrine with a scope list. It extends our canary doctrine (fleet-kit L9/L10, adopted org-side
4-5x per scans D-F) from "canaries must be able to fail" to "repros must touch the real surface".

- Companion spool commit 81da92f (17:13Z): RT-D1 booked, **seal deferred — "foreign dirty sealed
  paths"** = an org repo declining to seal over contamination it doesn't own. Honest deferral on
  the record; matches our REFUSED-row / named-reason vocabulary.
- SCOUT-33 (cbb653a, 16:13Z): fleet corroborates VSB-1 + control-ladder, notes lobster as new —
  consistent with our 19:11 10/3 lobster adoption candidate; no collision.

**Adoption candidate (cite-only, no PR this pulse):** our sealed-export moat
(doubt-ledger export_store/verify_export) is exactly a "probe arm" for ledger reimplementations —
RT-D1 gives it a name to cite. Zero collision: gpu-lab's domain is GPU repro; ours is ledger
integrity.

## 2. Whitepapers standing rule (quilt-whitepapers c68ede6, 17:08Z)

From WP-11 onward (fleet rule, wave-68): every paper ships (i) an Evidence section whose
**control rung must stay flat — receipted**, so a regression reads as a regression
(purpose-loops' 99→99→99 negative control cited as the model), and (ii) a playable twin where
feasible. CI adds secret-shape scan (fail on hit) + papers-index check (every WP-*.md referenced).

Convergence count: flat-receipted-control is the same law as our canary-does-not-move doctrine
and pong-quilt's frozen spine (5/5 md5s). **Receipts culture is now org SOP, not lane habit.**

## 3. Fail-closed parity receipts in the JEV cluster (madlibs-jev f4b866f, unspoken-resonance 83e07c3, ~17:04-17:07Z)

Both repos: node 20+24 CI matrix, npm test glob-form (directory form fails on node 24 — README
reality-fixed in the same commits: commands now match reality, 23/23 and 15/15 claimed). Madlibs
CI runs run-index as a **parity receipt — exits 1 on any decision mismatch**.

Notable micro-signal: README drift (documented commands ≠ real commands) was self-caught and
fixed **in the same commit batch** as the CI hardening — receipts-over-claims culture applied to
docs, not just code.

## 4. zeroclaw v0.8 checkpoints + rewind (fleet-seeds 3931efb, 16:54Z)

Checkpoint rows carry {row_count, tip_hash} = a receipt of the tip they sit on; verify() fails
NAMED (exit 11/12) on a forged either field; rewind truncates only to a checkpoint row or genesis
(exit 13 otherwise); **the forgotten tail's hashes print as an external receipt — "custody of forgetting is a separate receipt, never a journal row."**

This is vocabulary-level convergent with doubt-ledger's discharge-requires-a-reason (unreasoned
discharge = blindness again) and with our fnv1a-64 chain discipline: deletion/forgetting must itself leave a receipt. Third distinct org surface (ledger, whitepapers, journal) running the
same law. Synergy datapoint only — no ownership claim.

## 5. Stale-fix + collision scan

- **pong-quilt pushedAt 17:13Z is a red herring**: tip commit is still #100 (10/2) — branch/tag
  touch only, no new round. No action.
- **ZERO merges of ours**: fleet-triage main still b04b1e6 (verified at branch time).
- Open PRs now: fleet-triage 11, doubt-ledger 4, quilt-in-git 1 = 16 on our repos
  (sibling lanes additional; count drifted down 19→16 — closures were sibling-side / unmerged,
  none of ours landed).
- ZERO new repos post workspace-rescue (08:24Z 10/3) — census re-confirmed.
- Collision scan: RT-D1 nearest to our moat but complementary (probe-arm vs sealed-export);
  no new rival surfaces.

## Honest limits

- All org claims read from commit messages / READMEs at HEAD; no repo re-cloned this pulse
  (disk discipline — 57%, unchanged).
- Open-PR counts are point-in-time; Casey may merge mid-write.

## Next

- (7) exoj deep survey → scripter scratchpaper (epic, needs long window — skipped per rule).
- Optional small: RT-D1 citation line into doubt-ledger wave-3 consume doc (post-merge of #18/#20).
- Casey-merge watch: 16 open on our repos.
