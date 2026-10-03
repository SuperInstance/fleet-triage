#!/usr/bin/env python3
"""
ORG2 task 2, stage 3 -- the RELIABLE part of the pin census.

The BEHIND_HEAD verdict is weak in the right way: it only says "this commit is a
real ancestor of the target's head and is not the head". It cannot be wrong
about a pin's validity, only about its currency. That is the number worth
publishing, and it is the one that scales.

Distance is measured on FIRST-PARENT, because that is main's own line of
descent: "how many merges have landed since this pin was written" is the
question a reader of the doc actually has. Counting all reachable commits
answers a different and much scarier-looking question.
"""
import json, os, subprocess, sys, collections, threading
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
CL = os.path.join(CLDIR := os.path.join(BASE, "pinclones"))
_LOCKS, _G = {}, threading.Lock()


def sh(c, t=420):
    return subprocess.run(c, capture_output=True, text=True, timeout=t)


def lk(n):
    with _G:
        return _LOCKS.setdefault(n, threading.Lock())


def first_parent_behind(target, branch, sha):
    d = os.path.join(CL, target)
    # NOTE: do not gate on objects/ existing -- a --filter=tree:0 partial clone does
    # not always materialise it, and gating on it silently produced 0/304 measured.
    if not os.path.isdir(d):
        return None
    r = sh(["git", "-C", d, "rev-list", "--count", "--first-parent",
            f"{sha}..refs/remotes/origin/{branch}"], 240)
    if r.returncode != 0 or not r.stdout.strip().isdigit():
        return None
    return int(r.stdout.strip())


def main():
    pins = json.load(open(os.path.join(BASE, "pins_clean.json")))
    BH = [p for p in pins if p.get("verdict") == "BEHIND_HEAD"]
    targets = sorted({p["target"] for p in BH})
    # find each target's default branch once
    branch = {}
    for t in targets:
        for c in ("main", "master"):
            if sh(["git", "-C", os.path.join(CL, t), "rev-parse", "--verify", "--quiet",
                   f"refs/remotes/origin/{c}"], 120).returncode == 0:
                branch[t] = c
                break
    print(f"BEHIND_HEAD pins: {len(BH)} over {len(targets)} targets", flush=True)
    dist = {}
    def work(p):
        t, s = p["target"], p["sha"]
        if t not in branch:
            return (t, s), None
        with lk(t):
            return (t, s), first_parent_behind(t, branch[t], s)
    with ThreadPoolExecutor(max_workers=8) as ex:
        for k, v in ex.map(work, BH):
            dist[k] = v
    ok = {k: v for k, v in dist.items() if v is not None}
    for p in BH:
        p["first_parent_behind"] = dist.get((p["target"], p["sha"]))
    json.dump(BH, open(os.path.join(BASE, "pins_behind.json"), "w"))
    print(f"measured: {len(ok)}/{len(BH)}")
    buckets = collections.Counter()
    for v in ok.values():
        b = ("0 (raced to head)" if v == 0 else
             "1" if v == 1 else "2-4" if v <= 4 else "5-19" if v < 20 else "20+")
        buckets[b] += 1
    print("\nFIRST-PARENT COMMITS LANDED SINCE THE PIN")
    for k in ("0 (raced to head)", "1", "2-4", "5-19", "20+"):
        if buckets[k]:
            print(f"   {k:18s} {buckets[k]:4d}")
    print(f"\n  median behind: {sorted(ok.values())[len(ok)//2]}")
    print(f"  max behind:     {max(ok.values())}")
    print("\nWORST 20 (src -> target : first-parent commits behind)")
    rows = sorted(((v, k) for k, v in ok.items()), reverse=True)[:20]
    for v, (t, s) in rows:
        n = len({p["src"] for p in BH if p["target"] == t and p["sha"] == s})
        print(f"   {v:5d}  {t:26s} {s[:10]}   ({n} source file(s))")


if __name__ == "__main__":
    main()
