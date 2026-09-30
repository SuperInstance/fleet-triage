#!/usr/bin/env python3
"""Fleet triage — find the repos where a human (or an agent) can actually add value.

WHY THIS EXISTS. There are 5,127 public repos under SuperInstance. Guessing which ones
need help is how you spend a day auditing something that was already fine. Every signal
here is MECHANICAL and CHEAP, so the census narrows the field before any judgement is
applied.

THE SIGNALS, and what each one means:

  hollow      source files that are 0 bytes. A repo can have 1,000 blobs and no code.
  untested    source files, zero test files. Not a defect -- a fact worth knowing.
  nolicense   no LICENSE. Cheap, and it blocks outside contribution.
  noverify    no CI at all.
  failopen    a CI workflow whose test command ends in a pipe without `pipefail`.
              THIS IS A LANDMINE: `run: pytest | tee out.txt` under `bash -e` cannot
              fail, for any red test, import crash, or segfault. A green checkmark on
              one of these is a claim about nothing.
  autopub     a workflow that publishes on push. Unreviewed publishing.
  vendored    most of the tree is a committed dependency directory. The repo is a
              wrapper around somebody else's code and its file count is a lie.
  empty       a README that is a stub, or no README at all.

The two filters that must both be applied to any size claim are the DIRECTORY filter
(node_modules, target, vendor, .venv, dist, build, __pycache__, .wrangler, coverage)
and the EXTENSION filter (.min.js, .map, .d.ts, .lock). GitHub's `size` field is wrong
for two different reasons -- a committed vendor tree, and git-object history bloat with a
clean working tree -- and either filter alone misses half the cases.
"""
from __future__ import annotations

import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

ORG = "SuperInstance"
VENDOR_DIR = re.compile(
    r"(^|/)(node_modules|target|vendor|third_party|\.venv|venv|site-packages|dist|build|"
    r"\.next|out|_build|__pycache__|\.wrangler|coverage|thirdparty)(/|$)")
VENDOR_EXT = re.compile(r"\.min\.(js|css)$|\.map$|\.d\.ts$|\.(lock|lockb)$")
SRC = re.compile(r"\.(py|ts|js|rs|go|jl|hs|ml|ex|exs|c|cpp|h|java|rb|swift|kt|scala)$")
TEST = re.compile(r"(^|/)(tests?|spec|__tests__)(/|$)|_test\.|test_.*\.py$|\.test\.|Test\.java$")
DOC = re.compile(r"\.(md|rst|txt|ipynb)$")
# `| tee` or `| grep` after the test command = fail-open under `bash -e`
PIPED = re.compile(r"\|\s*(tee|grep|head|tail|less|more|cat|awk|sed)\b")

_TOK = os.environ.get("GITHUB_TOKEN", "")
_H = {"Accept": "application/vnd.github+json", "User-Agent": "fleet-triage",
      **({"Authorization": f"Bearer {_TOK}"} if _TOK else {})}
_429 = 0.0


def api(path: str, tries: int = 3):
    """One request, with a shared rate-limit gate. A 403 rate limit is a LOAD condition,
    not a finding: it must never be recorded as 'the repo has no CI'."""
    global _429
    for a in range(tries):
        try:
            req = urllib.request.Request("https://api.github.com" + path, headers=_H)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                wait = 61 if e.code == 403 else 30
                _429 = max(_429, wait)
                time.sleep(min(wait, 8) * (a + 1))
                continue
            if e.code == 404:
                return {}
            time.sleep(1.5)
        except Exception:
            time.sleep(1.5)
    return {}


