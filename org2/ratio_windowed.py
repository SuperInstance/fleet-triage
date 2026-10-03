#!/usr/bin/env python3
"""
ORG2 task 1, v3 -- the ratio, time-windowed and per-repo.

Why a window is mandatory: `direct_push` is dominated by repo CONSTRUCTION. A repo
built by `git add . && git commit` has N direct pushes and 0 PR merges by
definition, and it tells you nothing about merge culture five days later. So:

  * bucket every first-parent commit by commit date
  * report lifetime ratio AND recent-window ratio
  * report per-repo so a single bulk importer cannot carry the headline

Windows: 2026-09-25..now (5d, matches the org's "318 repos pushed in five days"),
and 2026-09-29..now (48h, the current culture).
"""
import json, os, subprocess, sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from commitcls import classify_merge, RE_SQUASH, BOT  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "bare")
PRISH = {"pr_merge", "squash_pr"}
# a hand-merge of a PR branch is still a PR landing; count it separately
HANDPR = {"hand_merge_prbranch", "hand_merge_pr_named", "hand_merge_dependabot"}


def one(repo):
    d = os.path.join(CACHE, repo)
    if not os.path.isdir(d):
        return None
    b = "main"
    if subprocess.run(["git", "rev-parse", "--verify", "--quiet", "main"], cwd=d,
                      capture_output=True).returncode != 0:
        if subprocess.run(["git", "rev-parse", "--verify", "--quiet", "master"], cwd=d,
                          capture_output=True).returncode != 0:
            return None
        b = "master"
    lg = subprocess.run(["git", "log", "--first-parent", "--date=short",
                         "--format=%ct\t%P\t%s", b], cwd=d,
                        capture_output=True, text=True, timeout=200)
    import datetime
    out = []
    for line in lg.stdout.splitlines():
        if not line.strip():
            continue
        ts, _, rest = line.partition("\t")
        parents, _, subj = rest.partition("\t")
        np = len(parents.split()) if parents.strip() else 0
        if np >= 2:
            c = classify_merge(subj)
        else:
            c = "squash_pr" if RE_SQUASH.search(subj.strip()) else \
                ("direct_push" if not BOT.match(subj) else "bot_push")
        try:
            day = datetime.datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
        except Exception:
            day = "?"
        out.append((day, c, subj[:130]))
    return out


def agg(rows, since=None):
    a = Counter()
    for day, c, _ in rows:
        if since and day < since:
            continue
        a[c] += 1
    return a


def main():
    names = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    data = {}
    def work(n):
        try:
            return n, one(n)
        except Exception:
            return n, None
    with ThreadPoolExecutor(max_workers=16) as ex:
        for n, r in ex.map(work, names):
            if r:
                data[n] = r
    json.dump({k: v for k, v in data.items()}, open(os.path.join(BASE, "windowed.json"), "w"))
    print("repos with history:", len(data))

    for label, since in (("LIFETIME", None), ("5d (>=2026-09-25)", "2026-09-25"),
                         ("48h (>=2026-09-29)", "2026-09-29")):
        tot = Counter()
        for rows in data.values():
            tot.update(agg(rows, since))
        direct = tot["direct_push"]
        prish = sum(tot[k] for k in PRISH)
        handpr = sum(tot[k] for k in HANDPR)
        print(f"\n== {label}  commits={sum(tot.values())}")
        print("   " + json.dumps(dict(tot.most_common())))
        print(f"   direct_push={direct}  formal_pr={prish}  hand_pr={handpr}")
        print(f"   RATIO direct : (formal+hand PR) = {direct}/{prish+handpr}"
              f" = {direct/(prish+handpr) if (prish+handpr) else float('inf'):.2f} : 1")
        print(f"   RATIO direct : formal PR only    = "
              f"{direct}/{prish} = {direct/prish if prish else float('inf'):.2f} : 1")

    print("\n== PER-REPO, 5d window, only repos with >=1 formal PR merge (sorted by ratio)")
    rows = []
    for repo, rs in data.items():
        a = agg(rs, "2026-09-25")
        if a["pr_merge"] + a["squash_pr"] < 1:
            continue
        d = a["direct_push"]
        p = a["pr_merge"] + a["squash_pr"]
        h = sum(a[k] for k in HANDPR)
        rows.append((d / (p + h) if (p + h) else 99, repo, d, p, h, a["hand_merge_feature"]))
    rows.sort(reverse=True)
    for ratio, repo, d, p, h, hf in rows:
        print(f"   {ratio:7.2f}:1  {repo:32s} direct={d:<4d} pr={p:<4d} handpr={h:<3d} handfeat={hf}")


if __name__ == "__main__":
    main()
