# PRODUCTION — fleet-kit, production lane

**Lane:** production. **Date:** 2026-10-01. **Base:** `5ad1e81` on `ci-production-sweep`.
**Nothing pushed.** All work is committed on the branch for review.

## Where this ran, and one thing to know first

The brief said to work in `/workspace/projects/fleet-kit/`. That directory contains only
the `fleetlint/` subproject and a stray copy of `fleetlint.py` — it has no `pyproject.toml`,
no `tests/`, no `.git`, and no `fleet_kit/` package. The repository is at
**`/workspace/projects/prod/fleet-kit/`** (branch `ci-production-sweep`, remote
`SuperInstance/fleet-kit`, base commit `5ad1e81`, the commit the playtest lane audited).
All work below is there. A copy of this report is in `/workspace/projects/fleet-kit/`.

**Environment note, because it changes what the proofs mean:** the brief said PyPI is
unreachable and that `pip install --break-system-packages` works. In this sandbox `pip`
was not installed at all and `ensurepip` is missing, so neither was true. `pypi.org` and
`files.pythonhosted.org` *were* reachable, so pip was bootstrapped from `get-pip.py`.
That is an environment fix, not a deliverable — but it is why blocker 3 could be proven
at all rather than argued.

---

## Blocker 1 — the six files that were not collected

### What they were

Six of twelve test modules died **at import**. `pytest` aborts the entire run on a
collection error, so the suite did not report red; it reported *short*, which is
indistinguishable from a smaller but complete suite. Two distinct root causes:

| # | files | cause |
|---|---|---|
| 4 | `test_audits.py`, `test_crab.py`, `test_matrix.py`, `test_plato.py` | `example_dir = "/home/ubuntu/.openclaw/workspace/repos/fleet-kit"` — a hardcoded absolute path to the original author's home directory. `FileNotFoundError` on every machine but his. **39 tests.** |
| 2 | `test_badges.py`, `test_plugins.py` | `import yaml` in `fleet_kit/plugins.py:10`, and `PyYAML` was **not declared in `pyproject.toml`**. `test_badges.py` reaches it via `fleet_kit/__init__.py:34`. |

The playtest lane's "6 of 12 files" is exactly these six. Neither cause is a test bug;
both are repository bugs, and both are in my lane.

A third instance of the same family sat one layer up: **five product modules defaulted
to `/home/ubuntu/.openclaw/workspace/...`** as a default *argument*
(`audits.py:106`, `badges.py:55`, `indexer.py:49`, `plugins.py:15`, `cli.py:176`). A
caller who omitted the flag got a nonexistent directory, and an audit of nothing reports
"0 findings". Also fixed.

### The command that proves it

```console
$ cd /workspace/projects/prod/fleet-kit
$ python3 -m pytest -q
........................................................................ [ 77%]
..........................................                               [100%]
186 passed in 2.87s
```

13 files, 186 tests, **0 collection errors**. Per file:

```console
$ python3 -m pytest --collect-only -q | grep '::' | cut -d: -f1 | sort | uniq -c
      9 tests/test_audits.py        <- was 0 (hardcoded path)
      7 tests/test_badges.py        <- was 0 (undeclared yaml)
     10 tests/test_consensus.py
      8 tests/test_construct.py
     12 tests/test_crab.py          <- was 0 (hardcoded path)
     65 tests/test_fleetlint.py     <- NEW: the linter's own suite, which did not exist
      3 tests/test_indexer.py
      4 tests/test_keeper.py
      8 tests/test_matrix.py        <- was 0 (hardcoded path)
      7 tests/test_models.py
     10 tests/test_plato.py         <- was 0 (hardcoded path)
     18 tests/test_plugins.py       <- was 0 (undeclared yaml)
     12 tests/test_services.py
     13 tests/test_utils.py
```

The "before", with the old `tests/` restored and **only** the `PyYAML` fix applied, so
the hardcoded-path failures are isolated:

```console
$ git checkout 5ad1e81 -- tests/ && python3 -m pytest -q
E   FileNotFoundError: [Errno 2] No such file or directory:
    '/home/ubuntu/.openclaw/workspace/repos/fleet-kit/fleet_kit/plato.py'
ERROR tests/test_audits.py - FileNotFoundError: [Errno 2] No such file or dir...
ERROR tests/test_crab.py   - FileNotFoundError: [Errno 2] No such file or dir...
ERROR tests/test_matrix.py - FileNotFoundError: [Errno 2] No such file or dir...
ERROR tests/test_plato.py  - FileNotFoundError: [Errno 2] No such file or dir...
!!!!!!!!!!!!!!!!!!! Interrupted: 4 errors during collection !!!!!!!!!!!!!!!!!!!!
4 errors in 0.52s
```

