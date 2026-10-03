#!/usr/bin/env python3
"""
ORG2 task 1: how much work bypasses PRs entirely?

Method: for each repo, `git clone --bare --filter=tree:0` (commit objects only, no
trees/blobs -> hundreds of KB even for multi-GB repos), then walk
`git log --first-parent --merges <default-branch>` and classify each merge commit
by SUBJECT SHAPE.

Why --first-parent: it is main's own line of descent. A PR merge that got
subsequently squash-merged leaves two merge commits; --first-parent counts what
actually landed on main, which is what the question is about.

Why subject shape: we have no API budget, so we cannot ask GitHub "is this a PR
merge?". GitHub's own PR merge commit is minted by GitHub and has a fixed
subject:  "Merge pull request #N from user/branch". Everything else -- "Merge
branch 'x'", "Merge remote-tracking branch 'origin/x'" -- was made by a human or
an agent running git locally and pushing to main. The shape is the evidence.

Output: one JSON per repo, plus a merged summary.
"""
import json, os, re, subprocess, sys, tempfile, shutil
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "bare")
OUT = os.path.join(BASE, "merges")
os.makedirs(CACHE, exist_ok=True)
os.makedirs(OUT, exist_ok=True)

# ---- classifiers -----------------------------------------------------------
# GitHub mints these itself. Anchored on the literal "pull request #N".
RE_PR = re.compile(r"^Merge pull request #(\d+)\b", re.I)
RE_BRANCH = re.compile(r"^Merge branch '(?P<b>.+)'", re.I)
RE_RT = re.compile(r"^Merge remote-tracking branch '(?P<b>.+)'", re.I)
RE_TAG = re.compile(r"^Merge (?:commit|tag) '(?P<b>[^']+)'", re.I)
# A merge of a *pull-request ref* is a hand merge of a PR branch, not a PR merge.
RE_PRREF = re.compile(r"refs/pull/", re.I)
RE_FF = re.compile(r"fast[- ]forward", re.I)


def classify(subject: str) -> str:
    s = subject.strip()
    if RE_PR.match(s):
        return "pr_merge"
    m = RE_BRANCH.match(s)
    if m:
        b = m.group("b")
        if RE_PRREF.search(b):
            return "hand_merge_prref"   # hand-merged a PR branch: not a PR merge
        return "direct_merge_branch"
    m = RE_RT.match(s)
    if m:
        b = m.group("b")
        if RE_PRREF.search(b):
            return "hand_merge_prref"
        if b.split("/")[-1] in ("master", "main", "develop"):
            return "branch_into_self"   # merging main into main: not real work
        return "direct_merge_rtremote"
    if RE_TAG.match(s):
        return "tag_merge"
    if RE_FF.search(s):
        return "ff_merge"
    return "other_merge"


def run(cmd, cwd=None, timeout=180):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                          timeout=timeout)


def probe(repo: str, owner="SuperInstance"):
    dest = os.path.join(CACHE, repo)
    url = f"https://github.com/{owner}/{repo}.git"
    if not os.path.isdir(dest):
        r = run(["git", "clone", "--bare", "--filter=tree:0", "--quiet", url, dest],
                timeout=300)
        if r.returncode != 0:
            return {"repo": repo, "error": (r.stderr or r.stdout).strip()[:300]}
    branch = "main"
    b = run(["git", "rev-parse", "--verify", "--quiet", "main"], cwd=dest, timeout=60)
    if b.returncode != 0:
        b = run(["git", "rev-parse", "--verify", "--quiet", "master"], cwd=dest, timeout=60)
        if b.returncode != 0:
            return {"repo": repo, "error": "no main/master"}
        branch = "master"
    lg = run(["git", "log", "--first-parent", "--merges", "--format=%H\t%s", branch],
             cwd=dest, timeout=180)
    if lg.returncode != 0:
        return {"repo": repo, "error": (lg.stderr or "")[:300]}
    rows, counts = [], {}
    for line in lg.stdout.splitlines():
        if not line.strip():
            continue
        h, _, s = line.partition("\t")
        c = classify(s)
        counts[c] = counts.get(c, 0) + 1
        rows.append({"sha": h[:12], "subj": s[:160], "class": c})
    # total commits on first-parent, merges vs non-merges
    tot = run(["git", "rev-list", "--first-parent", "--count", branch], cwd=dest, timeout=60)
    ntot = int(tot.stdout.strip()) if tot.returncode == 0 and tot.stdout.strip().isdigit() else None
    return {"repo": repo, "branch": branch, "head": run(["git","rev-parse",branch],cwd=dest).stdout.strip()[:12],
            "commits_first_parent": ntot, "merges": counts, "n_merges": len(rows),
            "rows": rows[:400]}


def main():
    names = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    print(f"probing {len(names)} repos", flush=True)
    res = {}
    done = 0
    def work(n):
        try:
            return n, probe(n)
        except Exception as e:
            return n, {"repo": n, "error": f"{type(e).__name__}: {e}"}
    with ThreadPoolExecutor(max_workers=16) as ex:
        for n, r in ex.map(work, names):
            res[n] = r
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(names)}", flush=True)
            with open(os.path.join(OUT, n + ".json"), "w") as f:
                json.dump(r, f)
    with open(os.path.join(BASE, "mergeratio_all.json"), "w") as f:
        json.dump(res, f)
    ok = {k: v for k, v in res.items() if "error" not in v}
    print(f"ok={len(ok)} err={len(res)-len(ok)}")
    tot = {}
    for v in ok.values():
        for c, n in v["merges"].items():
            tot[c] = tot.get(c, 0) + n
    print("class totals:", json.dumps(tot, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
