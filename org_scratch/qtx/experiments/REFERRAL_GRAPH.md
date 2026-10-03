# REFERRAL_GRAPH PoC — the mesh answers as a distribution

Mandate: Casey 2026-09-25 12:03 — "not one thing but a distribution of
intelligent referrals." Ideas are nodes, referrals are weighted LINKs, and the
answer to any question is a ranked VIEW over modules — every edge carrying the
receipt that proves it or the falsification condition that would kill it.

## What was built

- `src/referral_graph.mjs` — the substrate: nodes + hash-chained LINK rows
  (fnv1a-64, the fleet receipt idiom), weight law enforced at booking time,
  falsification probes, receipt audits, and the ranked-distribution VIEW.
- `experiments/referral_graph.seed.mjs` — the real v1 graph: 9 nodes across
  quilt-tools ↔ quilt-show ↔ quilt-arcade + quilt-quant → pong-quilt, 6
  edges, every edge with its kill switch declared.
- `experiments/referral_graph.pins.mjs` — 109 pins (108 offline-green +
  the live PR audit on `--live`). Run:
  `node experiments/referral_graph.pins.mjs --live` (the `--live` pass audits
  every provenance PR against GitHub; offline pins are labeled SKIPPED, never
  passed silently).

## Weight law (constitution)

| weight   | meaning                                   | mass |
|----------|-------------------------------------------|------|
| PENDING  | speculation — claim + kill switch only    | 0.05 |
| VERIFIED | merged PR **in the target repo** cites the technique | 1.00 |
| REFUTED  | falsification_condition met — killed, scar kept in chain | 0    |

Provenance (where the finding lives) is shape-checked but earns nothing —
do not conflate it with the currency.

### The trust lever (G11 port, 2026-09-27)

The blind view sums edge weight per target repo — and weight is cheap to
inflate: a repo the fleet has not earned to trust can merge N junk-citation
PRs into itself and BUY mass. `viewTrusted({trust, default: 0})` re-scales
every edge by its target repo's EARNED trust:
`effective = trust.get(repo, default) · weight`. An unseen source defaults
to 0 — it contributes nothing until the fleet earns reason to trust it.
Trust is the lever; weight alone is not. Ported from
**SuperInstance/jev-quilt `commons.py`** — `trust_weighted()` /
`provenance_merge()`, G11 "trust-weighted cross-fleet gluing", merged as
SuperInstance/jev-quilt#37 (a lie deposited at weight 1000 by a stranger is
scaled to 0 and cannot outvote a small trusted truth). Trust 1 for every
repo reduces exactly to the blind view (pinned).

## First findings

1. **The mesh started empty of currency — no longer.** All 5 seed edges began
   PENDING with real provenance (quilt-tools#3/#4/#5, quilt-arcade#2 — all
   audited MERGED live), but zero merged PRs in a *target* repo cited a
   seeded technique. On 2026-09-26 the first edge earned currency:
   **quilt-show PR #1** ("E3 verification record — script↔sim claim map +
   referral edge to quilt-tools PR #3", MERGED 2026-09-25T19:14:08Z, merge
   `a2f82a35`) carries the S2 driftwatch citation in-repo
   (`docs/E3-VERIFICATION.md` referral-edge record + `episode-3/sim.mjs`
   header), with quilt-show PR #3 (ep4-instruments, merged 21:30Z)
   re-citing it. Edge `qt-s2-driftwatch → qs-ep2` is now **VERIFIED=1.0**,
   receipt `SuperInstance/quilt-show#1`. The empty-currency baseline is
   broken; the view moved (see finding 2).
