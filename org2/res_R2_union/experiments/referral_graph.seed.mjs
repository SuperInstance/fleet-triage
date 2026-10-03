// Referral Graph — seed v1 (Casey 12:03 mandate, PoC).
//
// One sheet, three repos seeded: quilt-tools <-> quilt-show <-> quilt-arcade.
// Honesty note (the PoC's first finding): at seed time ZERO edges carry the
// mandate's currency — a merged PR IN THE TARGET repo citing the technique.
// quilt-show has no merged PRs at all (episodes direct-pushed); quilt-arcade's
// merged PRs cite the quilt-main playtest report, not a seeded-repo technique.
// So every real edge is PENDING with provenance (where the finding lives).
// The mesh starts by measuring what speculation cannot buy.
//
// UPDATE 2026-09-26: the first edge earned currency. quilt-show PR #1
// ("E3 verification record: script<->sim claim map + referral edge to
// quilt-tools PR #3") MERGED 2026-09-25T19:14:08Z (merge a2f82a35) — a
// merged PR in the to-node's repo citing the S2 driftwatch technique.
// Edge qt-s2-driftwatch -> qs-ep2 is therefore VERIFIED=1.0 with
// receipt SuperInstance/quilt-show#1. The other four edges stay PENDING.
// The empty-currency state (Finding #1) is broken; the view now moves.
//
// UPDATE 2026-09-26 (later): a third repo pair enters the sheet — the
// candidate surfaced by the 11:11 pulse's org review (queue file). git-agent
// PR #1 ("quilt_emit: vessel lifecycle events -> quilt 5-opcode WAL",
// MERGED 2026-09-26T00:27:18Z, merge 6bc099a) implements the five-opcode WAL
// spine whose canonical source is AI-Writings/algebra.md ("The Five
// Opcodes"). HONESTY: the merged code cites the DOCTRINE ("the fleet's
// quilt kernel speaks five opcodes") but never names the source repo, so
// the weight law is NOT met — booked PENDING with provenance, upgrade path
// = a follow-up citation naming algebra.md in-repo. Never self-upgrade.
// UPDATE 2026-09-26 (pm): the SECOND edge earned currency, breaking the
// single-edge monopoly. pong-quilt PR #28 ("R21: receipted quantum-coin
// champion tiebreak (cites quilt-quant coin-toss-v1)") MERGED
// 2026-09-26T05:27:42Z (merge b14791f) — a merged PR in the to-node's repo
// citing quilt-quant's live coin-toss-v1 engine (core.js VERIFIED_CLAIMS
// 'quantum-tiebreak' entry + tools/prerun.js seeded-mock citation, both live
// on main). Edge quant-coin-toss -> qq-quantum-tiebreak is VERIFIED=1.0 with
// receipt SuperInstance/pong-quilt#28. Two new nodes/repos enter the sheet:
// quilt-quant (from-side technique) and pong-quilt (to-side consumer).
//
// UPDATE 2026-09-26 (evening): the FOURTH edge earned currency — and it is
// jev-quilt's FIRST outgoing edge, minted by a repo that did not exist when
// the graph was seeded. quilt-cowboy PR #1 ("jev substance gate: jev-quilt
// doctrine on the paper-generation output gate", MERGED 2026-09-26T09:12:37Z,
// merge a3feccca) wires jev-quilt's substance noul + 0.6 admit threshold onto
// the cowboy v3 paper gate, citing SuperInstance/jev-quilt BY NAME in-repo
// (README.md "The JEV Substance Gate" + jev_substance_gate.py CITATION const
// + module docstring). The weight law is met: a merged PR in the to-node's
// repo names the source repo. Edge jq-substance-noul -> qb-jev-gate is
// VERIFIED=1.0 with receipt SuperInstance/quilt-cowboy#1. This was flagged as
// the synergy candidate in the 16:11 pulse (jev-quilt had zero outgoing
// currency; quilt-doctor named the length-proxy stand-in the gate replaces).
//
// UPDATE 2026-09-26 (evening): the THIRD edge earned currency, completing
// the day's arc doctrine -> code -> citation -> currency. git-agent PR #4
// ("docs: cite canonical opcode source (AI-Writings/algebra.md) in
// GRAND-QUILT — upgrades referral edge to VERIFIABLE") MERGED
// 2026-09-26T09:11:41Z (merge 8d6c31a) — a merged PR in the to-node's repo
// (git-agent) that names the from-source by name and URL
// (docs/GRAND-QUILT.md provenance block: 'Its canonical source is
// [AI-Writings/algebra.md](...)' + the edge name, citing the weight law
// itself). Edge aw-quint-opcode -> ga-quilt-emit is therefore VERIFIED=1.0
// with receipt SuperInstance/git-agent#4. The upgrade path booked at
// PENDING-time was followed exactly; never self-upgraded — the merge did it.
//
// UPDATE 2026-09-26 (late): the FIFTH edge earned currency — and it is the
// first edge whose TO-node is a repo born after the graph was seeded, plus
// the first edge where the honest direction is from pong-quilt OUTWARD.
// fleet-murmur PR #2 ("Honesty-receipts pass: transport modes, receipt
// ledger, quality-gate seam, claims registry", MERGED 2026-09-26T19:08:16Z,
// merge 5391ba56) names SuperInstance/pong-quilt BY NAME in-repo three
// times in CROSS-POLLINATE.md: the QA-REFUSAL honesty pins as the
// transport-honesty contract (a black-hole transport must not score 100%
// coverage), the session WAL (tools/wal-session.js) as the receipt-ledger
// substrate, and the VERIFIED_CLAIMS + readme-count registry as the claims
// registry shape. HONESTY NOTE on direction: the weight law requires the
// receipt to be a merged PR IN THE TO-NODE'S REPO, so the edge books
// pq-session-wal -> fm-honesty-receipts (receipt SuperInstance/fleet-murmur#2
// targets fleet-murmur, the to-node's repo). The 03:23 edge-watch note wrote
// the direction fm->pq from the citation's perspective; the substrate's
// receipt-repo rule is the constitution — the merge in the citing repo
// earns currency FOR the cited technique flowing INTO that repo.
//
// UPDATE 2026-09-27 (morning): the SEVENTH edge earned currency — booked
// from the exact lane the 05:24 pulse opened ("on merge books edge qgs→fm,
// target repo=fm — not fm→qgs as the pulse note guessed"). fleet-murmur
// PR #3 ("qgs adapter: live-verify seam against real quality-gate-stream
// (stale-API fix)", MERGED 2026-09-26T23:08:45Z, merge 8df75c6) rewrites
// tools/quality_gate_adapter.py against the live quality-gate-stream API
// (CustomCheck(name, fn), evaluate() -> GateResult.outcome, strict=True
// default — the pre-merge adapter called a stale API and raised TypeError /
// AttributeError against the real package) and names
// SuperInstance/quality-gate-stream BY NAME in-repo at three anchored sites:
// the adapter module docstring ("Cross-repo seam (cross-pollination
// receipt): SuperInstance/quality-gate-stream"), VERIFIED_CLAIMS.md VC10,
// and tests/test_qgs_adapter_glue.py (live pins import the real package,
// abstain as labeled skips when uninstalled, never fake green; an always-on
// pin asserts the citation string is present in the adapter source). Two
// sibling repos built the two halves of the review-honesty doctrine the
// same day (fleet-murmur#2 quality-gate seam / quality-gate-stream#2 strict
// mode); this merge pins them against dialect drift — the same
// exporter-in-consumer / live-verify-in-producer shape as the R26
// wal-export -> quilt-doctor seam. HONESTY on direction: the citing merge
// is in fleet-murmur, so the edge books qgs-strict-gate -> fm-qgs-adapter
// (currency flows INTO the citing repo), exactly as pre-booked.
// fleet-murmur becomes the first repo carrying TWO VERIFIED inbound edges.
//
// Weight law: PENDING = 0.05 (speculation is cheap) / VERIFIED = 1.0 (a
// merged PR in the to-node's repo cites the from-technique).
//
// UPDATE 2026-09-27 (late morning): the EIGHTH edge earned currency — and it
// is the first edge the graph's own repo earns as a TO-node from the
// commons/G11 lane, closing the loop the 08:11 pulse flagged (jev-quilt#37
// hardened the exact blind-sum Goodhart surface this graph still had). The
// lane was opened as that pulse's synergy candidate and shipped in
// quilt-tools PR #17 ("referral-graph: the G11 trust lever", MERGED
// 2026-09-27T01:27:12Z, merge d14fb44): viewTrusted() re-scales every edge
// by its TARGET repo's EARNED trust (effective = trust·weight; unseen source
// defaults to 0), ported FROM SuperInstance/jev-quilt BY NAME in-repo (src
// comment naming SuperInstance/jev-quilt commons.py trust_weighted() /
// provenance_merge(), plus the REFERRAL_GRAPH.md entry). The weight law is
// met in the TO-node's repo: the merge landing IN quilt-tools names the
// from-source. Edge jq-commons-g11 -> qt-trust-lever is VERIFIED=1.0 with
// receipt SuperInstance/quilt-tools#17, provenance SuperInstance/jev-quilt#37
// (the G11 merge that hardened the commons against weight inflation — the
// exact anti-Goodhart term this graph's blind view needed; Pin 11 pins the
// port's fixture semantics and the citation string).
//
// UPDATE 2026-09-27 (dawn): the SIXTH edge earned currency — and the second
// repo born after seeding enters as a to-node. moth-waveform PR #1
// ("Phase 2: duck-sensitivity receipts — which duck carries the regime?",
// MERGED 2026-09-26T21:06:24Z, merge dc1a142) cites fleet-murmur's vacuity
// scar BY NAME in-repo, at code level: sensitivity.py's health gate
// ("a gate that passes without a live floor measurement passes vacuously
// (fleet-murmur scar)") exists because fleet-murmur#2's transport-honesty
// contract proved a black-hole transport can score 100% coverage — the same
// honesty doctrine as the fm-honesty-receipts node this edge books from.
// The README "Receipts doctrine" section also names pong-quilt (honesty
// pins), hermit (quilt-WAL), quilt-doctor (moth-ledger trial balance),
// quality-gate-stream (REFUSAL receipts) and fleet-murmur (transport modes)
// as doctrine lineage. HONESTY: the load-bearing citation is the code-level
// scar; the README list is lineage, not technique. Edge
// fm-honesty-receipts -> mw-floor-gate is VERIFIED=1.0 with receipt
// SuperInstance/moth-waveform#1. Found by the 06:56 pulse's discovery-class
// org scan (the discovery tool reports; a human verified the citation shape).
//
// UPDATE 2026-09-27 (midday): the NINTH edge earned currency — and the
// stone lane lands exactly as pre-booked by the 11:04 pulse ("on merge,
// referral graph books NINTH VERIFIED edge pq-stone-v1-export ->
// stone-forward-adopt"). quilt-stone PR #1 ("smoke 12b: pong-quilt R36 is
// the first stone-v1 forward-format adopter — exporter's real stone-v1
// output pinned (verify/tamper/splice) + README adoption record", MERGED
// 2026-09-27T04:20:06Z, merge 093c1b1) cites SuperInstance/pong-quilt BY
// NAME in-repo at two anchored sites: README.md "Forward-format adopters"
// ("SuperInstance/pong-quilt PR #46 (merged 2026-09-27)") and smoke.mjs
// section 12b — five pins over the EXACT exporter bytes generated live from
// pong-quilt's tools/wal-export.js toStoneV1() at PR #46's merge tip (not
// retyped): header row is the mandatory stone.header with tool=pong-quilt
// (producer named, not laundered), post-seal edit -> hash_mismatch, row
// splice -> continuity break. The weight law is met in the TO-node's repo.
// quilt-stone is the third to-node born after the graph was seeded (after
// fleet-murmur and moth-waveform), and pong-quilt earns its SECOND outgoing
// edge — its R36 wal-export lane now both RECEIVES currency (pq->fm, edge
// five) and PAYS it forward into the fleet's canonical receipt-chain
// verifier. HONESTY: the 09:57 edge-watch flagged quilt-stone as
// LANE-AFFECTING (all receipt/WAL export lanes should target/verify-through
// stone-v1); this edge records the adoption, not the mandate itself.
//
// UPDATE 2026-09-27 (afternoon): the TENTH edge earned currency — the
// stone-v2 sign lane, pre-booked twice (14:56 "on quilt-stone#4 merge the
// pilot opens + candidate VERIFIED edge"; 16:04 R39 pilot shipped closed
// against the sign-lane tip). Both merges landed in Casey's burst:
// quilt-stone PR #4 ("STONE-V2-PILOTS sign lane: signTip/verifyTipSignature
// ed25519 tip staples", MERGED 2026-09-27T09:02:01Z, merge 023edbed) ships
// the sign lane, and pong-quilt PR #51 ("R39: STONE-V2-PILOTS first sign
// pilot — producer staples the birth-seal chain's tip", MERGED
// 2026-09-27T09:03:15Z, merge 07384ac2) cites SuperInstance/quilt-stone BY
// NAME in-repo at three anchored sites: PLAYLOG Round 39 ("the stone-v2 sign
// lane, SuperInstance/quilt-stone PR #4, STONE-SPEC.md §4.6.2"), the
// citation pin in tests/stone-sign-glue.test.js, and core.js
// VERIFIED_CLAIMS 'stone-sign-pilot' ("whenever the named quilt-stone
// checkout ships the stone-v2 sign lane"). HONESTY ON DIRECTION: the 16:04
// pulse note guessed the edge books pong-quilt→quilt-stone; the substrate's
// receipt-repo rule is the constitution (edge #5 booked the same way) —
// the citing merge is IN pong-quilt, so the edge books
// stone-sign-lane -> pq-sign-pilot: the verifier's signature primitive
// flowing INTO the producer that staples with it. quilt-stone earns its
// FIRST OUTGOING edge (it received currency at edge #9 five hours earlier);
// pong-quilt joins fleet-murmur as the second double-mass repo — receiving
// the coin (edge #2) AND the sign lane (edge #10).
//
// Weight law: PENDING = 0.05 (speculation is cheap) / VERIFIED = 1.0 (a
// merged PR in the to-node's repo cites the from-technique).
//
// UPDATE 2026-09-30 (14:56 pulse): the TWELFTH edge earned currency — the
// first lab↔ledger bidirectional pair, and the booking corrects a false
// negative. The 14:38 pulse's citation scan reported micrograd-quilt main
// citing SuperInstance/MicroMoth-quilt ZERO times despite consuming the
// exp018-036 receipt lineage, and queued a citation PR. Re-audit 2026-09-30
// (this pulse) found that scan WRONG: micrograd-quilt PR #7 ("qcells
// exp020-036: tie-band replication → two-regime desert hazard →
// triplet-stream rate-lane closure", MERGED 2026-09-30T04:49:20Z, merge
// 44de605) is a merged PR IN THE TO-NODE'S REPO whose diff ADDS
// labs/qcells/FINDINGS.md citing SuperInstance/MicroMoth-quilt BY NAME at
// four anchored sites (the lab charter header, the import-baseline manifest
// pin on MicroMoth-quilt main, the honest-limit gap posted on
// MicroMoth-quilt#3, the receipts/ dir lane note) plus
// docs/synergy-scan-2026-09-30-0711.md consuming MicroMoth-quilt#23/#24's
// MERGED sealed findings to redirect the lab's own queue ("do not re-run").
// No citation PR was opened — Casey's merge already earned the edge, and
// opening one would have been citation spam on a false premise. Edge
// mm-sealed-receipts -> mgq-qcells-lab is VERIFIED=1.0 with receipt
// SuperInstance/micrograd-quilt#7, provenance SuperInstance/MicroMoth-quilt#24
// (the exp018 seal the synergy scan consumes). The MIRROR edge is booked
// PENDING the same hour: MicroMoth-quilt#24 (MERGED 2026-09-29T21:25:32Z,
// merge 664506a5) seals the lab's exp018 autopsy and names the producer
// only as "the qcells lab (workspace/labs/qcells)" — a workspace path,
// never the repo SuperInstance/micrograd-quilt. That is the git-agent#1
// doctrinal-citation shape, which this graph booked PENDING until
// git-agent#4 named algebra.md — same law, upgrade path = a MicroMoth-quilt
// PR naming SuperInstance/micrograd-quilt in-repo (discovery now watches
// that stream). MicroMoth-quilt and micrograd-quilt become the fourth and
// fifth repos born after seeding; the lab is the producer, the ledger the
// seal, and the graph records both directions honestly.
//
// Each edge carries its kill switch: falsification_condition — the observed
// evidence string that would refute the claim (probe() books the death as a
// REFUSED row; the scar stays in the graph).

