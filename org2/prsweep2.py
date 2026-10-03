#!/usr/bin/env python3
"""
ORG2 task 4: re-sweep the open-PR queue. `git ls-remote --refs <url> 'refs/pull/*/merge'`
enumerates open PRs with zero API budget. Ref presence is the DISCOVERY oracle;
ancestry is the AUTHORITY (refs/pull/N/merge can outlive a merged PR -- iteration 1
found pong-quilt#88 in exactly that state).
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
OWNER = "SuperInstance"


def lsremote(repo):
    try:
        r = subprocess.run(
            ["git", "ls-remote", "--refs",
             f"https://github.com/{OWNER}/{repo}.git", "refs/pull/*/merge", "refs/heads/*"],
            capture_output=True, text=True, timeout=90)
        if r.returncode != 0:
            return repo, None, (r.stderr or "")[:200]
        return repo, r.stdout, None
    except Exception as e:
        return repo, None, f"{type(e).__name__}"


def main():
    names = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    out, errs = {}, {}
    with ThreadPoolExecutor(max_workers=24) as ex:
        for repo, so, err in ex.map(lsremote, names):
            if err:
                errs[repo] = err
                continue
            heads, prs = {}, {}
            for line in so.splitlines():
                sha, _, ref = line.partition("\t")
                ref = ref.strip()
                if ref.startswith("refs/pull/"):
                    parts = ref.split("/")
                    n = int(parts[2])
                    prs.setdefault(n, {})["merge"] = sha
                    if parts[3] == "head":
                        prs[n]["head"] = sha
                elif ref.startswith("refs/heads/"):
                    heads[ref[len("refs/heads/"):]] = sha
            out[repo] = {"prs": {str(k): v for k, v in sorted(prs.items())},
                         "heads": heads}
    with open(os.path.join(BASE, "prsweep2.json"), "w") as f:
        json.dump({"repos": out, "errors": errs}, f)
    tot = sum(len(v["prs"]) for v in out.values())
    print(f"repos ok={len(out)} err={len(errs)}  open PR merge-refs={tot}")
    for repo, v in sorted(out.items()):
        if v["prs"]:
            print(f"  {repo:34s} {sorted(int(k) for k in v['prs'])}")


if __name__ == "__main__":
    main()
