#!/usr/bin/env python3
"""
ORG2 task 1, v4 -- BULK IMPORT vs AGENT DIRECT PUSH.

Day-concentration alone cannot tell them apart: an agent committing one file per
second produces 35 commits in one day, and so does `tar | git fast-import`. The
discriminator is AUTHOR DATE vs COMMIT DATE:

  * a bulk import replays history -- original author dates survive, so
    (commit_date - author_date) is large and scattered across old timestamps;
  * an agent writing into main *now* mints both timestamps seconds apart.

So: FRESH = |commit_date - author_date| <= 300s. A repo whose 48h commits are
overwhelmingly FRESH is not replaying a tree, it is authoring into main.

Reported per repo so the headline can be deconcentrated by hand.
"""
import json, os, subprocess, sys, collections
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "bare")
PRISH = {"pr_merge", "squash_pr"}


def one(repo):
    d = os.path.join(CACHE, repo)
    if not os.path.isdir(d):
        return None
    b = "main"
    if subprocess.run(["git", "rev-parse", "--verify", "--quiet", "main"], cwd=d,
                      capture_output=True).returncode != 0:
        b = "master"
        if subprocess.run(["git", "rev-parse", "--verify", "--quiet", "master"], cwd=d,
                          capture_output=True).returncode != 0:
            return None
    lg = subprocess.run(["git", "log", "--first-parent", "--format=%ct\t%at\t%P\t%s", b],
                        cwd=d, capture_output=True, text=True, timeout=200)
    out = []
    for line in lg.stdout.splitlines():
        if not line.strip():
            continue
        p = line.split("\t", 3)
        if len(p) < 4:
            continue
        ct, at, parents, subj = int(p[0]), int(p[1]), p[2], p[3]
        np = len(parents.split()) if parents.strip() else 0
        out.append({"ct": ct, "at": at, "skew": abs(ct - at), "np": np, "subj": subj[:120]})
    return out


def main():
    names = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    res = {}
    def work(n):
        try:
            return n, one(n)
        except Exception:
            return n, None
    with ThreadPoolExecutor(max_workers=16) as ex:
        for n, r in ex.map(work, names):
            if r:
                res[n] = r
    json.dump(res, open(os.path.join(BASE, "authordate.json"), "w"))

    import datetime
    def day(ts):
        return datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")

    for since_ts, label in ((0, "LIFETIME"),
                            (int(datetime.datetime(2026, 9, 25).timestamp()), "5d"),
                            (int(datetime.datetime(2026, 9, 29).timestamp()), "48h")):
        agg = collections.Counter()
        for repo, rows in res.items():
            for c in rows:
                if c["ct"] < since_ts or c["np"] >= 2:
                    continue
                cls = "fresh_author" if c["skew"] <= 300 else "replayed_author"
                agg[cls] += 1
        print(f"{label:9s} 1-parent commits: {dict(agg)}  "
              f"fresh={agg['fresh_author']} replayed={agg['replayed_author']}")

    print("\n== per-repo, 48h, 1-parent commits, split fresh/replayed")
    rows = []
    since = int(datetime.datetime(2026, 9, 29).timestamp())
    for repo, cs in res.items():
        a = collections.Counter()
        for c in cs:
            if c["ct"] < since or c["np"] >= 2:
                continue
            a["fresh" if c["skew"] <= 300 else "replayed"] += 1
        if a["fresh"] + a["replayed"] >= 3:
            rows.append((a["fresh"], a["replayed"], repo))
    rows.sort(reverse=True)
    tf = tr = 0
    for f, r, repo in rows[:26]:
        tf += f; tr += r
        tag = "REPLAY-BULK" if f == 0 else ("AGENT-PUSH" if r == 0 else "mixed")
        print(f"   {repo:32s} fresh={f:<5d} replayed={r:<5d}  {tag}")
    print(f"   (top-26: fresh={tf} replayed={tr})")


if __name__ == "__main__":
    main()
