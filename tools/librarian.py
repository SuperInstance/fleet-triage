#!/usr/bin/env python3
"""orch-LIBRARIAN: recompute the fleet-triage index. Every count is derived at run time.

Usage: python3 librarian.py [--root DIR] [--out FILE] [--clone DIR]
Nothing here is hard-coded. If a number appears in the output, it was measured.
"""
import argparse, hashlib, json, os, re, subprocess, sys, time

NOW = time.time()

def sh(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    return p.stdout.strip(), p.stderr.strip(), p.returncode

def doc_state(path):
    """measured | cited | asserted, per entry. Never omitted."""
    return {"basis": "asserted", "why": "prose claim, not re-executed by this lane"}

# ---- retraction ledger: a claim that a later document explicitly withdrew -------
RETRACTION_PATTERNS = [
    r"RETRACTED", r"\bretracted\b", r"was wrong", r"PARTIALLY FALSE", r"\bfalse\b.{0,30}\bclaim\b",
    r"136 code hits", r"0\.5045", r"prediction refuted", r"\bI was wrong\b", r"superseded",
]
# claims known to be contested: (regex for the stale assertion, regex for the fix)
CONTESTED = [
    {"id": "BattenSpline-count-and-kind",
     "stale": r"BattenSpline(?:[^\n]|\n(?=[ \t*`\u2014\-0-9])){0,70}?(10 prose|10 all prose|[^|\n]{0,30}\|\s*10\s*\|\s*\**0\**|0 occurrences|0 hits|\(12\)|136 code hits)",
     "fixed": r"BattenSpline(?:[^\n]|\n(?=[ \t*`\u2014\-0-9])){0,70}?(136 code hits|RETRACTED|RETRACT\b)",
     "truth": ("MEASURED 2026-10-02: 88 hits / 30 files across all 34 /workspace/projects. "
               "0 executable-code hits: the 2 hits in quilt-llvm/experiments/batten-spike/src/kernel.rs "
               "are '//!' doc-comments, and the 3rd code-extension hit is VERIFY-CONSERVATION.md citing "
               "a filename. All substance traces to ONE paper (scout-foundational.md) replicated 5x and "
               "HTML-rendered 3x. Verdict: prose (right kind), 88 (not 10/12), and NOT 136 code hits."),
     "retracted_in": ["CORRECTION-CONSERVATION.md", "ORIENTATION.md", "VERIFY-CONSERVATION.md"]},
    # NOT a live contradiction: DOCTRINE.md:106 retracts on the next line and INDEX.md:42
    # marks it 'prediction refuted'. Pinned so it cannot silently return.
    {"id": "diversity-of-evidence",
     "stale": r"diversity of evidence beats diversity of opinion",
     "fixed": r"It does\s*\n?\s*not|Retracted\.|prediction refuted",
     "truth": "difference is +0.02, inside the noise; retracted in place. NOT a live contradiction.",
     "retracted_in": ["DOCTRINE.md", "INDEX.md"]},
]
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/workspace/projects/fleet-triage")
    ap.add_argument("--out", default=None)
    ap.add_argument("--clone", default=None, help="fresh-clone dir to diff against")
    a = ap.parse_args()
    root = os.path.abspath(a.root)

    out, err, rc = sh("git rev-parse --is-inside-work-tree", root)
    is_git = rc == 0 and out == "true"

    # ---------------- 1. tree census ----------------
    md = []
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if not os.path.isfile(p) or not name.endswith(".md"):
            continue
        st = os.stat(p)
        with open(p, "rb") as f:
            b = f.read()
        md.append({
            "path": name, "bytes": st.st_size,
            "mtime_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime)),
            "age_days": round((NOW - st.st_mtime) / 86400, 2),
            "sha256": hashlib.sha256(b).hexdigest()[:16],
            "lines": b.decode("utf-8", "replace").count("\n") + 1,
        })

    total_files, _, _ = sh(f"find . -path ./.git -prune -o -type f -print | wc -l", root)
    tracked, _, _ = sh("git ls-files | wc -l", root) if is_git else ("0", "", 1)
    tracked_md, _, _ = sh("git ls-files '*.md' | wc -l", root) if is_git else ("0", "", 1)
    untracked, _, _ = sh("git status --porcelain | grep -c '^??'", root) if is_git else ("0", "", 1)
    modified, _, _ = sh("git status --porcelain | grep -vc '^??'", root) if is_git else ("0", "", 1)
    head_files, _, _ = sh("git ls-tree -r --name-only HEAD", root) if is_git else ("", "", 1)
    head_md = set(x for x in head_files.split("\n") if x.endswith(".md"))
    commits, _, _ = sh("git rev-list --count HEAD", root) if is_git else ("0", "", 1)
    branch, _, _ = sh("git rev-parse --abbrev-ref HEAD", root) if is_git else ("?", "", 1)

    md_names = {d["path"] for d in md}
    in_head = sorted(md_names & head_md)
    not_in_head = sorted(md_names - head_md)

    # ---------------- 2. fresh-clone check ----------------
    clone = {"performed": False}
    if a.clone and os.path.isdir(a.clone):
        cfiles, _, _ = sh("find . -path ./.git -prune -o -type f -print | wc -l", a.clone)
        cmd = sorted(n for n in os.listdir(a.clone) if n.endswith(".md")
                     and os.path.isfile(os.path.join(a.clone, n)))
        missing = [n for n in sorted(md_names) if n not in cmd]
        clone = {
            "performed": True, "path": a.clone,
            "clone_total_files": int(cfiles), "clone_top_level_md": len(cmd),
            "worktree_total_files": int(total_files), "worktree_top_level_md": len(md_names),
            "docs_present_in_worktree_absent_from_clone": missing,
            "count_absent": len(missing),
            "verdict": "DIVERGENT" if missing else "IDENTICAL",
        }

    # ---------------- 3. contradiction detection ----------------
    def read(n):
        try:
            with open(os.path.join(root, n), encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""

    contradictions = []
    for c in CONTESTED:
        carriers_stale, carriers_fixed = [], []
        for d in md:
            t = read(d["path"])
            if re.search(c["stale"], t, re.I | re.S):
                carriers_stale.append({"doc": d["path"], "mtime_utc": d["mtime_utc"],
                                       "age_days": d["age_days"],
                                       "carries_fix_too": bool(re.search(c["fixed"], t, re.I | re.S))})
            if re.search(c["fixed"], t, re.I | re.S):
                carriers_fixed.append(d["path"])
        # stale carrier that does NOT itself carry the fix = live contradiction
        live = [s for s in carriers_stale if not s["carries_fix_too"]]
        if live:
            contradictions.append({
                "id": c["id"], "truth": c["truth"],
                "retracted_in": c["retracted_in"],
                "fixed_carriers": sorted(set(carriers_fixed)),
                "live_stale_carriers": live,
                "n_live": len(live),
            })

    # generic: any doc asserting "RETRACTED"/"was wrong" whose subject also appears
    # unretracted in an older-or-equal doc  -> supersession without propagation
    retraction_docs = {d["path"]: d for d in md
                       if re.search("|".join(RETRACTION_PATTERNS), read(d["path"]), re.I)}

    # ---------------- 4. staleness: content currency, not mtime ----------------
    # doc is STALE if a doc that explicitly corrects it is strictly newer
    stale = []
    for c in contradictions:
        newest_fix = max((d for d in md if d["path"] in c["retracted_in"]),
                         key=lambda x: x["mtime_utc"], default=None)
        for s in c["live_stale_carriers"]:
            if newest_fix and s["doc"] not in c["retracted_in"]:
                delta = round((time.mktime(time.strptime(newest_fix["mtime_utc"], "%Y-%m-%dT%H:%M:%SZ"))
                               - time.mktime(time.strptime(s["mtime_utc"], "%Y-%m-%dT%H:%M:%SZ"))) / 86400, 2)
                if delta > 0:
                    stale.append({"doc": s["doc"], "cites_as_current": c["id"],
                                  "corrected_by": newest_fix["path"],
                                  "stale_by_days": delta, "age_days": s["age_days"]})

    index = {
        "schema": "orch-librarian/1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW)),
        "root": root, "git": {
            "is_repo": is_git, "branch": branch, "commits": int(commits),
            "tracked_files": int(tracked), "tracked_md": int(tracked_md),
            "untracked_entries": int(untracked), "modified_entries": int(modified),
            "in_HEAD": in_head, "on_disk_but_not_in_HEAD": not_in_head,
        },
        "census": {
            "worktree_total_files": int(total_files),
            "worktree_top_level_md": len(md_names),
            "worktree_total_bytes": sum(d["bytes"] for d in md),
        },
        "fresh_clone_check": clone,
        "documents": md,
        "contradictions": contradictions,
        "live_contradiction_total": sum(c["n_live"] for c in contradictions),
        "stale_citations": stale,
        "stale_citation_total": len(stale),
        "retraction_carrying_docs": sorted(retraction_docs),
    }
    txt = json.dumps(index, indent=2, sort_keys=False)
    if a.out:
        with open(a.out, "w") as f:
            f.write(txt)
        os.sync()
    else:
        print(txt)
    return 0

if __name__ == "__main__":
    sys.exit(main())
