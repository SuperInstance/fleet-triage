# REFERRAL — SuperInstance/quilt-Kuramoto (resolver census case)

Referral doc (CANDIDATE per weight law, upgrades VERIFIED on merge).

Source: fleet-triage resolver quilt-family census (244 repos; digest in
`docs/QUILT-FAMILY-TRIAGE-2026-10-02.md`, PR fleet-triage#2).
**SuperInstance/quilt-Kuramoto** carries the family's largest citation
surface: **1,159 citation sites** → 341 RESOLVES / 277 PATH_PRECISE_ONLY /
**264 AMBIGUOUS** / **253 FILE_MISSING** / 14 REPO_UNKNOWN / 7 REPO_MISMATCH
/ 3 SKIP. This doc records what the census found there and the one fix this
repo's resolver taxonomy recommends.

## What quilt-Kuramoto is (framing matters)

quilt-Kuramoto is a **salvaged archive**, not a working codebase: ~610 files
harvested from ~40 upstream Quilt repos, uploaded as eight flat batches with
directory structure flattened into filenames, then re-sorted by provenance
headers. Its own `docs/MISSING.md` documents the harvest losses (HTTP 404s
saved as 14-byte files, rate-limit JSON saved as content, 128 files deleted).

The census's FILE_MISSING class **independently cross-checks that gap list**:
spot checks (12/12 sampled) confirm the cited files exist nowhere in the
243-repo index, and at least 7 FM citations name files quilt-Kuramoto's own
MISSING.md already documents as unrecoverable (quilt-verilog `docs/`
404s — `DESIGN.md`, `CONSERVATION.md`, `POLYFORMALISM.md`, etc.). Of 253 FM
targets, only 2 have a basename match anywhere inside the archive. Read
honestly: the FM class here is **archival loss the repo already knows about**,
now quantified org-wide — not ordinary doc drift, and not a defect count to
rank the repo by.

## The fixable class: 264 AMBIGUOUS bare-basename citations

The live, fixable surface is AMBIGUOUS: bare-basename citations whose target
exists in 2+ indexed repos, e.g. `wall_hx8k_util.txt` (quilt-kuramoto +
quilt-verilog), `quilt_command.h` (quilt-kuramoto + quilt-cuda), `qm2c.py` /
`qm_serve.c` / `quilt_vm.c` (quilt-kuramoto + quilt-esp32 [+ quilt-vm-c]).
In an archive of ~40 flattened upstreams, an unpinned basename is a genuine
referential hazard — the same class as this resolver's AMBIGUOUS taxonomy.

**Recommendation (consume, don't rival):** a bare-basename pinning pass —
rewrite `` `name.ext` `` citations to repo-qualified paths
(`` `code/quilt-verilog/.../name.ext` ``) wherever the basename resolves to
≥2 family repos. That is exactly this repo's resolver AMBIGUOUS outcome
applied as a doc lint; the resolver scan can gate it (`scan` → filter
outcome=AMBIGUOUS → per-doc pinning sweep → re-scan to green).

## Verification (this pulse, 2026-10-02)

- Counts re-derived from sealed census artifacts: 1,159 self-citations in
  quilt-Kuramoto; outcome split matches `triage_by_repo.json` exactly.
- FM spot check: 12/12 sampled FM targets confirmed absent from the
  quilt-Kuramoto clone (walk-verified).
- AMB spot check: 8/8 sampled AMB targets confirmed present in ≥2 indexed
  repos (`find -name` per repo).
- Archive framing verified by direct read of quilt-Kuramoto README +
  `docs/MISSING.md` (HEAD 070159bf, 2026-09-06).

## Honest limits

- Shallow-HEAD index (census run 2026-10-02 ~01:58 CST); quilt-Kuramoto
  HEAD 070159bf. Later pushes not covered.
- PATH_PRECISE_ONLY (277) is advisory-only — the census audit subcommand
  measured 49.2% FP on that class; hard outcomes (FM/LINE_OOR) measured 0.0% FP.
- The 253 FM count overlaps the archive's own documented losses; it should
  not be read as 253 defects to fix. The actionable number is 264 AMBIGUOUS.

Edge direction: quilt-Kuramoto → fleet-triage/resolver (this doc, merged in
the TARGET repo, cites the source repo by name). PENDING per weight law;
VERIFIED=1.0 on merge.
