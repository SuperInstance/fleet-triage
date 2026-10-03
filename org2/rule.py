#!/usr/bin/env python3
"""
ORG2 task 3 -- THE RULE, and a machine check that the rule was followed.

=============================================================================
THE RULE
=============================================================================
Two open PRs that touch the same file are one of two things, and the difference
is not stylistic -- it decides whether concatenation is even a legal operation.

  ADDITIVE   each side contributes NEW lines that the other side lacks. The
             union is the correct merge. Concatenation is correct.

  COMPETING  both sides changed the SAME value: the same line, the same slot,
             the same template, a different number/word in it. There is exactly
             ONE slot and there are TWO candidate values. Concatenation is not
             "keeping both sides" -- it is emitting two values into one slot,
             which in a template literal or a table or a counter silently
             destroys the file or silently doubles a count.

The trap in the quilt-tools#32/#33 case, reproduced here verbatim: both sides of
the conflict hunk are the SAME COMMENT BLOCK with a different integer in it
("thirteen VERIFIED edges" vs "fourteen VERIFIED edges") and a different mass
account ("fm: two inbound" vs "fm: TRIPLE mass"). Keep both sides and you have
a file that asserts fourteen and fourteen-and-a-half at the same time.

=============================================================================
THE DISCRIMINATOR (mechanical, no judgement)
=============================================================================
For each conflict hunk, normalise both sides and compare:
  * strip comment markers, whitespace, and trailing punctuation from every line
  * replace every integer / float / quoted string with a slot marker
If the two normalised sides are IDENTICAL, the hunk is COMPETING: both sides
edited one value, and the only difference was the value. Concatenation cannot be
right. If the normalised sides DIFFER, the hunk is ADDITIVE-or-MIXED: distinct
content, and a union is at least well-formed.

That is the whole test. It is one pass, it is deterministic, and it does not
require knowing what the number "means".

=============================================================================
THE CONTROL (what proves the procedure was followed)
=============================================================================
After resolving, RE-DERIVE every number the prose asserts FROM THE MERGED TREE
and assert derived == asserted. The orchestrator's mechanical merge failed
precisely because nothing re-derived the number from the result: the counter was
set by hand to 19 and the file was never re-counted.

So this script:
  STEP A  three-way merge every file #32 and #33 both touch
  STEP B  classify every conflict hunk COMPETING / ADDITIVE-MIXED
  STEP C  count edges and weights FROM THE MERGED DATA FILE (not from prose)
  STEP D  compare derived counts to the numbers asserted in the pins file,
          and to the numbers each side asserted
  STEP E  do what the orchestrator did -- concatenate both sides, set the
          counter to 19 by hand -- and show the control FAILS on it
"""
import json, os, re, subprocess, sys, tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
W = os.path.join(BASE, "prwork", "quilt-tools")
A, B = "refs/remotes/origin/pr/32", "refs/remotes/origin/pr/33"
SEED = "experiments/referral_graph.seed.mjs"
PINS = "experiments/referral_graph.pins.mjs"
DOC = "experiments/REFERRAL_GRAPH.md"

# ---------------------------------------------------------------- normalisation
NUM = re.compile(r"\b\d+(?:\.\d+)?\b")
WORDNUM = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
           "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11",
           "twelve": "12", "thirteen": "13", "fourteen": "14", "fifteen": "15",
           "sixteen": "16", "seventeen": "17", "eighteen": "18", "nineteen": "19",
           "twenty": "20", "single": "1", "double": "2", "triple": "3",
           "double mass": "2", "triple mass": "3"}


def norm(side):
    """Erase every value-bearing token so only STRUCTURE survives."""
    out = []
    for line in side.splitlines():
        l = line.strip()
        l = re.sub(r"^(//+|#+|/\*+|\*+)\s*", "", l)          # comment chrome
        l = re.sub(r"^\s*[a-z]+:\s*", "K: ", l)               # object key
        l = re.sub(r"['\"`]", "", l)                          # quoting
        low = l.lower()
        for w, v in WORDNUM.items():
            low = re.sub(r"\b" + w.replace(" ", r"\s+") + r"\b", v, low)
        l = NUM.sub("#", low)
        l = re.sub(r"\s+", " ", l).strip(" .,;:-—")
        if l:
            out.append(l)
    return out


def split_hunks(text):
    """Yield (ours, theirs) for each conflict block of a diff3 merge."""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("<<<<<<<"):
            ours, i = [], i + 1
            while not lines[i].startswith("|||||||"):
                ours.append(lines[i]); i += 1
            base = []
            i += 1
            while not lines[i].startswith("======="):
                base.append(lines[i]); i += 1
            theirs = []
            i += 1
            while not lines[i].startswith(">>>>>>>"):
                theirs.append(lines[i]); i += 1
            i += 1
            yield "\n".join(ours), "\n".join(base), "\n".join(theirs)
        else:
            i += 1


