#!/usr/bin/env python3
"""
ORG2 task 2, stage 2 -- VERIFY every extracted pin against the target repo's real HEAD.

Answers the question the pin actually asks: "is the state I claim about <target>
still true?" A pin is only trustworthy if the commit it names is one you can
locate, and the claim it supports has not been overtaken.

VERDICTS (ordered worst-last):
  DANGLING        sha does not exist in <target> at all. The claim is checkable
                  and fails. Worst case: a precise-looking pin to nothing.
  NOT_ANCESTOR    sha exists but is not on <target>'s main line -> rewritten or
                  orphaned branch history.
  BEHIND_HEAD     sha is an ancestor of HEAD, HEAD != sha -> the target has moved
                  since the pin. This is the ordinary, expected state of a pin.
                  Whether the CLAIM is now false is stage 3.
  AT_HEAD         sha IS head. Current.
  UNREACHABLE     network/clone failure. Recorded as a gap, never as a pass.

Clone strategy: --filter=tree:0 gives the FULL commit graph with no blob/trees,
so ancestry is exact AND cheap. A --depth=N clone would silently break
merge-base and make DANGLING appear for every old pin (iteration 1 hit exactly
that: 123 SHA_UNKNOWN verdicts it never re-tested).
"""
import json, os, subprocess, sys, collections
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
CL = os.path.join(BASE, "pinclones")
os.makedirs(CL, exist_ok=True)
OWNER = "SuperInstance"


def sh(cmd, cwd=None, t=420):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=t)


def ensure(target):
    d = os.path.join(CL, target)
    if os.path.isdir(os.path.join(d, "objects")):
        return d
    os.makedirs(d, exist_ok=True)
    sh(["git", "init", "-q", d])
    sh(["git", "-C", d, "remote", "add", "origin",
        f"https://github.com/{OWNER}/{target}.git"])
    return d


def head_of(d):
    for br in ("main", "master"):
        r = sh(["git", "-C", d, "ls-remote", "origin", f"refs/heads/{br}"], t=180)
        if r.returncode == 0 and r.stdout.strip():
            return br, r.stdout.split()[0]
    return None, None


def verify(item):
    target, sha = item["target"], item["sha"]
    try:
        d = ensure(target)
        br, head = head_of(d)
        if not head:
            return {**item, "verdict": "UNREACHABLE", "why": "no head ref"}
        if sh(["git", "-C", d, "fetch", "-q", "--filter=tree:0", "origin",
               f"refs/heads/{br}"], t=420).returncode != 0:
            return {**item, "verdict": "UNREACHABLE", "why": "fetch failed",
                    "head": head[:12]}
        full = head
        if sha == head or head.startswith(sha):
            return {**item, "verdict": "AT_HEAD", "head": head[:12]}
        # prefix match in either direction
        t = sh(["git", "-C", d, "cat-file", "-t", sha], t=120)
        if t.returncode != 0:
            return {**item, "verdict": "DANGLING", "head": head[:12],
                    "why": "sha absent from target object graph"}
        anc = sh(["git", "-C", d, "merge-base", "--is-ancestor", sha, "HEAD"], t=180)
        if anc.returncode == 0:
            behind = sh(["git", "-C", d, "rev-list", "--count", f"{sha}..{head}"], t=180)
            n = behind.stdout.strip() if behind.returncode == 0 else "?"
            return {**item, "verdict": "BEHIND_HEAD", "head": head[:12],
                    "commits_behind": n}
        return {**item, "verdict": "NOT_ANCESTOR", "head": head[:12]}
    except Exception as e:
        return {**item, "verdict": "UNREACHABLE", "why": f"{type(e).__name__}: {e}"}


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE, "pins3.json")
    pins = json.load(open(src))
    print(f"loaded {len(pins)} pins from {src}")
    # dedupe on (target, sha) for the expensive part
    uniq = sorted({(p["target"], p["sha"]) for p in pins})
    print(f"pins={len(pins)}  unique (target,sha)={len(uniq)}  "
          f"targets={len({t for t,_ in uniq})}", flush=True)
    res = {}
    done = 0
    def work(t):
        return verify({"target": t[0], "sha": t[1]})
    with ThreadPoolExecutor(max_workers=12) as ex:
        for r in ex.map(work, uniq):
            res[f"{r['target']}|{r['sha']}"] = r
            done += 1
            if done % 100 == 0:
                print("  ", done, flush=True)
    for p in pins:
        v = res.get(f"{p['target']}|{p['sha']}")
        if v:
            p["verdict"] = v["verdict"]
            p["head"] = v.get("head")
            p["commits_behind"] = v.get("commits_behind")
    json.dump(pins, open(os.path.join(BASE, os.path.basename(src).replace(".json","")+"_verified.json"), "w"))
    c = collections.Counter(p.get("verdict", "?") for p in pins)
    print(json.dumps(dict(c.most_common()), indent=1))


if __name__ == "__main__":
    main()