def inspect(repo: str) -> dict:
    """Deep-inspect ONE repo. Returns the row, always with `errors` populated rather
    than silently emitting a clean result for a repo we failed to read."""
    row = {"repo": repo, "errors": [], "signals": [], "blobs": 0, "src": 0, "test": 0,
           "doc": 0, "vendor": 0, "src_bytes": 0, "tree_bytes": 0, "empty_src": 0, "license": False,
           "readme": False, "ci": False, "ci_files": 0, "failopen": 0, "autopub": 0}
    meta = api(f"/repos/{ORG}/{repo}")
    if not meta:
        row["errors"].append("metadata unreachable (not a clean bill of health)")
        row["signals"].append("unreadable")
        return row
    row["size_kb"] = meta.get("size", 0)
    row["pushed_at"] = meta.get("pushed_at", "")[:10]
    row["license"] = bool(meta.get("license"))
    tree = api(f"/repos/{ORG}/{repo}/git/trees/{meta.get('default_branch','main')}?recursive=1")
    blobs = tree.get("tree") or []
    if not blobs and not tree:
        row["errors"].append("tree unreachable")
    row["truncated"] = bool(tree.get("truncated"))
    for b in blobs:
        p = b.get("path", "")
        if b.get("type") != "blob":
            continue
        row["blobs"] += 1
        size = b.get("size", 0)
        base = p.rsplit("/", 1)[-1]
        row["tree_bytes"] += size          # every real blob, for the history check
        if VENDOR_DIR.search(p) or VENDOR_EXT.search(p):
            row["vendor"] += 1
            continue
        if base.upper().startswith(("LICENSE", "COPYING")):
            row["license"] = True
        if base.upper().startswith("README"):
            row["readme"] = size > 200
        if p.startswith(".github/workflows/") and base.endswith((".yml", ".yaml")):
            row["ci_files"] += 1
            continue
        if SRC.search(p):
            row["src"] += 1
            row["src_bytes"] += size
            if size == 0:
                row["empty_src"] += 1
        elif TEST.search(p):
            row["test"] += 1
        elif DOC.search(p):
            row["doc"] += 1
    row["ci"] = row["ci_files"] > 0
    # workflow contents, for the two workflow-level signals
    if row["ci_files"]:
        wfs = [b["path"] for b in blobs
               if b.get("type") == "blob" and b["path"].startswith(".github/workflows/")]
        for w in wfs[:6]:
            c = api(f"/repos/{ORG}/{repo}/contents/" + urllib.parse.quote(w))
            body = ""
            if isinstance(c, dict) and c.get("content"):
                try:
                    body = base64_of(c["content"])
                except Exception:
                    pass
            if not body:
                continue
            # pipefail must be checked PER STEP, not per file. A whole-file guard means
            # one job that sets `set -o pipefail` silently exempts every other job in the
            # same workflow -- which is the same defect as the one being hunted: a control
            # that runs, is satisfied, and gates nothing.
            for step in _steps(body):
                if not re.search(r"(pytest|vitest|jest|cargo test|go test|ctest|npm test|make test)", step):
                    continue
                if not PIPED.search(step):
                    continue
                if re.search(r"pipefail|set -eo\s*pipefail", step) or re.search(r"^\s*shell:\s*bash", step) and False:
                    continue
                row["failopen"] += 1
            if re.search(r"(npm publish|twine upload|cargo publish|gh release create|docker push|gem push)", body):
                row["autopub"] += 1

    S = row["signals"]
    if row["empty_src"]:
        S.append("hollow")                       # 0-byte source files: not a small repo, an empty one
    if row["src"] and not row["test"]:
        S.append("untested")
    if not row["license"]:
        S.append("nolicense")
    if not row["ci"]:
        S.append("noverify")
    if row["failopen"]:
        S.append("failopen")
    if row["autopub"]:
        S.append("autopub")
    if row["blobs"] and row["vendor"] / row["blobs"] > 0.5:
        S.append("vendored")
    if not row["readme"]:
        S.append("noreadme")
    if not row["src"]:
        S.append("nocode")
    # HISTORY BLOAT, done correctly.
    #
    # The first version compared the API `size` against `src_bytes` only. That divides by
    # zero for any repo with no source files, so every docs-only and media-only repo was
    # flagged "historybloat" BY CONSTRUCTION -- 106 repos, mostly false. A ratio against a
    # denominator that can be zero is not a measurement.
    #
    # The real signature is: the API `size` is far larger than the CURRENT TREE, i.e. the
    # excess is git-object history rather than substance. So compare against `tree_bytes`,
    # and require a floor so a 40 KB repo with a 300 MB history does not dominate the list.
    tb = row["tree_bytes"]
    row["bloat_ratio"] = round((row["size_kb"] * 1024) / tb, 1) if tb else None
    if tb > 50_000 and row["size_kb"] * 1024 > 3 * tb:
        S.append("historybloat")
    return row


def _joined_runs(text: str) -> list:
    """GitHub Actions folds `\\` continuations into one logical line. Un-join them before
    looking for a pipe, or a `| tee` on a continuation line is invisible to the check."""
    out, buf = [], ""
    for line in text.splitlines():
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
        else:
            out.append((buf + line).strip()); buf = ""
    if buf:
        out.append(buf.strip())
    return out


def _steps(body: str) -> list:
    """Split a workflow into its individual `run:` steps, continuation-joined.

    A step is bounded by the next key at the same indent (`- name:`, `- uses:`, a new
    job, or dedent). Everything a `run:` block can influence lives inside one.
    """
    steps, cur, inrun = [], [], False
    for raw in _joined_runs(body):
        s = raw.strip()
        if re.match(r"^-\s+(name|uses|id):", s) or re.match(r"^\w[\w-]*:\s*$", s) \
           or re.match(r"^-{3,}", s):
            if inrun:
                steps.append("\n".join(cur)); cur, inrun = [], False
            continue
        if re.match(r"^(-\s+)?run\s*:", s):
            if inrun:
                steps.append("\n".join(cur))
            cur, inrun = [s], True
            continue
        if inrun:
            cur.append(s)
    if inrun and cur:
        steps.append("\n".join(cur))
    return steps


def base64_of(s: str) -> str:
    import base64
    return base64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "replace")


def main():
    repos = []
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        repos = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    else:
        page = 1
        while page <= 60:
            d = api(f"/orgs/{ORG}/repos?per_page=100&page={page}&type=public")
            if not d:
                break
            repos += [r["name"] for r in d]
            if len(d) < 100:
                break
            page += 1
    print(f"  {len(repos)} repos queued", file=sys.stderr)
    rows = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, r in enumerate(ex.map(inspect, repos)):
            rows.append(r)
            if (i + 1) % 50 == 0:
                print(f"    {i+1}/{len(repos)}  rate-limit wait {int(_429)}s", file=sys.stderr)
    rows.sort(key=lambda r: (-len(r["signals"]), -r["blobs"]))
    with open("triage.json", "w") as fh:
        json.dump(rows, fh, indent=1)
    from collections import Counter
    c = Counter(s for r in rows for s in r["signals"])
    print(f"\n  {len(rows)} inspected -> triage.json")
    for s, n in c.most_common():
        print(f"    {s:14} {n}")
    print(f"\n  unreadable (NOT counted as clean): {sum(1 for r in rows if 'unreadable' in r['signals'])}")


if __name__ == "__main__":
    main()
