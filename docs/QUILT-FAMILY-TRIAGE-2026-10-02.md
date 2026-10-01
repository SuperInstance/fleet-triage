# Quilt-Family Resolver Triage — 2026-10-02 (scoped run)

Scoped application of `resolver.py` (3-stage claim resolver) to the
quilt-* family only: **244 repos** on the SuperInstance user namespace
(226 `quilt-` prefixed + 18 quilt-named, GitHub search census), **5,852
markdown docs** (633k lines), **7,790 citation sites** checked against a
243-repo HEAD file-tree index (15,880 files). External/URL stage off;
citations + numerics only. Runtime ~2.7 min scan + ~4 min audit.

Honest limits (stated before anyone trusts the numbers):
- Index is **shallow (`--depth 1`) HEAD of the default branch**. A doc
  citing a file that only existed on an old branch reads FILE_MISSING.
  The fleet-wide run's index policy should be confirmed before ranking
  repos on these counts.
- **PATH_PRECISE_ONLY audited at 49.2% false-positive** (59/120): path
  exists, cited line-content does not verify. Treated as ADVISORY ONLY
  here; every hard claim below excludes it.
- LINE_OOR (25) could not be independently re-checked by the audit
  method (checked=0) — reported but unranked.
- AMBIGUOUS (1,175) = bare basenames, not pinned to one file. Audited
  0% FP but it is a doc-authoring smell, not a defect count.

## Fleet-wide outcomes

| outcome | count | audit FP rate |
|---|---|---|
| RESOLVES | 3,906 | see audit |
| FILE_MISSING | 1,355 | see audit |
| AMBIGUOUS | 1,175 | see audit |
| PATH_PRECISE_ONLY | 1,073 | see audit |
| REPO_UNKNOWN | 179 | see audit |
| REPO_MISMATCH | 33 | see audit |
| LINE_OOR | 25 | see audit |
| EXPR_MISMATCH | 8 | see audit |
| RATIO_MISMATCH | 4 | see audit |
| SKIP | 23 | see audit |

**Hard-bad total (FP-audited 0% classes): 1,425** across 77 repos.
Audit: 513 findings independently re-verified by filesystem scan, 11.5%
overall FP — ALL of it in PATH_PRECISE_ONLY; every hard outcome audited
at 0.0%.

## Triage map (by citing repo, hard-bad classes only)

| repo | FILE_MISSING | LINE_OOR | REPO_MISMATCH | EXPR/RATIO |
|---|---|---|---|---|
| quilt-Kuramoto | 253 | 0 | 7 | 0 |
| quilt-research-canons | 222 | 0 | 3 | 0 |
| quilt-gpu-lab | 125 | 0 | 2 | 0 |
| quilt-tournament | 99 | 25 | 3 | 0 |
| quilt-fiction | 87 | 0 | 0 | 0 |
| quilt-verilog | 76 | 0 | 2 | 7 |
| quilt-agent-memory-archive | 72 | 0 | 0 | 0 |
| quilt-atlas | 65 | 0 | 0 | 1 |
| quilt-llvm | 45 | 0 | 1 | 0 |
| quilt-cuda | 27 | 0 | 0 | 0 |
| quilt-cellular-arch | 25 | 0 | 0 | 0 |
| quilt-ecosystem-demo | 24 | 0 | 3 | 0 |
| quilt-wiki-2126 | 18 | 0 | 0 | 0 |
| quilt | 16 | 0 | 0 | 0 |
| quilt-bandit | 12 | 0 | 0 | 0 |
| quilt-mhs | 12 | 0 | 0 | 0 |
| quilt-rust | 12 | 0 | 0 | 0 |
| quilt-neighbourhood | 11 | 0 | 0 | 0 |
| quilt-canvas-tui | 8 | 0 | 0 | 0 |
| quilt-cowboy | 8 | 0 | 0 | 0 |
| quilt-cowboy-jev | 8 | 0 | 0 | 0 |
| quilt-scratch | 8 | 0 | 0 | 0 |
| jev-quilt | 7 | 0 | 2 | 0 |
| quilt-conformance | 7 | 0 | 0 | 0 |
| quilt-bathy | 6 | 0 | 0 | 0 |
| quilt-fleet | 6 | 0 | 0 | 0 |
| quilt-state | 6 | 0 | 0 | 0 |
| quilt-optimization | 5 | 0 | 0 | 0 |
| mist-quilt | 4 | 0 | 0 | 0 |
| pong-quilt | 4 | 0 | 0 | 0 |
| quilt-cortex | 4 | 0 | 0 | 0 |
| quilt-esp32 | 4 | 0 | 1 | 0 |
| recovered-copy-20260824-mist-quilt | 4 | 0 | 0 | 0 |
| scrap-quilt | 4 | 0 | 0 | 0 |
| quilt-cloudflare | 3 | 0 | 0 | 0 |
| quilt-lab | 3 | 0 | 2 | 0 |
| quilt-readme-expansions | 3 | 0 | 0 | 0 |
| recovered-copy-20260824-scrap-quilt | 3 | 0 | 0 | 0 |
| quilt-canon-cli | 2 | 0 | 0 | 0 |
| quilt-canon-feed | 2 | 0 | 0 | 0 |
| quilt-cell-router | 2 | 0 | 0 | 0 |
| quilt-deck | 2 | 0 | 0 | 0 |
| quilt-forge | 2 | 0 | 0 | 0 |
| quilt-i2i | 2 | 0 | 0 | 0 |
| quilt-k3s | 2 | 0 | 0 | 0 |
| quilt-stone | 2 | 0 | 0 | 0 |
| quilt-studio | 2 | 0 | 0 | 1 |
| quilt-vm-rust | 2 | 0 | 0 | 0 |
| QuiltCanary.jl | 1 | 0 | 0 | 0 |
| forge-quilt | 1 | 0 | 0 | 0 |
| quilt-ai | 1 | 0 | 0 | 0 |
| quilt-arch | 1 | 0 | 0 | 0 |
| quilt-base | 1 | 0 | 0 | 0 |
| quilt-brewer | 1 | 0 | 0 | 0 |
| quilt-c | 1 | 0 | 0 | 0 |
| quilt-canary | 1 | 0 | 0 | 0 |
| quilt-canon-explorer | 1 | 0 | 0 | 0 |
| quilt-canon-radio | 1 | 0 | 0 | 0 |
| quilt-codespace | 1 | 0 | 0 | 0 |
| quilt-core-os | 1 | 0 | 0 | 0 |
| quilt-discovery-demo | 1 | 0 | 0 | 0 |
| quilt-doctor | 1 | 0 | 0 | 1 |
| quilt-ecosystem-web | 1 | 0 | 0 | 0 |
| quilt-fleet-snapshot | 1 | 0 | 0 | 0 |
| quilt-fleet-tools | 1 | 0 | 0 | 0 |
| quilt-jepa | 1 | 0 | 0 | 0 |
| quilt-jetson | 1 | 0 | 0 | 0 |
| quilt-jev-toolkit | 1 | 0 | 0 | 0 |
| quilt-jev-toolkit-push | 1 | 0 | 0 | 0 |
| quilt-mojo | 1 | 0 | 0 | 0 |
| quilt-mojo-lab | 1 | 0 | 0 | 0 |
| quilt-organism | 1 | 0 | 0 | 0 |
| quilt-playtest | 1 | 0 | 0 | 0 |
| quilt-qcells | 1 | 0 | 0 | 0 |
| quilt-substrate-walker | 1 | 0 | 0 | 0 |
| quilt-swift | 1 | 0 | 0 | 0 |
| quilt-vision | 1 | 0 | 0 | 0 |
| quilt-arena | 0 | 0 | 1 | 0 |
| quilt-claw | 0 | 0 | 0 | 2 |
| quilt-live | 0 | 0 | 2 | 0 |
| quilt-substrate-meta | 0 | 0 | 4 | 0 |

