#!/usr/bin/env python3
"""
rollout_deps.py -- make the 9 red substrate-* harnesses run, from a FRESH CLONE.

For each repo, in a pristine `git clone -b main` of GitHub (no sibling checkouts present):
  1. apply the previous lane's fail-closed patch   (proves the fix is still in place)
  2. rewrite ONLY the `dependencies` block:  file:../X  ->  github:SuperInstance/X
  3. npm install
  4. npm test, record the exit code

No product code is edited. No test is edited. Nothing is stubbed.
"""
import json, os, re, shutil, subprocess, sys, textwrap

ROOT = "/workspace/projects/fleet-triage"
REPOS = ROOT + "/repos"
ART = ROOT + "/substrate-fix-artifacts/per-repo"
WORK = "/tmp/deps-rollout"

# the 9 that the fail-closed fix turned red
NINE = [
    "substrate-attest", "substrate-bundle", "substrate-contest", "substrate-delegate",
    "substrate-merger", "substrate-revoke", "substrate-traverse",
    "substrate-withdraw", "substrate-witness-log",
]
# control: the 2 that were already green. Run them too, so the panel is the whole family.
TWO = ["substrate-canary-pin", "substrate-membership"]

GH = "https://github.com/SuperInstance/%s.git"


def sh(cmd, cwd=None, timeout=300):
    p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,
                       text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def repoint_deps(repo_dir):
    """file:../X  ->  github:SuperInstance/X   (package.json only). Returns rewrites."""
    p = os.path.join(repo_dir, "package.json")
    d = json.load(open(p))
    rewrites = []
    new = {}
    for k, v in (d.get("dependencies") or {}).items():
        if isinstance(v, str) and v.startswith("file:../"):
            slug = v[len("file:../"):]
            new[k] = "github:SuperInstance/%s" % slug
            rewrites.append((k, v, new[k]))
        else:
            new[k] = v
    if rewrites:
        d["dependencies"] = new
        json.dump(d, open(p, "w"), indent=2)
        open(p, "a").write("\n")
    return rewrites


def run_one(repo):
    name = repo
    slug = name
    work = os.path.join(WORK, name)
    shutil.rmtree(work, ignore_errors=True)
    out = {"repo": name}

    # 1. pristine clone of upstream main -- no siblings, no node_modules, no fix
    rc, so, se = sh("git clone -q -b main %s ." % (GH % slug), cwd=work, timeout=180) \
        if os.makedirs(work, exist_ok=True) is None else (1, "", "mkdir")
    if rc != 0:
        out["stage"] = "clone"; out["err"] = se.strip()[:200]; return out
    out["cloned"] = True

    # 2. previous lane's fail-closed fix -- MUST be present for this lane to be valid
    patch = os.path.join(ART, name + ".patch")
    if os.path.exists(patch):
        rc, so, se = sh("git apply " + patch, cwd=work)
        out["failclosed_applied"] = (rc == 0)
        if rc != 0:
            out["stage"] = "patch"; out["err"] = se.strip()[:200]; return out
    else:
        out["failclosed_applied"] = None  # nothing to apply (attest had no test.js change)

    # prove the fail-open fix is really in the tree we are about to run
    t = open(os.path.join(work, "test.js")).read()
    out["exit_fix_present"] = ("process.exit(1)" in t)

    # 3. packaging fix
    out["rewrites"] = repoint_deps(work)

    # 4/5. install + test
    rc, so, se = sh("npm install --no-audit --no-fund", cwd=work, timeout=300)
    out["install"] = rc
    if rc != 0:
        out["stage"] = "install"; out["err"] = (so + se).strip()[-300:]
    rc, so, se = sh("npm test", cwd=work, timeout=120)
    out["test"] = rc
    out["stdout"] = so.strip()
    out["stderr"] = se.strip()
    return out


def main():
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK, exist_ok=True)
    results = []
    for r in NINE + TWO:
        res = run_one(r)
        results.append(res)
        print(json.dumps(res))
        sys.stdout.flush()
    with open(ROOT + "/substrate-fix-artifacts/rollout_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n================ PANEL ================")
    print("%-26s %-4s %-4s %-5s %s" % ("REPO", "inst", "test", "fix", "note"))
    for r in results:
        note = ""
        if r.get("test") != 0:
            m = re.search(r"FAIL:.*|Error:.*", (r.get("stderr") or r.get("stdout") or ""))
            note = (m.group(0)[:60] if m else (r.get("err") or "")[:60])
        print("%-26s %-4s %-4s %-5s %s" % (
            r["repo"], r.get("install"), r.get("test"),
            "Y" if r.get("exit_fix_present") else "n", note))
    green = [r["repo"] for r in results if r.get("test") == 0]
    red = [r["repo"] for r in results if r.get("test") != 0]
    print("\nGREEN %d : %s" % (len(green), ", ".join(green)))
    print("RED   %d : %s" % (len(red), ", ".join(red)))
    print("fail-closed fix present in all trees:",
          all(r.get("exit_fix_present") for r in results if r["repo"] in NINE))


if __name__ == "__main__":
    main()