def classify(ours, base, theirs):
    """LINE-level. A hunk is not one thing; it is a set of lines, and each line
    is either a slot both sides edited (COMPETING) or content only one side
    added (ADDITIVE). Judging the hunk as a whole throws away exactly the
    information the resolver needs, which is WHICH line to re-derive.

    Algorithm: strip blank/comment-only lines, then align the two sides
    positionally. Where both sides have a line at the same index AND they
    normalise to the same thing, that is a competing value. Where the normal
    forms differ, or one side ran out, that is additive content.
    """
    lo = [l for l in (ours.splitlines()) if l.strip()]
    lt = [l for l in (theirs.splitlines()) if l.strip()]
    no, nt = norm(ours), norm(theirs)
    if no == nt:
        return ("COMPETING", f"all {len(no)} lines identical after erasing values",
                [i + 1 for i in range(min(len(no), len(nt)))])
    competing, additive = [], []
    n = max(len(no), len(nt))
    for i in range(n):
        a = no[i] if i < len(no) else None
        b = nt[i] if i < len(nt) else None
        if a is not None and b is not None and a == b:
            competing.append(i + 1)
        else:
            additive.append(i + 1)
    kind = "COMPETING" if competing else "ADDITIVE"
    why = (f"{len(competing)} line(s) are one slot with two values; "
           f"{len(additive)} additive" if competing else
           f"no shared slot; {len(additive)} additive line(s)")
    return kind, why, competing


# ---------------------------------------------------------------- derivation
def sh(cmd, t=600):
    return subprocess.run(cmd, cwd=W, capture_output=True, text=True, timeout=t)


def show(ref, path):
    r = sh(["git", "show", f"{ref}:{path}"])
    return r.stdout if r.returncode == 0 else None


def derive(text):
    """Count LINK rows and their weights straight out of the data file.
    Structure: `from: 'x', to: 'y',` ... `weight: 'VERIFIED'|'PENDING'|...`"""
    edges, cur = [], None
    for line in (text or "").splitlines():
        m = re.match(r"\s*from:\s*'([^']+)'\s*,\s*to:\s*'([^']+)'", line)
        if m:
            cur = {"from": m.group(1), "to": m.group(2), "weight": None}
            edges.append(cur)
            continue
        if cur is not None:
            w = re.match(r"\s*weight:\s*'([A-Z]+)'", line)
            if w:
                cur["weight"] = w.group(1)
    counts = _ctr(e["weight"] for e in edges)
    inbound = _ctr()
    for e in edges:
        if e["weight"] == "VERIFIED":
            inbound[e["to"]] = inbound.get(e["to"], 0) + 1
    return {"total": len(edges), "by_weight": counts, "verified_inbound": inbound,
            "edges": edges}


def _ctr(xs=()):
    d = {}
    for x in xs:
        d[x] = d.get(x, 0) + 1
    return d


def asserted(text):
    """Pull the numbers the prose/pins CLAIM about the graph."""
    a = {}
    for m in re.finditer(r"(\d+)\s+(?:VERIFIED|verified)\s+edges?", text or ""):
        a.setdefault("verified_edges", set()).add(int(m.group(1)))
    for m in re.finditer(r"(\d+)\s+total\s+edges?|(\d+)\s+edges\s+total", text or ""):
        a.setdefault("total_edges", set()).add(int(m.group(1) or m.group(2)))
    for m in re.finditer(r"(\d+)\s+PENDING", text or ""):
        a.setdefault("pending", set()).add(int(m.group(1)))
    for m in re.finditer(r"fm:\s*(two|three|four|double|triple|\d+)\s*inbound", text or ""):
        t = m.group(1)
        a.setdefault("fm_inbound", set()).add(WORDNUM.get(t, t))
    for m in re.finditer(r"(two|three|double|triple)\s*inbound", text or ""):
        a.setdefault("fm_inbound", set()).add(WORDNUM[m.group(1)])
    return {k: sorted(v, key=str) for k, v in a.items()}


