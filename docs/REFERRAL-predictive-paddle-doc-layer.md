# REFERRAL — predictive-paddle v3 FINDINGS → doc-layer pinning (CANDIDATE)

Referral doc (CANDIDATE per weight law: upgrades VERIFIED only when a merged
PR in the citing repo carries it; never self-upgraded).

Source: SuperInstance/quilt-arcade `experiments/predictive_paddle_v3.FINDINGS.md`
(branch `predictive-paddle-cx-attractor`, PR quilt-arcade#6, sealed FAIL,
lane closed third strike). Cross-ref: fleet pulse study
`memory/study/2026-10-01-fleet-pulse-attractor-convergence.md` (kimi1 workspace)
and this repo's `docs/QUILT-FAMILY-TRIAGE-2026-10-02.md`.

## The shared shape

The v3 finding, measured with receipts: a **self-referential loop preserves
its own attractor**. In the paddle estimator, the certainty gate `A` gated
its own updates — commits raised A, A throttled the pull `w = …·(1−A_eff)`,
so the ring froze ~15 units from truth for the whole 50-match census
(w ≈ 0.003–0.05, H1 20.8% FAIL, H2 15.5% FAIL, H3 advisory 72% < control 86%
honest negative). Nothing inside the loop could see the freeze, because every
instrument on the loop's own path confirmed it.

This repo's resolver census found the **doc-layer analog at family scale**
(digest `docs/QUILT-FAMILY-TRIAGE-2026-10-02.md`, 244-repo census, 7,790
citation sites): **1,355 FILE_MISSING** citations name files that resolve
nowhere in the index — docs that keep citing a state the codebase left.
A doc that cites a moved/deleted file is a frozen ring: the prose reads
certain to a reader on the prose's own path, and only an instrument on a
**different path** (an independent resolver scan over live repos, not the
docs' own memory of the tree) can see it.

Third leg of the convergence (same night, three independent lanes, one
mechanism class): reverse-actualization wave-79 same-model re-anchoring
stuck D1 0.39–0.46 while D2 climbed (sealed FAIL); GPU-EXPERIMENTS rule 5 —
"a control built from the same call path as the probes confirmed a fault
instead of auditing it." Pattern: **escape needs an instrument on a
different path** (JEV typed-decision gates, two-reader rule, different-path
control, resolver scan-as-second-reader).

## What the resolver adds to the receipt doctrine

Receipt chains (fnv1a-64 chained from GENESIS, two-reader verify) already
make *claims* tamper-evident. The census shows the remaining gap is
**referential freshness**: a sealed receipt can faithfully record a citation
that was already stale when sealed. Recommended pairing, both cheap:

1. **Pin at seal time** — every doc that names a file records the resolver
   outcome (RESOLVES / FILE_MISSING / AMBIGUOUS) next to the citation, same
   commit. Stale-then-sealed becomes visible in the chain itself.
2. **Different-path re-scan gate** — resolver `scan` runs over the doc
   corpus on a schedule or pre-merge, failopen signals mapped to the HOLLOW
   taxonomy this repo already maintains. The scan is the second reader;
   the doc's own prose can never be.

## Honest boundary notes

- The v3 numbers are quoted from the sealed FINDINGS/receipt on the
  quilt-arcade branch (determinism head c445d1950942cc8a); not re-run here —
  this doc records the referral, not a replication.
- The 1,355 FILE_MISSING count is the census's shallow-HEAD index; archival
  loss (quilt-Kuramoto salvage case, `docs/REFERRAL-quilt-kuramoto.md`) is a
  distinct sub-class and should not be ranked as ordinary drift.
- Weight law: CANDIDATE until a merged PR in the citing repo carries this
  referral; PENDING → VERIFIED only on that merge.