`Interrupted` — **zero tests ran**. That is the mechanism: a collection error does not
make the suite red, it makes the suite short.

### What stops it recurring

`tests/test_fleetlint.py::TestSuiteIntegrity` asserts, as tests rather than as promises:

* every `tests/test_*.py` on disk appears in `--collect-only` output, and the output
  contains no collection error;
* no string literal in `tests/`, `fleet_kit/` or `fleetlint/` contains `/home/ubuntu`
  (comments and docstrings are excluded so a fix can explain itself);
* every dependency `pyproject.toml` declares is importable, and `import yaml` resolves.

---

## Blocker 2 — the token dependency

### What it was

Every rule took `(repo, ref, token)` and read through `get_text()` → `api.github.com`.
With no token the tool died with `HTTP Error 401: Unauthorized` and no output at all.
The playtest lane reported exactly that. It also meant nothing could run in CI, where
there is no secret.

### What I did

`fleetlint` is now split so that **a rule declares a capability, not a credential**:

* `fleetlint/sources.py` — `LocalSource` (a directory; zero credentials, zero network)
  and `GitHubSource` (`api.github.com`; needs `GITHUB_TOKEN`) behind one interface.
* `fleetlint/rules.py` — each rule declares `needs=("tree",)` or `needs=("tree","api")`.
  Twelve of the fifteen rules need only `tree`. **L1** (resolving `require('pkg')`
  against a *different* repository) and **L4** (deriving the fix from the repo's own
  `html_url`) genuinely need the API and are skipped by name without one.
* A rule that could not run produces a **`Skipped`**, a different type from a **`Finding`**,
  carried in `LintResult` and rendered in both the text and the JSON. It is never folded
  into the count and never summarised as "clean".
* `M5` (history size) on a tree with no `.git` reports an **`info`** finding saying the
  measurement did not happen — visible, but not a permanent exit 3 on every directory.

### The deliverable: a run with no token

The installed console script, no `GITHUB_TOKEN` in the environment, run from
`/tmp/elsewhere` (not the repository):

```console
$ cd /tmp/elsewhere
$ env -u GITHUB_TOKEN /tmp/venv/bin/fleetlint /workspace/projects/prod/fleet-kit

  local:/workspace/projects/prod/fleet-kit  —  0 finding(s)  [high 0 / medium 0 / low 0]
    L7-waived info   fleetlint/selftest.py:36
          the unaccented fixture is here on purpose: this is a NEGATIVE control for L6;
          the accented text must appear for the regex to be proven
          fix: no action; recorded so the waiver is visible
    L7-waived info   fleetlint/templates/node-package/test/canary.test.js:13
    L7-waived info   fleetlint/templates/python-package/tests/test_canary.py:18
    L7-waived info   fleetlint/templates/rust-crate/tests/canary.rs:12
    L7-waived info   tests/test_fleetlint.py:407
    --   SKIPPED L1: no-token
          needs the GitHub API; there is no GITHUB_TOKEN in this environment, so L1
          did not run and has not been cleared
    --   SKIPPED L4: no-token
          needs the GitHub API; there is no GITHUB_TOKEN in this environment, so L4
          did not run and has not been cleared
    L9    info     .rs
          L9 did not read 1 test file(s) in .rs; it analyses Python and JavaScript only
          fix: not an action. Recorded so that 'no finding in L9' is never read as
          'every test was checked' when some were out of reach.

  rule status
    M1   ran      0 finding(s)
    M2   ran      0 finding(s)
    M3   ran      0 finding(s)
    M4   ran      0 finding(s)
    M5   ran      0 finding(s)
    L1   SKIPPED  (no-token)
    L2   ran      0 finding(s)
    L3   ran      0 finding(s)
    L4   SKIPPED  (no-token)
    L5   ran      0 finding(s)
    L6   ran      0 finding(s)
    L7   ran      0 finding(s)
    L8   ran      0 finding(s)
    L9   ran      0 finding(s)   (1 file out of reach, disclosed above)

  TOTAL 0 finding(s) across 1 target(s)
  ── PARTIAL: 2 check(s) DID NOT RUN. The lines above are not a clean bill of health.
       L1 did not run: no-token
       L4 did not run: no-token

EXIT=3
```

**The count is 2, not the 3 you predicted.** L1 and L4 are the only two rules that
genuinely need `api.github.com`. The third boundary I expected — L9 on the `.rs` test
files in `templates/` — I first made a *skip*, and that was wrong: it made exit 3
permanent on any repository containing a Rust test, and a gate that can never return 0
is a gate nobody installs. L9 now *discloses* the files it could not read and still
counts as having run. I would rather print the true list than pad it to the estimate.

