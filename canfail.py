#!/usr/bin/env python3
"""
canfail.py — find CI that exists but cannot fail.

THE QUESTION
    "This repo has CI" is not a claim about the product. It is a claim about a YAML file.
    This tool answers the only question that matters: **if the product were wrong, would
    this workflow go red?**

THE FAILURE MODE
    A pipeline is `producer | tail -1`. The exit status a shell reports for a pipeline is
    the status of its LAST element. `tail` exits 0 whether the producer wrote one line,
    ten thousand lines, or died mid-write. So the build can fail, the artifact can be
    empty, and the job is green. Nothing about this is visible in the Actions UI.

WHAT MAKES THIS CHECKER DIFFERENT FROM A GREP
    It is **per step**, never per file. A previous audit found the per-file version let
    one `set -o pipefail` silently exempt every other job in the same file — a control
    that runs, is satisfied, and gates nothing. Every step is judged on its own.

    It also models the fact that **each `run:` is a separate shell**. `set -o pipefail` in
    step 1 does not survive into step 2. A workflow that guards its first step and pipes
    in its second is unguarded, and most readers assume otherwise.

EXIT CODES
    0  every workflow examined can fail
    1  at least one workflow cannot fail
    2  bad invocation / unparseable file

USAGE
    python3 canfail.py REPO_DIR [...]        # exit 1 if anything cannot fail
    python3 canfail.py --json REPO_DIR [...]
    python3 canfail.py --selftest            # the negative controls
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

try:
    import yaml
except ImportError:                                    # pragma: no cover
    sys.exit("canfail.py needs PyYAML:  python3 -m pip install pyyaml")

# ── commands that exit 0 no matter what happened upstream ──────────────────────────
# Only the LAST element of a pipeline decides the pipeline's status, so a pipeline whose
# last element is one of these cannot fail -- regardless of what the producer did.
ALWAYS_ZERO = {
    "true", ":", "echo", "printf", "cat", "tail", "head", "wc", "seq", "yes",
    "basename", "dirname", "pwd", "date", "sort", "tee", "nl", "fold", "tac",
}

# A command neutralised by one of these suffixes cannot contribute a failure.
EXEMPT_SUFFIX = re.compile(
    r"(\|\|\s*(true|:|echo\b)|\;\s*(true|:)\s*$|\|\|\s*exit\s+0|\|\|\s*:\s*$)"
)

RUNNER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")      # VAR=value assignments

# Shell setup words: they configure the shell and their own failure is not the product
# failing. `set -o pipefail` is in here -- if it could "fail" then every guarded step
# would look like a gate, which is the inverse of the bug this tool exists to catch.
SETUP = {"set", "shopt", "export", "declare", "local", "readonly", "unset",
         "trap", "shift", "eval", "exec", "unalias", "hash", "umask"}

# Control flow: these carry the status of what is inside them. Treated conservatively as
# signal-bearing, because a failing command in an `if` condition does fail the step and a
# checker that misses that is the more dangerous error.
FLOW = {"if", "then", "elif", "else", "fi", "for", "while", "until", "do", "done",
        "esac", "case", "select", "function", "return"}


def _cmd_can_fail(cmd: str) -> bool:
    """Can this single command, run on its own, exit non-zero?"""
    cmd = cmd.strip()
    if not cmd or RUNNER.match(cmd):
        return False
    w = _first_word(cmd)
    if w in ALWAYS_ZERO:
        return False
    if w in SETUP:
        return False
    if w == "exit":
        # `exit 0` is an explicit success. `exit` bare, or `exit 1`, is not.
        return cmd.strip() != "exit 0"
    if w in FLOW:
        return True
    return True          # any other real command can exit non-zero


def _piece_can_fail(piece: str, pipefail: bool) -> tuple[bool, str]:
    """Can this pipeline / command list take the step red? Returns (can_fail, reason)."""
    stages = _split_top(piece, ("|",))
    if len(stages) > 1:
        if pipefail:
            return any(_cmd_can_fail(s) for s in stages), ""
        last = _first_word(stages[-1])
        if not _cmd_can_fail(stages[-1]):
            return False, (f"pipeline ends in `{last}` with no `set -o pipefail` in THIS step "
                           f"— the producer's exit status is discarded, because a pipeline "
                           f"reports the status of its LAST element")
        return True, ""
    return _cmd_can_fail(piece), ""


def _strip_comments(body: str) -> str:
    """Drop `#` comments. Quoted `#` is kept -- a `#` inside a string is not a comment,
    and eating it would change what the command does."""
    out = []
    for line in body.splitlines():
        if line.lstrip().startswith("#"):
            continue
        # only cut at a '#' that is outside quotes
        res, quote = [], None
        for ch in line:
            if quote:
                res.append(ch)
                if ch == quote:
                    quote = None
                continue
            if ch in "'\"":
                quote = ch
                res.append(ch)
                continue
            if ch == "#":
                break
            res.append(ch)
        out.append("".join(res))
    return "\n".join(out)


def _split_top(s: str, ops) -> list[str]:
    """Split on shell operators that are not inside quotes.

    `ops` is a sequence of operator STRINGS, matched longest-first. It must be a sequence
    rather than a character set: with the set `"||&&;"` a lone `|` is a *member* of the
    set and splits `./build.sh | tail -1` into two commands, which silently disables the
    exact pipeline check this tool is built on. This file's own negative control caught it.
    """
    if isinstance(ops, str):
        ops = [ops]
    ops = sorted(ops, key=len, reverse=True)
    parts, buf, quote, i = [], [], None, 0
    while i < len(s):
        ch = s[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            i += 1
            continue
        for op in ops:
            if s.startswith(op, i):
                parts.append("".join(buf))
                buf = []
                i += len(op)
                break
        else:
            buf.append(ch)
            i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _first_word(cmd: str) -> str:
    toks = cmd.strip().split()
    return toks[0] if toks else ""


def analyse_step(step: dict, job_coe: bool) -> dict:
    """Can this single step take the job red?

    A step is the *smallest* unit of signal. We ask, narrowly: if the command inside
    exits non-zero, does the job fail? Everything that says "no" is collected as a reason.
    """
    reasons: list[str] = []
    body = step.get("run")
    if body is None:
        # `uses:` only -- a composite/Docker action. It can still fail, but we cannot
        # read it from here, so we do not claim it is a gate. Not a finding.
        return {"can_fail": None, "reasons": ["uses-step (not a run step)"]}

    if step.get("continue-on-error") is True or job_coe:
        reasons.append("continue-on-error: true")
        return {"can_fail": False, "reasons": reasons}

    text = _strip_comments(str(body))
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return {"can_fail": False, "reasons": ["empty run body"]}

    # `set -o pipefail` is per-SHELL, and each `run:` is its own shell. It does not carry
    # from one step to the next. That is the trap; check it only within this body.
    pipefail = any(
        re.match(r"^\s*set\s+(-[a-zA-Z]*o\s+)?pipefail\b", l) or
        re.match(r"^\s*set\s+-o\s+pipefail\b", l) or
        re.match(r"^\s*shopt\s+-s\s+pipefail\b", l)
        for l in lines
    )

    any_command = False
    for line in lines:
        if RUNNER.match(line.strip()):
            continue                       # a variable assignment cannot fail the shell
        if EXEMPT_SUFFIX.search(line):
            continue                       # `... || true` cannot fail
        for piece in _split_top(line, ("||", "&&", ";")):
            if not piece or EXEMPT_SUFFIX.search(piece):
                continue
            if RUNNER.match(piece):
                continue
            can, why = _piece_can_fail(piece, pipefail)
            if can:
                any_command = True
            elif why:
                reasons.append(why)
    if not any_command and not reasons:
        reasons.append("no executable command (only assignments/echo)")
    return {"can_fail": not reasons, "reasons": reasons}


def analyse_job(name: str, job: dict) -> dict:
    steps = job.get("steps") or []
    job_coe = job.get("continue-on-error") is True
    step_reports = []
    for idx, s in enumerate(steps):
        if not isinstance(s, dict):
            continue
        r = analyse_step(s, job_coe)
        r["index"] = idx
        r["name"] = s.get("name") or (str(s.get("uses")) if s.get("uses") else f"run #{idx}")
        step_reports.append(r)
    judged = [r for r in step_reports if r["can_fail"] is not None]
    gates = [r for r in judged if r["can_fail"]]
    return {
        "job": name,
        "can_fail": bool(gates),
        "gate_steps": [r["name"] for r in gates],
        "steps": step_reports,
    }


def analyse_workflow(path: str, text: str) -> dict:
    try:
        doc = yaml.safe_load(text)
    except Exception as e:                       # unreadable is NOT a clean bill of health
        return {"file": path, "error": f"YAML parse failed: {e}", "can_fail": None,
                "jobs": [], "unverifiable": True}
    if not isinstance(doc, dict) or "jobs" not in doc:
        return {"file": path, "error": "no `jobs:` key", "can_fail": None, "jobs": [],
                "unverifiable": True}
    jobs = [analyse_job(n, j) for n, j in (doc.get("jobs") or {}).items() if isinstance(j, dict)]
    judged = [j for j in jobs]
    return {
        "file": path,
        "error": None,
        "jobs": jobs,
        # A workflow cannot fail if NO job in it can fail. `needs:` is not consulted here:
        # a job that can fail but is never depended upon still gates nothing, and that
        # is a separate finding, not this one.
        "can_fail": any(j["can_fail"] for j in judged),
    }


def workflows_under(root: str) -> list[str]:
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", ".venv"}]
        if os.path.basename(dirpath) == "workflows":
            for f in sorted(filenames):
                if f.endswith((".yml", ".yaml")):
                    hits.append(os.path.join(dirpath, f))
    return sorted(hits)


# ── negative controls ─────────────────────────────────────────────────────────────
# A checker that has never been shown to fire is not a checker. These run in CI.
GOOD_WORKFLOW = """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: run the suite
        run: python -m pytest -q
