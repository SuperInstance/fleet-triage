#!/usr/bin/env python3
"""
draftcheck - the draft checker.

Paste prose (or point at a file). Finds:
  1. every `path:line` reference that does not resolve
  2. every numeric claim whose own stated operands disagree with it

Stdlib only. No network. No API key. Under a minute for any normal document.

    python3 draftcheck.py README.md
    python3 draftcheck.py --root . --json README.md
    cat notes.md | python3 draftcheck.py -
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# --------------------------------------------------------------------------
# 1. path:line references
# --------------------------------------------------------------------------
# A path-ish token, optional :line or :line-line. Deliberately conservative:
# we require a slash or a known source extension, so "note:3" in prose and
# "http://x/y" and "12:30" do not become findings.
PATHLINE = re.compile(
    r"""
    (?P<path>
        (?:[A-Za-z0-9_.\-]+/)+[A-Za-z0-9_.\-]+      # has a slash  -> definitely a path
      | [A-Za-z0-9_.\-]+\.(?:py|js|ts|tsx|jsx|mjs|cjs|sh|md|json|ya?ml|toml|rs|go|java|c|h|rb)
    )
    :(?P<line>\d+)
    (?:-(?P<line2>\d+))?
    """,
    re.VERBOSE,
)

# Extensions we will treat as "a real file we can count lines in"
COUNTABLE = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".cjs", ".sh", ".md",
    ".json", ".yaml", ".yml", ".toml", ".rs", ".go", ".java", ".c", ".h",
    ".rb", ".txt", ".cfg", ".ini", ".html", ".css",
}

# Words that look like filenames but never are. This is the false-positive
# control that matters most on ordinary prose.
NOT_A_PATH = {
    "e.g", "i.e", "etc", "vs", "no.", "cf", "ca", "approx", "fig", "eq",
    "note", "see", "ref", "vol", "ch", "sec", "al", "pp", "min", "max",
    "http", "https", "www", "README", "TODO", "FIXME",
}

# Inside a fenced code block, a path:line is a *citation*, not a claim about
# this repo. We still check it, but as INFO not ERROR (see note below).
FENCE = re.compile(r"^\s*(```|~~~)")


def strip_fences(lines):
    """Return a parallel list of (line_no, text, in_fence)."""
    out, in_f = [], False
    for i, ln in enumerate(lines, 1):
        if FENCE.match(ln):
            in_f = not in_f
            out.append((i, ln, in_f))
            continue
        out.append((i, ln, in_f))
    return out


# Path segments that mean "inside a repository" rather than naming one. If the
# FIRST segment of a path is one of these, the citation is within-repo and we
# can adjudicate it against every repo we hold. Anything else in first position
# is taken to name a repository.
GENERIC_DIRS = {
    "src", "lib", "libs", "tests", "test", "tools", "tool", "docs", "doc",
    "scripts", "bin", "game", "edge", "types", "adapters", "research", "examples",
    "example", "internal", "pkg", "cmd", "app", "srcs", "source", "python",
    "rust", "server", "client", "web", "api", "core", "ui", "build", "dist",
    "target", "vendor", "third_party", "node_modules", ".quilt", "onboarding",
    "coordination", "agent-messages", "round17", "repos", "work", "interface",
    "interfaces", "modules", "common", "shared", "assets", "resources", "config",
    "conf", "etc", "var", "usr", "home", "workspace", "experiments", "experiment",
    "notes", "prompts", "prompts", "deploy", "deployment", "ops", "infra",
    "terraform", "k8s", "charts", "proto", "protos", "schemas", "migrations",
    "benchmarks", "bench", "fixtures", "snapshots", "generated", "migrations",
}

_linecache: dict[str, int | None] = {}
_pathindex: set[str] | None = None


def build_index(roots) -> set:
    """One walk, cached. Stat()-ing every candidate for every reference is
    O(refs x roots) and took 7.9s on one document; indexing the same roots once
    takes well under a second and makes the whole tool's cost independent of how
    many roots the practitioner points it at."""
    global _pathindex
    if _pathindex is not None:
        return _pathindex
    idx = set()
    for r in roots:
        for dirpath, dirnames, filenames in os.walk(r):
            dirnames[:] = [d for d in dirnames
                           if d not in (".git", "node_modules", "__pycache__",
                                        ".venv", "target", "dist", "build")]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                idx.add(full)
                try:
                    idx.add(os.path.relpath(full, r))
                except ValueError:
                    pass
    _pathindex = idx
    return idx


def line_count(path: str, root: str) -> int | None:
    if path in _linecache:
        return _linecache[path]
    full = path if os.path.isabs(path) else os.path.join(root, path)
    n = None
    try:
        if os.path.isfile(full):
            with open(full, "rb") as fh:
                n = sum(1 for _ in fh)
    except OSError:
        n = None
    _linecache[path] = n
    return n


def resolve_candidates(path: str, root: str, docdir: str, extra_roots=()):
    """A relative path may be relative to the doc, to the primary root, or to
    any of the extra roots. All are legitimate; we try all before calling it
    broken.

    extra_roots matters more than it looks. Measured on this account's docs:
    `src/lib.rs` exists in 117 of 280 repos, so a directory component does NOT
    disambiguate anything. Resolving against a single root turns every report
    that cites another repo into a false positive."""
    cands = []
    if os.path.isabs(path):
        cands.append(path)
    else:
        cands.append(os.path.join(docdir, path))
        cands.append(os.path.join(root, path))
        for r in extra_roots:
            cands.append(os.path.join(r, path))
    return cands


def hits_for(path: str, root: str, docdir: str, extra_roots=(), idx=None):
    """Every existing candidate, via the cached index when we have one."""
    cands = resolve_candidates(path, root, docdir, extra_roots)
    if idx is None:
        return [c for c in cands if os.path.isfile(c)], len(cands)
    return [c for c in cands if c in idx or os.path.isfile(c)], len(cands)


def check_pathlines(text: str, root: str, docdir: str, extra_roots=(), idx=None):
    findings = []
    for lineno, line, in_fence in strip_fences(text.splitlines()):
        # Ignore anything inside a markdown link target or an http(s) URL
        if re.search(r"https?://", line):
            line_wo_urls = re.sub(r"https?://\S+", " ", line)
        else:
            line_wo_urls = line
        for m in PATHLINE.finditer(line_wo_urls):
            path, ln = m.group("path"), int(m.group("line"))
            base = os.path.basename(path)
            stem, ext = os.path.splitext(base)
            if ext == "" and base.lower().rstrip(".") in NOT_A_PATH:
                continue
            if path.startswith((".", "..")) and " " in path:
                continue
            hits, n_cands = hits_for(path, root, docdir, extra_roots, idx)
            cands = resolve_candidates(path, root, docdir, extra_roots)
            exists = bool(hits)
            if not exists:
                # SCOPE HONESTY. A bare filename with no directory component
                # ("README.md:91") inside a report *about another repo* is not
                # broken -- it is unresolvable from here, and the tool has no way
                # to tell those apart. Claiming it is missing would be a lie of
                # the exact kind this tool exists to catch. So: ambiguous, and
                # ranked below a real miss. A path WITH a directory is a claim
                # about this repo and is reported as an error.
                first = path.split("/")[0]
                if "/" not in path:
                    kind = "ambiguous-path"
                elif first not in GENERIC_DIRS:
                    # The first segment names something repo-shaped that is not
                    # on this disk. We cannot tell a broken citation from a
                    # citation into a repo we simply do not have, so we do not
                    # claim it is broken. Measured on this account: 179 of 186
                    # "unresolved" refs were exactly this.
                    kind = "unverifiable-repo"
                else:
                    kind = "unresolved-path"
                if kind == "ambiguous-path":
                    why = (f"{path!r} has no directory component, so it may "
                           f"belong to another repo; not resolvable from {root}")
                elif kind == "unverifiable-repo":
                    why = (f"{path!r}: {first!r} is a repo-shaped path segment "
                           f"not present in any of the {len(cands)} locations "
                           f"searched -- cannot be checked, not proven broken")
                else:
                    why = (f"no file at {path!r} in any of the {len(cands)} "
                           f"searched locations (first segment {first!r} is a "
                           f"generic source dir, so this is a within-repo "
                           f"citation we can actually adjudicate)")
                findings.append({
                    "kind": kind, "line": lineno,
                    "ref": m.group(0), "path": path, "want_line": ln,
                    "in_fence": in_fence, "why": why,
                })
                continue
            if ext.lower() in COUNTABLE:
                # Count EVERY match, not just the first. `src/lib.rs` exists in
                # 117 of the 280 repos on this account; range-checking line 2403
                # against whichever 61-line one sorted first produced a confident
                # and completely fabricated finding. A line number is only
                # meaningful against a file you have uniquely identified.
                if len(hits) > 1:
                    findings.append({
                        "kind": "range-ambiguous", "line": lineno,
                        "ref": m.group(0), "path": path, "want_line": ln,
                        "in_fence": in_fence,
                        "why": (f"{path!r} matches {len(hits)} different files; "
                                f":{ln} cannot be checked against an arbitrary one"),
                    })
                    continue
                n, hit = (line_count(hits[0], root), hits[0]) if hits else (None, None)
                if n is not None and ln > n:
                    # THREE TIERS, and the middle one is the honest one.
                    # A path WITH a directory is a claim about this repo: if it
                    # resolves and the line is past the end, it is broken.
                    # A BARE filename that happens to match a file here may
                    # have been meant to point at a different repo's file of the
                    # same name -- that is unknowable, so it is reported, but
                    # ranked below, and counted separately in the false-positive
                    # rate. An earlier version suppressed bare-filename range
                    # checks entirely, which silently destroyed the whole
                    # line-out-of-range class (8 findings -> 0). Suppressing a
                    # class to make a number look good is the defect, not the fix.
                    qualified = "/" in path
                    findings.append({
                        "kind": "line-out-of-range" if qualified else "range-bare",
                        "line": lineno,
                        "ref": m.group(0), "path": path, "want_line": ln,
                        "in_fence": in_fence,
                        "why": (f"{path} has {n} lines, cited :{ln}"
                                + ("" if qualified else
                                   f"  (matched {os.path.relpath(hit, root)}; a "
                                   f"bare filename may belong to another repo)")),
                    })
    return findings


# --------------------------------------------------------------------------
# 2. numeric claims whose stated operands disagree
# --------------------------------------------------------------------------
# Each rule is (regex, checker). The checker returns None if the claim is
# self-consistent or not decidable, else a string explaining the mismatch.
def _f(x: str) -> float:
    return float(x.replace(",", "").replace("_", ""))


# A number, no capture group. Rules wrap it themselves so that group
# numbering can never silently shift (this bit us once already).
N = r"[\d][\d,_]*(?:\.\d+)?"


def _f(s):
    return float(s.replace(",", "").replace("_", ""))


def _pct_close(a, b, tol=1.0):
    return abs(a - b) <= tol


def _check_expr(lhs, rhs):
    """Evaluate a flat term chain (a+b+c, a*b*c) and compare to the stated result.
    Mixed + and * is not decidable here and is declined rather than guessed."""
    toks = re.findall(N + r"|[+x*\u00d7]", lhs)
    if len(toks) < 3:
        return None
    ops = {toks[i] for i in range(1, len(toks), 2)}
    if len(ops) > 1:                       # mixed precedence -- decline
        return None
    op = toks[1]
    nums = [_f(t) for t in toks[0::2]]
    if op == "+":
        got = sum(nums)
        shown = " + ".join(f"{n:g}" for n in nums)
    else:
        got = 1.0
        for n in nums:
            got *= n
        shown = " x ".join(f"{n:g}" for n in nums)
    if abs(got - _f(rhs)) <= 0.51:
        return None
    return f"{shown} = {got:g}, not {rhs}"


RULES = []

# "126 of 140 is 90%" / "126/140 = 90%" / "3 of 4 are 90% of 5"
RULES.append((
    re.compile(r"\b(?P<a>" + N + r")\s*(?:of|/)\s*(?P<b>" + N +
               r")\s*(?:is|are|=|=>|->|\u2192)?\s*\(?\s*(?P<p>" + N + r")\s*%"),
    lambda m: None if _f(m["b"]) == 0 or _pct_close(_f(m["a"]) / _f(m["b"]) * 100, _f(m["p"]))
    else f"{m['a']} of {m['b']} is {_f(m['a'])/_f(m['b'])*100:.1f}%, not {m['p']}%",
))

# "A are B% of C"
RULES.append((
    re.compile(r"\b(?P<a>" + N + r")\s+(?:are|is)\s+(?P<p>" + N +
               r")\s*%\s+(?:of|out of)\s+(?P<c>" + N + r")"),
    lambda m: None if _f(m["c"]) == 0 or _pct_close(_f(m["a"]) / _f(m["c"]) * 100, _f(m["p"]))
    else f"{m['a']} of {m['c']} is {_f(m['a'])/_f(m['c'])*100:.1f}%, not {m['p']}%",
))

# "3 + 4 = 12" / "3 x 4 = 12" / "1+4+6+1+1+1 = 14"
# The WHOLE term chain is consumed. Matching only the first two operands and
# comparing them to the final result is how "1+4+6+1+1+1 = 14" got reported as
# a defect. A sum is not a binary operator applied once.
RULES.append((
    re.compile(r"\b(?P<lhs>" + N + r"(?:\s*[+x*\u00d7]\s*" + N + r")+)"
               r"\s*=\s*(?P<rhs>" + N + r")"),
    lambda m: _check_expr(m["lhs"], m["rhs"]),
))

# "half of 100 is 60" / "a third of 90 is 40"
FRAC = {"half": 0.5, "a third": 1 / 3, "two thirds": 2 / 3, "a quarter": 0.25,
        "three quarters": 0.75, "twice": 2.0, "double": 2.0, "triple": 3.0,
        "two times": 2.0, "three times": 3.0}
RULES.append((
    re.compile(r"\b(?P<w>" + "|".join(re.escape(k) for k in FRAC) + r")\s+of\s+(?P<n>" + N +
               r")\s+is\s+(?P<r>" + N + r")", re.IGNORECASE),
    lambda m: (
        None if abs(FRAC[m["w"].lower()] * _f(m["n"]) - _f(m["r"])) <= max(0.51, 0.01 * _f(m["r"]))
        else f"{m['w']} of {m['n']} is {FRAC[m['w'].lower()]*_f(m['n']):g}, not {m['r']}"
    ),
))


def check_numbers(text: str):
    findings = []
    for lineno, line, in_fence in strip_fences(text.splitlines()):
        if line.lstrip().startswith(">"):
            continue
        for rx, chk in RULES:
            for m in rx.finditer(line):
                try:
                    why = chk(m)
                except (ValueError, ZeroDivisionError, KeyError):
                    why = None
                if why:
                    findings.append({
                        "kind": "numeric-mismatch", "line": lineno,
                        "claim": m.group(0).strip(), "why": why,
                        "in_fence": in_fence,
                    })
    return findings


# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="check a draft for broken "
                                             "path:line refs and self-contradicting numbers")
    ap.add_argument("path", help="markdown/text file, or - for stdin")
    ap.add_argument("--root", default=None,
                    help="repo root to resolve relative paths against "
                         "(default: the file's directory)")
    ap.add_argument("--also-root", action="append", default=[], metavar="DIR",
                    help="additional root to search; repeatable. Use this when "
                         "the document cites files that live in sibling repos. "
                         "Can also be a glob, e.g. --also-root '../*/'")
    ap.add_argument("--index", action="store_true",
                    help="walk the roots once and cache every path, instead of "
                         "stat-ing per reference. Faster for very large root "
                         "sets on fast disks; measured SLOWER on a NAS mount.")
    ap.add_argument("--root-glob", action="append", default=[], metavar="PAT",
                    help="shell glob expanded to resolution roots, e.g. "
                         "'/workspace/projects/*'. Repeatable. This is the "
                         "setting that actually moves the false-positive rate: "
                         "measured, the FP class was almost entirely citations "
                         "into repos outside the primary root.")
    ap.add_argument("--sibling-repos", default=None, metavar="DIR",
                    help="shorthand: treat every immediate subdirectory of DIR "
                         "as a resolution root (the common report-about-many-"
                         "repos case)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--include-fences", action="store_true",
                    help="also report findings inside code fences")
    args = ap.parse_args()

    if args.path == "-":
        text = sys.stdin.read()
        docdir = os.getcwd()
    else:
        if not os.path.isfile(args.path):
            print(f"draftcheck: no such file: {args.path}", file=sys.stderr)
            return 2
        with open(args.path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        docdir = os.path.dirname(os.path.abspath(args.path)) or os.getcwd()

    root = os.path.abspath(args.root) if args.root else docdir

    import glob as _glob
    extra = [os.path.abspath(p) for p in args.also_root]
    for pat in args.root_glob:
        extra += [os.path.abspath(p) for p in sorted(_glob.glob(pat))
                  if os.path.isdir(p)]
    if args.sibling_repos:
        base = os.path.abspath(args.sibling_repos)
        extra += [os.path.join(base, d) for d in sorted(os.listdir(base))
                  if os.path.isdir(os.path.join(base, d))]
    extra = [e for e in extra if os.path.isdir(e)]

    # Walking the NAS to build an index measured SLOWER than stat-ing it
    # (48s vs 7.9s on one document): this filesystem punishes tree walks. So
    # the index is opt-in via --index, and the default is stat, which is ~0.3s
    # per document at 282 roots.
    idx = build_index([root, docdir] + extra) if (extra and args.index) else None
    findings = (check_pathlines(text, root, docdir, extra, idx) + check_numbers(text))
    findings.sort(key=lambda f: (f["line"], f["kind"]))
    if not args.include_fences:
        findings = [f for f in findings if not f.get("in_fence")]

    if args.json:
        print(json.dumps({"file": args.path, "root": root,
                          "extra_roots": len(extra),
                          "findings": findings, "count": len(findings)}, indent=2))
    else:
        if not findings:
            print(f"draftcheck: clean — no unresolved path:line and no "
                  f"self-contradicting number in {args.path}")
        for f in findings:
            tag = "NUM  " if f["kind"] == "numeric-mismatch" else "PATH "
            print(f"{tag} line {f['line']:>4}: {f['why']}")
            if f["kind"].startswith(("unresolved", "line-out")):
                print(f"            cited as `{f['ref']}`")
        soft = sum(1 for f in findings
                   if f["kind"] in ("ambiguous-path", "range-bare",
                                    "range-ambiguous", "unverifiable-repo"))
        err = len(findings) - soft
        print(f"\n{err} finding(s) + {soft} unconfirmed in "
              f"{os.path.basename(args.path)} (root: {root})")
        if soft:
            print("  (unconfirmed = bare filename with no directory; it matched "
                  "a file here but may belong to another repo.)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
