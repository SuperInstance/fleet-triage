#!/usr/bin/env python3
"""Census 2: the try/catch population.

Census 1 (prepend a throw outside any handler) measured 330 harnesses and found
0 fail-open -> every harness WITHOUT a top-level try/catch already fails closed.

Census 2 targets only the harnesses that DO have one, and injects the failure
INSIDE the try block, which is what a real product failure looks like.
"""
import re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path("/workspace/projects/fleet-triage/repos")
sys.path.insert(0, "/workspace/projects/fleet-triage")
from fleetlint_failopen import (is_harness, git_files, CATCH_RE, PY_EXCEPT_RE,
                                EXIT_PRIMITIVES, LANG_BY_EXT)

POISON_JS = "  throw new Error('CENSUS: injected failure inside try');\n"
POISON_PY = "    raise SystemExit('CENSUS: injected failure inside try')\n"

def poison(src, ext):
    """Insert a throw/raise as the first statement of the TRY body, not the catch.

    v1 was wrong and I have to record why, because it produced a false FAIL-OPEN
    reading on the two repos that actually pass. CATCH_RE matches the *catch*; the
    first `{` after its match start is the catch's own brace, so the throw landed in
    the handler. A handler that never runs is a no-op: the try succeeded, the catch
    body was dead code, and the harness correctly returned 0. The instrument was
    measuring nothing and reporting it as a defect.
    """
    if ext == ".py":
        m = PY_EXCEPT_RE.search(src)
        if not m:
            return None
        at = m.start("body")
        return src[:at] + POISON_PY + src[at:]
    m = CATCH_RE.search(src)
    if not m:
        return None
    # walk BACK to the `try` that owns this catch, then poison the try's body
    t = src.rfind("try", 0, m.start())
    if t == -1:
        return None
    brace = src.index("{", t)
    return src[:brace + 1] + "\n" + POISON_JS + src[brace + 1:]

def run(cmd, cwd, timeout=45):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              timeout=timeout).returncode
    except Exception:
        return None

failopen, clean, skipped = [], [], []
for repo in sorted(ROOT.iterdir()):
    if not repo.is_dir() or repo.name.startswith("."):
        continue
    for rel in [f for f in git_files(repo) if is_harness(f, Path(f).suffix)]:
        ext = Path(rel).suffix
        if ext not in LANG_BY_EXT or "node_modules" in rel:
            continue
        src = repo / rel
        if not src.exists():
            continue
        try:
            text = src.read_text(errors="replace")
        except Exception:
            continue
        pat = PY_EXCEPT_RE if ext == ".py" else CATCH_RE
        if not pat.search(text):
            continue                      # no handler -> census 1 already cleared it
        mutated = poison(text, ext)
        if mutated is None:
            skipped.append((repo.name, rel)); continue
        with tempfile.TemporaryDirectory() as td:
            work = Path(td) / "w"
            try:
                shutil.copytree(repo, work, symlinks=True,
                                ignore=shutil.ignore_patterns("node_modules", ".git"))
            except Exception:
                skipped.append((repo.name, rel)); continue
            (work / rel).write_text(mutated)
            code = run(["node", rel] if ext != ".py" else ["python3", rel], work)
            (failopen if code == 0 else clean).append((repo.name, rel, code))

print("try/catch harnesses probed : %d" % (len(failopen) + len(clean)))
print("FAIL-OPEN  (exit 0 on failure): %d" % len(failopen))
for n, r, _ in failopen:
    print("   %-42s %s" % (n, r))
print("fail-closed (non-zero)     : %d" % len(clean))
for n, r, c in clean:
    print("   %-42s %s  exit=%s" % (n, r, c))
if skipped:
    print("skipped: %s" % skipped[:10])