The same information, machine-readable:

```console
$ env -u GITHUB_TOKEN /tmp/venv/bin/fleetlint --json /workspace/projects/prod/fleet-kit | \
      python3 -c "import json,sys; d=json.load(sys.stdin); \
      print('complete:', d['complete']); \
      print('skipped :', [(s['rule'], s['reason']) for t in d['targets'] for s in t['skipped']])"
complete: False
skipped : [('L1', 'no-token'), ('L4', 'no-token')]
```

### A *remote* target with no token

There is nothing to read — not even a file list — so the tool refuses to start, loudly,
and offers the credential-free path. It does not exit 0, and it does not print "clean":

```console
$ env -u GITHUB_TOKEN /tmp/venv/bin/fleetlint SuperInstance/pong-quilt
  SuperInstance/pong-quilt  --  PermissionError: the GitHub source needs a token.
  Set GITHUB_TOKEN, or point fleetlint at a local checkout (fleetlint ./path/to/repo)
  -- every mechanical check runs there with no credentials at all.
EXIT=2
```

### The gate that can actually gate

A linter that can never return 0 gets ignored, so the no-credential subset is the CI gate
and it can be green:

```console
$ env -u GITHUB_TOKEN /tmp/venv/bin/fleetlint --rules M1,M2,M3,M4,M5,L2,L3,L5,L6,L7,L8,L9 /workspace/projects/prod/fleet-kit
  ...
  TOTAL 0 finding(s) across 1 target(s) — all 12 rules ran
EXIT=0
```

### Tests, not claims

`tests/test_fleetlint.py::TestNoCredentialIsNoExcuse` and `::TestExitCodes` cover it:
`LintResult.complete` is `False` whenever anything was skipped; the JSON carries
`"complete": false`; the exit code is 3; the output contains `DID NOT RUN` and does not
contain a clean bill of health; a `Skipped` and a `Finding` are different types; and a
rule that raises is a `LintHarnessBroken` that **aborts** the run rather than shortening
the list.

---

## Blocker 3 — the wheel

### What it was

`pyproject.toml` shipped `include = ["fleet_kit", "fleet_kit.*"]`. `fleetlint/` was not a
package — it was a directory containing one loose script — so `pip install fleet-kit`,
the documented install, did not deliver the linter at all.

### What I did

* `fleetlint` is a package: `__init__.py`, `__main__.py`, `model.py`, `sources.py`,
  `rules.py`, `vacuous.py`, `selftest.py`, `scaffold.py`, with `fleetlint.py` retained as
  the runnable shim so the documented `python3 fleetlint/fleetlint.py <repo>` still works
  (tested).
* `[project.scripts] fleetlint = "fleetlint.fleetlint:main"`, and `packages` lists
  `fleetlint` explicitly.
* `PyYAML>=5.1` declared, because `plugins.py` imports it.
* `requires-python = ">=3.9"` (3.8 has no `importlib.resources.files`).
* `pythonpath = ["."]` in the pytest config, because bare `pytest` did not put the repo
  root on `sys.path` and the suite only ever passed via `python -m pytest`.
* The templates now have a **code path that finds them** — `fleetlint --templates`,
  `--scaffold` — which is what makes the packaging requirement load-bearing instead of
  decorative.

### The packaging bug, and the one I introduced fixing it

The first `package-data` attempt globbed `templates/*` through `templates/*/*/*/*/*/*`.
The resulting wheel was missing **every** `templates/*/.github/workflows/ci.yml` —
because `*` does not match a leading dot — and carried three `__pycache__/*.pyc`. Both
failures are invisible in the source tree and appear only after `pip install`.

The list is now enumerated by name, and a test holds it equal to the directory:

```
templates/docs-site/.github/workflows/ci.yml
templates/node-package/.github/workflows/ci.yml
templates/rust-crate/.github/workflows/ci.yml
```

### The command that proves it