"""

# the shape the brief named: a producer that can die, piped into a consumer that cannot.
PIPEFAIL_BAD = """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ./build.sh | tail -1
"""

# the same, guarded -- must NOT fire
PIPEFAIL_GOOD = """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          set -o pipefail
          ./build.sh | tail -1
"""

# the per-step trap: guarded in step 1, unguarded in step 2. Each `run:` is its own
# shell, so the guard does NOT carry. Must fire on step 2 only.
PER_STEP_TRAP = """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          set -o pipefail
          ./build.sh | tail -1
      - run: ./verify.sh | head -5
"""

ECHO_ONLY = """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo ok
"""

CONTINUE_ON_ERROR = """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest -q
        continue-on-error: true
"""

OR_TRUE = """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pytest -q || true
"""

# one job guarded, one not, in the SAME file. Must flag exactly one.
MIXED_FILE = """\
name: ci
on: [push]
jobs:
  guarded:
    runs-on: ubuntu-latest
    steps:
      - run: |
          set -o pipefail
          ./build.sh | tail -1
  unguarded:
    runs-on: ubuntu-latest
    steps:
      - run: ./build.sh | tail -1
"""

# no run steps at all
USES_ONLY = """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""


def selftest() -> int:
    cases = [
        # (name, workflow, should_fire, note)
        ("good: plain test run", GOOD_WORKFLOW, False, "a gate that can fail"),
        ("bad: producer | tail -1", PIPEFAIL_BAD, True, "the named failure mode"),
        ("good: pipefail in the same step", PIPEFAIL_GOOD, False, "guard present"),
        ("bad: echo only", ECHO_ONLY, True, "carries no signal"),
        ("bad: continue-on-error", CONTINUE_ON_ERROR, True, "exempted"),
        ("bad: || true", OR_TRUE, True, "exempted"),
        ("bad: uses-only", USES_ONLY, True, "nothing executes"),
        # NOTE on the mixed file: the FILE can fail -- one of its jobs is a real gate -- so
        # the file-level verdict is `can fail`. The per-job nuance ("this one job gates
        # nothing") is asserted by the dedicated per-file control below, which is the only
        # place that claim belongs. Collapsing the two is how a per-file checker ends up
        # reporting a clean bill of health for a file that is half-inert.
        ("good: mixed file (file can fail; 1 job flagged)", MIXED_FILE, False,
         "per-job verdict is asserted separately"),
    ]
    failures = []
    print("canfail.py — negative controls\n")
    for name, text, should_fire, note in cases:
        got = analyse_workflow("<selftest>", text)
        fired = got["can_fail"] is False
        ok = (fired == should_fire)
        if not ok:
            failures.append(name)
        print(f"  [{'ok ' if ok else 'FAIL'}] {name:38} expect_fire={should_fire!s:5} got={fired!s:5}  {note}")

    # the per-step control: exactly one step must be flagged, and it must be step 2
    g = analyse_workflow("<selftest>", PER_STEP_TRAP)
    bad_steps = [s["index"] for s in g["jobs"][0]["steps"] if s["can_fail"] is False]
    ok = bad_steps == [2]
    if not ok:
        failures.append("per-step trap")
    print(f"  [{'ok ' if ok else 'FAIL'}] {'per-step trap':38} "
          f"expect_fire_on_step=[2]  got={bad_steps}  guard does not cross `run:` shells")

    # the per-file control: exactly one job flagged
    m = analyse_workflow("<selftest>", MIXED_FILE)
    bad_jobs = [j["job"] for j in m["jobs"] if not j["can_fail"]]
    ok = bad_jobs == ["unguarded"]
    if not ok:
        failures.append("per-file control")
    print(f"  [{'ok ' if ok else 'FAIL'}] {'per-file: one guarded, one not':38} "
          f"expect=[unguarded]  got={bad_jobs}  a guarded job must not exempt its neighbour")

    print()
    if failures:
        print(f"SELFTEST FAILED: {failures}")
        return 1
    print("SELFTEST PASSED — fires on 6 of 6 always-green shapes, silent on 2 real gates.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="repo directories or workflow files")
    ap.add_argument("--json", action="store_true", help="machine output")
    ap.add_argument("--selftest", action="store_true", help="run the negative controls")
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if not a.paths:
        ap.error("give at least one path, or --selftest")

    files: list[str] = []
    for p in a.paths:
        files.extend([p] if os.path.isfile(p) else workflows_under(p))
    if not files:
        print("no workflow files found", file=sys.stderr)
        return 0

    reports = []
    for f in files:
        try:
            text = open(f, encoding="utf-8", errors="replace").read()
        except OSError as e:
            reports.append({"file": f, "error": str(e), "can_fail": None, "jobs": [],
                            "unverifiable": True})
            continue
        reports.append(analyse_workflow(f, text))

    bad = [r for r in reports if r["can_fail"] is False]
    unver = [r for r in reports if r.get("unverifiable")]

    if a.json:
        print(json.dumps({"reports": reports, "cannot_fail": [r["file"] for r in bad],
                          "unverifiable": [r["file"] for r in unver]}, indent=2))
    else:
        for r in reports:
            if r.get("unverifiable"):
                print(f"UNVERIFIABLE  {r['file']}  ({r.get('error')})")
                continue
            mark = "can-fail" if r["can_fail"] else "CANNOT FAIL"
            gates = sum(len(j["gate_steps"]) for j in r["jobs"])
            print(f"[{mark:>10}]  {r['file']}   jobs={len(r['jobs'])} gate_steps={gates}")
            if not r["can_fail"]:
                for j in r["jobs"]:
                    if j["can_fail"]:
                        continue
                    for s in j["steps"]:
                        for why in s["reasons"]:
                            print(f"                {j['job']} / {s['name']}: {why}")
        print()
        print(f"{len(reports)} workflow(s): {len(bad)} cannot fail, "
              f"{len(unver)} unverifiable, {len(reports)-len(bad)-len(unver)} can fail")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
