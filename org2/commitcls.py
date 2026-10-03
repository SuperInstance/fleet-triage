#!/usr/bin/env python3
"""
ORG2 task 1, v2 -- the denominator mergeratio.py was missing.

`git log --merges` only sees commits with >=2 parents. Two whole classes of landed
work are invisible to it:

  * squash merges   -> 1 parent, subject usually ends " (#123)"
  * fast-forward / direct push -> 1 parent, no PR marker at all

So the v1 ratio (0.22 direct:PR) was computed over merge commits ONLY and is an
upper bound on apparent PR discipline, not a measure of it. This pass walks ALL
first-parent commits and classifies non-merge commits by subject shape:

  squash_pr   subject ends "(#N)"            -> a PR landed, squashed
  direct_push no (#N), no known-bot prefix   -> landed with no PR at all
  ff_or_other                                   -> ambiguous (see report)

We cannot see GitHub's PR ledger without the API, so "(#N)" is a *convention*, not
a proof. The report states that limit. But it is the only unauthenticated signal
that exists, and it is 1-parent-complete where --merges is not.
"""
import json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

BASE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE, "bare")

RE_SQUASH = re.compile(r"\(#(\d+)\)\s*$")
RE_PR = re.compile(r"^Merge pull request #(\d+)\b", re.I)
RE_BRANCH = re.compile(r"^Merge branch '(?P<b>.+)'", re.I)
RE_RT = re.compile(r"^Merge remote-tracking branch '(?P<b>.+)'", re.I)
RE_PRREF = re.compile(r"refs/pull/|origin/pr/", re.I)
RE_DEP_BRANCH = re.compile(r"^Merge branch 'dependabot/", re.I)
RE_PSHORT = re.compile(r"^Merge branch 'p(\d+)'\b", re.I)   # dependabot branch naming
# A branch name that names a feature, not a bot: real work, hand-merged.
RE_HANDJOB = re.compile(r"^Merge (?:branch|remote-tracking branch|PR|pull request) "
                        r"'?(?P<b>[a-z][a-z0-9._/-]{2,60})", re.I)
BOT = re.compile(r"^\s*(Merge pull request|dependabot|Bump |build\(deps)", re.I)


def classify_merge(subject):
    s = subject.strip()
    if RE_PR.match(s):
        return "pr_merge"
    if RE_RT.match(s):
        b = RE_RT.match(s).group("b")
        if RE_PRREF.search(b):
            return "hand_merge_prbranch"      # PR branch, merged by hand
        if b.split("/")[-1] in ("main", "master", "develop"):
            return "merge_extern_main"        # pulled main from elsewhere into main
        return "hand_merge_other_branch"
    m = RE_BRANCH.match(s)
    if m:
        b = m.group("b")
        if b.startswith("http") or "github.com" in b:
            return "merge_extern_main"
        if RE_DEP_BRANCH.match(s):
            return "hand_merge_dependabot"
        if RE_PSHORT.match(s):
            return "hand_merge_dependabot"    # 'p54' is dependabot's branch naming
        return "hand_merge_feature"
    if re.match(r"^Merge PR #\d+", s, re.I):
        return "hand_merge_pr_named"         # a PR, merged with a custom subject
    if re.match(r"^merge[:\s]", s, re.I):
        return "hand_merge_lowercase"
    if re.match(r"^Merge (?:commit|tag) '", s, re.I):
        return "tag_merge"
    return "other_merge"


def probe(repo):
    dest = os.path.join(CACHE, repo)
    if not os.path.isdir(dest):
        return {"repo": repo, "error": "no clone (not in tierA set)"}
    r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "main"],
                       cwd=dest, capture_output=True, text=True)
    branch = "main"
    if r.returncode != 0:
        r = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "master"],
                           cwd=dest, capture_output=True, text=True)
        if r.returncode != 0:
            return {"repo": repo, "error": "no main/master"}
        branch = "master"
    lg = subprocess.run(["git", "log", "--first-parent", "--format=%H\t%P\t%s", branch],
                        cwd=dest, capture_output=True, text=True, timeout=180)
    counts, rows = {}, []
    for line in lg.stdout.splitlines():
        if not line.strip():
            continue
        h, _, rest = line.partition("\t")
        parents, _, subj = rest.partition("\t")
        np = len(parents.split()) if parents.strip() else 0
        if np >= 2:
            c = classify_merge(subj)
        else:
            m = RE_SQUASH.search(subj.strip())
            c = "squash_pr" if m else ("direct_push" if not BOT.match(subj) else "bot_push")
        counts[c] = counts.get(c, 0) + 1
        if len(rows) < 600:
            rows.append({"sha": h[:12], "np": np, "cls": c, "subj": subj[:150]})
    return {"repo": repo, "branch": branch, "counts": counts, "n": sum(counts.values()),
            "rows": rows}


def main():
    names = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    res, done = {}, 0
    def work(n):
        try:
            return n, probe(n)
        except Exception as e:
            return n, {"repo": n, "error": f"{type(e).__name__}: {e}"}
    with ThreadPoolExecutor(max_workers=16) as ex:
        for n, r in ex.map(work, names):
            res[n] = r
            done += 1
            if done % 50 == 0:
                print(" ", done, flush=True)
    json.dump(res, open(os.path.join(BASE, "commitcls_all.json"), "w"))
    ok = {k: v for k, v in res.items() if "error" not in v}
    tot = {}
    for v in ok.values():
        for c, n in v["counts"].items():
            tot[c] = tot.get(c, 0) + n
    print("repos", len(ok), "commits", sum(tot.values()))
    print(json.dumps(dict(sorted(tot.items(), key=lambda x: -x[1])), indent=1))


if __name__ == "__main__":
    main()
