#!/usr/bin/env python3
"""Run a consumer's run_tests.py with the /workspace/repos shadowing neutralised.

Every quilt-canon-* suite begins with
    sys.path.insert(0, "/workspace/repos/<its own name>")
so an unmodified run imports a DIFFERENT checkout that happens to exist on this
sandbox, not the repo under test. This wrapper rewrites that one insert to a
nonexistent sentinel so the local tree is what actually gets imported. It changes
nothing on disk and deletes nothing.
"""
import sys, runpy, os

_orig_insert = sys.path.insert
SENTINEL = "/workspace/repos/__SHADOWED_BY_RUNNER__"


def guarded_insert(i, path):
    if isinstance(path, str) and path.startswith("/workspace/repos/"):
        path = SENTINEL
    return _orig_insert(i, path)


sys.path.insert = guarded_insert
script = sys.argv[1]
sys.argv = [script] + sys.argv[2:]
os.chdir(os.path.dirname(os.path.abspath(script)) or ".")
runpy.run_path(os.path.basename(script), run_name="__main__")
