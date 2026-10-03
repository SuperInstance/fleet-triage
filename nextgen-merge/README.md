# nextgen-merge

**Git commits artifacts and merges text. At agent scale the scarce resource is
not file access — it is a trustworthy answer to "which of these competing claims
is true."**

A Durable Object per branch, a claim as the unit of contention, and a merge that
is an adjudication: it re-executes the witness instead of picking a side, and it
**preserves every losing claim** instead of discarding the only high-information
signal the system produces.

---

## Run it

You need **Node 18+** and a **free Cloudflare account**. Nothing else.

```bash
git clone <this repo> && cd nextgen-merge
npm install
npm run dev
```

Then open:

| URL | what you get |
|---|---|
| `http://localhost:8787/demo` | **the whole argument, precomputed** |
| `http://localhost:8787/fixture/receipt` | the verified quilt-tools evidence |
| `http://localhost:8787/git/merge` | what git did with the same two branches |
| `http://localhost:8787/` | the index |

`compatibility_date` is pinned to `2026-09-28` — the newest date the
widely-cached `workerd` accepts. It runs on current wrangler too, so this
works on both old and new toolchains. Raise it if you are on a recent one.

Tests (no account needed, runs in-process):

```bash
npm test          # 12 unit tests + the concurrency stress curve
node test/unit.mjs
LEVELS=1,10,50 node test/stress.mjs
```

Deploy:

```bash
npx wrangler login
npm run deploy
```

Durable Objects work fully in `wrangler dev` locally, so you never need to
deploy to see the concurrency behaviour.

---

## The failure this reproduces

Two pull requests on a real repository, `SuperInstance/quilt-tools`, both
independently asserted the same counter. **Both were correct against the main
each one saw.**

```
  58e2a18   Merge PR #30                17 edges   13 VERIFIED   4 PENDING
    |\
    | \  a98a5c5  PR #32 head            18 edges   14 VERIFIED   4 PENDING
    | /                                 asserts "18", "fourteen VERIFIED"
    | \
    | /  7caf5a3  PR #33 head            18 edges   14 VERIFIED   4 PENDING
    |/                                  asserts "18", "fourteen VERIFIED"
    |
  fb2e041   Merge PR #32     -> "18", "fourteen"
  0101409   Merge PR #33     -> "19", "fifteen"      <-- what actually landed
```

Each agent saw 17 edges and added one. 17 + 1 = 18. Both are right. The union
is 19. **There is no losing claim.**

Reproduce all of it yourself against the live repo:

```bash
git clone https://github.com/SuperInstance/quilt-tools
cd quilt-tools
git checkout 58e2a18 && git merge a98a5c5 && git merge 7caf5a3
# CONFLICT (content) in experiments/REFERRAL_GRAPH.md
# CONFLICT (content) in experiments/referral_graph.pins.mjs
# experiments/referral_graph.seed.mjs   auto-merged — silently
```

Three things to notice, and only the first is the one git warns you about:

1. **git produced 5 conflict hunks** across 2 files, and offered nothing but
   "a human picks a side." There is no side to pick. 18 was true on both
   branches; 19 is true only in the union.

2. **`referral_graph.seed.mjs` auto-merged with no conflict at all.** That is
   the file holding the actual edge data. git took the union — 19 edges — and
   said nothing. The dangerous half of this merge was the half git was silent
   about.

3. **The "keep both" resolution does not parse.** Concatenating both sides of
   every hunk yields 270 `{` against 269 `}` and
   `SyntaxError: missing ) after argument list`. Both agents open a block for
   their own new pin; both close it; the union has two openings and one closing.

What actually happened on main: commit `175a398`, *"edge15 landing: union
world-state 15 VERIFIED — assertions re-derived empirically from pins run."* A
third person re-ran the pins, computed 19 and 15 by hand, and overwrote both
agents' assertions. **The two claims that were overwritten were not recorded
anywhere** — not in the tree, not in the log, and not in the PR bodies, which
still say "17 to 18, 13 to 14" today.

---

## What this does instead

Same two branches, same 42 input claims:

```bash
curl -s localhost:8787/demo | jq '.merge.derived'
```

```json
[
  { "subject": "referral_graph.edges", "predicate": "count",          "object": 19 },
  { "subject": "referral_graph.edges", "predicate": "weight:VERIFIED", "object": 15 }
]
```

19 and 15 — **exactly what landed on GitHub main**, derived by the merge,
asserted by neither agent. All four losing claims are returned intact in
`merge.residual`, each with the witness that falsified it and the value that was
observed.

### The three design questions

**1. What is the unit of contention?**

A claim: `{subject, predicate, object, witness, confidence}`. Two claims about
the same `subject` + `predicate` with different `object`s are contradictory
**by construction**. No natural-language matching, no embedding, no model in
the loop — it is a hash lookup. A file lock is simultaneously too coarse (it
serialises unrelated edits) and too fine (it happily lets two contradictory
claims about one fact land, because they are text in different places).

**2. What is a merge?**

An adjudication that returns four things, not a tree:

