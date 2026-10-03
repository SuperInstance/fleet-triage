#!/usr/bin/env python3
"""
apply_dep_fix.py -- write the packaging fix into the 11 local repos, on the existing
fix/fail-closed-harness branch. package.json ONLY. No product code. No test touched.

  file:../X   ->   github:SuperInstance/X

Emits a per-repo patch in substrate-fix-artifacts/dep-fix-per-repo/.
"""
import json, os, re, subprocess

ROOT = "/workspace/projects/fleet-triage"
REPOS = ROOT + "/repos"
OUT = ROOT + "/substrate-fix-artifacts/dep-fix-per-repo"
os.makedirs(OUT, exist_ok=True)

REWRITE = re.compile(r'"(file:\.\./([^"]+))"')


def sh(c, cwd=None):
    p = subprocess.run(c, shell=True, cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def patch_one(repo):
    d = os.path.join(REPOS, repo)
    sh("git stash list >/dev/null", cwd=d)
    sh("git checkout -q fix/fail-closed-harness", cwd=d)
    if sh("git diff --quiet", cwd=d)[0] != 0:
        return repo, "DIRTY-WORKTREE", []
    p = os.path.join(d, "package.json")
    src = open(p).read()
    changes = []

    def sub(m):
        changes.append((m.group(1), "github:SuperInstance/" + m.group(2)))
        return '"github:SuperInstance/%s"' % m.group(2)

    new = REWRITE.sub(sub, src)
    if not changes:
        return repo, "no-change", []
    open(p, "w").write(new)
    # keep it valid json -- assert rather than assume
    json.load(open(p))
    msg = (
        "fix(deps): resolve sibling packages from a fresh clone\n\n"
        "file:../X  ->  github:SuperInstance/X\n\n"
        "file: targets are unresolvable unless the sibling happens to be\n"
        "checked out as a directory named X next to this one. A stranger\n"
        "cloning this repo alone could never install or run it. The\n"
        "siblings are all published, so npm can fetch them itself.\n\n"
        "package.json only. No product code, no test touched."
    )
    sh("git add -A", cwd=d)
    p = subprocess.run("git commit -q -F -", shell=True, cwd=d, input=msg,
                       capture_output=True, text=True)
    if p.returncode != 0:
        return repo, "COMMIT-FAIL: " + p.stderr.strip()[:120], changes
    # emit per-repo patch
    sh("git format-patch -1 --stdout -o " + OUT + " >/dev/null", cwd=d)
    sh("git diff -1 --binary > %s/%s.patch" % (OUT, repo), cwd=d)
    return repo, "OK", changes


def main():
    repos = sorted(d for d in os.listdir(REPOS) if d.startswith("substrate-"))
    for r in repos:
        repo, status, changes = patch_one(r)
        print("%-26s %-14s %s" % (repo, status,
                                  "; ".join("%s -> %s" % c for c in changes) or "-"))


if __name__ == "__main__":
    main()
