# Unfalsifiable gates: antidote cross-ref (2026-10-03)

Cite-only adoption note, adoption-not-rivalry. Source: quilt-research-canons
scout **SCOUT-2026-10-03T1320Z-unfalsifiable-gates-and-lau-cluster.md**
(commit "Scout 2026-10-03T1320Z: unfalsifiable gates (npm test = echo)…"),
whose findings were re-verified read-side before this note was written:

1. `educationgamecocapn`: `npm test` is literally `echo 'Tests passed'` —
   mutation-verified GREEN with `tests/`, `node_modules/`, and `src` all
   deleted (three destroyed states, exit 0 each). A gate that cannot fail.
2. The same scout round caught its own **52x census truncation**
   (HTTP/2 lowercase-header pager bug, 100 of 5,161 rows) that **passed its
   own uniqueness assertion** — 100 == 100 is true. Truncation wearing a
   passing assert.

Both findings are exactly the failure class this lane's canary doctrine was
minted against (memory/snowball-queue.md 09:40 10/2 decorative-pin audit,
now encoded org-side as **fleet-kit L9/L10**, cited by quilt-gpu-lab CI-1,
see CANON-CROSSREF-L9L10.md):

- **A canary that cannot fail is worse than no canary** — `echo 'Tests passed'`
  reports success under every destruction, so it trains trust it has not
  earned. Antidote pattern: every pin suite must contain at least one pin
  whose RED state has been DEMONSTRATED, not assumed (L9/L10 law; our
  FAIL-first sealed logs precede every green seal).
- **Truncation that passes its own assert = the emitted≠accepted moat shape** —
  an output (100 rows) validated against nothing but itself is a claim, not a
  receipt. Antidote pattern: cross-check counts against an independent anchor
  (`Link: rel="last"` page number), and treat silent termination ("no next
  link") as a claim to verify rather than a fact — the scout's own correction
  section says exactly this.

No ownership claim; the unfalsifiable-gates finding and its mutation proofs
belong to the canons scout. This note exists so the citation chain
L9/L10 → 09:40 10/2 audit → SCOUT-1320Z verified findings is traversable from
the org side, and so any future anti-fail-open CI template adoption cites the
scout's evidence, not this summary.
