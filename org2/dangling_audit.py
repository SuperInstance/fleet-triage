#!/usr/bin/env python3
"""
ORG2 task 2 -- PRECISION AUDIT of the DANGLING bucket.

A hand audit of the first DANGLING pin I checked (quilt-tools -> git-agent
8d6c31a) found the pin was CORRECT: git-agent has
    8d6c31a Merge pull request #4 from SuperInstance/docs/quilt-opcode-provenance
So the automated verdict was wrong and the DANGLING bucket cannot be reported as
a count of broken pins.

This script re-checks a random sample of DANGLING pins with a FULL bare clone
(--filter=tree:0, all refs) and a three-way answer:
  REAL      the sha is a commit in the target, on main's line  -> pin is fine,
            the automated verdict was a clone artifact
  OFF-MAIN  the sha is a commit in the target but not on main   -> genuinely
            unusable as a "current state" pin
  ABSENT    no such commit anywhere in the target              -> genuinely broken
  NOFETCH   the clone failed -> counted as unknown, never as broken

The point is to publish a PRECISION figure for the bucket, not a scary number.
"""
import json, os, random, subprocess, sys, collections
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
CL = os.path.join(BASE, "auditclones")
os.makedirs(CL, exist_ok=True)
OWNER = "SuperInstance"


def sh(cmd, t=600):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=t)


def check(item):
    target, sha = item["target"], item["sha"]
    d = os.path.join(CL, target)
    try:
        if not os.path.isdir(os.path.join(d, "objects")):
            sh(["git", "clone", "--bare", "--filter=tree:0", "--quiet",
                f"https://github.com/{OWNER}/{target}.git", d])
        br = None
        for c in ("main", "master"):
            r = sh(["git", "-C", d, "rev-parse", "--verify", "--quiet",
                    f"refs/heads/{c}"])
            if r.returncode == 0:
                br = c
                break
        if not br:
            return {**item, "audit": "NOFETCH", "why": "no main/master"}
        t_ = sh(["git", "-C", d, "cat-file", "-t", sha], 180)
        if t_.returncode != 0 or t_.stdout.strip() != "commit":
            # also try it as a full sha / a unique prefix among ALL refs
            r2 = sh(["git", "-C", d, "rev-list", "--all"], 300)
            hits = [c for c in r2.stdout.split() if c.startswith(sha)]
            if not hits:
                return {**item, "audit": "ABSENT"}
            return {**item, "audit": "OFF-MAIN" if not _on_main(d, hits[0], br) else "REAL",
                    "resolved": hits[0][:12]}
        return {**item, "audit": "REAL" if _on_main(d, sha, br) else "OFF-MAIN"}
    except Exception as e:
        return {**item, "audit": "NOFETCH", "why": f"{type(e).__name__}"}


def _on_main(d, sha, br):
    return sh(["git", "-C", d, "merge-base", "--is-ancestor", sha,
               f"refs/heads/{br}"], 180).returncode == 0


def main():
    pins = json.load(open(os.path.join(BASE, "pins_clean.json")))
    D = [p for p in pins if p.get("verdict") == "DANGLING"]
    # dedupe on (target, sha) so a clone is reused
    uniq = sorted({(p["target"], p["sha"]) for p in D})
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    random.seed(20261001)
    sample = random.sample(uniq, min(n, len(uniq)))
    print(f"DANGLING pins={len(D)}  unique(target,sha)={len(uniq)}  "
          f"sampling {len(sample)}", flush=True)
    res = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(check, [{"target": t, "sha": s} for t, s in sample]):
            res.append(r)
            print(f"  {r['audit']:8s} {r['target']:26s} {r['sha'][:12]}", flush=True)
    c = collections.Counter(r["audit"] for r in res)
    tot = sum(c.values())
    print("\nPRECISION OF THE DANGLING BUCKET (hand-audited sample)")
    for k, v in c.most_common():
        print(f"   {k:8s} {v:3d}  {100*v/tot:5.1f}%")
    real = c["REAL"] + c["OFF-MAIN"]
    print(f"\n  => {real}/{tot} = {100*real/tot:.0f}% of automated DANGLING verdicts are "
          f"wrong (the sha is real).")
    print(f"  => publishable broken-pin count from this bucket: {c['ABSENT']} "
          f"of {len(uniq)} sampled-unique, scaled = ~{round(c['ABSENT']/tot*len(uniq))} "
          f"IF the sample is representative (n={tot}, wide CI).")
    json.dump(res, open(os.path.join(BASE, "dangling_audit.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
