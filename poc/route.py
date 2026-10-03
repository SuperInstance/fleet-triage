#!/usr/bin/env python3
"""
route - the decider that declines.

A workflow step that returns an answer OR refuses, and is useful either way.

The routing is built on the one measured property that makes refusal possible:
`score` on ordered levels returns a CONTINUOUS position plus `confidence` plus
the full `probabilities` map, and confidence tracks the SEPARATION of the
distribution rather than its height. A 0.57/0.43 split comes back at
confidence 0.35 -- that is the model asking to be routed to a human.

    python3 route.py                 # run the demo battery
    python3 route.py --threshold 0.6 # move the gate and watch cases flip
    python3 route.py --sweep         # show the whole threshold curve

Exit code 0 even when it abstains. A refusal is a successful run.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import jevc

SEVERITY = [
    "Cosmetic; no user impact and no workaround needed",
    "Minor; degraded behaviour but a workaround exists",
    "Serious; a core workflow is broken and users are affected",
    "Critical; data loss, security, or money is at stake",
]
DECIDABLE = [
    "The stated evidence is sufficient to decide without a human",
    "The stated evidence nearly decides it; a human should confirm",
    "The stated evidence does not decide it; a human must look",
    "The case is outside anything the evidence speaks to",
]

CASES = {
    "cosmetic-typo": (
        "A README spells 'recieve' instead of 'receive' in the install "
        "section. No code path is affected. The fix is one character.",
        "act"),   # cosmetic, but trivially decidable -> expected to CALL
    "duplicate-charge": (
        "A payment webhook's retry block is blamed for duplicate charges. "
        "The stated evidence: 2 incidents in 90 days, both visible in support "
        "tickets. The proposed change deletes 40 lines of retry logic. No "
        "sample size, no incident review, no statement that the retries and "
        "the duplicates are the same events.",
        "defer"),  # expected to ABSTAIN
    "auth-bypass": (
        "An auth middleware change would let a session cookie survive a "
        "password change. Stated evidence: none. The diff is described as "
        "'cleanup' and the author notes the old check 'was annoying'.",
        "defer"),  # expected to ABSTAIN
    "dead-dependency": (
        "A build pins lodash 4.17.11 and CI reports 1 high-severity advisory "
        "(prototype pollution, CVE-2020-8203) with a known fixed version "
        "4.17.21. The upgrade touches one lockfile line and CI is green on a "
        "dry run of the patched version.",
        "act"),
}

Q = {
    "severity": {"type": "score",
                 "instructions": "How severe is this issue, given only the "
                                 "evidence stated in the case?",
                 "criteria": SEVERITY},
    "decidable": {"type": "score",
                  "instructions": "Can this case be decided on the evidence "
                                  "that is actually stated, without a human "
                                  "adding information?",
                  "criteria": DECIDABLE},
}


def norm(sc: dict) -> str:
    """Map a score answer to a readable band. We keep the whole distribution;
    we never reduce it to the argmax alone."""
    p = sc.get("probabilities") or {}
    if not p:
        return "?"
    peak = max(p, key=lambda k: float(p[k]))
    try:
        return ["L0", "L1", "L2", "L3"][int(peak)]
    except (ValueError, IndexError):
        return "L?"


def dec_band_idx(sc: dict) -> int:
    p = sc.get("probabilities") or {}
    if not p:
        return 0
    return int(max(p, key=lambda k: float(p[k])))


def dist(sc: dict) -> str:
    p = sc.get("probabilities") or {}
    return " ".join(f"{k}:{float(v):.2f}" for k, v in sorted(p.items()))


def run(cases: dict, threshold: float, verbose: bool = True):
    """ONE CALL PER CASE, with a battery of questions inside it.

    The first version of this tool put all four cases into one shared state and
    asked both questions once. Every case came back with byte-identical
    answers (gate 0.16 for all four) -- the model scored the BATCH, not the
    cases. The contract's "adding questions does not increase response time"
    is true, but it is true of QUESTIONS ABOUT ONE STATE. It is emphatically
    not a licence to put N items in one state and read off N answers. Batching
    items silently destroys the tool and returns a confident uniform answer.
    """
    rows = []
    for name, (text, _) in cases.items():
        # state = the single case. Both questions ride along in one call.
        out = jevc.ask(text, Q)
        a = jevc.answers(out)
        sev = a.get("severity", {})
        dec = a.get("decidable", {})
        # THE GATE. Both signals must clear it. We use confidence, not the
        # argmax probability -- see JEV-CONTRACT.md on why those differ.
        gate = min(float(sev.get("confidence", 0.0)),
                   float(dec.get("confidence", 0.0)))
        # THE VETO, and it is not the threshold.
        #
        # min(severity_conf, decidable_conf) alone is wrong, and measurably so.
        # The auth-bypass case came back with decidable = L2 at confidence 0.93
        # -- i.e. "a human must look", 0.94 of the mass -- while severity sat at
        # only 0.53 confidence. min() let the low number dominate and the case
        # was CALLED at threshold 0.50. A crisp opinion about how bad something
        # is must not buy permission to skip asking whether anyone can tell.
        #
        # So: two independent conditions, either of which routes to a human.
        #   1. the decidable distribution puts real mass on "a human must look"
        #   2. both confidences clear the threshold
        veto = dec_band_idx(dec) >= 2
        verdict = "ABSTAIN" if (veto or gate < threshold) else "CALL"
        rows.append({
            "case": name, "verdict": verdict, "gate": gate,
            "veto": bool(veto), "expected": cases[name][1],
            "severity": sev.get("score"), "sev_conf": sev.get("confidence"),
            "sev_dist": dist(sev), "sev_band": norm(sev),
            "dec_score": dec.get("score"), "dec_conf": dec.get("confidence"),
            "dec_dist": dist(dec), "dec_band": norm(dec),
        })
    if verbose:
        print(f"{'case':<20} {'verdict':<9} {'gate':>5}  severity band/conf"
              f"        decidable band/conf")
        print("-" * 88)
        for r in sorted(rows, key=lambda r: r["gate"]):
            print(f"{r['case']:<20} {r['verdict']:<9} {r['gate']:>5.2f}  "
                  f"{r['sev_band']} {float(r['sev_conf']):.2f}  "
                  f"[{r['sev_dist']}]   {r['dec_band']} {float(r['dec_conf']):.2f}"
                  f"  [{r['dec_dist']}]")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="a workflow step that answers or "
                                             "refuses, and is useful either way")
    ap.add_argument("--threshold", type=float, default=0.50,
                    help="abstain unless BOTH confidences clear this "
                         "(default 0.50)")
    ap.add_argument("--sweep", action="store_true",
                    help="run the battery once, then replay it across "
                         "thresholds to show which case flips when")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.json:
        rows = run(CASES, args.threshold, verbose=False)
        print(json.dumps({"threshold": args.threshold, "rows": rows,
                          "cost": jevc.cost_note()}, indent=2))
        return 0

    print(f"ABSTAIN GATE  threshold={args.threshold:.2f} "
          f"(both confidences must clear it, else route to a human)\n")
    rows = run(CASES, args.threshold)

    called = [r["case"] for r in rows if r["verdict"] == "CALL"]
    abstained = [r["case"] for r in rows if r["verdict"] == "ABSTAIN"]
    print(f"\nCALL    ({len(called)}): {', '.join(called) or 'none'}")
    print(f"ABSTAIN ({len(abstained)}): {', '.join(abstained) or 'none'}")

    ok = sum(1 for r in rows
             if (r["verdict"] == "CALL") == (r["expected"] == "act"))
    print(f"\nagrees with the hand label on {ok}/{len(rows)} cases "
          f"(hand labels are in CASES; they were written before the calls)")

    if args.sweep:
        print("\n--- threshold sweep: the same battery, replayed ---")
        print(f"{'threshold':>10}  {'CALL':<28} {'ABSTAIN'}")
        prev = None
        for th in [i / 100 for i in range(0, 101, 5)]:
            c = sorted(r["case"] for r in rows
                       if r["gate"] >= th and not r["veto"])
            a = sorted(r["case"] for r in rows
                       if r["gate"] < th or r["veto"])
            mark = ""
            if prev is not None and set(c) != set(prev):
                moved = sorted(set(prev) ^ set(c))
                mark = "   <-- " + ", ".join(moved) + " flips"
            print(f"{th:>10.2f}  {','.join(c) or '-':<28} "
                  f"{','.join(a) or '-'}{mark}")
            prev = c
        print("\nThe gate value of each case (confidence is the min of the two "
              "signals):")
        for r in sorted(rows, key=lambda r: r["gate"]):
            print(f"  {r['case']:<20} gate={r['gate']:.2f}")

    print(f"\n{jevc.cost_note()}")
    print("A refusal is a successful run: this exits 0 whether it calls or "
          "abstains.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
