# Edge-watch digest — 2026-10-03 11:1x CST (snowball pulse)

Scope: three newest SuperInstance repos (created 00:15–01:42Z 10/3) + queue-state correction. Read-only scan; verdicts are collision-shaped, not quality judgments.

## 1. mavis-workspace (01:42Z) — SYNERGY CANDIDATE, zero collision

"An agent you can clone": workspace knowledge as a wiki + a **key form** (small JSON one instance emits so another can be oriented without a shared conversation) + RETRACTIONS-first reading order.

Mechanism (verified by direct README/tool read):
- `emit_key.py --task ... --out key.json` emits `key_form_version: 1` with `task`, `last_measured` (null-forced — "null is visibly different from a number"; tool warns if you set a number without a command), `beliefs`, `refuted` (warns when empty — an unstated empty list reads as "nothing was corrected"), `known_failures` (names the CLASS of mistake: "a receipt is a fact; a rule is something you can follow").
- Reading order mandates `wiki/RETRACTIONS.md` FIRST — published, plausible, and wrong — before INDEX/EXPERIMENTS/ENVIRONMENT.

Mapping onto our fleet lanes (adoption, not rivalry):
- **fleet-ws scout workspace** (`/srv/fleet/ws`, markers, readyz): the key form is a candidate for the marker-file payload — a structured handoff key instead of prose README alone.
- **doubt-ledger**: `refuted` ≈ our discharged-claims-with-reason; `last_measured: null`-forcing ≈ our INCONCLUSIVE-first-class / null-vs-zero doctrine (GPU-EXPERIMENTS rules adopted 10/1: std==0 → INCONCLUSIVE never PASSED).
- **memory/study + pulse receipts**: RETRACTIONS-first matches our stale-claim correction practice (queue item #8 stale-entry fix 10/3; tidepool moat re-run correction 10/2 15:56).
- **checkpoint discipline** (ax suspend/resume adoption): the key carries state, the wiki carries knowledge, AGENT.md carries character — same three-layer split as our checkpoint/meta.yaml/handoff split.

Open follow-up (small): pin a `key_form` schema note in our ws README or doubt-ledger wave-3 consume-don't-rival doc — DEFERRED to a future pulse, not built here.

## 2. dicebear-quilt (01:31Z) — ZERO collision

DiceBear avatar library fork (default branch 11.x, upstream README preserved, README.upstream.md present). Avatar/asset layer; no overlap with receipts, ledgers, engines, or fleet tooling. No action.

## 3. quilt-studios (00:15Z) — adjacent, consume-don't-rival

"Play the game, then scroll down and watch the quilt think" — one engine, four rungs (sandbox garden, melon puzzle, composer studio, pong x-ray with live quilt layers). Next.js/Prisma app.

- The **pong x-ray with live quilt layers** rung visualizes quilt state during play — it is a VIEW layer. It does not touch the pong-quilt engine, receipt chains, or pin suites. No collision with pong-quilt#102 (R80 sigma-trail).
- If it later reads quilt-in-git state, our wave4-query / notes2feed seams (#9/#11, both on main) are the natural consume surfaces. WATCH only; no hedge PR warranted.

## 4. Queue-state correction (stale claim fixed)

10:11 pulse premise "quilt-in-git main through #8/#9" is now STALE: main has moved through **#8 (w3 union), #9 (wave4-query), #10 (9c memo §2/§4/§7), #11 (notes2feed feed.v1)** — all merged. Consequently:
- quilt-in-git#12 (ADSR envelope tool, our open PR) is now 2 merges behind main. Files are disjoint by inspection (`.quilt/bin/quilt-adsr` + `tests/pins_adsr.sh` + `docs/ADSR-ENVELOPE.md` vs research/docs merges), so no rebase forced; a courtesy rebase can wait for Casey's review pass.
- Open PRs fleet-wide (verified via `gh pr list` this pulse): doubt-ledger#18 + #16, quilt-in-git#12, pong-quilt#102 = **4 open, all Casey-gated**. Yesterday's "zero open PRs" claim stays refuted.

## Honest limits

- Scan depth = README/top-level tree + key-form doc only for mavis-workspace; no code read inside dicebear-quilt or quilt-studios beyond root listings.
- "Zero collision" means no overlap with OUR open lanes as of this pulse; it is not a warranty about lanes we haven't imagined.