2. **The view discriminates — now with real mass, twice.** Answer distribution at
   seed was quilt-arcade 40% · quilt-show 40% · quilt-tools 20%. After the
   first VERIFIED edge: **quilt-show 87.5%** · quilt-arcade 8.3% ·
   quilt-tools 4.2%. After the second — **pong-quilt PR #28** ("R21:
   receipted quantum-coin champion tiebreak", MERGED 2026-09-26T05:27:42Z,
   merge `b14791f`) carrying quilt-quant's `coin-toss-v1` citation in-repo
   (`core.js` VERIFIED_CLAIMS `quantum-tiebreak` entry + `tools/prerun.js`,
   PR #29 symmetrized the flip journal) — edge `quant-coin-toss →
   qq-quantum-tiebreak` flips **VERIFIED=1.0**, receipt
   `SuperInstance/pong-quilt#28`, and the single-edge monopoly is broken:
   **quilt-show 47.7% · pong-quilt 45.5%** · quilt-arcade 4.5% ·
   quilt-tools 2.3%. Currency now flows tools→show AND quant→pong — two
   independent directions of cross-use. After the third edge (git-agent#4
   cites algebra.md) the view carried five repos; after the FOURTH —
   **quilt-cowboy#1 cites jev-quilt's substance noul by name, jev-quilt's
   first outgoing edge** — the view is **quilt-show 25.0% · git-agent 23.8%
   · pong-quilt 23.8% · quilt-cowboy 23.8%** · quilt-arcade 2.4% ·
   quilt-tools 1.2%.
3. **Falsification is mechanical.** Each edge declares the exact observed
   evidence that would kill it; `probe()` books the death as a REFUSED row
   (scar stays in the chain, mass drops from the view). NEGATIVE_SPACE idiom,
   graph-native.

## Referral edges (lane rule — this doc's own links)

- REFERRAL_GRAPH → **quilt-show**: Episode 2's "demonstrate, don't assert" is
  now load-bearing for this graph's weight law (PENDING until demonstrated).
  Kill switch: a quilt-show episode whose central claim ships with no receipt
  and no declared kill condition.
- REFERRAL_GRAPH → **quilt-arcade**: plugin manifests are the natural
  on-disk shape for a node's identity; a game plugin citing a lab technique
  would mint the graph's first VERIFIED edge. Kill switch: the plugin gate
  accepting a manifest with no provenance field.
- REFERRAL_GRAPH → **tidepool** (staged, repo not yet seeded): semantic
  recall auto-placing referral edges — prediction error = breeding novelty
  (JEPA's mesh role made literal). Kill switch: an auto-placed edge entering
  the view with weight above PENDING.

## Next rungs

- ~~First VERIFIED edge~~ **DONE 2026-09-26** — quilt-show#1 cites S2; edge
  VERIFIED=1.0, view moved.
- ~~Second VERIFIED edge / break the single-edge monopoly~~ **DONE
  2026-09-26** — pong-quilt#28 cites quilt-quant coin-toss-v1; edge
  VERIFIED=1.0. The view now carries two independent currency directions.
  Third candidate visible: ep4's twist-field instruments could carry an
  S3-shaped witness row into a plugin-adjacent artifact, or git-agent's
  quilt_emit (#1, merged) citing the 5-opcode WAL could earn agent→quilt.
- JEPA predicts which repo a new finding refers to — prediction error logged
  as a receipt = the breeding-reward hook.
- ~~`auditReceipts` against the live org PR stream (cron) so VERIFIED weights
  decay honestly when cited PRs are reverted~~ **guard DONE** (the pins'
  live audit covers receipts); **discovery DONE 2026-09-26** —
  `experiments/referral_graph.discovery.mjs` watches the org's merged-PR
  stream for *mintable* currency (first live run: 0 real candidates across
  the 4 PENDING edges; 1 hit — quilt-tools#6 — EXCLUDED as self-referential:
  the graph's own artifact cannot mint its currency, anti-Goodhart guard
  pinned as Pin 10). Candidates surface with their PR; a human verifies the
  citation is load-bearing, then the seed flips — this tool never books.
  **Fuzzy-match guard LIVE 2026-09-28:** `gh search prs` ranks, not
  filters — the live run surfaced quilt-arcade#3 ("Pong: realtime laws on
  the discrete sheet") for 'episode-3 watcher' when that PR never mentions
  watchers or episode 3 in title, body, or diff. Human verification rejected
  it; the tool now citation-verifies every hit (literal hint text in
  title/body/diff) before it may present as a CANDIDATE — fails are
  FUZZY-REJECTED, gh errors VERIFY-UNKNOWN, both surfaced never booked
  (Pin 12). Second live run after the guard: 0 real candidates across the
  4 PENDING edges.
- **Third candidate booked PENDING 2026-09-26** — the 11:11 pulse's org
  review flagged git-agent PR #1 ("quilt_emit: vessel lifecycle events →
  quilt 5-opcode WAL", MERGED 00:27:18Z, merge `6bc099a`). The merged code
  implements AI-Writings/algebra.md's five-opcode spine (BIND/LINK/EFFECT/
  VIEW/TICK, hash-chained fnv1a WAL) — but cites the doctrine without
  naming the source repo, so the weight law keeps edge
  `aw-quint-opcode → ga-quilt-emit` at **PENDING** (provenance
  `SuperInstance/git-agent#1`, live-audit merged). Upgrade path: an
  in-repo citation naming `algebra.md`. git-agent enters the VIEW for the
  first time (PENDING mass). Honest-provenance discipline: a merged PR
  citing the *idea* but not the *source* is speculation with good
  provenance, not currency.
- **Fourth edge VERIFIED 2026-09-26 (evening) — jev-quilt's first outgoing
  currency** — the 16:11 pulse's synergy candidate landed without us
  lifting a finger: **quilt-cowboy PR #1** ("jev substance gate: jev-quilt
  doctrine on the paper-generation output gate", MERGED 2026-09-26T09:12:37Z,
  merge `a3feccca`) replaced the v3 admission proxy (length ≥ 300 alone —
  1,745 papers admitted on a stand-in, per RD_QUILT_3_0's own admission)
  with jev-quilt's substance noul + 0.6 admit threshold, citing
  `SuperInstance/jev-quilt` **by name** in-repo (README + `CITATION` const +
  module docstring). Weight law met in the TARGET repo: edge
  `jq-substance-noul → qb-jev-gate` is **VERIFIED=1.0**, receipt
  `SuperInstance/quilt-cowboy#1`. Two new repos enter the sheet
  (jev-quilt, quilt-cowboy); jev-quilt's referral view went from zero
  outgoing to one — the doctrine now flows outward four ways.
- **Fifth edge VERIFIED 2026-09-26 (night) — pong-quilt's first OUTGOING
  currency, first to-node born after seeding** — the 03:04 pulse's synergy
  candidate landed on its own: **fleet-murmur PR #2** ("Honesty-receipts
  pass: transport modes, receipt ledger, quality-gate seam, claims
  registry", MERGED 2026-09-26T19:08:16Z, merge `5391ba56`) names
  `SuperInstance/pong-quilt` **by name** in-repo three times in
  `CROSS-POLLINATE.md`: the QA-REFUSAL seam (R23–R28 honesty pins) as the
  transport-honesty contract ("a black-hole transport must not score 100%
  coverage"), `tools/wal-session.js`'s session WAL as the receipt-ledger
  substrate ("one verifier reads every fleet ledger"), and the
  VERIFIED_CLAIMS + readme-count pin as the claims-registry shape. Weight
  law met: edge `pq-session-wal → fm-honesty-receipts` is **VERIFIED=1.0**,
  receipt `SuperInstance/fleet-murmur#2` — booked in the direction the
  substrate enforces (receipt targets the to-node's repo), the honest
  correction of the pulse note's citation-order prose.
- **Sixth edge VERIFIED 2026-09-27 (dawn) — the scar becomes load-bearing in
   a third instrument** — the 06:56 pulse's discovery-class org scan caught
   **moth-waveform PR #1** ("Phase 2: duck-sensitivity receipts — which duck
   carries the regime?", MERGED 2026-09-26T21:06:24Z, merge `dc1a142`)
   citing fleet-murmur's vacuity scar **by name, at code level**:
   `sensitivity.py` — "a gate that passes without a live floor measurement
   passes vacuously (fleet-murmur scar)". The no-op health gate exists
   because fleet-murmur#2's transport-honesty contract proved a black-hole
   transport can score 100% coverage. Weight law met: edge
   `fm-honesty-receipts → mw-floor-gate` is **VERIFIED=1.0**, receipt
   `SuperInstance/moth-waveform#1`. HONESTY: the README Receipts-doctrine
   list (pong-quilt, hermit, quilt-doctor, quality-gate-stream,
   fleet-murmur) is recorded in the claim as lineage, not the currency
   anchor — only the load-bearing code-level citation mints. The view now
   carries eight repos: **quilt-show 16.9% · fleet-murmur 16.1% ·
   git-agent 16.1% · moth-waveform 16.1% · pong-quilt 16.1% · quilt-cowboy
   16.1%** · quilt-arcade 1.6% · quilt-tools 0.8% — and fleet-murmur earns
   its first OUTGOING currency (all prior fm mass was incoming).
- **Seventh edge VERIFIED 2026-09-27 (morning) — the pre-booked interop lane
   lands, and fleet-murmur becomes the first double-mass repo** — the 05:24
   pulse opened this lane with the direction pre-booked ("on merge books
   edge qgs→fm, target repo=fm — NOT fm→qgs as the pulse note guessed"):
   **fleet-murmur PR #3** ("qgs adapter: live-verify seam against real
   quality-gate-stream (stale-API fix)", MERGED 2026-09-26T23:08:45Z, merge
   `8df75c6`) rewrites `tools/quality_gate_adapter.py` against the live
   quality-gate-stream API — the pre-merge adapter called a stale API and
   raised TypeError/AttributeError against the real package, so the fix and
   the citation shipped in the same PR — and names
   **SuperInstance/quality-gate-stream BY NAME in-repo at three anchored
   sites**: the adapter module docstring ("Cross-repo seam
   (cross-pollination receipt): SuperInstance/quality-gate-stream"),
   `VERIFIED_CLAIMS.md` VC10, and `tests/test_qgs_adapter_glue.py` (4 live
   pins run the real package; labeled skips when uninstalled, never fake
   green; an always-on pin asserts the citation string survives in source).
   Two sibling repos built the two halves of the review-honesty doctrine
   the same day (fleet-murmur#2 seam / quality-gate-stream#2 strict mode);
   this merge pins them against dialect drift — the exporter-in-consumer /
   live-verify-in-producer shape of the R26 wal-export → quilt-doctor seam.
   Weight law met: edge `qgs-strict-gate → fm-qgs-adapter` is
   **VERIFIED=1.0**, receipt `SuperInstance/fleet-murmur#3`. The view now:
   **fleet-murmur 27.8%** (first repo carrying TWO VERIFIED inbound edges)
   · quilt-show 14.6% · git-agent 13.9% · moth-waveform 13.9% · pong-quilt
   13.9% · quilt-cowboy 13.9% · quilt-arcade 1.4% · quilt-tools 0.7%.
   HONESTY: quality-gate-stream earns currency as a from-node only;
   from-node-only repos (quilt-quant, AI-Writings, quality-gate-stream)
   carry no view mass — the view measures where doctrine LANDS.
- **Eighth edge VERIFIED 2026-09-27 (late morning) — the G11 trust lever
   lands IN this repo, and the commons lane earns its first to-node
   currency here** — the 08:11 pulse flagged the synergy the same morning
   the R8 Goodhart lane reopened the buyable-view surface; the lane
   shipped seven hours later. **quilt-tools PR #17** ("referral-graph:
   the G11 trust lever", MERGED 2026-09-27T01:27:12Z, merge `d14fb44`)
   ports `viewTrusted({trust, default:0})` from **SuperInstance/jev-quilt
   `jev_quilt/commons.py` BY NAME** — `trust_weighted()` /
   `provenance_merge()`, the G11 "trust-weighted cross-fleet gluing"
   commons hardened against weight inflation in **jev-quilt#37** (MERGED
   2026-09-27T00:06:03Z). The blind view sums edge weight per target repo:
   a source the fleet has not earned to trust can merge N junk-citation
   PRs into its own repo and buy mass. `viewTrusted` re-scales every edge
   by its TARGET repo's EARNED trust (`effective = trust·weight`; unseen
   source defaults to 0 and contributes NOTHING until the fleet earns
   reason to trust it; trust 1 everywhere reduces exactly to the blind
   view). Pin 11 pins the fixture semantics — blind view BUYABLE at >90%
   junk mass; unseen junk → 0; trust is THE lever — plus the citation
   string surviving in `src/referral_graph.mjs`. Weight law met: edge
   `jq-commons-g11 → qt-trust-lever` is **VERIFIED=1.0**, receipt
   `SuperInstance/quilt-tools#17`, provenance `SuperInstance/jev-quilt#37`.
   The view now: **fleet-murmur 24.4%** (still the only double-inbound
   repo) · quilt-show 12.8% · quilt-tools 12.8% (VERIFIED+PENDING, its
   first mass above epsilon) · git-agent 12.2% · moth-waveform 12.2% ·
   pong-quilt 12.2% · quilt-cowboy 12.2% · quilt-arcade 1.2%. HONESTY:
   jev-quilt's currency here is the commons' anti-Goodhart term itself —
   the graph pre-hardened its own weight law against the exact attack the
   blind view invited; the citation names `jev_quilt/commons.py` at path
   level, not just the repo.
- **Ninth edge VERIFIED 2026-09-27 (midday) — the stone-v1 forward-adoption
   lane lands exactly as pre-booked** — the 11:04 pulse wrote "on merge,
   referral graph books NINTH VERIFIED edge pq-stone-v1-export →
   stone-forward-adopt"; Casey merged at 12:20 CST and the booking follows
   the same never-self-upgraded pattern as edges #5–#8. **quilt-stone PR
   #1** ("smoke 12b: pong-quilt R36 is the first stone-v1 forward-format
   adopter — exporter's real stone-v1 output pinned (verify/tamper/splice)
   + README adoption record", MERGED 2026-09-27T04:20:06Z, merge `093c1b1`)
   lands the adoption IN THE VERIFIER's repo: `smoke.mjs` section 12b pins
   five checks over the exporter's **EXACT bytes** (generated live from
   pong-quilt's `tools/wal-export.js` `toStoneV1()` at PR #46's merge tip,
   not retyped) — alg=stone-v1/genesis canonical/links=5, the mandatory
   `stone.header` row carries `tool=pong-quilt` (producer named, not
   laundered), a post-seal edit is caught as `hash_mismatch`, a row splice
   breaks continuity — and README.md's **Forward-format adopters** section
   names `SuperInstance/pong-quilt` PR #46 BY NAME. Weight law met in the
   to-node's repo: edge `pq-stone-v1-export → stone-forward-adopt` is
   **VERIFIED=1.0**, receipt `SuperInstance/quilt-stone#1`, provenance
   `SuperInstance/pong-quilt#46`. The view now: **fleet-murmur 21.7%**
   (still the only double-inbound repo) · quilt-show 11.4% · quilt-tools
   11.4% · git-agent 10.9% · moth-waveform 10.9% · pong-quilt 10.9% ·
   quilt-cowboy 10.9% · quilt-stone 10.9% (third to-node born after
   seeding) · quilt-arcade 1.1%. HONESTY: pong-quilt's currency here is its
   SECOND outgoing edge — the R36 wal-export lane both receives currency
   (pq→fm, edge five) and pays it forward into the fleet's canonical
   receipt-chain verifier; the 09:57 edge-watch flagged stone as
   LANE-AFFECTING (all receipt/WAL export lanes should target/
   verify-through stone-v1) — this edge records the adoption, not the
   mandate itself.
- **Tenth edge VERIFIED 2026-09-27 (17:2x CST) — the stone-v2 sign-lane
   adoption, pre-booked twice and landed in Casey's merge burst.** The
   14:56 pulse wrote "on quilt-stone#4 merge the pilot opens + candidate
   VERIFIED edge"; the 16:04 pulse shipped the R39 sign pilot CLOSED
   against the sign-lane tip and pre-booked the booking. **quilt-stone
   PR #4** ("STONE-V2-PILOTS sign lane: signTip/verifyTipSignature ed25519
   tip staples", MERGED 2026-09-27T09:02:01Z, merge `023edbed`) ships the
   signature primitive, and **pong-quilt PR #51** ("R39: STONE-V2-PILOTS
   first sign pilot — producer staples the birth-seal chain's tip",
   MERGED 2026-09-27T09:03:15Z, merge `07384ac2`) lands the first real
   adoption: `tools/prerun.js` staples the R37 birth-seal chain's tip
   through the named checkout's `signTip`/`verifyTipSignature` (signs a
   COPY — the unsigned stone-v1.json stays canonical; verify BEFORE write;
   refused staple bricks the run; ships closed with a labeled skip),
   citing `SuperInstance/quilt-stone` BY NAME in-repo at three anchored
   sites: PLAYLOG Round 39, `tests/stone-sign-glue.test.js`'s citation pin,
   and `core.js` VERIFIED_CLAIMS `stone-sign-pilot`. Edge
   `stone-sign-lane → pq-sign-pilot` is **VERIFIED=1.0**, receipt
   `SuperInstance/pong-quilt#51`, provenance `SuperInstance/quilt-stone#4`.
   HONESTY ON DIRECTION: the pulse notes guessed pong-quilt→quilt-stone;
   the substrate's receipt-repo rule (edge #5 precedent) is the
   constitution — the citing merge is IN pong-quilt, so currency flows
   INTO pong-quilt. quilt-stone earns its FIRST OUTGOING edge five hours
   after receiving edge #9; pong-quilt joins fleet-murmur as the second
   double-inbound repo. The view now: **fleet-murmur 21.7% · pong-quilt
   21.7%** (tie, name order) · quilt-show 11.4% · quilt-tools 11.4% ·
   git-agent 10.9% · moth-waveform 10.9% · quilt-cowboy 10.9% ·
   quilt-stone 10.9% · quilt-arcade 1.1%.
- **Eleventh edge BOOKED PENDING 2026-09-30 (08:11 pulse) — the KAT bridge
   lane, one step earlier in the PR lifecycle than any prior booking.** The
   07:11 pulse's org scan caught AI-Writings#70 (MERGED
   2026-09-29T21:26:53Z) shipping `labs/jev-kat/jev_kat.mjs` — the JEV
   known-answer control instrument — and the 08:03 pulse commissioned the
   bridge into jev-quilt: **jev-quilt PR #47** (OPEN at booking) names
   `SuperInstance/AI-Writings` **in-repo at anchored sites**: the bridge pins
   the canonical instrument by repo + commit
   `3f8405888366e3697b3775017fa5fe13d6244226` + sha256
   `5f280b8b435852872fadeb449f4382275e80be56e80035da02274db8006e1cc5` as an
   executable constant (a drifted upstream cannot be bridged silently),
   `tests/test_jev_kat_bridge.py` asserts the citation string survives in
   source, and the module docstring records AI-Writings#70 as the
   instrument's canonical home. An instrument consumed by pin-and-digest is
   doctrine LANDING in the consumer's repo. **Honest weight-law read: an OPEN
   PR earns nothing** — edge `aw-jev-kat → jq-kat-bridge` is booked
   **PENDING=0.05** with the merge itself as the upgrade path (the discovery
   watcher now scans jev-quilt's merged-PR stream for `jev_kat` /
   `known-answer control` / `AI-Writings`; on merge a human verifies the
   citation is load-bearing and flips the seed — never self-upgraded).
   Precedent discipline: `aw-quint-opcode` was booked PENDING on a
   merged-but-doctrinal citation and earned currency only when the
   target-repo merge named the source — same law, one lifecycle step
   earlier. jev-quilt enters the VIEW for the first time as a TO-node
   (PENDING mass; both its prior edges were outgoing). The view now:
   **fleet-murmur 21.6% · pong-quilt 21.6%** (tie) · quilt-show 11.4% ·
   quilt-tools 11.4% · git-agent 10.8% · moth-waveform 10.8% ·
   quilt-cowboy 10.8% · quilt-stone 10.8% · quilt-arcade 1.1% ·
   jev-quilt 0.5%.
