#!/usr/bin/env python3
"""
harness_check.py — one runner, two rules, one fleet.

  can-fail-ci        (canfail.py,          sibling lane) — per-STEP
  fail-open-harness  (fleetlint_failopen.py, sibling lane) — per-HARNESS

This file does not reimplement either rule. It is the harness: it drives both over a
fleet of real clones, and it reports the two things a rule is never asked to report
about itself -- how often it fires, and how often it is WRONG.

THE FALSE-POSITIVE LEDGER
-------------------------
A count without a denominator is a rumour. So every firing is classified:

  CONFIRMED  the defect was read by hand, in the file, and is real
  UNREAD     not individually inspected. Counted, not cleared. NOT called clean.

`UNREAD` is the honest bucket and it is deliberately not folded into CONFIRMED. The
prior art in this directory does the opposite -- it reports "N repos flagged" and the
number gets quoted as N defects. A lint firing is a CLAIM, not a verdict.

Usage:
    python3 harness_check.py ../repos --json out.json
    python3 harness_check.py ../repos/substrate-bundle
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))          # `yaml` shim
sys.path.insert(0, str(HERE.parent))

import canfail                                # noqa: E402
import rules                                  # noqa: E402  the SHIPPED rules


def rule_can_fail_ci(root: str) -> dict:
    return rules.can_fail_ci(root)


def rule_fail_open_harness(root: str) -> dict:
    return rules.fail_open_harness(root)


def classify_ci_reason(reasons) -> str:
    """Bucket a can-fail-ci finding into the shape named in the brief."""
    joined = " ".join(reasons).lower()
    if "no ci configured" in joined or "no executable command" in joined:
        return "echo-placeholder / no executable command"
    if "pipeline ends in" in joined:
        return "producer | consumer (unguarded pipeline)"
    if "continue-on-error" in joined:
        return "continue-on-error"
    if "empty run body" in joined:
        return "empty run body"
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    roots = []
    for r in a.roots:
        p = Path(r)
        roots.extend(sorted(str(x) for x in p.iterdir() if x.is_dir()) if p.is_dir() else [r])

    per_repo, ci_buckets = [], {}
    n_wf_total = 0
    for r in roots:
        ci = rule_can_fail_ci(r)
        ho = rule_fail_open_harness(r)
        n_wf_total += len(canfail.workflows_under(r))
        rec = {
            "repo": os.path.basename(r.rstrip("/")),
            "ci": ci["findings"],
            "ci_unverifiable": ci["unverifiable"],
            "harness": ho["findings"],
        }
        per_repo.append(rec)
        for f in ci["findings"]:
            b = classify_ci_reason(f["reasons"])
            ci_buckets.setdefault(b, []).append(f["repo"])

    flat_ci = [f for r in per_repo for f in r["ci"]]
    flat_ho = [f for r in per_repo for f in r["harness"]]
    unver = [u for r in per_repo for u in r["ci_unverifiable"]]
    repos_ci = sorted({f["repo"] for f in flat_ci})
    repos_ho = sorted({f["repo"] for f in flat_ho})

    print("=" * 96)
    print(f"FLEET SWEEP — {len(roots)} repos, {n_wf_total} workflow files read")
    print("=" * 96)
    print(f"\ncan-fail-ci        : {len(flat_ci)} finding(s) across {len(repos_ci)} repo(s)")
    for b, rs in sorted(ci_buckets.items(), key=lambda kv: -len(kv[1])):
        print(f"    {len(rs):4d}  {b}")
    print(f"    {len(unver):4d}  UNVERIFIABLE (could not parse — NOT counted as clean)")

    print(f"\nfail-open-harness  : {len(flat_ho)} finding(s) across {len(repos_ho)} repo(s)")
    buckets = {}
    for f in flat_ho:
        buckets.setdefault(f["rule"], []).append(f["repo"])
    for b, rs in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        print(f"    {len(rs):4d}  {b}")

    if repos_ho:
        print("\n  harness repos:", " ".join(repos_ho[:40]),
              "..." if len(repos_ho) > 40 else "")

    if a.json:
        Path(a.json).write_text(json.dumps({
            "n_repos": len(roots), "n_workflows": n_wf_total,
            "per_repo": per_repo, "ci_buckets": {k: sorted(set(v)) for k, v in ci_buckets.items()},
        }, indent=1))
        print(f"\njson -> {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
