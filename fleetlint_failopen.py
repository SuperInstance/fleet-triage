#!/usr/bin/env python3
"""
fleetlint rule: FAILOPEN-HARNESS
===============================
A test harness must be able to report FAILURE. Three ways it cannot:

  A. FAIL-CLOSED VIOLATION  -- a TOP-LEVEL exception handler that cannot
     terminate the process non-zero. It *observes* the failure and discards
     it. Only column-0 handlers count: a nested catch inside a test body is
     the correct idiom (capture a subprocess failure, assert on it after).

  B. NO-ASSERT VIOLATION    -- the harness contains no assertion primitive at
     all. It can print OK and can never print NOT-OK. Strictly larger than A:
     A is a special case of B wearing a try/catch.

  C. UNREACHABLE ENTRYPOINT -- test files exist but package.json declares no
     `test` script, so the documented way to run them is a hard error and the
     only way anyone runs them is by hand.

A, B = FAIL.  C = WARN.

CALIBRATION HISTORY (this rule over-fired twice before it was clean; both
regressions are recorded in the comments at the point they were fixed):
  v1  A fired on every nested catch  -> 16 false positives in pong-quilt,
      a repo that is demonstrably correct. Fixed: column-0 only.
  v2  B missed python's bare `assert x == y` (no paren) and treated
      __init__.py / conftest.py / fixtures/ as harnesses -> 49 repos flagged.
      Fixed: real harness predicate + bare-assert pattern.
"""

import re
import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------- A

EXIT_PRIMITIVES = re.compile(
    r"""process\s*\.\s*exit(?!Code)\s*\(
        | process\s*\.\s*exitCode
        | os\s*\.\s*_exit
        | sys\s*\.\s*exit
        | System\s*\.\s*exit
        | std\s*::\s*process\s*::\s*exit
        | \braise\s+[A-Za-z]
        | \bpanic!\s*\(
        | \bassert[A-Za-z_]*\s*\(
        | \bexit\s+[1-9]""",
    re.VERBOSE | re.IGNORECASE,
)

# v1 FIX: column-0 only. A nested catch is a control-flow idiom, not a sink.
CATCH_RE = re.compile(
    r"^\}?[ \t]*catch\s*(?:\([^)]*\))?\s*\{"
    r"(?P<body>[^{}]*(?:\{[^{}]*\}[^{}]*)*)\}",
    re.MULTILINE,
)
PY_EXCEPT_RE = re.compile(
    r"^except\b.*?:[ \t]*(?P<body>(?:[ \t]+.*\n|\n)+?)(?=\S)", re.MULTILINE
)


def check_fail_closed(src, lang):
    out = []
    if lang == "js":
        pats = CATCH_RE
    elif lang == "py":
        pats = PY_EXCEPT_RE
    else:
        return out
    for m in pats.finditer(src):
        body = m.group("body")
        if EXIT_PRIMITIVES.search(body):
            continue  # handler can fail loudly. OK.
        out.append(
            {
                "rule": "A",
                "line": src[: m.start()].count("\n") + 1,
                "detail": "top-level exception handler has no "
                "exit/throw/assert path",
            }
        )
    return out


# ---------------------------------------------------------------- B

ASSERT_PRIMITIVES = re.compile(
    r"""require\s*\(\s*['"](?:node:)?assert
        | \bfrom\s+['"](?:node:)?assert
        | \bimport\s+[^\n]*\bassert\b
        | \bassert\s*\.\s*\w+              # js:   assert.equal
        | \bassert[A-Za-z_]*\s*\(\s*      # py:   assertEqual(
        | \bassert\s+(?![.(])             # py:   bare `assert x == y`   <- v3 FIX
        | \bassert\s+$
        | \bexpect\s*\(
        | \bshould\s*\.\s*\w+
        | \bmust\s*\.\s*\w+
        | \bassert_(?:eq|ne|true|false|throws)!\s*
        | \bcheckEquals\s*\(""",
    re.VERBOSE,
)

# v3 FIX: hand-rolled assertion counter -- `let fail=0` ... `fail++` ... exit.
DIY_COUNTER = re.compile(
    r"\b(?:let|const|var)\s+[A-Za-z_$][\w$]*\s*=\s*0\b"   # any counter
    r".{0,400}?\b(?:fail|failures|failed|errors)\s*\+\+",
    re.DOTALL | re.IGNORECASE,
)

HANDROLLED = re.compile(
    r"if\s*\([^\n)]*\)[^\n]{0,40}?\b(?:throw|raise|panic)\b"
    r"|if\s+[^\n:]+:[ \t]*(?:raise|assert)\b",
    re.IGNORECASE,
)