- **Eleventh edge FLIPPED VERIFIED 2026-09-30 (09:11 pulse) — the KAT
   bridge lane closes one lifecycle step after booking.** jev-quilt PR #47
   MERGED 2026-09-30T00:18:30Z (merge 45912589941ce29f02c8a6659bfe2b4e7abfccb9)
   — Casey merged the commissioned bridge overnight. The 09:11 pulse ran the
   weight-law check by hand, not self-upgraded: the MAIN-tree source still
   carries the load-bearing citation (`tools/jev_kat_bridge.mjs` pins repo +
   commit `3f8405888366e3697b3775017fa5fe13d6244226` + sha256
   `5f280b8b435852872fadeb449f4382275e80be56e80035da02274db8006e1cc5` as
   executable constants; `tests/test_jev_kat_bridge.py` still asserts the
   citation string survives). The discovery watcher had surfaced #47 among
   ten `AI-Writings`-hint candidates — the hint scanner ranks, the human
   confirms load-bearing. Falsification condition checked and NOT met. Edge
   `aw-jev-kat → jq-kat-bridge` is **VERIFIED=1.0**, receipt
   `SuperInstance/jev-quilt#47` — jev-quilt's first INBOUND currency (both
   prior edges were outgoing; it paid doctrine forward before ever receiving
   it). The seed, pins (93→95 checks; three view pins correctly tripped RED
   on the state change and were re-pinned to the post-flip distribution),
   and this log move together — never self-upgraded, earned at the merge.
   The view now: **fleet-murmur 17.9% · pong-quilt 17.9%** (tie) ·
   quilt-show 9.4% · quilt-tools 9.4% · git-agent 8.9% · jev-quilt 8.9% ·
   moth-waveform 8.9% · quilt-cowboy 8.9% · quilt-stone 8.9% ·
   quilt-arcade 0.9%.
