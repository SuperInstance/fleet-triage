# lattice-cell

**One repository, one cell: wakes on a push, executes, commits, dissolves — and
the lattice can tell you when it did not.**

Built by the R&D lane for `SuperInstance/cf-native-backend`. The protocol layer
is published separately at `SuperInstance/quilt-adjudication` (11/11 pins, demo
green from a cold clone) and is **not** re-implemented here. No pushes to
`quilt-in-git` or `quilt-adjudication`, ever.

*Receipts culture applies with full force: every claim here is pinned or
labelled.*

---

## What is actually established

| claim | evidence |
|---|---|
| A hard kill at each of 6 checkpoints leaves a **different** substrate state, and all 6 are decidable | `pins/crash-matrix.log` |
| A commit lost between execute and push yields a **negative receipt** (`LOST`), never a false `COMMIT` | `tests/invariants.mjs` I11 |
| A lost outcome is **recoverable** by a git walk, because the commit carries `Dispatch-Id:` | `pins/crash-matrix.log`, I6 |
| The quilt receipt is a **pure function of the commit** — delete it, regenerate byte-identically | `pins/purity.log` |
| The invariant suite kills **6/6** semantic mutants, each by a named check | `pins/mutation.log` |
| Adding lattice members to a contest does **not** resolve it (margin 1→6, conclusion unchanged) | `tests/contest.mjs` C3d |
| `plato-tile-encoder`'s own layout comment does not sum to its own total (388 ≠ 384) | `pins/quilt-word.log` |
| **NOT established:** anything on a real Cloudflare edge | see below |

### Deploy status: UNVERIFIABLE, not false

There is no `CLOUDFLARE_TOKEN` in the R&D sandbox (`env` has no `*TOKEN*`/
`*KEY*` variable) and `wrangler@4.146.0 whoami` returns *"You are not
authenticated"*. `src/worker.js` and `src/ledger-do.js` have therefore **never
run on an edge.** Per `ORIENTATION.md` a failed fetch is `UNVERIFIABLE`, not
false, and this is recorded as an open gap rather than dressed as a green check.

What *has* run: `src/cell.js` and `src/contest.js` are the **same modules** the
Worker imports, executed against real local and bare remotes by the suite. The
Worker layer is the untested part, and it is thin by design.

First thing to do with a token:

```sh
export CLOUDFLARE_TOKEN=...        # account 049ff5e84ecf636b53b162cbb580aae6
npx wrangler kv namespace create PLAN      # paste ids into wrangler.toml
npx wrangler kv namespace create CELLS
npx wrangler r2 bucket create lattice-cell
npx wrangler deploy
curl "$WORKER/reconcile?repo=…&ledger=…"   # the operation that must survive
```

---

## The design in one paragraph

Two planes. **Plane A** is git: the commit, the frame, the postcondition,
written *after* the work and durable because it was pushed. **Plane B** is a
Durable Object: a lease table written and flushed *before* the work, and it is
the **only** departure from "the commit is the only durable artifact" — because
a commit is a positive artifact, and a positive artifact cannot represent
silence. The two are joined by `Dispatch-Id:` in the commit message, which makes
the ledger a cache and lets it be rebuilt from git with a walk. The full
argument, the invariants, and open question 1 are in
**[`protocol/LATTICE.md`](protocol/LATTICE.md)**.

```
   DISPATCH (durable, flushed BEFORE work)        COMMIT (durable, pushed AFTER work)
   ┌───────────────────────────────┐              ┌────────────────────────────────┐
   │ d-0-aaa  shared  set dial→0.9  │─────────────▶│ Dispatch-Id: d-0-aaa           │
   │ lease 30s     OPEN            │              │ Cell-Intent: set dial 1 to 0.9  │
   └───────────────────────────────┘              │ Cell-Postcondition: dial:…==0.9 │
                                                  └────────────────────────────────┘
   crash here → LOST (negative receipt)  ·  crash after push → reconciled COMMIT
```

## What a frame is

Not a log, not a narrative, not the diff. **A pre-registered intent and a
post-registered relation, and nothing else.** The postcondition is re-read from
the committed tree and recorded as `postcondition_holds: true|false` — a frame
that cannot come back false is a comment with a header. See LATTICE.md §4.

## Run it

```sh
./harness/crash-matrix.sh     # hard-kill (exit 137) at each of 6 checkpoints
node tests/invariants.mjs     # 32 checks
node tests/contest.mjs        # 14 checks
node tests/mutation.mjs       # 6 mutants, each required to be killed
```

Everything is dependency-free Node 22 and real git. No network, no account, no
model, no judge.

## Layout

```
protocol/LATTICE.md   the wire format, the invariants, the Q1 argument
src/ledger.js         append-only dispatch ledger; MemStore (DO) + FileStore (fsync'd)
src/cell.js           wake / execute / commit / dissolve, 6 crash points, reconcile()
src/contest.js        C1 declare, C2 pure record, C3 the panel trap as a function
src/worker.js         Worker entry      — DEPLOY-PENDING, never executed on an edge
src/ledger-do.js      one DO per cell   — DEPLOY-PENDING, never executed on an edge
harness/              the crash matrix
tests/                invariants, contest, and the suite's own mutation score
pins/                 receipts
```

## Licence

Same as the rest of the fleet.
