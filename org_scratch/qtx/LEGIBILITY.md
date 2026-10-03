## What this is

A read-only legibility pass. **No existing file is modified** — this PR only adds
`LEGIBILITY.md`, and it is trivially deletable. Close it and nothing else changes.

### Why

A census of 100 fleet repos (`SuperInstance/quilt-research-canons/projects/fleet-legend/`)
graded every repo against five obligations. This one already passes entry (L1, L2); it
fails the two that only cost something once a reader is already inside:

- **L4 — what this does NOT do.** Missing in 55 of 100 repos.
- **L5 — what to do when it fails.** Missing in 59 of 100 repos.

### What is in here, and where each line came from

5 finding(s), each read out of the repository and each carrying its evidence. Nothing
is inferred from the README, because the README is the thing being fixed.

| finding | evidence |
|---|---|
| A CI workflow exists (1 file(s), e.g. `.github/workflows/ci.yml`), but which events it runs on and what it actually executes are decided inside that file, not here | `.github/workflows/ci.yml` exists in the tree |
| It ships no automated tests, so nothing here is verified automatically | file listing: no path matches `tests/`, `test_*.py`, `*_test.{go,py,ts}`, or `*.test.*js` |
| It carries no LICENSE file, so there is no stated grant to copy from, modify or redistribute it | file listing: no path matches `LICENSE*` or `COPYING*` |
| The repository has a build file (`package.json`) but no test entry point was found in it, so there is no command to cite as a receipt | `package.json` read; no `test` script/target matched |
| Error-raising calls are not collected in one place: 3 call sites appear across 16 files (`src/toolkit.mjs`:91; `experiments/s2-driftwatch-jev.mjs`:51; `experiments/s1-triagedesk-live.mjs`:29). Nothing in the repository treats them as a set, so a reader who hits one has to grep for it | read 16 of 38 (a sample, so this is a lower bound) source file(s) in the tree; grep: `raise|throw|panic!|log.Fatal|process.exit` |

### What we deliberately did NOT write

- **Failure modes (L5).** 3 error-raising call sites exist in the source (16 of 38 (a sample, so this is a lower bound) file(s) read), but the *message a user sees* and *what to do about each one* are not derivable from a file listing. Write the two or three that actually happen. A human has to supply these; guessing them is how a completer invents a failure mode.

A completer that invents a receipt or a failure mode produces a confident lie, and a
confident lie is worse than a blank space, because a reader cannot tell it from a real
limitation. Where a fact was not derivable, this file says so instead of filling the gap.

### If you want to accept part of this

Take the table and ignore the rest. Every row is a predicate over the file listing or over
named source lines, so disagreeing with a row costs you one `ls` or one `grep` — say so in
a review comment and the line gets corrected or dropped.

Reviewed with tooling from `SuperInstance/quilt-research-canons/projects/fleet-legend/`.