- **Twelfth edge VERIFIED 2026-09-30 (14:56 pulse) — the lab↔ledger pair,
   ledger→lab, and a FALSE NEGATIVE corrected in the claim itself.** The
   14:38 pulse queued a citation PR to micrograd-quilt on the claim that its
   main cited SuperInstance/MicroMoth-quilt ZERO times despite consuming the
   exp018-036 receipt lineage. This pulse's re-audit found that scan WRONG:
   **micrograd-quilt PR #7** ("qcells exp020-036: tie-band replication →
   two-regime desert hazard → triplet-stream rate-lane closure", MERGED
   2026-09-30T04:49:20Z, merge `44de605`) is a merged PR in the to-node's
   repo whose diff ADDS `labs/qcells/FINDINGS.md` citing
   SuperInstance/MicroMoth-quilt **by name at four anchored sites** — the lab
   charter header, the import-baseline manifest pin on MicroMoth-quilt main,
   the honest-limit gap posted on MicroMoth-quilt#3, the receipts/ lane note —
   plus `docs/synergy-scan-2026-09-30-0711.md` consuming MicroMoth-quilt#23/#24's
   MERGED sealed findings to redirect the lab's own queue ("do not re-run").
   No citation PR was opened — Casey's merge already earned the edge, and
   opening one would have been citation spam on a false premise. Weight law
   met: edge `mm-sealed-receipts → mgq-qcells-lab` is **VERIFIED=1.0**,
   receipt `SuperInstance/micrograd-quilt#7`, provenance
   `SuperInstance/MicroMoth-quilt#24`. micrograd-quilt enters the view at
   full VERIFIED mass (a to-node born after seeding, skipping epsilon).
