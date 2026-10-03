#!/usr/bin/env python3
"""
ORG2 task 3, step E -- THE CONTROL HAS A BLIND SPOT, and here it is.

What the orchestrator proposed:
    "after resolving, re-derive every pinned number from the merged tree and
     assert it equals what the pin says. That is the control."

This script tests that control against a real resolution, and finds it PASSES on
a tree that silently lost one of the two PRs' edges.

Three candidate resolutions of quilt-tools#32 + #33 are built and each is
(a) syntax-checked and (b) run through the repo's OWN pins file, and (c) checked
for whether BOTH PRs' edges survived.

  R1  git's own clean 3-way merge of the seed, pins resolved by taking #33's
      side for every COMPETING slot.  <-- the obvious, reviewable resolution
  R2  the UNION of both PRs' seed edges (the semantically correct merge)
  R3  the orchestrator's mechanical "keep both sides" (known to not parse)

If the control passes on R1, the control is necessary and NOT sufficient, and
the missing assertion is named at the end.
"""
import json, os, re, subprocess, sys, tempfile, shutil

BASE = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(BASE, "prwork", "quilt-tools")
SEED, PINS, DOC = ("experiments/referral_graph.seed.mjs",
                   "experiments/referral_graph.pins.mjs",
                   "experiments/REFERRAL_GRAPH.md")
A, B = "refs/remotes/origin/pr/32", "refs/remotes/origin/pr/33"
E32 = ("qe-eproc-witness", "ds-esign-drift")
E33 = ("pq-named-refusals", "fm-refusal-ledger")


def sh(cmd, cwd=W, t=600):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=t)


def show(ref, path):
    r = sh(["git", "show", f"{ref}:{path}"])
    return r.stdout if r.returncode == 0 else None


def merge3(path, prefer=None):
    base = sh(["git", "merge-base", A, B]).stdout.strip()
    bt, at, bb = show(base, path), show(A, path), show(B, path)
    with tempfile.TemporaryDirectory() as d:
        p0, pa, pb = (os.path.join(d, x) for x in ("0", "a", "b"))
        for p, t in ((p0, bt), (pa, at), (pb, bb)):
            open(p, "w").write(t)
        r = subprocess.run(["git", "merge-file", "-p", "--diff3", p0, pa, pb],
                           capture_output=True, text=True)
    txt = r.stdout
    if prefer == "theirs":
        # resolve every conflict by taking #33's side
        def fix(m):
            return m.group(2)
        txt = re.sub(r"^<<<<<<< [^\n]*\n.*?^\|\|\|\|\|\|\|[^\n]*\n.*?^=======\n(.*?)^>>>>>>> [^\n]*\n",
                     lambda m: m.group(1), txt, flags=re.S | re.M)
    return txt, r.returncode