```console
$ python3 -m venv /tmp/venv
$ pip install .
Successfully built fleet-kit
Successfully installed PyYAML-6.0.3 fleet-kit-0.2.0

$ cd /tmp/elsewhere            # NOT the repository
$ env -u GITHUB_TOKEN /tmp/venv/bin/fleetlint --selftest
  fleetlint self-test OK -- 14 rules, 6 L6 pattern controls,
  6 L9 controls (1 positive, 4 negative, 1 waiver)
exit=0

$ /tmp/venv/bin/fleetlint --templates
/tmp/venv/lib/python3.11/site-packages/fleetlint/templates
  docs-site        2 file(s)
  node-package     4 file(s)
  python-package   5 file(s)
  rust-crate       4 file(s)

$ /tmp/venv/bin/fleetlint --scaffold python-package /tmp/elsewhere/newrepo
  python-package -> /tmp/elsewhere/newrepo
$ find /tmp/elsewhere/newrepo -type f
/tmp/elsewhere/newrepo/pyproject.toml
/tmp/elsewhere/newrepo/src/PKG/canary.py
/tmp/elsewhere/newrepo/tests/test_canary.py

$ /tmp/venv/bin/fleet-kit --help
usage: fleet-kit [-h] [--version] {plato,keeper,audit,badges,index} ...
```

`--templates` resolves to **`site-packages`**, not to the source tree. That is the whole
claim: everything works in the checkout and works after install, from a directory that is
not the repository, with no credentials.

15 of 15 template files present in the wheel; the three `.github/workflows/ci.yml` files
that the glob version dropped are in it.

---

## The rule you asked for — L9 `vacuous-test`

### The shape

A test whose **assertions** reference only literals and constants defined inside the test
body, and whose body never mentions the product, cannot be a test of the product. It is
the shape of `voxelglyph`'s `test_weights_sum_256`:

```python
def test_weights_sum_256(self):
    # The docstring's load-bearing claim: weights sum exactly 256, so the
    # >>8 is an exact normalisation, not an approximation.
    self.assertEqual(77 + 150 + 29, 256)
```

The real `LUMA_WR` could sum to 294 and the suite stayed green. This is a **syntactic
reachability** check, not a mutation, and it is reported as one. The closure is taken to a
fixed point through local bindings, module-level bindings, comprehension targets, `for` /
`with` targets and fixture attributes, so `widest = self.result["widest"]` followed by an
assert on `widest` counts as reaching the product.

### The two controls you named

| control | source | expected | measured |
|---|---|---|---|
| **positive** | `voxelglyph` at `6553863`, the real file, extracted with `git show` | fires on `test_weights_sum_256` | **1 finding, exactly that test** |
| **negative** | `pong-quilt` at `HEAD`, 64 test files, 301 tests, cloned | silence | **0 findings across all 64 files** |

Both are in `fleetlint/selftest.py` and run under `--selftest` and in the suite.

Because a control that only proves a rule *can* fire does not prove it is useful, I also
measured the **same pong-quilt file with one test mutated** into the canonical defect
(its body replaced with `const zero = 0; assert.equal(zero, 0)`). The same file that is
silent unmutated produces exactly 1 finding mutated. Same file, same harness, same rule —
the only thing that changed is the one test.

And the fix the fleet actually applied is silent: `voxelglyph` at `425b746`, where
`test_weights_sum_256` now reads `sum(LUMA_WR)`, produces **0 findings**.

### The false-positive rate, measured

Naïvely shipped, the rule produced **331 false positives in one repository**
(`sunset-ecosystem`, out of 8,780 tests) because its tests receive the product through
`@pytest.fixture`, and **111 across pong-quilt** from the observer pattern. Both are
fixed by scoping, and the scoping is stated in the rule's docstring:

* a test with a **fixture parameter** is left alone;
* a test whose **body** mentions the product is left alone, however indirect the
  assertion;
* a test that imports **nothing of yours** is not this rule's business;
* a test reading a **file** (`FINDINGS.md`, a fixture on disk) is a data pin, not a
  vacuous test.

Fleet sweep over every `tests/**` directory in `/workspace/repos` and
`/workspace/projects/prod` — 288+ Python test files, 9,915 tests:

```
FLEET: 5 findings over 9,915 tests
  3  sunset-ecosystem   -- all three are `assert True` placeholders
  1  quilt-spreadsheet  -- test_fnv1a_64 re-implements FNV-1a in the test body and
                           asserts 0x024a555471370b18d without calling the product
  1  quilt-egg          -- the same defect
```

The two `fnv1a_64` cases are the same species as the canonical one: the canary is pinned
against a *copy of the algorithm* typed into the test. The product's own `fnv1a_64` could
be wrong and both suites would stay green. That is the rule doing what it was built for
on a defect nobody has reported yet.

### What it does not catch — stated plainly

* It is not a mutation. A test can reference the product and still not notice if the
  product is wrong. That is what the playtest lane's mutations are for.
* **It does not catch `quilt-tools`.** The second species — the product runs, and the
  judge cannot fail — is not a reachability property, and a syntactic rule cannot see it.
  Catching it needs a harness mutation: run the suite with the grader replaced by one that
  always fails, and require red. `fleetlint` has no such rule and I did not write one; it
  is the remaining gap, and it is a real one.