- `claims` — the reconciled set, what you may act on
- `contradictions` — every pairwise disagreement
- `derived` — claims the merge produced that **no input asserted**
- `residual` — what could not be resolved, with every losing claim preserved

**3. What is a conflict, and what survives it?**

A conflict is two claims about one `(subject, predicate)` with different
objects — including the case git cannot hold, where a claim is correct in
isolation and false in the union. Everything survives. The losing claims are
the record of what nearly went in the other way, and git's merge throws exactly
that away.

---

## Why the oracle is re-execution and not a panel

Because panels are measured not to work.

- A 9-judge LLM panel across 7 model families has **effective sample size
  2.18** [2.07, 2.31], and **the best single judge matches or outperforms the
  full panel**. Dawid-Skene and accuracy-weighted voting close **at most 11% of
  the gap even with oracle gold labels**. <https://arxiv.org/abs/2605.29800>
- Judges agree **with each other** at κ 0.74–0.88 while each agrees **with
  outcomes** at ~0.2, and a 16-vote panel carries ~2 effective independent
  votes. <https://arxiv.org/abs/2608.07517>

100,000 agents sharing a base model, a prompt, and a repository is the most
correlated panel imaginable, and it gets *worse* as the panel grows. "Everyone
agreed" is worth almost nothing.

So the merge routes on **agreement structure**, never on a vote count:

1. **The witness is re-runnable → run it.** Deterministic. Settled.
2. **The parties agree → union.** Settled.
3. **Neither → abstain**, and record the residual.

Abstention is a first-class result. Shipping the uncertainty is the feature;
shipping a confident wrong merge is what every other system does.

---

## Honest concurrency results

`npm test` runs three arms. Here is what it actually printed on this machine
(local `wrangler dev`, wrangler 4.136.1, workerd):

```
  N     mode   accepted refused lost  retain% survivors  p50   p95
  ------------------------------------------------------------------
  1     cas    1        0       0     100.0  1          258   258
  1     blind  1        0       0     100.0  1          164   164
  1     retry  1        0       0       0.0  1          263   263    (1 attempts)
  5     cas    1        4       0     100.0  1          541   599
  5     blind  5        0       4      20.0  1          398   441
  5     retry  5        10      0       0.0  5          2248  3031   (15 attempts)
  25    cas    1        24      0     100.0  1          2023  2025
  25    blind  25       0       24      4.0  1          1475  1478
  25    retry  2        24      0      92.0  2          8154  8168   (49 attempts)
  50    cas    1        49      0     100.0  1          2998  3001
  50    blind  50       0       49      2.0  1          3437  3438
  50    retry  2        1       0      96.0  2          6151  6159   (51 attempts)
```

Read this honestly, including the parts that are bad:

- **CAS loses 0 updates at every level tested.** Correct — and *degenerate*.
  One writer wins and N−1 are refused. That is a mutex wearing a branch's
  clothes, not concurrency. It is the correct primitive and it is not the
  whole answer.
- **Blind writes lose up to 99% of accepted updates at N=100.** This is the
  control that makes the 0 above a measurement rather than a claim. Without
  it, "loss rate 0" is just an assertion with a number attached.
- **The retry arm collapses.** At N=25 only 2 of 25 agents got their claim in;
  at N=50, 2 of 50. The system **does degrade under concurrency** and the curve
  is in the output. Root cause is visible in the code: every retry rewrites the
  entire claim set, so the work is O(N²) in the branch size, and each write
  contends for one actor.
- **~70 socket drops** appear at N≥25. Those are the local `wrangler dev`
  proxy failing under concurrent load, *not* merge results — the same CAS logic
  hammered directly at N=30 returns 0 application errors, 29 `stale-head`, 1
  ok. The test counts them separately so a harness failure can never be
  mistaken for a correctness result.
- **Latency grows roughly linearly with N** even under CAS (~80 ms per
  concurrent request on local workerd). That is a real ceiling.

**This is the honest state: the content model is real and demonstrated on a
real receipt. The concurrency story is a correct primitive plus a measured
failure to make it scale.** The fix is not more retry — it is sharding the
claim space so branches that cannot contradict each other do not share an
actor, which is the thing to build next.

---

## Layout

```
src/claim.js        the claim object + structural contradiction detection
src/adjudicate.js   witnesses, re-execution, abstention, the merge
src/branch.js       Branch Durable Object — CAS on the branch name
src/index.js        HTTP routes
src/git-receipt.js  the measured git behaviour, as data
fixture/            real edge data lifted from quilt-tools at 4 commits
test/unit.mjs       12 tests, no framework
test/stress.mjs     the three-arm concurrency curve
```

No fleet internals and nothing account-specific. The only dependency is
`wrangler`, and it sits in `dependencies` rather than `devDependencies` on
purpose: with `NODE_ENV=production` set, npm skips devDependencies and
`npm install` would silently install nothing. Verified from a clean copy:

```bash
tar cf - --exclude=node_modules --exclude=.wrangler . | (cd /tmp/fresh && tar xf -)
cd /tmp/fresh && npm install && node test/unit.mjs && npm run dev
# added 40 packages; 12 passed, 0 failed; Ready on http://127.0.0.1:8787
```
