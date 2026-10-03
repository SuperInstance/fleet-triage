#!/usr/bin/env python3
"""EMPIRICAL fail-open census.

For every harness in the fleet, inject a guaranteed top-level throw into a COPY
and ask the only question that matters: what does the process return?
  exit 0  -> FAIL-OPEN   (a failing test is indistinguishable from a passing one)
  non-zero -> FAIL-CLOSED
This does not consult any regex. It runs the harness and reads $?.
"""
import os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path("/workspace/projects/fleet-triage/repos")
sys.path.insert(0, "/workspace/projects/fleet-triage")
from fleetlint_failopen import is_harness, LANG_BY_EXT, git_files

POISON = {
    ".js":   "throw new Error('CENSUS: injected failure');\n",
    ".mjs":  "throw new Error('CENSUS: injected failure');\n",
    ".cjs":  "throw new Error('CENSUS: injected failure');\n",
    ".ts":   "throw new Error('CENSUS: injected failure');\n",
    ".py":   "raise SystemExit('CENSUS: injected failure')\n",
}

def run(cmd, cwd, timeout=45):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None

rows = []
for repo in sorted(ROOT.iterdir()):
    if not repo.is_dir() or repo.name.startswith("."):
        continue
    files = git_files(repo)
    harnesses = [f for f in files if is_harness(f, Path(f).suffix)]
    if not harnesses:
        continue
    for rel in harnesses:
        ext = Path(rel).suffix
        if ext not in POISON:
            continue
        src = repo / rel
        if not src.exists():
            continue
        # skip anything that needs a build/venv we cannot reconstruct cheaply
        if "node_modules" in rel or rel.startswith("vendor/"):
            continue
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / "w"
            try:
                shutil.copytree(repo, work, symlinks=True,
                                ignore=shutil.ignore_patterns("node_modules", ".git"))
            except Exception:
                continue
            target = work / rel
            if not target.exists():
                continue
            try:
                target.write_text(POISON[ext] + target.read_text(errors="replace"))
            except Exception:
                continue
            rc = (["node", rel] if ext != ".py" else ["python3", rel])
            code = run(rc, work)
            rows.append((repo.name, rel, code))

failopen = [r for r in rows if r[2] == 0]
print("harnesses probed: %d" % len(rows))
print("FAIL-OPEN (poisoned harness still exits 0): %d" % len(failopen))
for name, rel, _ in failopen:
    print("  %-40s %s" % (name, rel))
err = [r for r in rows if r[2] is None]
print("indeterminate (timeout/err): %d  %s" % (len(err), sorted({r[0] for r in err})))