# v4 FIX: "no explicit assert" is NOT the same as "cannot fail". A pytest file
# with zero asserts whose assertion is "this did not raise" is a legitimate
# (if weak) smoke test. The discriminator is whether a RUNNER collects the
# file: a collected test inherits an implicit fail-on-exception assertion from
# the runner. A standalone root-level script that nobody's runner collects has
# no such inheritance. So B only fires on the standalone-script shape.
COLLECTED_DIR = re.compile(r"(^|/)(tests?|__tests__|spec)/")


def check_no_assert(src, lang, rel=""):
    """B. A harness that cannot declare failure, and that no runner collects."""
    if (ASSERT_PRIMITIVES.search(src) or HANDROLLED.search(src)
            or DIY_COUNTER.search(src)):
        return []
    if COLLECTED_DIR.search(rel):
        return []          # runner supplies the implicit assertion. Not a FAIL.
    if lang == "py" and PY_TEST_RE.search(rel):
        return []          # pytest/ unittest naming => runner collects it
    return [
        {
            "rule": "B",
            "line": 1,
            "detail": "harness contains no assertion primitive; it can print "
            "OK and can never print NOT-OK",
        }
    ]


# ------------------------------------------------- harness identification
# v2 FIX: __init__.py, conftest.py and anything under fixtures/ are NOT
# harnesses. Treating them as harnesses was most of the 49-repo over-fire.

LANG_BY_EXT = {
    ".js": "js", ".mjs": "js", ".cjs": "js", ".ts": "js", ".mts": "js",
    ".py": "py",
}
NOT_A_HARNESS = re.compile(
    r"(^|/)(__init__|conftest|setup|utils?)\.py$"
    r"|(^|/)fixtures?/"
    r"|(^|/)(helpers?|mocks?)/"
    r"|(^|/)[._]"
)
PY_TEST_RE = re.compile(r"(^|/)test_[^/]+\.py$|(^|/)[^/]+_test\.py$")
JS_TEST_RE = re.compile(
    r"(^|/)test\.[a-z]+$"                      # test.js
    r"|(^|/)[^/]+\.test\.[a-z]+$"              # foo.test.js
    r"|(^|/)tests?/[^/]+$"                     # anything directly in tests/
)
SKIP_DIR_PARTS = (
    "node_modules", "__pycache__", "fixtures", "fixture", "examples",
    "docs", "vendor", "third_party", "bindings", "worker", "packages",
    ".agents", "skills",
    # name-collision dirs: a *_test.py here is a config, not a test
    "configs", "experiments", "scripts", "tools", "migrations",
)


def is_harness(rel, suffix):
    if suffix not in LANG_BY_EXT:
        return False
    parts = rel.split("/")
    if any(p in SKIP_DIR_PARTS for p in parts[:-1]):
        return False
    if NOT_A_HARNESS.search(rel):
        return False
    if suffix == ".py":
        return bool(PY_TEST_RE.search(rel))
    return bool(JS_TEST_RE.search(rel))


# ---------------------------------------------------------------- C

def check_entrypoint(harnesses, pkg):
    if not pkg or not harnesses:
        return []
    if "test" in (pkg.get("scripts") or {}):
        return []
    return [
        {
            "rule": "C",
            "line": 0,
            "detail": "%d harness file(s) present but package.json declares "
            "no `test` script" % len(harnesses),
        }
    ]


# ---------------------------------------------------------------- driver

def git_files(root):
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            capture_output=True, text=True, timeout=30,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.split()
    except Exception:
        pass
    # not a git checkout (or git unavailable): fall back to a walk
    out = []
    for p in sorted(Path(root).rglob("*")):
        if p.is_file():
            out.append(p.relative_to(root).as_posix())
    return out


def lint_repo(root):
    root = Path(root)
    findings = []
    harnesses = []
    for rel in git_files(root):
        suffix = Path(rel).suffix
        if is_harness(rel, suffix):
            harnesses.append(rel)
    for rel in harnesses:
        p = root / rel
        if not p.exists():
            continue
        try:
            src = p.read_text(errors="replace")
        except Exception:
            continue
        lang = LANG_BY_EXT[suffix_of(rel)]
        for f in (check_fail_closed(src, lang)
                  + check_no_assert(src, lang, rel)):
            f["file"] = rel
            findings.append(f)
    pkg = None
    pj = root / "package.json"
    if pj.exists():
        try:
            pkg = json.loads(pj.read_text())
        except Exception:
            pkg = None
    for f in check_entrypoint(harnesses, pkg):
        f["file"] = "package.json"
        findings.append(f)
    return findings


def suffix_of(rel):
    return Path(rel).suffix


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    total = 0
    for a in args:
        fs = lint_repo(a)
        if fs:
            print("\n%s" % a.rstrip("/"))
            for f in fs:
                total += 1
                print("  FAILOPEN-HARNESS/%s  %s:%s  %s"
                      % (f["rule"], f["file"], f["line"], f["detail"]))
    print("\n%d finding(s)" % total)
