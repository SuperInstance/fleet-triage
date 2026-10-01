# Orchestration board — 2026-09-30

One line per lane. State is `DONE` / `RUNNING` / `BLOCKED` / `QUEUED`, and BLOCKED always
names the thing that unblocks it. Nothing is DONE until a number exists and a clean clone
reproduces it.

| lane | repo | state | next move |
|---|---|---|---|
| L1 linear-vs-optimal play | pie-minimax | **DONE** | 0.1807 vs 0.1431 floor. 10/10 clean-clone |
| L2 what a discrete judge is good for | selectlib | **DONE** | coarse (seam) yes, fine selection no. 10/10 tests |
| L3 the judge as a router (fusion claim 4) | jev-fusion | **DONE** | all 4 claims are prior art; only #4 worth building |
| L4 3x3 scaffolding bugs | pie-minimax | **DONE** | 3 bugs, all silent, all recorded |
| L5 4x4 four-in-a-row + composition | ga4444 | **DONE** | **3,338 positions = the COMPLETE tree. The game is a DRAW** |
| L6 connect4 ground truth | connect4 | **DONE** | **54,166 positions, plies 1-6, digest 0x4ef8351a5c319637** |
| L7 why does dimension change stability | murmuration | **RUNNING** | scout dispatched, report unread |
| L8 cutting-edge math, 4 axes | — | **RUNNING** | scout dispatched, report unread |
| L9 vision model reads the text | voxelglyph | **BLOCKED** | `mcode-tools` returns `invalid signature` |
| L10 ladder + architecture review | ladder | **DONE** | 4 findings, source pushed for checking |
| L11 fleet openness | — | **DONE** | 5,127 repos, 0 private, 5,111 open to PRs |
| L12 3D ASCII renderer review | ladder | **DONE** | 3 findings incl. a z-buffer that is written and never read |
| L13 a Jev client that cannot fail quietly | jev-harness | **DONE** | 8 tests, live 5/5, gap 0.647. public, 7 files |
| L14 novel uses + anti-patterns for Jev | jev-harness | **RUNNING** | subagent writing USES.md |
| L15 fleet census | fleet-triage | **DONE** | 5,108 repos. **the namespace is a USER account, not an org** |
| L16 mechanical triage, 500 most-active | fleet-triage | **RUNNING** | hollow / nolicense / failopen / vendored, per repo |
| L17 the 62 no-language repos | fleet-triage | **RUNNING** | W1a. hollow vs vendored vs mirror vs genuine, verified per tree |
| L18 cross-repo synergy + extraction | fleet-triage | **RUNNING** | W1b. families, VERIFIED duplication, real merges |
| L19 release safety, 17 first-party autopublishers | fleet-triage | **RUNNING** | W2a. 11 of 17 have ZERO tests |
| L20 disposition of 10 empty repos | fleet-triage | **RUNNING** | W2b. stub, or referenced-and-broken? |
| L21 history-bloat, corrected | fleet-triage | **DONE** | **106 flagged -> 36 real. instrument was 66% false** |
| L22 GPU experiment queue + decision trees | fleet-triage | **DONE** | 10 experiments, verified live in 9 repos' docs/ |
| L23 the Cog Thesis: trainable cells | quilt-dba + exoj | **QUEUED** | hypothesis + falsifiable test. **nothing measured yet** |
| L24 I/O determinacy across 9 cells | quilt-dba | **QUEUED** | unblocks L23. needs the mismatched-simulator control |
| L25 neural extraction on Connect 4 | connect4 | **QUEUED** | **unblocked.** ground truth exists, labels are exact |
| L26 4x4 composition: does the 3x3 effect replicate? | ga4444 | **QUEUED** | **unblocked. complete tree, max 9 plies** |
| L27 decision-tree ceiling on 3x3 | pie-minimax | **DONE** | tree 0.6793 vs linear 0.5708 vs floor 0.4206 |
| L28 subagent spawn probe | — | **BLOCKED** | 9 dispatches, 0 artifacts. probe dispatched, no reply |
| L29 depth-matched COMPOSED vs SIMPLE | pie-minimax | **QUEUED** | the naive version has the WRONG SIGN |

## L23/L24 — the Cog Thesis (Casey, 2026-09-30 23:57)

> "quilt-dba and exoj are two sides of the same coin... both can be grown into something that
> can have parts trained easily using simulated data because the smaller nuclear routes and
> objects have a defined role from the view of the inputs and outputs connected to it and the
> job is inside a cellular neural system so the simulation data has a lot of filters working
> leading in and out and lots of ways to distill and teach a cell beyond random generation
> being a definable cog in a system."

**The thesis, sharpened:** a component inside a cellular system is learnable from simulated
data when its role is **computable from its own I/O contract**, and the surrounding system
filters enough that simulating the I/O is faithful. Synthetic data is normally unfaithful;
this claims faithfulness is available *by construction* rather than by luck, because the
system constrains the socket.