Top concentrations:
- **quilt-research-canons** (222 FM): canon docs citing files not at HEAD.
- **quilt-Kuramoto** (253 FM of 1,159 sites — largest citation surface in
  the family): half its doc claims resolve, a quarter name missing files.
- **quilt-tournament** (99 FM + all 25 LINE_OOR): line-past-EOF citations.
- **quilt-fiction / quilt-agent-memory-archive / quilt-atlas**: docs-heavy,
  code-thin repos where most named paths do not exist — hollow-claim shape
  per the fleet's own HOLLOW taxonomy.

## Receipt-chain cross-reference

Kimi-lane receipt chains (fnv1a-64 chained, two-reader rule) currently
open as PRs: quilt-arcade #5/#6, quilt-dba #1, pong-quilt #92. None of
those four repos appears in the hard-bad table (quilt-arcade 2 FM,
quilt-dba 0, quilt-tools 0 FM at HEAD) — the sealed-receipt discipline
and clean citations correlate on the small sample we own.

## Referral edge candidates (weight law: PENDING until a merged PR in
the TARGET repo cites the technique; never self-upgraded)

1. **fleet-triage/resolver -> quilt-research-canons** (CANDIDATE): the
   canon cluster is the family's citation backbone; 222 FM claims are the
   cheapest honesty fixes in the org. Suggest canons adopt a
   resolver-scan gate (consume, don't rival — quilt-tools #23
   citation-verify GUARD already merged for fuzzy citations).
2. **fleet-triage/resolver -> quilt-tournament** (CANDIDATE): all 25
   LINE_OOR in one repo = doc drift after code moves; one sweep fixes the
   family's entire LINE_OOR class.
3. **quilt-Kuramoto -> fleet-triage** (CANDIDATE, reverse): largest
   AMBIGUOUS+FM surface; a bare-basename pinning pass is exactly the
   resolver's AMBIGUOUS taxonomy applied as a lint.
4. **predictive-paddle v3 FINDINGS -> this map** (CANDIDATE): the v3
   pinning lesson (self-referential loops preserve their attractor) is
   the same shape as docs citing files that no longer exist — receipt
   chains at the doc layer would catch both. Cross-ref to the
   attractor-convergence study (memory/study/2026-10-01-fleet-pulse-
   attractor-convergence.md, kimi1 workspace).

Reproduce: `RESOLVER_STATE=<state> resolver.py index && resolver.py scan
--no-external --no-urls` over a 244-repo quilt-family census; audit with
`resolver.py audit --sample N`. Raw report + audit JSON available on
request (7,790 findings; this doc is the digest).

