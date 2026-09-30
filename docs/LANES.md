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
| L5 4x4 four-in-a-row + composition | ga4444 | **BLOCKED** | solver correct; 7-ply generation too slow. **needs the C solver** |
| L6 connect4 ground truth | connect4 | **BLOCKED** | same. needs a ply-bounded C export |
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