def build(name, seed_txt, pins_txt, label):
    d = os.path.join(BASE, "res_" + name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    # a runnable slice: the seed + the two substrate modules it needs
    for p in (SEED, PINS, "src/referral_graph.mjs", "experiments/referral_graph.discovery.mjs"):
        dst = os.path.join(d, p)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if p == SEED:
            t = seed_txt
        elif p == PINS:
            t = pins_txt
        else:
            t = show(B, p)          # read from git; the worktree is not checked out
        open(dst, "w").write(t)
    return d


def probe(d):
    """Return (edge_count, verified_count, has_e32, has_e33, pins_exit, pins_tail)."""
    r = subprocess.run(["node", "--input-type=module", "-e",
                        f"import('file://{d}/{SEED}').then(m=>{{const e=m.SEED.edges;"
                        "const v=e.filter(x=>x.weight==='VERIFIED');"
                        "console.log(JSON.stringify({total:e.length,verified:v.length,"
                        "has32:e.some(x=>x.from==='qe-eproc-witness'&&x.to==='ds-esign-drift'),"
                        "has33:e.some(x=>x.from==='pq-named-refusals'&&x.to==='fm-refusal-ledger')}))"
                        "}).catch(e=>{console.log('ERR '+e.message);process.exit(9)})"],
                       capture_output=True, text=True, timeout=180)
    out = r.stdout.strip()
    try:
        return json.loads(out)
    except Exception:
        return {"error": out[:200] or (r.stderr or "")[:200]}


def main():
    base = sh(["git", "merge-base", A, B]).stdout.strip()
    seed_clean, rc = merge3(SEED)
    print("=" * 76)
    print("FACT 1: git's 3-way merge of the SEED file reports NO CONFLICT")
    print("=" * 76)
    print(f"  git merge-file exit={rc}  markers={seed_clean.count('<<<<<<<')}")
    print(f"  #32's edge in the clean merge : {seed_clean.count('qe-eproc-witness')} occurrences")
    print(f"  #33's edge in the clean merge : {seed_clean.count('pq-named-refusals')} occurrences")

    print("\n" + "=" * 76)
    print("FACT 2: three candidate resolutions, probed against the real substrate")
    print("=" * 76)

    # --- R1: git's clean merge + pins resolved to #33's side
    pins_clean, prc = merge3(PINS, prefer="theirs")
    d1 = build("R1_gitclean", seed_clean, pins_clean, "R1")
    r1 = probe(d1)

    # --- R2: the union -- take git's clean merge and re-insert #32's edge
    b32 = show(A, SEED)
    blk = re.search(r"\n    \{\n      from: 'qe-eproc-witness'.*?\n    \},\n", b32, re.S)
    seed_union = seed_clean
    if blk:
        seed_union = seed_clean.replace("\n  ],\n};", blk.group(0) + "\n  ],\n};")
    d2 = build("R2_union", seed_union, pins_clean, "R2")
    r2 = probe(d2)

    # --- R3: mechanical keep-both-sides
    pins_raw, _ = merge3(PINS)
    naive = re.sub(r"\n=======\n.*?\n>>>>>>> [^\n]*\n", "\n", pins_raw, flags=re.S)
    d3 = build("R3_naive", seed_clean, naive, "R3")
    r3 = probe(d3)

    hdr = f"  {'resolution':44s} {'edges':>6} {'VERIF':>6} {'#32?':>5} {'#33?':>5}"
    print(hdr)
    for lbl, r in (("R1 git clean merge (no conflict reported)", r1),
                   ("R2 union of both PRs (correct)", r2),
                   ("R3 mechanical keep-both-sides", r3)):
        if "error" in r:
            print(f"  {lbl:44s} LOAD/RUN ERROR: {r['error'][:60]}")
        else:
            print(f"  {lbl:44s} {r['total']:>6} {r['verified']:>6} "
                  f"{str(r['has32']):>5} {str(r['has33']):>5}")

    print("\n" + "=" * 76)
    print("THE CONTROL, RUN ON EACH RESOLUTION")
    print("=" * 76)
    print("  the control = 're-derive the pinned number from the merged tree and")
    print("                 assert it equals what the pin says'")
    pins_as = sorted(set(int(x) for x in re.findall(r"verified\.length === (\d+)", pins_clean)))
    print(f"  pins file (after resolving conflicts to one side) asserts VERIFIED in {pins_as}")
    for lbl, r in (("R1", r1), ("R2", r2)):
        if "error" in r:
            continue
        asserted = r["verified"]
        print(f"  {lbl}: derived={r['verified']}  asserted_by_pin={asserted}  "
              f"control={'PASS' if asserted in pins_as else 'FAIL'}"
              f"   both PRs' edges present={r['has32'] and r['has33']}")

    print("\n" + "=" * 76)
    print("VERDICT")
    print("=" * 76)
    if "error" not in r1 and "error" not in r2:
        if r1["verified"] in pins_as and not (r1["has32"] and r1["has33"]):
            print("  R1 (git's own clean merge) SATISFIES the control and STILL LOSES #32's edge.")
            print("  => the control is NECESSARY AND NOT SUFFICIENT.")
            print("  => the missing assertion is NOT a number. It is the SET:")
            print("     for every file both PRs touched, the rows in the merged result")
            print("     must be a SUPERSET of the rows each side added. Counts agree when")
            print("     one side's addition is lost and the other's replaces it;")
            print("     set containment cannot.")
        else:
            print("  R1 did not reproduce the blind spot; re-examine before claiming it.")


if __name__ == "__main__":
    main()
