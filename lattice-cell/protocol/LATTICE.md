# LATTICE — the wire format and the invariants

Status: **designed, implemented, and tested locally. NOT deployed.** There is no
`CLOUDFLARE_TOKEN` in the R&D sandbox and `wrangler whoami` reports
"You are not authenticated", so nothing here has run on a real edge. That is
`UNVERIFIABLE`, not `false` (ORIENTATION.md). Everything below marked *pin* was
executed here; everything marked *deploy-pending* was not.

---

## 1. Two planes, and exactly one of them may be lost

| | Plane A — content | Plane B — intent |
|---|---|---|
| store | git objects on a remote | Durable Object (locally: fsync'd file) |
| written | AFTER the work | **BEFORE the work** |
| holds | the diff, the frame, the postcondition | who was asked to do what, and when it stops being owed |
| loss | catastrophic, and visible | **recoverable** by `reconcile()` |
| survives Worker death | yes, because it was pushed | yes, because it was flushed first |

The vision says *the commit is the only durable artifact*. That is right about
**content** and wrong about **intent**, and the error is load-bearing.

> **A commit is a POSITIVE artifact.** A hash chain is total over the commits
> that exist and completely silent about the commits that do not. So
> *"cell woke and disagreed"* and *"cell was dispatched and died"* are the same
> observation: nothing. At 477 cells you will not notice, because the verifier
> reports `chain valid, N committed` and **N is a count of successes printed
> next to a denominator nobody measured.**

This is the fleet's standing disease, not a new one: the `6.8×` property test
that passes at any value; `INACCESSIBLE` reported next to `EMPTY`; 13 repos
"failing open" where a failing test and a passing test emit the same exit code.
**A hash chain over a set with holes is still a valid hash chain.**

So the ledger is not a second record. It is the one thing that makes silence
representable, and it is the **only** departure from "commit is the only
durable artifact."

## 2. The join key

`Dispatch-Id: <id>` goes in the commit message.

Without it, a lost outcome is unrecoverable: the ledger has an open dispatch and
git has a commit, and nothing says they are the same event. With it, `reconcile()`
is a **git walk** and the ledger is a cache. That is what lets the Durable
Object be treated as disposable — a substrate you cannot lose is a substrate you
cannot use for anything new.

*Mutation A drops this line; the suite goes red at I5a.* (pin: mutation score)

## 3. Invariants

| | statement | killed by |
|---|---|---|
| I1 | no OUTCOME without a DISPATCH (no fabricated receipt) | mutant F → I1b |
| I2 | every DISPATCH is settled exactly once | mutant C → I10b |
| I3 | `outcome.at >= dispatch.at`; the log is monotonic | — |
| I4 | a recorded tip is reachable **from a remote ref** (a cold clone can see it) | — |
| I5 | the commit carries id + intent + postcondition | mutant A → I5a |
| I6 | `reconcile` is total over pushed commits and is a fixpoint | — |
| I7 | a no-op run is `REFUSED`, never `COMMIT` | mutant D → I7a |
| I8 | a postcondition is evaluated and its verdict recorded, true or false | mutant E → I8a |
| I9 | the same intent twice is two dispatches, never a reused outcome | — |
| I10 | the dispatch row is durable **and execute has not begun** at that point | mutant C → I10e |
| I11 | `reconcile` must NOT certify a commit that never reached a remote | mutant B → I11b |

**I10 and I11 were missing until the mutation score came back 4/6.** Both were
visible in `harness/crash-matrix.sh` the entire time, as rows nobody had
promoted to assertions. See `what I learned`.

## 4. The frame: what a frame IS

> *"without dropping a single frame of execution logic" — what is a frame?*

**A frame is a pre-registered claim plus a post-registered relation, and
nothing else.** Not a log, not a narrative, not a diff.

```
quilt-cell(shared): set dial 1 to 0.9

Dispatch-Id: d-0-256ae609
Cell-Intent: set dial 1 to 0.9
Cell-Postcondition: dial:shared:1 == 0.9
```

Two things make this a frame rather than a comment:

1. **The intent is written BEFORE the diff exists.** The failure this fixes is
   named in the brief: *"the branch name was typed in the first ninety seconds
   and nothing marked when it stopped being true."* You cannot mark drift on a
   claim that was never bound to a check. A branch name is free text; a
   postcondition is an expression.
2. **The postcondition is a RELATION over the committed tree, and it is
   evaluated.** `dial:shared:1 == 0.9` is re-read from the commit after it
   lands and recorded as `postcondition_holds: true|false`. It is not a
   description of the work; it is a claim that can come back false. A frame
   whose postcondition cannot come back false is a comment with a header.

This is `GIFT-ORACLE.md` applied to the thing the vision is vaguest about: when
you cannot know the right output, check that a relationship holds.

## 5. Where the log lives — open question 1, argued

**The strongest case FOR D1/R2**, since the orchestrator wants to be argued out
of git-native and deserves the best version of the other side:

At 477 repos, *"which cells have unsettled dispatches?"* is a query. Git cannot
answer it. Discovering open leases means walking 477 repos' refs — O(477)
network operations on a cold cache — where D1 answers it in one indexed query.
That is real, it is why CF was on the table, and it is a genuine weakness of
per-repo-native.

**Why it still loses, in two steps.**

*Step 1 — the query is over facts git already has.* "Which dispatches are
open?" is not new information; it is a fold over the ledger. Moving the log to
D1 does not create the fact, it only makes the fold faster. And the fold can be
made cheap without moving anything: the lease state is derivable from commits
carrying `Dispatch-Id:` that have no matching outcome. **A remote-reachability
walk over ONE hub repo answers it in one fetch.** (Pinned: `reconcile()` does
exactly this walk, over real repos, in `tests/invariants.mjs` I6.)

*Step 2 — the decisive one.* **Per-repo-native git cannot express a cross-cell
fact at all.** Two cells that disagree are a fact about the *pair*. There is no
object in repo A, and no object in repo B, that says "A and B disagree." The
contest record in `src/contest.js` has to live somewhere, and that somewhere is
a third repository. So the hub repo is not a performance optimisation; it is
forced by the one thing the lattice is actually for.

**Therefore, with a hard rule:**

> **Content is per-repo-native (git). Cross-cell facts go in a hub repo (also
> git). Cloudflare primitives are the discovery index only — a cache that is
> allowed to be wrong and is never the record.**

Delete D1, R2 and Queues entirely and the lattice still reconciles, because
reconciliation is a git walk. That is the test of whether a component is
infrastructure or decoration, and it is the same test that says a Durable Object
is a lease table and not a database.

The Durable Object earns its place on a different axis, and it is the one the
brief names: **a branch name is a natural key and the contention is per-branch,
so the serializable unit is the branch.** A DO's input gate gives that without
a lockfile — which matters precisely because the substrate is multi-writer here
and `quilt-in-git` already measured what single-writer journals do under
contact (tracked `watch.log` conflicts on the second branch; see its
`quilt-init` comment).

## 6. The disagreement protocol

The vision says cells *heal one another*. They do not, and the reason is
n_eff ≈ 2 measured six ways: a lattice from one account, one doctrine, one base
model, and mostly one another as forks is the most correlated ensemble
available. Differential testing across forks cannot catch a bug copied along
with the code. **A lattice asked to adjudicate its own disagreement will agree
loudly and be wrong together.**

> **The lattice does not adjudicate. It records.**

- **C1** — a contest is declared when two cells commit different values for the
  same `(alias, dial)` on divergent tips. A fact about the substrate; needs no
  model and no judge. Ancestor/descendant tips are explicitly *not* a contest
  (the control that cannot pass: `tests/contest.mjs` C1c).
- **C2** — the contest record is a **pure function of the two commits**,
  order-independent, sha256 over its own body. Same property as the receipt,
  for the same reason: *a witness you can regenerate is a witness you can
  audit.* (pin: `pins/purity.log`)
- **C3** — **more cells do not resolve a contest.** `resolveWithPanel()` returns
  `resolved: false` for *every* input, and that is the design working rather
  than a stub. It records the tally, the majority it would have leaned on, and
  the **margin** — and pins the finding that the margin grows from 1 to 6 while
  the conclusion does not move (`tests/contest.mjs` C3d). That test *is* the
  n_eff argument, executed rather than cited.

The dialect is `quilt-adjudication`'s, not a new one — winner, loser, reason,
`to_accept_the_loser`. That repo is published, demoed and 11/11 pinned; this
lane has no business inventing a second wire format. What is added here is the
part per-repo git cannot express.

## 7. Fairness — the honest cost

Lease expiry is a **liveness** guarantee, and liveness needs a fairness
argument that safety does not:

> We assume the scheduler eventually re-admits any cell whose lease expired.
> If it does not, a cell can starve silently — and starvation is exactly the
> absence this ledger was built to make visible, now hidden one level down.

So `LEASE_EXPIRED` is a record that the question was **re-asked**, never that
the work is impossible. The distinction is in the type, and any consumer that
conflates them has rebuilt the hole.