export const SEED = {
  name: 'referral-graph-v1',
  repos: ['quilt-tools', 'quilt-show', 'quilt-arcade', 'git-agent', 'AI-Writings'],
  repos: ['quilt-tools', 'quilt-show', 'quilt-arcade', 'quilt-quant', 'pong-quilt', 'jev-quilt', 'quilt-cowboy', 'fleet-murmur', 'moth-waveform', 'quality-gate-stream', 'quilt-stone', 'MicroMoth-quilt', 'micrograd-quilt'],

  nodes: [
    { id: 'qt-api-lab', repo: 'quilt-tools', kind: 'lab',
      summary: 'api-lab R1: what the typed oracle can and cannot see (E1 ordinal rungs, E2 receipts flip credit)' },
    { id: 'qt-s2-driftwatch', repo: 'quilt-tools', kind: 'experiment',
      summary: 'S2 drift map: oracle has no variance-collapse concept; shape-beats-threshold not prompt-visible' },
    { id: 'qt-s3-tide', repo: 'quilt-tools', kind: 'experiment',
      summary: 'S3 quantum-tided budget: PENDING/ENTANGLED/COLLAPSED witnessed pre-outcome; insolvency refuses absolutely' },
    { id: 'qs-ep2', repo: 'quilt-show', kind: 'episode',
      summary: 'Episode 2 The Receipt: a claim must be DEMONSTRATED with receipts, never asserted in prose' },
    { id: 'qs-ep3', repo: 'quilt-show', kind: 'episode',
      summary: 'Episode 3 player work: waveform + watchers + drag-to-reshape' },
    { id: 'qa-negspace', repo: 'quilt-arcade', kind: 'constitution',
      summary: 'NEGATIVE_SPACE.md: declined patches and divergences documented as first-class constitution' },
    { id: 'qa-plugins', repo: 'quilt-arcade', kind: 'plugin-system',
      summary: 'Modular plugins: every game a two-file plugin (module + manifest), receipt-rendered run_all' },
    { id: 'aw-quint-opcode', repo: 'AI-Writings', kind: 'canon',
      summary: 'algebra.md "The Five Opcodes": BIND/LINK/EFFECT/VIEW/TICK (+FORGET) — the fleet WAL spine, 5 laws, canonical semantics' },
    { id: 'ga-quilt-emit', repo: 'git-agent', kind: 'agent-integration',
      summary: 'quilt_emit.py: vessel lifecycle events -> fnv1a hash-chained 5-opcode JSONL WAL; first quilt-native fleet agent' },
    { id: 'quant-coin-toss', repo: 'quilt-quant', kind: 'lab',
      summary: 'coin-toss-v1: the moth-quantum engine — receipted quantum coin, every flip journaled' },
    { id: 'qq-quantum-tiebreak', repo: 'pong-quilt', kind: 'experiment',
      summary: 'R21 champion selection: equal-fitness ties broken by a receipted quantum coin via the makeEvaluator onTie seam' },
    { id: 'jq-substance-noul', repo: 'jev-quilt', kind: 'lab',
      summary: 'the substance noul + 0.6 admit threshold (JevLens mean >= 0.6 reads VERIFIABLE) — the fleet\'s live judgment on generated text' },
    { id: 'qb-jev-gate', repo: 'quilt-cowboy', kind: 'gate-integration',
      summary: 'v3 output gate: the length-only admission proxy (synthesis_len >= 300) replaced by jev-quilt\'s substance noul, meter mode default + COWBOY_JEV_ENFORCE hard-hold' },
    { id: 'pq-session-wal', repo: 'pong-quilt', kind: 'experiment',
      summary: 'R26 session-WAL lane: receipt-panel rows re-anchored into the fleet five-opcode quilt WAL (tools/wal-session.js / wal-export.js), R24 canonical-md5 lineage doctrine, doctor-verdict lens on the QA-REFUSAL seam' },
    { id: 'fm-honesty-receipts', repo: 'fleet-murmur', kind: 'integration',
      summary: 'honesty-receipts pass: transport-honesty contract (black-hole transport must not score 100%), fnv1a hash-chained MurmurLedger receipt substrate, VERIFIED_CLAIMS-style claims registry' },
    { id: 'mw-floor-gate', repo: 'moth-waveform', kind: 'lab',
      summary: 'duck-sensitivity receipts: the no-op health gate measures the floor in-run because a gate without a live floor measurement passes vacuously (the fleet-murmur scar); every threshold names its calibration' },
    { id: 'qgs-strict-gate', repo: 'quality-gate-stream', kind: 'gate-integration',
      summary: 'review-honesty scoring gate: strict mode, routing + rolling windows, installable package — rumors/payloads below threshold are REFUSED with a named reason, never silently scored' },
    { id: 'fm-qgs-adapter', repo: 'fleet-murmur', kind: 'integration',
      summary: 'quality_gate_adapter: fleet-murmur\'s mill gate routed through the REAL quality-gate-stream package (CustomCheck/evaluate API, closed-by-default, absence returns None never faked), pinned by 4 live package-run pins + weight-law citation naming SuperInstance/quality-gate-stream' },
    { id: 'fm-refusal-ledger', repo: 'fleet-murmur', kind: 'integration',
      summary: 'the IETF refusal-events ledger lane: docs/ietf-kamimura-refusal-events-ledger.md audits pong-quilt main\'s named refusal-events corpus against draft-kamimura-scitt-refusal-events-03 (abstract sha-pinned; source re-verified still -03 on datatracker 2026-10-01), FAIL-first corpus pin via tests/test_refusal_events_ledger.py (fleet-murmur#8, merged 2026-09-30T19:31:12Z)' },
    { id: 'jq-commons-g11', repo: 'jev-quilt', kind: 'commons',
      summary: 'the G11 trust-weighted commons: jev_quilt/commons.py trust_weighted() / provenance_merge() — cross-fleet gluing re-scaled by earned per-source trust, default 0 for unseen sources (jev-quilt#37, merged 2026-09-27T00:06:03Z)' },
    { id: 'qt-trust-lever', repo: 'quilt-tools', kind: 'experiment',
      summary: 'the G11 trust lever on the referral view: viewTrusted({trust, default:0}) re-scales each edge by its target repo\'s earned trust — the blind summed-weight view is buyable, trust is the lever (quilt-tools#17, merged 2026-09-27T01:27:12Z)' },
    { id: 'pq-stone-v1-export', repo: 'pong-quilt', kind: 'experiment',
      summary: 'R36 wal-export stone-v1 lane: tools/wal-export.js toStoneV1() re-anchors the live receipt-panel WAL into quilt-stone\'s forward format (stone.header + hash-chained rows, tool=pong-quilt named) — first forward-format adopter (pong-quilt#46, merged 2026-09-27)' },
    { id: 'stone-forward-adopt', repo: 'quilt-stone', kind: 'integration',
      summary: 'the canonical receipt-chain verifier adopts pong-quilt R36 as first stone-v1 forward-format adopter: smoke section 12b pins the exporter\'s REAL output (verify/tamper/splice) + README Forward-format adopters record (quilt-stone#1, merged 2026-09-27T04:20:06Z)' },
    { id: 'stone-sign-lane', repo: 'quilt-stone', kind: 'lab',
      summary: 'the stone-v2 sign lane: signTip/verifyTipSignature ed25519 tip staples — signed msg = "stone-v2"||tip_row_hash, stored tip binds the signature to the exact chain, post-sign body edit re-seals hashes green but the signature still refuses (the laundering pin) (quilt-stone#4, merged 2026-09-27T09:02:01Z)' },
    { id: 'pq-sign-pilot', repo: 'pong-quilt', kind: 'experiment',
      summary: 'R39 STONE-V2-PILOTS first sign pilot: the prerun producer staples the R37 birth-seal chain\'s tip via the named quilt-stone checkout\'s signTip — signs a COPY (unsigned stone-v1.json stays canonical), verifyTipSignature BEFORE write, refused staple bricks the run, ships closed with a labeled skip (pong-quilt#51, merged 2026-09-27T09:03:15Z)' },
    { id: 'pq-named-refusals', repo: 'pong-quilt', kind: 'experiment',
      summary: 'the named refusal-events corpus on pong-quilt main: QA-REFUSAL (R12), byo-qpam-fallback (R16), WAL-EXPORT/REFUSED + WAL-EXPORT/EMPTY (R30), SEAL/REFUSED, and at R67 SAVE/COEV-EMPTY + LOAD/COEV-MALFORMED (SAVE/COEV-UNSTABLE R64 supersession lineage kept in claim prose) — every refusal names its kind and reason, zero prompt content' },
    { id: 'aw-jev-kat', repo: 'AI-Writings', kind: 'instrument',
      summary: 'AI-Writings#70 labs/jev-kat/jev_kat.mjs — the JEV known-answer control instrument: canonical KAT cases characterising the fleet oracle before its judgment gates anything (merged 2026-09-29T21:26:53Z)' },
    { id: 'jq-kat-bridge', repo: 'jev-quilt', kind: 'integration',
      summary: 'jev-quilt#47 tools/jev_kat_bridge.mjs — bridge fetching the canonical AI-Writings KAT instrument at pinned commit 3f8405888 (sha256 5f280b8b…e1cc5 verified pre-exec), receipting the live characterisation under jev_sessions/, offline gate exit 0/2/3 (MERGED as SuperInstance/jev-quilt#47 2026-09-30T00:18:30Z, merge 4591258994)' },
    { id: 'mm-sealed-receipts', repo: 'MicroMoth-quilt', kind: 'lab',
      summary: 'the sealed receipt lineage on the MicroMoth import substrate: fnv1a-64 import-baseline manifest + per-receipt sha256 byte-match tables (manifest mismatch voids the seal), runner sealed as the exact bytes executed, FAIL-first pins per receipt (exp016 fba4ec7 #22 / exp017 #23 / exp018 664506a5 #24, all merged 2026-09-29)' },
    { id: 'mgq-qcells-lab', repo: 'micrograd-quilt', kind: 'lab',
      summary: 'the qcells local lab (labs/qcells): novel experimentation on the MicroMoth substrate, exp018-036 lineage with per-exp sealed results + telemetry + FINDINGS.md, receipts pushed for sealing into MicroMoth-quilt (micrograd-quilt#7 merged 2026-09-30T04:49:20Z)' },
  ],

  edges: [
    {
      from: 'stone-sign-lane', to: 'pq-sign-pilot',
      claim: 'quilt-stone\'s stone-v2 sign lane gives a receipt chain a producer-identity staple — but a signature primitive nobody staples with is a library, not a doctrine. CURRENCY EARNED 2026-09-27: pong-quilt PR #51 ("R39: STONE-V2-PILOTS first sign pilot — producer staples the birth-seal chain\'s tip", MERGED 2026-09-27T09:03:15Z, merge 07384ac2) lands the first real adoption IN THE PRODUCER\'s repo: tools/prerun.js staples the R37 birth-seal chain\'s tip through the named quilt-stone checkout\'s signTip/verifyTipSignature (signs a COPY — the unsigned stone-v1.json stays canonical; verifyTipSignature with the producer public key runs BEFORE write; a refused staple bricks the run exit 1; the seam ships closed with a labeled skip when the checkout has no signTip — never silent), citing SuperInstance/quilt-stone BY NAME in-repo at three anchored sites: PLAYLOG Round 39 ("the stone-v2 sign lane, SuperInstance/quilt-stone PR #4, STONE-SPEC.md §4.6.2"), the citation pin in tests/stone-sign-glue.test.js, and core.js VERIFIED_CLAIMS \'stone-sign-pilot\'. The 4 glue pins ran LIVE against the sign-lane tip 047be72 before merge: seal links 5 + staple ok + the post-sign FORGED-edit laundering refusal ("signed tip does not match the chain tip") + wrong-key refusal. HONESTY ON DIRECTION: the 14:56/16:04 pulse notes guessed pong-quilt→quilt-stone; the substrate\'s receipt-repo rule (edge #5 precedent) books stone-sign-lane -> pq-sign-pilot — the merge in the citing repo earns currency FOR the cited technique flowing INTO that repo. quilt-stone\'s FIRST outgoing edge (it received edge #9 five hours earlier); pong-quilt joins fleet-murmur as the second double-inbound-mass repo — the sign lane lands in the same repo that already breaks ties by quantum coin. Pre-booked twice, earned by Casey\'s merge burst, never self-upgraded.',
      weight: 'VERIFIED',
      provenance: 'SuperInstance/quilt-stone#4', // the sign-lane merge (023edbed) whose signTip/verifyTipSignature the pilot staples with
      receipt: 'SuperInstance/pong-quilt#51',
      falsification_condition: 'a pong-quilt prerun run against a quilt-stone checkout shipping signTip where the staple file is written without verifyTipSignature passing first, or the post-sign FORGED-edit laundering case verifies green, or the SuperInstance/quilt-stone citation removed from PLAYLOG Round 39 / tests/stone-sign-glue.test.js / core.js VERIFIED_CLAIMS',
    },
    {
      from: 'pq-stone-v1-export', to: 'stone-forward-adopt',
      claim: 'pong-quilt\'s R36 wal-export lane produces real stone-v1 forward-format chains from the live receipt panel — but an export format nobody verifies through is a dialect, not a standard. CURRENCY EARNED 2026-09-27: quilt-stone PR #1 ("smoke 12b: pong-quilt R36 is the first stone-v1 forward-format adopter", MERGED 2026-09-27T04:20:06Z, merge 093c1b1) lands the adoption IN THE VERIFIER\'s repo: smoke section 12b pins five checks over the exporter\'s EXACT bytes (generated live from tools/wal-export.js toStoneV1() at PR #46\'s merge tip, not retyped) — alg=stone-v1/genesis canonical/links=5, the mandatory stone.header row carries tool=pong-quilt (producer named, not laundered), a post-seal edit is caught as hash_mismatch, a row splice breaks continuity — and README.md\'s Forward-format adopters section names SuperInstance/pong-quilt PR #46 BY NAME. Weight law met in the to-node\'s repo. Third to-node born after seeding (fleet-murmur, moth-waveform, quilt-stone); pong-quilt\'s SECOND outgoing edge — it both receives currency (pq->fm) and pays it forward into the canonical verifier. Pre-booked at 11:04 ("on merge, referral graph books NINTH VERIFIED edge"), earned by Casey\'s merge, never self-upgraded.',
      weight: 'VERIFIED',
      provenance: 'SuperInstance/pong-quilt#46', // the R36 merge whose toStoneV1() output the smoke pins
      receipt: 'SuperInstance/quilt-stone#1',
      falsification_condition: 'a quilt-stone smoke 12b run where the pinned pong-quilt fixture verifies under anything but stone-v1 semantics, or the SuperInstance/pong-quilt citation removed from README.md Forward-format adopters / smoke.mjs section 12b',
    },
    {
      from: 'jq-commons-g11', to: 'qt-trust-lever',
      claim: 'The referral graph\'s blind view sums edge weight per target repo, and weight is cheap to inflate: a source the fleet has not earned to trust can merge N junk-citation PRs into its own repo and buy itself mass — the exact Goodhart surface jev-quilt\'s G11 hardened in the commons the same week. CURRENCY EARNED 2026-09-27: quilt-tools PR #17 (merged 2026-09-27T01:27:12Z, merge d14fb44) ports the G11 trust lever into the graph\'s weight law — viewTrusted({trust, default:0}) re-scales every edge by its TARGET repo\'s EARNED trust (effective = trust·weight; an unseen source defaults to 0 and contributes NOTHING until the fleet earns reason to trust it; trust 1 everywhere reduces exactly to the blind view) — citing SuperInstance/jev-quilt commons.py trust_weighted() / provenance_merge() BY NAME in-repo (src/referral_graph.mjs comment + experiments/REFERRAL_GRAPH.md), the same honesty pattern as the moth-waveform code-level scar. This was the 08:11 pulse\'s synergy candidate, shipped exactly as flagged; Pin 11 pins the fixture semantics (blind view BUYABLE at >90% junk mass; unseen junk → 0; trust is the lever) and the citation string. First edge where the graph\'s own repo is the TO-node of a commons-lane technique; pre-hardens the currency against the weight-inflation attack the R8 Goodhart lane red-teams.',
      weight: 'VERIFIED',
      provenance: 'SuperInstance/jev-quilt#37', // the G11 merge that landed trust_weighted()/provenance_merge() on jev-quilt main
      receipt: 'SuperInstance/quilt-tools#17',
      falsification_condition: 'the referral view mass computed from summed edge weights with no earned-trust term while junk-citation PRs remain mergeable into a self-controlled repo, or the SuperInstance/jev-quilt commons.py citation removed from src/referral_graph.mjs / REFERRAL_GRAPH.md',
    },
    {
      from: 'qgs-strict-gate', to: 'fm-qgs-adapter',
      claim: 'Two sibling repos built the two halves of the review-honesty doctrine on the same day — fleet-murmur#2 shipped a quality-gate seam, quality-gate-stream#2 shipped strict-mode scoring — and an unadaptered dialect drift between them would silently corrupt every rumor score crossing the seam. CURRENCY EARNED 2026-09-26: fleet-murmur PR #3 (merged 2026-09-26T23:08:45Z, merge 8df75c6) lands tools/quality_gate_adapter.py rewritten against the LIVE quality-gate-stream API (the pre-merge adapter raised TypeError/AttributeError against the real package — stale-API broken at birth, the fix shipped in the same PR that named the source), citing SuperInstance/quality-gate-stream BY NAME in-repo at three anchored sites: the adapter module docstring, VERIFIED_CLAIMS.md VC10, and tests/test_qgs_adapter_glue.py (4 live pins run the real package, labeled skips when uninstalled, never fake green; an always-on pin asserts the citation string survives in source). Direction honesty: the merge is in fleet-murmur, so per the substrate receipt-repo rule the edge books qgs-strict-gate -> fm-qgs-adapter — currency flows INTO the citing repo, exactly the direction pre-booked when the lane opened. fleet-murmur is the first repo carrying two VERIFIED inbound edges; the exporter-in-consumer / live-verify-in-producer shape mirrors the R26 wal-export -> quilt-doctor seam.',
      weight: 'VERIFIED',
      provenance: null, // the technique lives on quality-gate-stream main (strict-mode gate, installable package); the receipt is the fleet-murmur merge
      receipt: 'SuperInstance/fleet-murmur#3',
      falsification_condition: 'the fleet-murmur adapter scoring a rumor through a hand-rolled reimplementation while quality-gate-stream is installed, or the SuperInstance/quality-gate-stream citation removed from the adapter source / VC10 / the glue pins',
    },
    {
      from: 'fm-honesty-receipts', to: 'mw-floor-gate',
      from: 'fm-honesty-receipts', to: 'mw-floor-gate',
      claim: 'fleet-murmur\'s transport-honesty contract is a scar other instruments must carry: a black-hole transport scored 100% coverage until the honesty REFUSAL receipt named it. moth-waveform\'s no-op health gate exists for exactly that reason. CURRENCY EARNED 2026-09-26: moth-waveform PR #1 (merged 2026-09-26T21:06:24Z, merge dc1a142) cites the scar BY NAME in-repo at code level — sensitivity.py: "a gate that passes without a live floor measurement passes vacuously (fleet-murmur scar)" — plus the README Receipts-doctrine section naming fleet-murmur (transport modes) among the doctrine lineage (pong-quilt honesty pins, hermit quilt-WAL, quilt-doctor moth-ledger trial balance, quality-gate-stream REFUSAL receipts). Load-bearing citation is the code-level scar; the README list is lineage, not technique. Second to-node born after the graph was seeded.',
      weight: 'VERIFIED',
      provenance: null, // the scar lives on fleet-murmur main (CROSS-POLLINATE.md transport-honesty contract); the receipt is the moth-waveform merge
      receipt: 'SuperInstance/moth-waveform#1',
      falsification_condition: 'a moth-waveform sensitivity receipt whose no-op health gate passed without a live floor measurement (noop row absent from the receipt) or the fleet-murmur scar citation removed from sensitivity.py',
    },
    {
      from: 'pq-session-wal', to: 'fm-honesty-receipts',
      claim: 'pong-quilt\'s receipt lineage — QA-REFUSAL honesty pins (a claim must name how it knows), the session-WAL exporter re-anchoring the live receipt panel into the fleet five-opcode quilt WAL, and the VERIFIED_CLAIMS + readme-count registry pinned two-way against the live suite — is exactly the contract a gossip mesh needs before it scores delivery coverage. CURRENCY EARNED 2026-09-26: fleet-murmur PR #2 (merged 2026-09-26T19:08:16Z, merge 5391ba56) cites SuperInstance/pong-quilt BY NAME in-repo, three times in CROSS-POLLINATE.md: the QA-REFUSAL seam (R23-R28 honesty pins) as the transport-honesty contract, tools/wal-session.js\'s session WAL as the receipt-ledger substrate (\"one verifier reads every fleet ledger\"), and the VERIFIED_CLAIMS + readme-count pin as the claims-registry shape. First edge whose to-node is a repo born after the graph was seeded; first outward currency from pong-quilt.',
      weight: 'VERIFIED',
      provenance: null, // the techniques live on pong-quilt main (tools/wal-session.js, core.js VERIFIED_CLAIMS); the receipt is the fleet-murmur merge
      receipt: 'SuperInstance/fleet-murmur#2',
      falsification_condition: 'a murmur gossip round scored 100% delivery coverage with a black-hole transport and no honesty REFUSAL receipt, or the pong-quilt citations removed from CROSS-POLLINATE.md',
    },
    {
      from: 'jq-substance-noul', to: 'qb-jev-gate',
      claim: 'quilt-cowboy\'s admission proxy was length alone — 1,745 generated papers entered the canon on synthesis_len >= 300 and nothing else (RD_QUILT_3_0 admits the length-as-concreteness proxy is a stand-in). CURRENCY EARNED 2026-09-26: quilt-cowboy PR #1 (merged 2026-09-26T09:12:37Z, merge a3feccca) wires jev-quilt\'s substance noul + 0.6 admit threshold onto the v3 output gate, citing SuperInstance/jev-quilt BY NAME in-repo (README.md "The JEV Substance Gate" section + jev_substance_gate.py CITATION const + module docstring), judged through any duck-typed backend exposing available() + decide_batch() — jev_quilt\'s TypeSafeBackend satisfies the protocol directly. First jev-quilt OUTGOING edge: all prior currency flowed show/pong/quant/tools.',
      weight: 'VERIFIED',
      provenance: null, // the doctrine lives on jev-quilt main (substance noul + threshold); the receipt is the to-repo merge
      receipt: 'SuperInstance/quilt-cowboy#1',
      falsification_condition: 'a v3 worklog entry admitted to the canon with jev_substance present below 0.6 and no jev_admitted=False flag, or the CITATION naming SuperInstance/jev-quilt removed from the gate module',
    },
    {
      from: 'quant-coin-toss', to: 'qq-quantum-tiebreak',
      claim: 'A champion-selection tie is a verdict: silent index order is an unwitnessed collapse. pong-quilt\'s R21 wires the makeEvaluator onTie seam to quilt-quant\'s coin-toss-v1 (seeded mock of the live engine, citation verified against quilt-quant lab/play.mjs, every flip journaled — R22 symmetrized the journal). CURRENCY EARNED 2026-09-26: pong-quilt PR #28 (merged 2026-09-26T05:27:42Z, merge b14791f) carries the coin-toss-v1 citation in-repo (core.js VERIFIED_CLAIMS \'quantum-tiebreak\' entry + tools/prerun.js).',
      weight: 'VERIFIED',
      provenance: null, // quilt-quant ships direct-pushed (zero PRs) — the finding lives in lab/play.mjs itself
      receipt: 'SuperInstance/pong-quilt#28',
      falsification_condition: 'a replayed prerun where equal-fitness champions are ordered by array index with no coin flip journaled',
    },
    {
      from: 'qt-s2-driftwatch', to: 'qs-ep2',
      claim: 'S2 measured the exact wall behind E2\'s thesis: shape-beats-threshold cannot be asserted in a prompt — the episode\'s "demonstrate, don\'t assert" now has an api-lab receipt map under it. CURRENCY EARNED 2026-09-26: quilt-show PR #1 (merged 2026-09-25T19:14:08Z, merge a2f82a35) carries this citation in-repo (docs/E3-VERIFICATION.md referral-edge record + episode-3/sim.mjs header); quilt-show PR #3 (ep4-instruments, merged 21:30Z) re-cites it.',
      weight: 'VERIFIED',
      provenance: 'SuperInstance/quilt-tools#3',
      receipt: 'SuperInstance/quilt-show#1',
      falsification_condition: 'a replayed stream where the 0.80 threshold fires before shape on st02 slow drift',
    },
    {
      from: 'qt-api-lab', to: 'qs-ep2',
      claim: 'E2 quantified persuasion risk: receipts flip credit 1/4 -> 4/4 whether or not the underlying claim is true — Episode 2\'s verifyChain discipline is the counter-move',
      weight: 'PENDING',
      provenance: 'SuperInstance/quilt-tools#5',
      falsification_condition: 'a receipts-inline run where ground-truth agreement does not move vs bare',
    },
    {
      from: 'qt-s3-tide', to: 'qa-plugins',
      claim: 'S3\'s witnessed pre-outcome states (PENDING/ENTANGLED/COLLAPSED) are the receipt shape a quantum coin plugin needs before its verdict drives game state',
      weight: 'PENDING',
      provenance: 'SuperInstance/quilt-tools#4',
      falsification_condition: 'a plugin event driven by a coin outcome with no pre-outcome witness row',
    },
    {
      from: 'qa-negspace', to: 'qt-api-lab',
      claim: 'NEGATIVE_SPACE\'s declined-patch-12 doctrine is the same shape as E2\'s receipts-over-scores: document the divergence, never silently port it — the lab should score claims the same way',
      weight: 'PENDING',
      provenance: 'SuperInstance/quilt-arcade#2',
      falsification_condition: 'a quilt-main PR merging the verbatim patch 12 with no cost-regression receipt',
    },
    {
      from: 'qs-ep3', to: 'qa-plugins',
      claim: 'Episode 3\'s drag-to-reshape watcher loop is a playable reactive surface — the same seam the arcade plugins expose through run_all',
      weight: 'PENDING',
      provenance: null,
      falsification_condition: 'a watcher demo that cannot be re-expressed as a two-file plugin without losing behavior',
    },
    {
      from: 'aw-quint-opcode', to: 'ga-quilt-emit',
      claim: 'AI-Writings/algebra.md defines the five-opcode spine and its laws (BIND idempotent; algebra.md says do not add opcodes); git-agent#1 (MERGED 2026-09-26T00:27:18Z, merge 6bc099a) built quilt_emit.py — vessel events mapped one-to-one to BIND/LINK/EFFECT/VIEW/TICK lines in a hash-chained WAL — on exactly that spine. git-agent#1\'s citation was DOCTRINAL only ("the fleet quilt kernel speaks five opcodes"), the source repo never named — so the edge was booked PENDING with the upgrade path recorded. CURRENCY EARNED 2026-09-26: git-agent PR #4 (merged 2026-09-26T09:11:41Z, merge 8d6c31a) lands the in-repo citation naming AI-Writings/algebra.md by name and URL (docs/GRAND-QUILT.md provenance block, live-verified on git-agent main), exactly the upgrade path booked here.',
      weight: 'VERIFIED',
      provenance: 'SuperInstance/git-agent#1',
      receipt: 'SuperInstance/git-agent#4',
      falsification_condition: 'git-agent quilt_emit.py shipping an opcode mapping that contradicts algebra.md semantics (e.g. VIEW given mutation semantics, or a 6th opcode added) with no algebra reference anywhere in the repo',
    },
    {
      from: 'aw-jev-kat', to: 'jq-kat-bridge',
      claim: 'A fleet oracle instrument consumed by pin-and-digest is doctrine landing in the consumer\'s repo: AI-Writings#70 (MERGED 2026-09-29T21:26:53Z) shipped labs/jev-kat/jev_kat.mjs as the canonical KAT instrument, and SuperInstance/jev-quilt#47 (OPEN at booking 2026-09-30 — this pulse\'s commissioned bridge) names SuperInstance/AI-Writings in-repo at anchored sites: the bridge pins the instrument by repo + commit 3f8405888366e3697b3775017fa5fe13d6244226 + sha256 5f280b8b435852872fadeb449f4382275e80be56e80035da02274db8006e1cc5 as an executable constant, tests/test_jev_kat_bridge.py asserts the citation string survives in source (a drifted upstream cannot be bridged silently), and the module docstring records AI-Writings#70 as the instrument\'s canonical home. CURRENCY EARNED 2026-09-30: SuperInstance/jev-quilt PR #47 MERGED 2026-09-30T00:18:30Z (merge 45912589941ce29f02c8a6659bfe2b4e7abfccb9) — the weight law is met: a merged PR in the to-node\'s repo whose MAIN-tree source carries the load-bearing citation (verified by the 09:11 pulse: tools/jev_kat_bridge.mjs on jev-quilt main still pins repo + commit 3f8405888366e3697b3775017fa5fe13d6244226 + sha256 5f280b8b435852872fadeb449f4382275e80be56e80035da02274db8006e1cc5, and tests/test_jev_kat_bridge.py still asserts the citation string survives). The discovery watcher surfaced #47 among the candidates; the load-bearing check was done by hand, not self-upgraded. Precedent arc complete: aw-quint-opcode was booked PENDING on a merged-but-doctrinal citation and earned currency when a merge named the source — here the booking named the source from day one and the merge closed the loop one lifecycle step later.',
      weight: 'VERIFIED',
      provenance: 'SuperInstance/jev-quilt#47', // merged 2026-09-30T00:18:30Z — the citing PR IS the finding's home
      receipt: 'SuperInstance/jev-quilt#47',
      falsification_condition: 'jev-quilt#47 merging with the SuperInstance/AI-Writings citation removed from tools/jev_kat_bridge.mjs source or the tests/test_jev_kat_bridge.py citation pin, or the bridge executing an instrument whose sha256 does not match the pinned digest 5f280b8b…e1cc5',
    },
    {
      from: 'mm-sealed-receipts', to: 'mgq-qcells-lab',
      claim: 'A sealed receipt lineage nobody\'s experiment names is a ledger talking to itself: the qcells lab runs ON the MicroMoth substrate and consumes the ledger\'s sealed findings, and its merged work says so. CURRENCY EARNED 2026-09-30: micrograd-quilt PR #7 ("qcells exp020-036: tie-band replication → two-regime desert hazard → triplet-stream rate-lane closure", MERGED 2026-09-30T04:49:20Z, merge 44de605) is a merged PR IN THE TO-NODE\'S REPO whose diff ADDS labs/qcells/FINDINGS.md citing SuperInstance/MicroMoth-quilt BY NAME at four anchored sites — the lab charter header ("Lab for novel experimentation on SuperInstance/MicroMoth-quilt"), the import-baseline manifest pin on MicroMoth-quilt main, the honest-limit gap posted on MicroMoth-quilt#3, and the receipts/ dir lane note — plus docs/synergy-scan-2026-09-30-0711.md consuming MicroMoth-quilt#23/#24\'s MERGED sealed findings to redirect the lab\'s own queue ("the lab\'s follow-on items are now already answered cross-repo; do not re-run"). The from-technique is the ledger those receipts seal into: fnv1a-64 import-baseline manifest + sha256 byte-match receipt tables with per-receipt FAIL-first pins (exp016 sealed receipt commit fba4ec7 via MicroMoth-quilt#22 is the exp019 data_provenance anchor). HONESTY: the 14:38 pulse\'s citation scan reported this repo cited ZERO times by micrograd-quilt main — that scan was a FALSE NEGATIVE; the re-audit that booked this edge found 5+ by-name citations in the merged tree, so no citation PR was opened (one would have been citation spam on a false premise) and the edge is booked directly on Casey\'s merge. Fourth and fifth repos born after seeding enter together; the lab is the producer, the ledger the seal — this edge books the ledger→lab direction, and the mirror (lab→ledger) is booked PENDING in the same hour.',
      weight: 'VERIFIED',
      provenance: 'SuperInstance/MicroMoth-quilt#24', // the exp018 seal (664506a5) whose merged finding the in-repo synergy scan consumes to redirect the lab queue
      receipt: 'SuperInstance/micrograd-quilt#7',
      falsification_condition: 'the SuperInstance/MicroMoth-quilt citations removed from labs/qcells/FINDINGS.md or docs/synergy-scan-2026-09-30-0711.md, or a lab experiment consuming a sealed MicroMoth-quilt receipt with no receipt reference anywhere in the consuming artifact',
    },
    {
      from: 'mgq-qcells-lab', to: 'mm-sealed-receipts',
      claim: 'The ledger\'s receipts seal the lab\'s work — and a seal that names its producer only by workspace path is a doctrinal citation, not a currency: it identifies the work, not the repo. MicroMoth-quilt PR #24 ("exp018 receipt: hard-root autopsy — FITNESS DESERT AT THE BIRTH CLOUD", MERGED 2026-09-29T21:25:32Z, merge 664506a5) seals the qcells lab\'s exp018 autopsy and names the producer as "the qcells lab (workspace/labs/qcells)" — a filesystem path, never the repo SuperInstance/micrograd-quilt. That was the git-agent#1 doctrinal-citation shape, booked PENDING for six hours. CURRENCY EARNED 2026-09-30 (17:56 pulse): **MicroMoth-quilt PR #29** ("docs(audit): qcells lab canonical home = SuperInstance/micrograd-quilt — provenance note + citation pin", MERGED 2026-09-30T09:27:01Z) is a merged PR IN THE TO-NODE\'S REPO that adds an AUDIT.md "Qcells lab — canonical home" note naming SuperInstance/micrograd-quilt BY NAME as the lab\'s durable addressable home (labs/qcells tree; sealed lineage exp018–exp022 mirrored as receipt PRs #5–#7; MM↔mgq first lab↔ledger bidirectional pair), with tests/test_lab_home_citation.py pinning the citation in-repo (repo named; local path framed by citation — a drifted citation cannot pass silently). The graph\'s first bidirectional pair now carries VERIFIED mass in BOTH directions — mm→mgq earned by the lab\'s merged FINDINGS (micrograd-quilt#7), the mirror earned by the ledger\'s merged AUDIT note (MicroMoth-quilt#29). Sealed receipts untouched (immutable); the note amends provenance without rewriting history. Never self-upgraded — the merge in the target repo did the earning.',
      weight: 'VERIFIED',
      provenance: 'SuperInstance/MicroMoth-quilt#24', // the seal whose producer-citation shape is the claim's whole subject
      receipt: 'SuperInstance/MicroMoth-quilt#29',
falsification_condition: 'a MicroMoth-quilt receipt sealing qcells-lab work that drops the workspace/labs/qcells producer reference entirely (the sealed bytes\' provenance unmoored from any lab identity), or the upgrade PR merging with the SuperInstance/micrograd-quilt citation removed',
    },
    {
      from: 'pq-named-refusals', to: 'fm-refusal-ledger',
      claim: 'pong-quilt\'s refusals are named, receipted, and prompt-content-free (QA-REFUSAL, byo-qpam-fallback, WAL-EXPORT/REFUSED, WAL-EXPORT/EMPTY, SEAL/REFUSED — and at R67 SAVE/COEV-EMPTY + LOAD/COEV-MALFORMED, with the SAVE/COEV-UNSTABLE R64 name surviving in claim prose as supersession lineage) — exactly the worked named-corpus substrate draft-kamimura-scitt-refusal-events-03\'s refusal-claim audit needs a real deployment to be read against. CURRENCY EARNED 2026-09-30: fleet-murmur PR #8 ("Refusal-events ledger: draft-kamimura-scitt-refusal-events-03 × pong-quilt named refusals", MERGED 2026-09-30T19:31:12Z, merge b21a4a46) is a merged PR IN THE TO-NODE\'S REPO citing SuperInstance/pong-quilt BY NAME at an anchored, pinned site: the ledger doc\'s PQ_PIN repo constant plus a corpus table pinned to pong-quilt main merge 52b42b4 — six named refusal kinds present-tense grepped at that pin with line-level sites recorded — and tests/test_refusal_events_ledger.py running a FAIL-first corpus pin (a main tree without the corpus trips RED naming the missing kind, so a drifted citation cannot pass silently). Direction honesty per the substrate\'s receipt-repo rule (edge #2 precedent): the merge is in fleet-murmur, so the edge books pq-named-refusals -> fm-refusal-ledger — currency flows INTO the citing repo. The 17:49 pulse\'s org note recorded "mints pq->fm refusal-ledger edge" at merge time; this booking lands the mint the merge earned — never self-upgraded. fleet-murmur becomes the fleet\'s first TRIPLE-inbound repo (honesty-receipts#2, qgs-adapter#3, refusal-ledger#8); pong-quilt\'s THIRD outgoing edge (session-wal honesty, stone-v1 forward-adoption, named refusals).',
      weight: 'VERIFIED',
      provenance: null, // the refusal corpus lives on pong-quilt main (the pinned 52b42b4 tree); the receipt is the fleet-murmur merge
      receipt: 'SuperInstance/fleet-murmur#8',
      falsification_condition: 'the SuperInstance/pong-quilt citation removed from the ledger doc or the PQ_PIN corpus-pin test, or a re-audit of the pinned pong-quilt main merge where a named corpus kind is absent from the tree while the pin still reports green (a drifted citation passing silently)',
    },
    {
      from: 'qe-eproc-witness', to: 'ds-esign-drift',
      claim: 'A fleet witness instrument consumed by pin-and-digest is doctrine landing in the consumer repo: quilt-ewitness (created 2026-09-30T09:25Z) ships src/eproc.mjs — anytime-valid e-process witnesses for training claims, Ville bound 1/delta, sigma pre-registered under refusal, retraction built in — and SuperInstance/delta-shape#1 ("Drift significance layer (E1-E5): e-witness bridge consuming SuperInstance/quilt-ewitness", MERGED 2026-09-30T19:31:08Z, merge commit 57c07426) names SuperInstance/quilt-ewitness in-repo at anchored sites on merged main: vendor/quilt-ewitness/eproc.mjs pinned BY BYTES (@ 61b9e04, sha256 aad90ac5aedb4d8e19b189808b47b22fc7258044af2c25c8f7fc90efec19e63a, provenance in vendor/quilt-ewitness/SOURCE.txt — the fleet vendored-dist pattern), src/esign.mjs witnessDrift() sha256-checks the vendored instrument BEFORE trusting it (the hash IS the identity; mismatched bytes refuse to witness), and the owning repo is named in README ("Shape != significance — now answered by the e-witness bridge", consuming from SuperInstance/quilt-ewitness as a sha256-pinned vendored instrument). HONEST HISTORY: this edge was booked PENDING twice before the merge outran the booking — 23:56 9/30 on branch edge14-pending-delta-shape (commit 7ddd151, lost in a /tmp wipe before push), rebuilt 02:41 as quilt-tools#31 (merge 812a644), whose commit was later reset off main — so this commit books the edge at its earned weight in one step, with the merge itself as the receipt (the aw-jev-kat precedent: booked PENDING on an open PR, flipped by the merge, never self-upgraded). delta-shape is the SIXTH to-node born after seeding (fleet-murmur, moth-waveform, quilt-stone, micrograd-quilt, MicroMoth-quilt, delta-shape); quilt-ewitness enters as a from-node (from-node-only repos earn no view mass).',
      weight: 'VERIFIED',
      provenance: 'SuperInstance/delta-shape#1', // the merged PR in the to-node's repo whose vendored-bytes citation IS the claim's subject
      receipt: 'SuperInstance/delta-shape#1',
      falsification_condition: 'delta-shape main dropping the SuperInstance/quilt-ewitness citation from src/esign.mjs / vendor/quilt-ewitness/SOURCE.txt / README, or witnessDrift() executing vendored bytes whose sha256 does not match the pinned digest aad90ac5...',
    },

  ],
};
