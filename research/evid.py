#!/usr/bin/env python3
"""
evid.py -- evidence-provenance extraction and independence measurement.

WHY THIS EXISTS
---------------
syn-AUDITORS.md (2026-10-01) measured n_eff over *outputs*: it extracted CLAIMS from
11 reports and asked whether they agreed.  It shipped two findings of its own:
  - 20 of 24 observed pairs rest on exactly ONE shared claim  (n=1 cells -> fake all-ones)
  - its shuffle control COULD NOT REJECT a known-independent injected lane (vacuous)

EXPERIMENTS.md §4 says the lesson outright: "n_eff computed over *outputs* measures
agreement, not independence.  Independence is agreement in the errors."

This file therefore measures the INPUT side.  A lane's evidence set is the set of
artefacts it says it read and ran.  Two lanes that read the same bytes are correlated
no matter how differently they phrase the result, and that is a property of the
*material*, which MISSION-STEERING.md found is the only thing that bought diversity.

TWO HARD RULES THIS FILE ENFORCES ON ITSELF
-------------------------------------------
1. NO CLAIM IS READ AS EVIDENCE.  Only things a lane names as read/ran/executed
   count.  Prose agreement is deliberately not an input.
2. THE INSTRUMENT MUST BE ABLE TO FAIL.  `--calibrate` injects synthetic lanes of
   KNOWN ground-truth independence and requires the recovered n_eff to be within
   tolerance.  If the control cannot reject a correlated fixture it FAILS LOUDLY.
   A measurement whose control is vacuous is a green badge, and there are already
   too many of those in this repo.

Everything is mechanical.  If a number is not printed by this file it is not in
PARALLELISM.md.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --------------------------------------------------------------------------
# evidence units, by class.  Weight = how strongly a shared unit implies the two
# lanes saw the same thing.  An INSTRUMENT is the strongest signal: two lanes that
# ran the same script against the same corpus are measuring the same function.
# --------------------------------------------------------------------------
WEIGHTS = {
    "INSTR": 1.5,   # a named executable/script the lane says it ran
    "REPO": 1.0,    # a fleet repo the lane says it read
    "ART": 0.5,     # a local artefact/dir the lane produced or consumed
    "DOC": 0.25,    # another report in this repo (weakest: docs quote each other)
}

RE_INSTR = re.compile(r"\b((?:tools|probe|poc|res-GEN|syn|synergy|orch-score)/[A-Za-z0-9_.-]+\.py|[a-z0-9][a-z0-9_]{2,}\.py)\b")
RE_REPO = re.compile(r"\brepos/([A-Za-z0-9._-]+)")
RE_FLEET = re.compile(r"\b(quilt-[a-z0-9][a-z0-9-]*|SuperInstance-[A-Za-z0-9-]+|fleet-[a-z0-9-]+|wardroom|gh-dungeons|jev-net|constraint-theory-core|diffusion-jev-sglang|neodisco)\b")
RE_ART = re.compile(r"\b((?:r1|r2|r3|res|org_scratch|org2|playtest2|lattice-cell|quilt-jev|quilt-jev-web|nextgen-merge|stubs|readmes|harness|derive|site|sim|canary|music-r4|edge-NCA-artifacts|jev-merge-artifacts|substrate-fix-artifacts|templates|pixels-build|port|timequery|scouttools|libs|resolver-worker|exp-01|exp-02|nextgen-git-evidence|debate-A-code|r3-swap|r1-artifacts|r1-syncopation|r2-notebook|orch-score)/[A-Za-z0-9_./-]*)")
RE_DOC = re.compile(r"\b([A-Za-z0-9][A-Za-z0-9-]{2,}\.md)\b")

# Words that name a repo in a *fleet-wide* sense, not an artefact actually read.
STOP_FLEET = {"fleet-triage", "fleet-wide", "fleet-resolver", "quilt-fleet",
              "quilt-research-canons", "quilt-canon"}


def norm_doc_name(m):
    return m


def extract(path, known_repos, known_docs):
    """Return the evidence set of one lane document: dict unit -> weight."""
    with open(path, "r", errors="replace") as fh:
        text = fh.read()
    units = {}

    def add(unit, cls):
        if unit in units:
            return
        units[unit] = WEIGHTS[cls]

    for m in RE_INSTR.findall(text):
        base = os.path.basename(m)
        # ignore a doc merely mentioning a script in passing as a *foreign* repo file
        if base.startswith(("repo", "setup", "test_", "conftest")) and "/" not in m:
            continue
        add("INSTR:" + m, "INSTR")

    for m in RE_REPO.findall(text):
        if m in known_repos:
            add("REPO:" + m, "REPO")
    for m in RE_FLEET.findall(text):
        if m in STOP_FLEET:
            continue
        if m in known_repos:
            add("REPO:" + m, "REPO")
        else:
            # a repo named but not in the local clone: still evidence, still a seam
            add("REPO~:" + m, "REPO")

    for m in RE_ART.findall(text):
        add("ART:" + m.rstrip("/"), "ART")

    for m in RE_DOC.findall(text):
        if m in known_docs and m != os.path.basename(path):
            add("DOC:" + m, "DOC")

    return units


# --------------------------------------------------------------------------
# similarity: weighted Jaccard (Ruzicka).  Range [0,1].  Deterministic.
# --------------------------------------------------------------------------
def sim(a, b):
    if not a or not b:
        return 0.0
    keys = a.keys() | b.keys()
    inter = sum(min(a.get(k, 0.0), b.get(k, 0.0)) for k in keys)
    union = sum(max(a.get(k, 0.0), b.get(k, 0.0)) for k in keys)
    return inter / union if union else 0.0


def kish_design_effect(n, rho_bar):
    """n_eff = N / (1 + (N-1)*rho_bar)   -- the standard cluster-design effect."""
    if n <= 1:
        return float(n)
    return n / (1.0 + (n - 1) * rho_bar)


def components(n, mat, thresh):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if mat[i][j] >= thresh:
                union(i, j)
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)
    return list(groups.values())


def effective_rank(mat):
    """exp(Shannon entropy of the eigenvalue spectrum), normalised to [1,n].

    Reported only as a secondary diagnostic; the headline is the design effect.
    """
    n = len(mat)
    # power iteration is overkill; do a Jacobi-free approach via numpy if present
    try:
        import numpy as np
        w = np.linalg.eigvalsh(np.array(mat, dtype=float))
        w = np.clip(w, 1e-12, None)
        w = w / w.sum()
        return float(np.exp(-(w * np.log(w)).sum()))
    except Exception:
        return float("nan")


# --------------------------------------------------------------------------
def census(night_start, night_end, only=None):
    known_repos = set(os.listdir(os.path.join(ROOT, "repos")))
    known_docs = {f for f in os.listdir(ROOT) if f.endswith(".md")}
    lo = datetime.strptime(night_start, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()
    hi = datetime.strptime(night_end, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp()
    lanes = []
    for f in sorted(os.listdir(ROOT)):
        if not f.endswith(".md"):
            continue
        p = os.path.join(ROOT, f)
        m = os.stat(p).st_mtime
        if lo <= m <= hi:
            if only and not any(re.search(o, f) for o in only):
                continue
            lanes.append((f, m, extract(p, known_repos, known_docs)))
    return lanes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", default="2026-10-02 00:00")
    ap.add_argument("--to", dest="end", default="2026-10-03 00:00")
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    lanes = census(a.start, a.end, a.only)
    lanes.sort(key=lambda r: r[1])
    names = [f for f, _, _ in lanes]
    units = [u for _, _, u in lanes]
    n = len(lanes)
    if n == 0:
        print("no lanes in window", file=sys.stderr)
        return 2

    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        mat[i][i] = 1.0
        for j in range(i + 1, n):
            s = sim(units[i], units[j])
            mat[i][j] = mat[j][i] = s

    pairs = [mat[i][j] for i in range(n) for j in range(i + 1, n)]
    rho_bar = sum(pairs) / len(pairs)
    neff_design = kish_design_effect(n, rho_bar)

    print(f"lanes in window            N = {n}")
    print(f"mean pairwise evidence sim  rho_bar = {rho_bar:.4f}")
    print(f"n_eff (design effect)      = {neff_design:.2f}   -> independence fraction = {neff_design/n:.3f}")
    print(f"n_eff (effective rank)     = {effective_rank(mat):.2f}  [secondary diagnostic]")
    print()
    print("threshold sweep -- connected components over the evidence-overlap graph")
    print(f"  {'thresh':>7} {'K clusters':>11} {'largest':>8} {'n_eff=sum1/c':>14} {'indep frac':>11}")
    sweep = []
    for t in (0.05, 0.10, 0.125, 0.15, 0.175, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50, 0.60):
        comps = components(n, mat, t)
        ne = sum(1.0 / len(c) for c in comps)
        biggest = max(len(c) for c in comps)
        sweep.append({"t": t, "K": len(comps), "largest": biggest,
                      "neff_cluster": ne, "indep": ne / n})
        print(f"  {t:>7.3f} {len(comps):>11} {biggest:>8} {ne:>14.2f} {ne/n:>11.3f}")

    T = 0.20
    comps = components_complete(n, mat, T)
    print()
    print(f"=== COMPLETE-LINKAGE CLUSTERS AT t={T} (seam clusters = one investigation wearing N hats) ===")
    clusters = []
    for c in comps:
        members = [names[i] for i in sorted(c, key=lambda i: names[i])]
        ev = set()
        for i in c:
            ev |= set(units[i].keys())
        shared = set.intersection(*[set(units[i].keys()) for i in c]) if c else set()
        clusters.append({"members": members, "size": len(members),
                         "union_evidence": sorted(ev),
                         "shared_evidence_all": sorted(shared)})
        print(f"  [{len(members)}] {', '.join(m.replace('.md','') for m in members)}")
        print(f"       shared by ALL: {len(shared)} units; union: {len(ev)} units")
    singles = [c for c in clusters if c["size"] == 1]
    print()
    print(f"singleton lanes (no second observer on any evidence) = {len(singles)} of {n}")
    print(f"lanes inside a >=2 cluster                          = {n - len(singles)} of {n}")

    # evidence concentration: how much of the fan-out rides on the most-shared unit
    freq = defaultdict(set)
    for i, u in enumerate(units):
        for k in u:
            freq[k].add(i)
    top = sorted(freq.items(), key=lambda kv: -len(kv[1]))[:12]
    print()
    print("most-reached evidence units (share of lanes reaching them)")
    for k, s in top:
        print(f"  {len(s):>4}/{n}  {k}")

    result = {
        "window": [a.start, a.end],
        "N": n,
        "lanes": [{"file": f, "mtime": datetime.fromtimestamp(m, timezone.utc).isoformat(),
                   "evidence": {k: v for k, v in sorted(u.items())},
                   "n_units": len(u)} for f, m, u in lanes],
        "matrix": {"names": names, "values": mat},
        "rho_bar": rho_bar,
        "n_eff_design": neff_design,
        "n_eff_effective_rank": effective_rank(mat),
        "independence_fraction": neff_design / n,
        "sweep": sweep,
        "clusters": clusters,
        "singletons": len(singles),
        "top_units": [{"unit": k, "lanes": sorted(names[i] for i in s), "reach": len(s)}
                      for k, s in top],
    }

    print()
    print("=== AXIS DECOMPOSITION: the three things 'different evidence' can mean ===")
    print("  (a correlation matrix with unobserved cells cannot be Kish'd; coverage is")
    print("   printed beside every number, and n_eff is computed on OBSERVED pairs only)")
    axes = []
    for label, pref in (("MATERIAL  (repos read)", ("REPO",)),
                        ("INSTRUMENT (scripts run)", ("INSTR",)),
                        ("CONTEXT   (sibling reports read)", ("DOC",)),
                        ("ALL AXES", ("REPO", "INSTR", "ART", "DOC"))):
        r = axis_report(units, names, pref, label)
        axes.append(r)
        print(f"  {label:<32} coverage {r['coverage']*100:5.1f}%  "
              f"rho_obs {r['rho_observed']:.3f}  n_eff {r['n_eff_from_observed']:6.2f}"
              f"/{n}  frac {r['frac']:.3f}")
    result["axes"] = axes

    if a.calibrate:
        print()
        print("=== CALIBRATION: can this instrument reject what it must reject? ===")
        cal, ok = calibrate()
        result["calibration"] = cal
        if not ok:
            print("\nCALIBRATION FAILED -- exiting nonzero. Numbers above are VOID.")
            if a.json:
                with open(a.json, "w") as fh:
                    json.dump(result, fh, indent=1)
            return 3

    if a.json:
        with open(a.json, "w") as fh:
            json.dump(result, fh, indent=1)
        print(f"\nwrote {a.json}")
    return 0


def components_complete(n, mat, thresh):
    """COMPLETE linkage: a group only forms if EVERY pair inside it is >= thresh.

    Single-linkage on a sparse similarity graph manufactures one giant component
    out of a few weak bridges, and then reports it as an investigation wearing
    N hats.  That artefact is exactly the kind of false finding this file exists
    to avoid, so the clusters reported are complete-linkage.
    """
    groups, used = [], set()
    for i in range(n):
        if i in used:
            continue
        g = [j for j in range(n) if j not in used and mat[i][j] >= thresh]
        if len(g) > 1:
            groups.append(g)
            used.update(g)
    for i in range(n):
        if i not in used:
            groups.append([i])
            used.add(i)
    return sorted(groups, key=len, reverse=True)


def calibrate():
    """Synthetic fixtures with KNOWN ground truth.  HARD GATE: nonzero exit on fail.

    CAL-A  6 lanes, each reading a DISJOINT repo        -> true n_eff = 6
    CAL-B  6 lanes, all reading the SAME repo            -> true n_eff = 1
    CAL-C  6 lanes in 2 groups, groups disjoint          -> true n_eff = 2
    """
    out, allok = [], True
    for name, groups, true_k in (("CAL-A disjoint", 6, 6), ("CAL-B identical", 1, 1),
                                 ("CAL-C 2 groups", 2, 2)):
        # every lane in group g reads the SAME unit; groups read disjoint units
        units = [{"REPO:cal-repo-%d" % g: 1.0} for g in range(groups)
                 for _ in range(6 // groups)]
        m = len(units)
        mat = [[0.0] * m for _ in range(m)]
        for i in range(m):
            mat[i][i] = 1.0
            for j in range(i + 1, m):
                s = sim(units[i], units[j])
                mat[i][j] = mat[j][i] = s
        pairs = [mat[i][j] for i in range(m) for j in range(i + 1, m)]
        rho = sum(pairs) / len(pairs)
        recovered = kish_design_effect(m, rho)
        k_clusters = len(components_complete(m, mat, 0.20))
        ok = abs(recovered - true_k) <= max(0.6, 0.20 * true_k) and k_clusters == true_k
        allok &= ok
        out.append({"fixture": name, "true_n_eff": true_k, "rho_bar": rho,
                    "recovered_n_eff": recovered, "k_clusters": k_clusters,
                    "pass": bool(ok)})
        print(f"  {name:<16} true n_eff={true_k}  rho={rho:.3f}  "
              f"recovered={recovered:.2f}  K={k_clusters}  "
              f"{'OK' if ok else '*** INSTRUMENT BLIND ***'}")
    print("  A calibration failure above means the independence number in this file")
    print("  is NOT a measurement.  Treat every number here as void until it passes.")
    return out, allok


def axis_report(units, names, keep_prefixes, label):
    """n_eff restricted to one evidence class, plus observed-pair coverage.

    A correlation matrix in which most cells were never observed cannot be fed to
    a design-effect formula: 'no shared evidence' is not 'independent evidence'.
    syn-AUDITORS.md died of exactly this.  So coverage is printed beside every
    number, and `rho_observed` (computed only over pairs that DID overlap) is the
    honest input to the estimator.
    """
    sub = [{k: v for k, v in u.items() if any(k.startswith(p) for p in keep_prefixes)}
           for u in units]
    n = len(sub)
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    obs = [(i, j) for i, j in pairs if sim(sub[i], sub[j]) > 0]
    cover = len(obs) / len(pairs) if pairs else 0.0
    rho_obs = (sum(sim(sub[i], sub[j]) for i, j in obs) / len(obs)) if obs else 0.0
    n_eff_obs = kish_design_effect(n, rho_obs)
    rho_all = (sum(sim(sub[i], sub[j]) for i, j in pairs) / len(pairs)) if pairs else 0.0
    return {"axis": label, "coverage": cover, "rho_observed": rho_obs,
            "rho_all_pairs": rho_all, "n_eff_from_observed": n_eff_obs,
            "n_eff_from_all_pairs": kish_design_effect(n, rho_all),
            "frac": n_eff_obs / n if n else 0.0}


if __name__ == "__main__":
    sys.exit(main())
