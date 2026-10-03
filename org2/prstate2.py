#!/usr/bin/env python3
"""
ORG2 task 4 -- re-run the conflict detector on the queue as it stands now, and
report the state of the four merges the orchestrator performed.

Rules learned in iteration 1, both re-applied here:
  * ref presence is DISCOVERY, ancestry is AUTHORITY (pong-quilt#88 advertises a
    merge ref but is already merged);
  * a shallow clone SILENTLY INVERTS ancestry (--depth=N breaks merge-base), so
    every verdict here runs against a full commit graph (--filter=tree:0 gives
    full commits with no blobs -- cheap AND deep).
"""
import json, os, subprocess, sys, itertools
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(BASE, "prwork")
os.makedirs(W, exist_ok=True)
OWNER = "SuperInstance"

# The queue as of the re-sweep, plus the four the orchestrator merged.
PRIO = {
    "Patchwork-experts": [1],
    "chiaroscuro": [1],
    "quilt-gpu-lab": [6],
    "quilt-pincher": [12, 13, 14],
    "quilt-research-canons": [4],
    "quilt-tools": [32, 33],
    "pong-quilt": [88],
    # already merged by the orchestrator -- we assert the merge landed
    "fleet-murmur": [9],
    "voxelglyph": [1],
}


def sh(cmd, cwd, t=300):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=t)


def prep(repo):
    d = os.path.join(W, repo)
    if not os.path.isdir(os.path.join(d, "objects")):
        os.makedirs(d, exist_ok=True)
        r = sh(["git", "init", "-q", d], None)
        sh(["git", "-C", d, "remote", "add", "origin",
            f"https://github.com/{OWNER}/{repo}.git"], None)
    # full commit graph, no blobs
    sh(["git", "-C", d, "fetch", "-q", "--filter=tree:0", "origin",
        "+refs/heads/*:refs/remotes/origin/*",
        "+refs/pull/*/head:refs/remotes/origin/pr/*"], None, 600)
    return d


def verdict(d, pr):
    head = f"refs/remotes/origin/pr/{pr}"
    if sh(["git", "-C", d, "rev-parse", "--verify", "--quiet", head], None).returncode != 0:
        return {"pr": pr, "state": "NO_HEAD_REF"}
    # is it on main/master?
    for br in ("main", "master"):
        r = sh(["git", "-C", d, "merge-base", "--is-ancestor", head,
                f"refs/remotes/origin/{br}"], None)
        if r.returncode == 0:
            return {"pr": pr, "state": "MERGED", "into": br}
    r = sh(["git", "-C", d, "rev-list", "--count", head], None)
    return {"pr": pr, "state": "OPEN", "commits_on_pr": r.stdout.strip()}


def pairwise(d, repo, prs):
    """git merge-tree --write-tree A B  -> conflicts, without touching a worktree.
    Exit 1 + a tree oid on stdout means CONFLICT; exit 0 means clean."""
    out = []
    for a, b in itertools.combinations(prs, 2):
        ra, rb = f"refs/remotes/origin/pr/{a}", f"refs/remotes/origin/pr/{b}"
        if (sh(["git", "-C", d, "rev-parse", "--verify", "--quiet", ra], None).returncode
                or sh(["git", "-C", d, "rev-parse", "--verify", "--quiet", rb], None).returncode):
            out.append({"pair": [a, b], "result": "SKIP (missing ref)"})
            continue
        r = sh(["git", "-C", d, "merge-tree", "--write-tree", "--name-only", ra, rb], None, 600)
        conflict_files = []
        if r.returncode != 0:
            for line in r.stdout.splitlines():
                if line and not line.startswith("#"):
                    conflict_files.append(line.strip())
        out.append({"pair": [a, b],
                    "result": "CONFLICT" if r.returncode != 0 else "clean",
                    "files": conflict_files[:12]})
    return out


def main():
    sweep = json.load(open(os.path.join(BASE, "prsweep2.json")))
    report = {}
    for repo, prs in sorted(PRIO.items()):
        d = prep(repo)
        vs = [verdict(d, p) for p in prs]
        # only compare PRs that are genuinely OPEN (a merged PR is not a conflict)
        openprs = [v["pr"] for v in vs if v["state"] == "OPEN"]
        pw = pairwise(d, repo, openprs) if len(openprs) > 1 else []
        head = sh(["git", "-C", d, "rev-parse", "--verify", "--quiet",
                   "refs/remotes/origin/main"], None)
        report[repo] = {"verdicts": vs, "pairwise": pw,
                        "main": head.stdout.strip()[:12] if head.returncode == 0 else "master"}
        print(f"\n== {repo}  (main={report[repo]['main']})", flush=True)
        for v in vs:
            print(f"   #{v['pr']:<4d} {v['state']:9s} {v.get('into') or v.get('commits_on_pr','')}")
        for p in pw:
            print(f"   pair {p['pair']} -> {p['result']}  {p.get('files','')}")
    json.dump(report, open(os.path.join(BASE, "prstate2.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