- **Thirteenth edge FLIPPED VERIFIED 2026-09-30 (17:56 pulse) — the mirror
   earns its currency; the first bidirectional pair is VERIFIED in both
   directions.** The 14:56 pulse booked the lab→ledger mirror PENDING on the
   git-agent#1 doctrinal shape (MicroMoth-quilt#24 names the producer only
   as "the qcells lab (workspace/labs/qcells)"). Casey merged the upgrade
   path six hours later: **MicroMoth-quilt PR #29** ("docs(audit): qcells
   lab canonical home = SuperInstance/micrograd-quilt — provenance note +
   citation pin", MERGED 2026-09-30T09:27:01Z) is a merged PR in the
   to-node's repo whose diff ADDS an AUDIT.md "Qcells lab — canonical home"
   note naming **SuperInstance/micrograd-quilt by name** as the lab's
   durable addressable home (labs/qcells tree; sealed lineage exp018–exp022
   mirrored as receipt PRs #5–#7), with `tests/test_lab_home_citation.py`
   pinning the citation in-repo (repo named; local path framed by citation).
   Honest handling of history: sealed receipts are immutable — the note
   amends provenance without touching them. Weight law met: edge
   `mgq-qcells-lab → mm-sealed-receipts` is **VERIFIED=1.0**, receipt
   `SuperInstance/MicroMoth-quilt#29`, provenance unchanged
   (`SuperInstance/MicroMoth-quilt#24`). The discovery watcher surfaced #29
   on the booked hint scan (`micrograd-quilt` / `qcells lab`); the flip was
   confirmed by hand against the merged diff — load-bearing citation, FAIL
   test intact, never self-upgraded. The mm⇄mgq pair now carries VERIFIED
   mass in BOTH directions — the graph's first fully-verified bidirectional
   relationship. MicroMoth-quilt enters the view at full VERIFIED mass.
   The view now: **fleet-murmur 15.2% · pong-quilt 15.2%** (tie) ·
   quilt-show 8.0% · quilt-tools 8.0% · git-agent 7.6% · jev-quilt 7.6% ·
   micrograd-quilt 7.6% · MicroMoth-quilt 7.6% · moth-waveform 7.6% ·
   quilt-cowboy 7.6% · quilt-stone 7.6% · quilt-arcade 0.8%.
