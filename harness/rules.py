#!/usr/bin/env python3
"""
rules.py — the two lint rules as SHIPPED, with this lane's calibrations applied.

This module does not reimplement either rule. It imports the sibling lane's
`canfail.py` and `fleetlint_failopen.py` and applies two documented refinements on
top. The point of the indirection is that the negative-control suite and the fleet
sweep must drive the SAME code. A control that tests module A while the sweep ships
module B is a control of nothing.

REFINEMENT 1 — `uses:`-only jobs are UNVERIFIABLE, not FAIL
-----------------------------------------------------------
canfail reads only `run:` bodies. A job built entirely from composite/Docker actions
reports `can_fail: False`, i.e. "this workflow cannot fail". That is a false positive:
a composite action absolutely can fail, the rule simply cannot see inside it.

Measured on 275 repos: 2 of 66 can-fail-ci findings are this shape. Left as FAIL they
inflate the count with claims the rule is not entitled to make. Downgraded to
UNVERIFIABLE, which is the honest verdict: not checked, not cleared.

REFINEMENT 2 — rule B's "a runner collects it" exemption requires that the runner
              would actually collect SOMETHING
---------------------------------------------------------------------------
fleetlint_failopen v4 suppresses rule B for any file matching `test_*.py` on the
reasoning that pytest supplies the implicit fail-on-exception assertion. That
reasoning is sound only if the file defines tests. A file named `test_verify.py`
containing no `def test_*`, no `it(`, no `test(` is collected by pytest and collects
NOTHING — the suite reports success over an empty roster, which is the same disease
one level up.

So the exemption is narrowed: a pytest-named file is exempt only if it actually
defines at least one test. This is a strict narrowing of an exemption, so it can only
add findings, never remove them.

REFINEMENT 3 - an env-var prefix is not the absence of a command
---------------------------------------------------------------
canfail skips any `run:` line matching `^[A-Za-z_][A-Za-z0-9_]*=` on the reasoning
that "a variable assignment cannot fail the shell". That is true of a line that is
ONLY assignments, and false of the overwhelmingly common form

    PYTHONPATH=src pytest -q
    RUST_BACKTRACE=1 cargo test
    CI=true npm test

which are three real gates. The current code declares all three as "no executable
command", i.e. it reports a working CI as inert. That is the fail-detector failing
open, which is the one direction this lane exists to remove.

Measured fleet impact: 1 repo (quilt-crabbox), 2 findings. Small here, severe in
kind -- `FOO=bar <cmd>` is how most real CI configures a run, so this under-counts
badly on any fleet with a richer CI set than these 275 clones.

Fixed by narrowing the skip to lines that are ENTIRELY assignments, and stripping the
prefix before judging the command that follows. Applied as a scoped patch of
canfail.RUNNER rather than a fork, so the sibling rule keeps working unchanged
everywhere else.

All three refinements are recorded in negctl/controls.py as controls, so none can be
introduced silently.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (str(HERE), str(HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import contextlib

import canfail                                # noqa: E402
import fleetlint_failopen as fh               # noqa: E402

# ── REFINEMENT 3 ───────────────────────────────────────────────────────────────
_ASSIGN_ONLY = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*=(?:'[^']*'|\"[^\"]*\"|[^\s]*)(?:\s+|$))+\s*$")
_ENV_PREFIX = re.compile(
    r"^(?:[A-Za-z_][A-Za-z0-9_]*=(?:'[^']*'|\"[^\"]*\"|[^\s]*)\s+)+")


class _RunnerShim:
    """Stands in for canfail.RUNNER: matches ONLY assignment-only lines.

    canfail calls `RUNNER.match(piece)` and skips on a hit. Returning a hit for
    `PYTHONPATH=src pytest -q` is what made the rule blind to real gates. This hits
    only when nothing but assignments remain.
    """

    def __init__(self, inner):
        self._inner = inner

    def match(self, s, *a, **k):
        return True if _ASSIGN_ONLY.match(s.strip()) else None

    def search(self, s, *a, **k):
        return self._inner.search(s, *a, **k)

    def sub(self, *a, **k):
        return self._inner.sub(*a, **k)

    def finditer(self, *a, **k):
        return self._inner.finditer(*a, **k)


@contextlib.contextmanager
def _env_prefix_patched():
    """Strip env-var prefixes so the command after them is judged on its merits."""
    orig_runner, orig_split = canfail.RUNNER, canfail._split_top
    canfail.RUNNER = _RunnerShim(orig_runner)

    def split_top(s, ops):
        return orig_split(_ENV_PREFIX.sub("", s), ops)

    canfail._split_top = split_top
    try:
        yield
    finally:
        canfail.RUNNER, canfail._split_top = orig_runner, orig_split


# a file that actually defines tests the runner will collect
DEFINES_TESTS = re.compile(
    r"""
    ^\s*(?:async\s+)?def\s+test[A-Za-z0-9_]*\s*\(      # py
    | ^\s*(?:it|test|describe)\s*\(                    # jest/mocha/node:test
    | \bclass\s+Test[A-Za-z0-9_]*\b                   # unittest
    """,
    re.MULTILINE | re.VERBOSE,
)


def declares_own_failure(src: str) -> bool:
    """Does the file roll its own pass/fail tally and act on it?

    v1 of REFINEMENT 2 reused the sibling rule's DIY_COUNTER, which matches
    `FAIL++` but not `FAIL += 1`, and required the counter to be initialised with
    `let/const/var NAME = 0`. On the fleet that produced a FALSE POSITIVE on
    gpu_bpe4quilt/tests/test_quilt_bpe.py -- a real, working, fail-closed harness of
    ~40 hand-rolled `check(name, got, want)` calls ending in
    `sys.exit(1 if FAIL else 0)`. The rule called it a defect. It is the best harness
    in the sweep.

    The lesson generalises past this one file: an exemption is only as good as the
    predicate that overrides it, and a narrow override predicate silently converts
    every well-written non-idiomatic harness into a finding. So the check is written
    as "does it increment anything named like a failure, in any of the four ways
    people actually write that", rather than as one regex.
    """
    if re.search(r"\b(?:let|const|var)\s+[A-Za-z_$][\w$]*\s*=\s*0\b"
                 r".{0,600}?\b(?:fail|failures|failed|errors)\s*\+\+",
                 src, re.DOTALL | re.IGNORECASE):
        return True
    # augmented / plain increments on a failure-shaped name. The group is CAPTURING
    # because the third alternative backreferences it; `(?:...)` there is a
    # re.error, not a style choice.
    if re.search(r"\b(fail|fails|failure|failures|failed|error|errors|bad)\b"
                 r"\s*(?:\+\+|\+=\s*1|=\s*\1\s*\+\s*1)",
                 src, re.IGNORECASE):
        return True
    # a tally consulted in a conditional that decides the exit status
    if re.search(r"\bexit\s*\([^)]*\b(?:fail|FAIL)\b", src):
        return True
    if re.search(r"\bsys\.exit\s*\(\s*1\s+if\b", src):
        return True
    if re.search(r"\bprocess\.exit(?:Code)?\s*=?\s*[^;]*\b(?:fail|FAIL)\b", src):
        return True
    return False


def workflow_verdict(path: str, text: str):
    """File-level verdict for one workflow, with REFINEMENT 1 applied.

    Returns (verdict, jobs) where verdict is one of:
      "FAIL"          a readable gate exists  -> can fail
      "FIRE"          no readable gate        -> the finding
      "UNVERIFIABLE"  not read; neither fired nor cleared

    v1 of this helper aggregated with `any(finding)`, which is a STEP-level truth
    reported as a FILE-level one: a workflow with one guarded job and one inert job
    has a real step finding and a green file verdict, and the control went red on
    exactly that pair. Aggregation level is not a detail.
    """
    with _env_prefix_patched():
        r = canfail.analyse_workflow(path, text)
    if r.get("unverifiable"):
        return "UNVERIFIABLE", r["jobs"]
    readable = []
    for job in r["jobs"]:
        runs = [s for s in job["steps"] if s["can_fail"] is not None]
        if runs and all("uses-step" in ";".join(s["reasons"]) for s in runs):
            continue                      # REFINEMENT 1: not read, so not a finding
        readable.extend(s for s in job["steps"] if s["can_fail"] is False)
    if r["can_fail"] is False and not readable:
        return "FIRE", r["jobs"]
    if r["can_fail"] is False:
        return "FIRE", r["jobs"]
    return "FAIL", r["jobs"]


def can_fail_ci(root: str) -> dict:
    """can-fail-ci, per step, with uses-only downgraded to UNVERIFIABLE."""
    findings, unverifiable = [], []
    for wf in canfail.workflows_under(root):
        try:
            text = Path(wf).read_text(errors="replace")
        except Exception as e:
            unverifiable.append({"file": os.path.relpath(wf, root),
                                 "why": f"unreadable: {e}"})
            continue
        with _env_prefix_patched():
            r = canfail.analyse_workflow(wf, text)
        rel = os.path.relpath(wf, root)
        if r.get("unverifiable"):
            unverifiable.append({"file": rel, "why": r.get("error")})
            continue
        for job in r["jobs"]:
            for st in job["steps"]:
                if st["can_fail"] is False:
                    # REFINEMENT 1: a job whose every step is `uses:` was never read.
                    runs = [s for s in job["steps"] if s["can_fail"] is not None]
                    if runs and all(
                        "uses-step" in ";".join(s["reasons"]) for s in runs
                    ):
                        unverifiable.append({
                            "file": rel, "job": job["job"],
                            "why": "all steps are `uses:` — not readable, not cleared",
                        })
                        continue
                    findings.append({
                        "repo": os.path.basename(root.rstrip("/")),
                        "rule": "can-fail-ci", "file": rel, "job": job["job"],
                        "step": st["index"], "step_name": st["name"],
                        "reasons": st["reasons"],
                    })
    return {"findings": findings, "unverifiable": unverifiable}


def fail_open_harness(root: str) -> dict:
    """fail-open-harness, with the rule-B exemption narrowed (REFINEMENT 2)."""
    out = []
    for f in fh.lint_repo(root):
        f = dict(f)
        f["repo"] = os.path.basename(root.rstrip("/"))
        f["rule"] = "fail-open-harness/" + str(f.get("rule"))
        out.append(f)
    # Anything the raw rule suppressed purely on the pytest-name exemption, but which
    # defines no tests, is recovered here.
    #
    # v1 called `fh.check_no_assert(...)` to decide whether the raw rule *would* have
    # fired. That function is exactly where the exemption lives, so it returned [] and
    # the recovery never triggered. The condition is therefore spelled out here rather
    # than delegated, and `is_collector_exempt` is the single definition of the
    # exemption both the sibling rule and this recovery must agree on.
    for rel in _harness_files(root):
        if not rel.endswith(".py") or not fh.PY_TEST_RE.search(rel):
            continue
        if not is_collector_exempt(rel):
            continue
        p = Path(root) / rel
        try:
            src = p.read_text(errors="replace")
        except Exception:
            continue
        if DEFINES_TESTS.search(src):
            continue
        if (fh.ASSERT_PRIMITIVES.search(src) or fh.HANDROLLED.search(src)
                or declares_own_failure(src)):
            continue
        out.append({
            "repo": os.path.basename(root.rstrip("/")),
            "rule": "fail-open-harness/B", "file": rel, "line": 1,
            "detail": "named like a pytest module but defines no test and "
                      "declares no assertion; the runner collects an empty "
                      "roster and reports success over it",
        })
    return {"findings": out, "unverifiable": []}


def is_collector_exempt(rel: str) -> bool:
    """fleetlint_failopen v4's exemption, named so both copies of the rule agree.

    A file is exempt from rule B when a test runner is expected to collect it. That
    is true if it lives in a tests/ directory or matches pytest naming. What v4 did
    not check is whether the runner would collect anything AT ALL -- see
    REFINEMENT 2 in this module's docstring.
    """
    return bool(fh.COLLECTED_DIR.search(rel) or fh.PY_TEST_RE.search(rel))


def _harness_files(root: str):
    for rel in fh.git_files(root):
        if fh.is_harness(rel, Path(rel).suffix):
            yield rel


def lint_repo(root: str) -> dict:
    ci = can_fail_ci(root)
    ho = fail_open_harness(root)
    return {"can-fail-ci": ci["findings"],
            "can-fail-ci_unverifiable": ci["unverifiable"],
            "fail-open-harness": ho["findings"]}