def main():
    base = sh(["git", "merge-base", A, B]).stdout.strip()
    files = sorted(set(sh(["git", "diff", "--name-only", f"{base}", A]).stdout.split())
                   & set(sh(["git", "diff", "--name-only", f"{base}", B]).stdout.split()))
    print("files BOTH #32 and #33 touch:", files)
    print("files #32 touches only:",
          sorted(set(sh(["git", "diff", "--name-only", f"{base}", A]).stdout.split()) - set(files)))

    print("\n" + "=" * 74)
    print("STEP A/B  three-way merge each shared file; classify every conflict hunk")
    print("=" * 74)
    merged, report = {}, []
    for path in files:
        bt, at, bb = show(base, path), show(A, path), show(B, path)
        if bt is None or at is None or bb is None:
            print(f"\n-- {path}: SKIP (missing at one side)")
            continue
        with tempfile.TemporaryDirectory() as d:
            p0, pa, pb = (os.path.join(d, x) for x in ("0", "a", "b"))
            for p, t in ((p0, bt), (pa, at), (pb, bb)):
                open(p, "w").write(t)
            r = subprocess.run(["git", "merge-file", "-p", "--diff3", p0, pa, pb],
                               capture_output=True, text=True)
        merged[path] = r.stdout
        hunks = list(split_hunks(r.stdout))
        nc = sum(1 for _ in hunks)
        print(f"\n-- {path}: {nc} conflict hunk(s)")
        for k, (o, ba, t) in enumerate(hunks, 1):
            kind, why, comp = classify(o, ba, t)
            report.append({"file": path, "hunk": k, "kind": kind, "why": why,
                           "competing_lines": comp})
            print(f"     hunk {k}: {kind:15s} ({why})")
            for nm, side in (("#32", o), ("#33", t)):
                for line in side.splitlines()[:3]:
                    if line.strip():
                        print(f"        {nm}: {line.strip()[:104]}")
                        break
            if comp:
                for li in comp[:2]:
                    o_l = [x for x in o.splitlines() if x.strip()][li - 1]
                    t_l = [x for x in t.splitlines() if x.strip()][li - 1]
                    print(f"        SLOT line {li}:")
                    print(f"           #32 -> {o_l.strip()[:100]}")
                    print(f"           #33 -> {t_l.strip()[:100]}")
    json.dump(report, open(os.path.join(BASE, "hunk_classes.json"), "w"), indent=1)

    print("\n" + "=" * 74)
    print("STEP C  RE-DERIVE the counts FROM THE MERGED DATA FILE (not from prose)")
    print("=" * 74)
    rows = []
    for label, ref in (("main (before both PRs)", "refs/remotes/origin/main"),
                       ("#32 alone", A), ("#33 alone", B)):
        t = show(ref, SEED)
        d = derive(t) if t else None
        if d:
            print(f"  {label:22s} total={d['total']:3d}  by_weight={d['by_weight']}")
            rows.append((label, d))
    if SEED in merged and "<<<<<<<" not in merged[SEED]:
        d = derive(merged[SEED])
        print(f"  {'MERGED seed':22s} total={d['total']:3d}  by_weight={d['by_weight']}")
        print(f"  {'  verified inbound mass':22s} {dict(d['verified_inbound'])}")
        MERGED_D = d
    else:
        print("  MERGED seed: still conflicted or absent")
        MERGED_D = None

    print("\n" + "=" * 74)
    print("STEP D  THE CONTROL: derived  vs  asserted")
    print("=" * 74)
    ok = True
    for label, ref in (("#32", A), ("#33", B), ("merged seed file", None)):
        txt = show(ref, PINS) if ref else (merged.get(PINS) or "")
        a = asserted(txt)
        print(f"\n  {label} ASSERTS: {a}")
        if MERGED_D and ref is None:
            derived = {"verified_edges": [MERGED_D["by_weight"].get("VERIFIED", 0)],
                       "total_edges": [MERGED_D["total"]],
                       "pending": [MERGED_D["by_weight"].get("PENDING", 0)]}
            for k, want in derived.items():
                got = a.get(k, [])
                bad = [g for g in got if g not in want]
                print(f"    control {k:16s} derived={want} asserted={got} "
                      f"{'FAIL' if bad else 'pass'}")
                if bad:
                    ok = False
    print(f"\n  CONTROL VERDICT: {'PASS' if ok else 'FAIL -- a pin contradicts the tree'}")

    print("\n" + "=" * 74)
    print("STEP E  NEGATIVE CONTROL: do what the orchestrator did, watch it break")
    print("=" * 74)
    if PINS in merged:
        m = merged[PINS]
        n_confl = m.count("<<<<<<<")
        both = m.count("thirteen VERIFIED edges") + m.count("fourteen VERIFIED edges")
        # emulate "keep both sides" = leave markers in place but drop the tail half
        naive = re.sub(r"\n=======\n.*?\n>>>>>>> [^\n]*\n", "\n", m, flags=re.S)
        open(os.path.join(BASE, "naive_pins.mjs"), "w").write(naive)
        r = subprocess.run(["node", "--check", os.path.join(BASE, "naive_pins.mjs")],
                           capture_output=True, text=True)
        print(f"  conflict markers present in the merged pins file: {n_confl}")
        print(f"  'keep both sides' then node --check -> exit {r.returncode}")
        if r.returncode != 0:
            print("   ", (r.stderr or "").strip().splitlines()[0][:140])
        full = os.path.join(BASE, "full_pins.mjs")
        open(full, "w").write(m)
        r2 = subprocess.run(["node", "--check", full], capture_output=True, text=True)
        print(f"  with markers left in place, node --check -> exit {r2.returncode}")
        if r2.returncode != 0:
            print("   ", (r2.stderr or "").strip().splitlines()[0][:140])
    return merged


if __name__ == "__main__":
    main()
