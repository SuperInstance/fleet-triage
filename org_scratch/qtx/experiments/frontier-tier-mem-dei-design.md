# FRONTIER DESIGN RECEIPT — breeding-over-WAL: TierMem convergence + DEI champion-gossip

Date: 2026-09-28 (snowball pulse, kimi1 lane)
Status: DESIGN DOC — every claim PENDING until it earns a receipt; kill switches in §5.
Provenance: edge-watch pulses 2026-09-27/28 (/tmp/edge-watch-latest.md chain, queue
file memory/snowball-queue.md). External identifiers cited as recorded there, not
re-fetched this pulse — each carries a kill switch if the citation drifted.

## 1. Frontier read — three external shapes converging on the fleet ledger

1. **TierMem** (independent build, spotted edge-watch 2026-09-28 06:24): immutable
   raw-log + summary tier + a *sufficiency router* that decides when summary is
   enough. Shape = the fleet WAL's layering (raw rows → VIEW summaries) arrived at
   independently.
2. **DEI (arXiv 2605.27130, per edge-watch)**: extends DRQ to *distributed async
   champion-gossip over MAP-Elites* — champions propagate between islands without
   a central archive, archive assembled from gossip.
3. **bassrehab / red-queen** (per edge-watch): MAP-Elites now cargo-installable —
   the *algorithm* layer is commoditizing; the archive/replay layer is the part
   that stays distinctive.

**Convergence claim (PENDING):** ledger layering — raw + summary + routing — is no
longer distinctive. Anyone can rebuild TierMem's shape in a weekend. The fleet's
moat narrows to two things TierMem/DEI do NOT have: the **five-opcode receipt WAL**
(BIND/LINK/VIEW as the canonical cell) and **re-execution** (a receipt that is only
valid when re-running the op from the WAL replays byte-identical).

## 2. The delta (what we keep)

| layer | commoditized? | fleet answer |
|---|---|---|
| raw log + summary tier | yes (TierMem) | keep, unremarkable |
| sufficiency routing | yes (TierMem router) | adopt the *idea*; route on receipt-presence, not size |
| MAP-Elites breeding | yes (bassrehab/red-queen, DEI) | keep as island-internal engine only |
| champion transport | DEI gossip, no receipts | **replace with receipt-gated WAL export** |
| ledger semantics | not commoditized | **five-opcode receipts + re-execution = the moat** |

## 3. Design — champion-gossip → HolonomyConsensus (the fleet-flavored variant)

DEI ships champions as gossip messages: content + provenance claim. The fleet
variant, **HolonomyConsensus**, changes one thing: *a champion is not a champion
until its breeding run is sealed into the five-opcode WAL and the seal
re-executes.*

1. Island finishes a breeding round → its ledger writer anchors the survivors as
   LINK rows (five-opcode WAL, genesis BIND, VIEW for summaries — the
   `wal-export.js` / `quilt_emit` shape the fleet already verifies through
   quilt-stone v1/v2).
2. Export crosses islands as the DEI gossip envelope, PLUS the WAL slice hash —
   not the whole log, the chain head + receipt idiom (fnv1a-64, prev-chained).
3. Receiving island verifies through its local quilt-stone verifier BEFORE
   admitting the champion into its own archive. Verify = re-execute the
   champion's recorded op sequence; divergence at any seq → refuse, receipt the
   refusal (the fleet QA-REFUSAL idiom), keep the scar.
4. Archive assembly (DEI's "archive from gossip") becomes: assemble from gossip,
   then rank the assembled set by VERIFIED-edge trust (the G11 trust lever
   already in REFERRAL_GRAPH.md) — a champion arriving from an untrusted island
   contributes PENDING mass only until its chain earns weight.

**One-line doctrine:** DEI gossips champions; HolonomyConsensus gossips champions
*with receipts*, and the archive ranks by earned trust, not arrival order.

## 4. Referral edges this design implies (to book, PENDING until landed)

- `dei-champion-gossip → holonomy-consensus` — fleet design derives from DEI's
  transport; citation of arXiv 2605.27130 is the provenance. Kill switch: §5 K1.
- `pq-wal-export → holonomy-consensus` — pong-quilt's five-opcode exporter
  (PR #33 merged, wal-export) is the canonical producer the design adopts.
  Kill switch: §5 K2.
- `tier-mem-sufficiency → receipt-presence-router` — adopt TierMem's router
  idea, re-pointed at receipt-presence as the routing signal. Kill switch: §5 K1.

## 5. Kill switches

- **K1 (citation drift):** if DEI 2605.27130 or the TierMem shape is found to be
  miscited (title/venue/semantics differ from edge-watch's record), every edge
  citing it flips REFUTED and this doc's §1/§3 get an erratum row in the chain —
  never silently edited.
- **K2 (shape drift):** if `tools/wal-export.js` (pong-quilt main) diverges from
  the five-opcode BIND/LINK/VIEW shape, the `pq-wal-export` edge above flips
  REFUTED and the design re-targets the new canonical producer.
- **K3 (commoditization):** if an external system ships champion transport WITH
  receipt-sealed re-execution and earned-trust ranking first, this design is no
  longer distinctive — flip the doc to "adopt, don't build" and book the edge as
  incoming instead of outgoing.

## 6. What is deliberately NOT claimed

- No code ships here. This is the design receipt; the implementation lane
  (island adapter on top of wal-export + stone verify) is a separate unit.
- No VERIFIED weight is claimed for any edge in §4 — all PENDING per the weight
  law until a merged PR in the target repo cites the technique.
- The sufficiency-router port is an idea to steal, not a repo to build.

Receipt: see `experiments/out/frontier-tier-mem-dei.receipt.json` — sha256 of
this file at seal time, chain `genesis`.
