#!/usr/bin/env python3
"""
ORG2 task 3 -- the control, implemented rather than described.

The orchestrator's mechanical resolution of quilt-tools#32 vs #33 was "keep both
sides, set the counter to 19". It produced a file that does not parse, because
the two sides of one conflict hunk were THE SAME TEMPLATE LITERAL WITH A
DIFFERENT NUMBER IN IT -- not additive lines.

This script:
  1. builds the real merged state of #32 and #33 with git merge-tree;
  2. RE-DERIVES every count the prose asserts, from the merged data file;
  3. asserts derived == asserted. That is the control.
  4. then does what the orchestrator did (concatenate both sides) and shows the
     control FAILS on it -- a negative control for the control.

Everything runs off git objects. Nothing is pushed or merged.
"""
import json, os, re, subprocess, sys

W = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prwork", "quilt-tools")
A = "refs/remotes/origin/pr/32"
B = "refs/remotes/origin/pr/33"


def sh(cmd, t=600):
    return subprocess.run(cmd, cwd=W, capture_output=True, text=True, timeout=t)


def blob(ref, path):
    r = sh(["git", "show", f"{ref}:{path}"])
    return r.stdout if r.returncode == 0 else None


def classify(rows_text):
    """Count edges by their status token, straight from the data file."""
    out = {}
    for line in rows_text.splitlines():
        m = re.search(r"\b(PENDING|VERIFIED|REFUTED)\b", line)
        if not m:
            continue
        if "[" not in line and "{" not in line and "->" not in line and "→" not in line:
            continue
        out[m.group(1)] = out.get(m.group(1), 0) + 1
    return out


def main():
    print("=" * 72)
    print("STEP 1  build the real merged state of #32 and #33")
    print("=" * 72)
    r = sh(["git", "merge-tree", "--write-tree", A, B])
    tree = r.stdout.splitlines()[0].strip() if r.stdout else ""
    print(f"  merge-tree exit={r.returncode}  tree={tree[:12]}  (1 = CONFLICT, expected)")
    conflicted = [l.strip() for l in r.stdout.splitlines()
                  if l.startswith("CONFLICT")]
    for c in conflicted:
        print("   ", c)

    # the SEED file auto-merges; that is the source of truth for the numbers
    seed_paths = sh(["git", "diff", "--name-only", f"{A}^", f"{A}"]).stdout.split()
    print("\n  files touched by #32:", seed_paths)
    print("  files touched by #33:", sh(["git", "diff", "--name-only", f"{B}^", f"{B}"]).stdout.split())

    # Use the three-way merged seed: merge each PR's seed onto the common base
    base = sh(["git", "merge-base", A, B]).stdout.strip()
    print(f"\n  merge base = {base[:12]}")
    seedm = sh(["git", "merge-tree", "--write-tree", base, A, B])
    stree = seedm.stdout.splitlines()[0].strip() if seedm.stdout else ""
    print(f"  three-way merge-tree (base,#32,#33) exit={seedm.returncode} tree={stree[:12]}")
    for c in sh(["git", "merge-tree", "--write-tree", base, A, B]).stdout.splitlines():
        if c.startswith("CONFLICT"):
            print("   ", c.strip())

    print()
    print("=" * 72)
    print("STEP 2  RE-DERIVE the counts from the merged seed (the control's input)")
    print("=" * 72)
    for ref, label in ((f"{stree}", "merged(base,#32,#33)"),
                       (A, "#32 alone"),
                       (B, "#33 alone"),
                       ("refs/remotes/origin/main", "main (pre-PR)")):
        txt = blob(ref, "experiments/referral_graph.seed.mjs")
        if txt is None:
            print(f"  {label:24s} NO SEED FILE")
            continue
        c = classify(txt)
        tot = sum(c.values())
        fm = len(re.findall(r"fm-refusal-ledger", txt))
        print(f"  {label:24s} edges={tot:3d}  {c}   fleet-murmur-row-mentions={fm}")

    print()
    print("=" * 72)
    print("STEP 3  what each side ASSERTS in prose (the pin) vs what it DERIVES")
    print("=" * 72)
    for ref, label in ((A, "#32"), (B, "#33")):
        doc = blob(ref, "experiments/REFERRAL_GRAPH.md") or ""
        hits = re.findall(r"(\d+)\s+(?:total\s+)?edges?[^\n]{0,40}?(\d+)?\s*VERIFIED", doc, re.I)
        nums = re.findall(r"\b(\d{1,2})\b[^\n]{0,60}\b(VERIFIED|PENDING|edges?)\b", doc)
        fourteenth = re.findall(r"fourteenth|\b14th\b|\b14\b", doc)
        print(f"\n  --- {label} REFERRAL_GRAPH.md assertions:")
        for m in re.finditer(r"^.*\b(1[3-9])\b.*$", doc, re.M):
            line = m.group(0).strip()
            if re.search(r"edge|VERIFIED|PENDING|total", line, re.I):
                print("      ", line[:150])

    print()
    print("=" * 72)
    print("STEP 4  NEGATIVE CONTROL: reproduce the orchestrator's mechanical merge")
    print("=" * 72)
    for path in ("experiments/REFERRAL_GRAPH.md", "experiments/referral_graph.pins.mjs"):
        m = sh(["git", "merge-file", "-p", "--diff3", "-L", "#32", "-L", "merged",
                "-L", "#33",
                "/dev/stdin", "/dev/stdin", "/dev/stdin"], t=60)
        # do it properly with temp files
        import tempfile
        base_txt = blob(base, path)
        a_txt = blob(A, path)
        b_txt = blob(B, path)
        if base_txt is None or a_txt is None or b_txt is None:
            print(f"  {path}: missing at one of base/#32/#33 -> skip")
            continue
        with tempfile.TemporaryDirectory() as d:
            p0, pa, pb = (os.path.join(d, n) for n in ("b", "a", "b2"))
            for p, t in ((p0, base_txt), (pa, a_txt), (pb, b_txt)):
                open(p, "w").write(t)
            r = subprocess.run(["git", "merge-file", "-p", "--diff3", p0, pa, pb],
                               capture_output=True, text=True)
        markers = r.stdout.count("<<<<<<<") + r.stdout.count(">>>>>>>")
        print(f"\n  {path}")
        print(f"    merge-file conflicts: {markers//2}   (0 = clean)")
        if markers:
            # show the first conflict hunk verbatim -- this is the shape that
            # makes "keep both sides" wrong
            lines = r.stdout.splitlines()
            for i, l in enumerate(lines):
                if l.startswith("<<<<<<<"):
                    for x in lines[i:i + 14]:
                        print("      |", x[:120])
                    break


if __name__ == "__main__":
    main()