* Product references smuggled through a runtime mutation or a deep object lookup are not
  seen.
* It analyses Python (via `ast`) and JavaScript (lexically). Other languages are
  **skipped by name**, which is why L9 appears in the skip list above.

### The waiver, and why it prints

`# fleetlint:waive vacuous-test <reason>` silences a finding. A waiver is accepted only
within four lines of the finding (a comment at the top of a 900-line file is a switch,
not a waiver) and it is **printed in the output and carried in the JSON** as
`L7-waived` / a recorded reason. An escape hatch nothing audits is the `quilt-gpu-lab
--allow-dirty` failure class with fresh paint.

---

## Things I found that were not on the list

1. **L8 could not fire.** `LOAD_ONLY.findall(src, re.M)` — `re.M` is the integer 8, and
   `findall`'s second positional argument is `pos`, not `flags`. Every file was scanned
   from character 8 with `MULTILINE` never set. Fixed, with a regression test.
2. **L2 was advertised and never implemented.** The docstring and the README both list
   `L2 canary-missing`; `check_metadata` never emitted an `L2`. The original signal
   ("a repo in a polyformal fleet with no canary") is not reproducible from a single
   repository. It is now implemented narrowly and honestly: *a tree that carries a canary
   and has no CI that could run it*. Repos with no canary are silent, because we do not
   know they are fleet members.
3. **`urllib.parse` was never imported.** `get_text` used `urllib.parse.quote` while the
   module imported only `urllib.request` and `urllib.error`. It worked by accident, via a
   transitive import inside CPython's own `urllib.request`.
4. **`fleetlint` had no tests at all**, which is why the playtest lane could not answer
   "does it over-fire?". It has 65 now, and every rule carries a control: a tree it must
   fire on and a tree it must stay silent on. A rule with only a positive control is a
   rule that has not been shown to be able to stay quiet.
5. **M1 was structurally blind.** `LocalSource` pruned vendored directories during the
   walk, so the rule meant to measure vendor bloat never saw the tree. It also counted
   untracked `__pycache__`, which the repository has already declared it does not ship;
   M1 now measures `git ls-files`.

---

## The one remaining `cron` away

`.github/workflows/ci.yml` is added and clears this repository's own L2 finding
("a canary and no CI that could ever run it"). It runs, on push and nightly:

* `python -m fleetlint --selftest` — the instrument, before anything trusts it;
* `python -m pytest -q` — the suite, on 3.9 / 3.11 / 3.12;
* `fleetlint --rules <the 12 no-credential rules> .` — the gate, which can return 0;
* the full run, **asserting exit 3 and asserting the JSON names L1/L4 as skipped** — so
  the "partial" path is itself covered;
* a separate job that installs into a clean venv, leaves the repository directory, and
  asserts the templates resolve inside `site-packages`.

**I have not run it.** No GitHub Actions runner is available in this sandbox, so the
workflow is unverified beyond "the commands in it are the commands in this report, and
they all pass here". Treat the first run as unproven.

---

## Summary against the bar

| | before | after | proof |
|---|---|---|---|
| test files collected | 6 of 12 | **13 of 13** | `pytest -q` → 186 passed, 0 collection errors |
| linter test suite | 0 files | **65 tests** | `pytest tests/test_fleetlint.py -q` → 65 passed |
| mechanical checks with no token | 0 (401) | **12 of 15** | output above, `EXIT=3`, L1/L4 named as not-run |
| "did not run" reported | no | **yes, by name, in text and JSON** | `complete: False`, `skipped: [('L1','no-token'), …]` |
| linter in the wheel | no | **yes, with a console script** | `fleetlint --selftest` from `/tmp/elsewhere`, exit 0 |
| templates after install | n/a | **15/15, in `site-packages`** | `fleetlint --templates` |
| L9 | did not exist | fires on the canonical case, silent on pong-quilt ×64, catches the mutation | `fleetlint --selftest`; 5 findings / 9,915 tests fleet-wide |

---

## Note on this file's location

This copy is at `/workspace/projects/fleet-kit/PRODUCTION.md` because the brief named that
path. The repository itself is at **`/workspace/projects/prod/fleet-kit/`** — the only
directory that has `.git`, `pyproject.toml`, `tests/` and the `fleet_kit/` package. This
directory contains only the `fleetlint/` subproject and a stray root-level copy of
`fleetlint.py`; there is nothing to build or test in it.

The commit is `8b28209` on branch `ci-production-sweep`. Nothing has been pushed.
