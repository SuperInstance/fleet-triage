#!/usr/bin/env python3
"""
ORG2 task 2, verifier v2 -- fixed after v2's verdicts were audited by hand.

v2's output was wrong and the negative control caught it: d51631e came back
NOT_ANCESTOR, but d51631e is demonstrably on pong-quilt main's first-parent
line. Three bugs, all of which produced FALSE findings:

  1. RACE. `ensure()/head_of()/fetch()` ran from 12 threads against SHARED clone
     directories. Concurrent `git init` + `git fetch` on one dir made some
     fetches partial. Every DANGLING and many UNREACHABLE were this. A pin was
     reported as naming a nonexistent commit when the clone was simply empty.
  2. `git merge-base --is-ancestor <sha> HEAD` against an UNBORN HEAD.
     `git init` leaves HEAD pointing at a branch that does not exist until you
     fetch into it, so every ancestry test failed -> NOT_ANCESTOR for all.
  3. No assertion that the fetch actually produced a ref before judging.

Fixes: a per-target lock, ancestry always against refs/remotes/origin/<branch>,
and a hard precondition -- if the ref is not present after fetch the verdict is
UNREACHABLE, never DANGLING. A verdict is only ever emitted from state we
proved we had.
"""
import json, os, subprocess, sys, threading, collections
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
CL = os.path.join(BASE, "pinclones")
os.makedirs(CL, exist_ok=True)
OWNER = "SuperInstance"
_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


def sh(cmd, t=420):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=t)


def lock_for(name):
    with _LOCKS_GUARD:
        if name not in _LOCKS:
            _LOCKS[name] = threading.Lock()
        return _LOCKS[name]


def ensure(target):
    d = os.path.join(CL, target)
    if not os.path.isdir(os.path.join(d, "objects")):
        os.makedirs(d, exist_ok=True)
        sh(["git", "init", "-q", d])
        sh(["git", "-C", d, "remote", "add", "origin",
            f"https://github.com/{OWNER}/{target}.git"])
    return d


def verify(item):
    target, sha = item["target"], item["sha"]
    with lock_for(target):                      # <-- the fix for the race
        try:
            d = ensure(target)
            br = None
            for cand in ("main", "master"):
                r = sh(["git", "-C", d, "ls-remote", "origin", f"refs/heads/{cand}"], 180)
                if r.returncode == 0 and r.stdout.strip():
                    br = cand
                    head = r.stdout.split()[0]
                    break
            if not br:
                return {**item, "verdict": "UNREACHABLE", "why": "no main/master on origin"}
            ref = f"refs/remotes/origin/{br}"
            have = sh(["git", "-C", d, "rev-parse", "--verify", "--quiet", ref], 120)
            if have.returncode != 0 or have.stdout.strip() != head:
                f = sh(["git", "-C", d, "fetch", "-q", "--filter=tree:0", "origin",
                        f"+refs/heads/{br}:{ref}"], 420)
                if f.returncode != 0:
                    return {**item, "verdict": "UNREACHABLE", "why": "fetch failed"}
            # PRECONDITION: the head ref must exist and resolve before any verdict
            chk = sh(["git", "-C", d, "rev-parse", "--verify", "--quiet", ref], 120)
            if chk.returncode != 0 or not chk.stdout.strip():
                return {**item, "verdict": "UNREACHABLE", "why": "head ref missing after fetch"}
            if head.startswith(sha) or sha == head:
                return {**item, "verdict": "AT_HEAD", "head": head[:12]}
            t = sh(["git", "-C", d, "cat-file", "-t", sha], 120)
            if t.returncode != 0 or t.stdout.strip() != "commit":
                return {**item, "verdict": "DANGLING", "head": head[:12],
                        "why": "no such commit in target's fetched history"}
            a = sh(["git", "-C", d, "merge-base", "--is-ancestor", sha, ref], 180)
            if a.returncode == 0:
                n = sh(["git", "-C", d, "rev-list", "--count", f"{sha}..{head}"], 180)
                return {**item, "verdict": "BEHIND_HEAD", "head": head[:12],
                        "commits_behind": n.stdout.strip() if n.returncode == 0 else "?"}
            return {**item, "verdict": "NOT_ANCESTOR", "head": head[:12],
                    "why": "commit exists but is not on the target's main line"}
        except Exception as e:
            return {**item, "verdict": "UNREACHABLE", "why": f"{type(e).__name__}: {e}"}


def main():
    src = sys.argv[1]
    pins = json.load(open(src))
    uniq = sorted({(p["target"], p["sha"]) for p in pins})
    print(f"pins={len(pins)} unique={len(uniq)} targets={len({t for t,_ in uniq})}",
          flush=True)
    rm = os.path.join(CL, os.path.basename(src).split(".")[0])
    if os.path.isdir(rm):
        import shutil
        shutil.rmtree(rm)
    res = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, r in enumerate(ex.map(verify, [{"target": t, "sha": s} for t, s in uniq])):
            res[f"{r['target']}|{r['sha']}"] = r
            if (i + 1) % 100 == 0:
                print("  ", i + 1, flush=True)
    for p in pins:
        v = res.get(f"{p['target']}|{p['sha']}")
        if v:
            p["verdict"] = v["verdict"]
            p["head"] = v.get("head")
            p["commits_behind"] = v.get("commits_behind")
            p["why"] = v.get("why")
    out = os.path.join(BASE, os.path.basename(src).replace(".json", "") + "_ver.json")
    json.dump(pins, open(out, "w"))
    c = collections.Counter(p.get("verdict", "?") for p in pins)
    print(json.dumps(dict(c.most_common()), indent=1))
    for p in pins:
        if p["src"] == "fleet-murmur" and p["target"] == "pong-quilt":
            print(f"  CONTROL {p['sha']} -> {p['verdict']} head={p.get('head')} "
                  f"behind={p.get('commits_behind')}")


if __name__ == "__main__":
    main()