**The falsifiable prediction, and the experiment:** define `determinacy(c) = 1 - output
entropy under fixed input`. **The transfer gap between simulated-trained and real-trained
should be a decreasing function of `determinacy`.** That correlation *is* the test. Nine cells
in `quilt-dba/engine/cells/` (`ai api formula io listener program router sensor value`) give
the range; `exoj`'s formalism (Field as a category, observers as functors) is what makes
"computable from its I/O" precise rather than intuitive. **Neither repo alone can test it.**

**A control that cannot fail is the obvious failure mode here.** Train on a deliberately
mismatched simulator: if the transfer gap does not widen, the original simulator was not
carrying the signal and the thesis is **untested, not supported**. It is also the most likely
outcome, because real and simulated distributions may be too similar to distinguish.

**Full doc:** [`fleet-triage/docs/COG-THESIS.md`](https://github.com/SuperInstance/fleet-triage/blob/main/docs/COG-THESIS.md)

**NOTHING HERE HAS BEEN MEASURED.** This is a hypothesis with a test, not a result.

## Wave 1 — the fleet, instrumented before it is judged

**Do not guess which repos need help; measure it.** `fleet-triage/triage.py` reads every
repo's recursive tree and computes eight mechanical signals: `hollow` (0-byte source),
`untested`, `nolicense`, `noverify`, `failopen`, `autopub`, `vendored`, `historybloat`.
A read that fails is recorded `unreadable`, never as a clean bill of health.

**The instrument had the defect it was built to hunt, and I found it by testing it.** The
`pipefail` check was originally *per workflow file*, so one job that set `-o pipefail`
silently exempted every other job in the same file. That is the whole pattern again: a
control that runs, is satisfied, and gates nothing. Now checked **per step**, with a
negative control — a file where one job is guarded and one is not must flag exactly one.

**A finding about the fleet's shape:** `/orgs/SuperInstance/repos` returns **404** while
`/user/repos` returns everything. **The namespace is a user account, not an organisation.**
That is not cosmetic — org-level Actions policy, team-scoped secrets, and org branch
protection defaults do not exist for a user namespace, and any governance assumption built
on "our org" is false here.

**Also:** 62 of the 500 most-active repos report **no language at all**, which is what
GitHub says when the only source files are empty or absent. `hermes-memory-mcp` is a
confirmed instance (706 "src" files, all vendored zod; `mcp-server.ts` is 0 bytes; `main`
points at a file that does not exist). The cluster is under investigation.

## The instrument was wrong, and the arithmetic caught it

`covers` reported **344 MB of files inside a 291 MB repo** — arithmetically impossible. That
is not a GitHub quirk; the tree was complete and the true sum was 361 MB. Following it up
found a bug in **my own `historybloat` signal**: it compared API `size` against `src_bytes`,
which is **zero for any repo with no source files**. A ratio against a denominator that can
be zero is not a measurement — it is a construction, and it flagged 106 repos, most of them
docs-only and media-only repos that were never bloated.

**Corrected:** compare against `tree_bytes` (all real blobs), with a 50 KB floor so a tiny
repo with a large history does not dominate. Result: **36 genuine**, and they are exactly
the signature I had recorded independently months ago — `lau-construct-integration-v2`
70,717 KB against a 67 KB tree, `lau-constellation` 302,785 KB against 147 KB.

**70 of 106 were false.** Found by refusing to accept an impossible number, not by reading
the code. The same discipline, applied to my own instrument rather than to someone else's
repo, is the entire method.

## The number 5,127 is not a code number

The sweep's sharpest structural finding. Of the 500 most-active repos:

- **30 have no source files at all** — and they are not broken. `synesis-research` is 502 of
  506 blobs markdown. `papermill` is 245 of 288 markdown. `animal-ai` is 902 YAML + 61 PNG
  and 23 GIFs — an upstream paper's documentation tree. `covers` is 91 MP3 + 37 WAV.
  **These are mirrors of docs and asset repos, counted as fleet members.**
- **60 are over 50% vendored**, some at 99.8% (`Equipment-Context-Handoff`: 10 real source
  files in 9,196 blobs). Their file counts are a measurement of somebody else's dependencies.
- **11 of 17 first-party autopublishers have zero tests**, including `quilt` itself (92
  source files, 1 test). The other 18 autopublishers are forks inheriting upstream CI and
  are **not** a finding — the fork flag is the discriminator, and without it this looks like
  a fleet-wide crisis instead of 17 repos.

## L6 is DONE — and the C solver is the lesson

**54,166 positions, plies 1–6, both known-answer checks passing, all export controls
passing, digest `0x4ef8351a5c319637`.** Labels are solved to FULL depth, not to the export
horizon, so a label is the true game value and not an artefact of how deep we looked.
Normalised to player zero: p0's stones, p0's value, every row, regardless of ply parity.

**I wrote it myself because the subagent produced no artifact.** Fifth time. Rule stands.

**Five bugs, and every single one ran to completion and produced a plausible number:**
1. **C precedence** — `b + 1 << 27` is `(b+1) << 27`. Accidentally right on an empty board,
   silently wrong after the first stone.
2. **The column masks were not column masks** — column 1's evaluated to `0`. Every column
   except column 0 read as "height zero, always playable"; the search explored a board that
   does not exist.
3. **The perspective swap double-counted the stone** — opponent is `mask ^ pos`, not
   `m2 ^ pos`. **The two known-answer checks did NOT catch this** because `has_won()` fires
   before the recursion. The export's stone-count control caught it.
4. **The export's sign flipped with row parity** — every 1-ply row +1, every 2-ply row −1,
   which looks exactly like signal.
5. **My own new control was vacuous** — `rewind()` on a `fclose()`d `FILE*` read nothing and
   reported `OK (0 rows)`. **A control that passes on zero rows is not a control.**

Plus two controls wrong in the *other* direction: the first stone-count check asserted "p1 has
at most one stone", trivially true at ply 1 and false at ply 6 where both have three — so it
**rejected a correct export for being correct.** The invariant is `|p0 − p1| ≤ 1`.

**THE PLAN WAS WRONG.** The brief said extend the Python bitboard. Five bugs, each producing
a number, is the evidence against that. C is where the bitboard is checkable *and* fast.

## L5 is DONE — and the answer was not the one I asserted

**3,338 positions. That is the COMPLETE 4x4 four-in-a-row game tree** — the longest game is
9 plies and every ply from 10 on is empty. Labels exact, p0-normalised, FNV-1a 64 digest
`0xcdc9636c704a7ba2`, byte-identical across two runs.

**The game is a DRAW.** I asserted `+1` into the known-answer check before establishing it.
My solver said `-1`. **Both were wrong.** Two independent methods — a retrograde table over
all 161,029 reachable states, and a plain max-min with no negation — both say `0`.

**The lesson is not that I had a bug. It is that the known-answer check was the wrong
instrument.** I was one step from editing the solver to match my guess. Checking
independently turned a coin flip into a measurement. **Asserting a known answer you have not
established is how a wrong number survives.**

The bug that made it wrong: the C only detected a win by the *player to move*, and checked
the previous mover's line only when the board was full. On a board where games end by ply 9
with two-thirds empty, the search carried on from ended games. Invisible on 7x6.

**`verify.py` ships in the repo.** 2000 random legal positions, 2000 agreements, 0
disagreements. A check you can only run once on the day you write the code is a comment.

**A fact worth having:** all four one-ply positions are 0. After *any* first move the
position is still a draw. The 4x4 opening is not a winning attempt at all.

## L27 is DONE — and it retires the original headline

**Decision-tree ceiling on 3×3, 5-fold cross-validated, variance across DATA FOLDS:**

| model | all 2,423 | single-optimal only (n=1246) |
|---|---|---|
| random empty cell (floor) | 0.5753 ± 0.0212 | 0.4206 ± 0.0284 |
| **linear 9×9** | 0.7148 ± 0.0170 | **0.5708 ± 0.0175** |
| **decision tree, depth 16** | **0.7879 ± 0.0224** | **0.6793 ± 0.0289** |

**The linear model reaches 0.840 of the best tree.** So 0.1807 was never "a neural net is bad
at minimax" — it was **"a linear map is bad at minimax"**, true and much less interesting,
and it was reported without the number that would have said so.

### The state count I had been carrying was impossible

**180,361 reachable our-turn states** — a 3×3 board has 3⁹ = **19,683** distinct states, so
even with whose-turn labelled the ceiling is 39,366. **The figure exceeded the entire state
space by 4.6×.** Real numbers: **5,478** reachable states, **2,423** with us to move,
**48.6%** (not 14.7%) with more than one optimal move. Corrected in 4 repos.

Same failure family as the fleet `historybloat` signal: **a count nobody checked against the
size of the space it claims to count.** 3⁹ = 19,683 is checkable in your head.

### The composition penalty is a property of ADDITIVITY, not of the task

Pre-registered SIMPLE/COMPOSED split, normalised by fraction of headroom closed:

```
subset                     chance     tree   linear     tree fills  linear fills
SIMPLE   (0-1 own threat)    0.2547   0.6685   0.5509          55.5%         39.7%
COMPOSED (2+ own threats)    0.5395   0.8008   0.6435          56.7%         22.6%
```

**The tree shows NO composition penalty (55.5% vs 56.7%, indistinguishable). The linear model
loses ~43% of its closed headroom.** So minimax composition is not beyond these models — it
is beyond *this representation*. A sum of local votes cannot represent a count over separate
lines; a model that can form intermediate conjunctions can, and does.

**And the naive version of this contrast has the WRONG SIGN.** A position with two own
threats is structurally a *late* position, so its chance level is already 0.54 and raw
accuracy reads as "COMPOSED is harder" when it is not. L29 is the depth-matched version.

## The two real blockers

**Compute (L5, L6).** Every game rung needs ground truth, and pure-Python negamax does not
finish. The C bitboard solver is the answer and it is not a research question — it is a
half-day of work. **This blocks two lanes and unblocks the whole ladder.**

**Credentials (L9).** `mcode-tools` is installed and its launcher works; every remote call is
rejected with `invalid signature`. That is a credentials problem, not a capability problem,
and only Casey can fix it.

## What I should have done two hours ago

Stop running everything serially inside one context. L5, L6, L7 and L8 do not depend on each
other. Three of them are subagent-shaped right now.
