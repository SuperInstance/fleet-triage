#!/usr/bin/env python3
"""
second_opinion - an independent second opinion on a decision already made.

Reads the STATED REASONING of a recorded review and asks whether the evidence
actually supports it. It does not ask whether the conclusion is popular and it
does not ask whether it agrees with the other reviewer.

The interesting output is the DISAGREEMENT. Most reviewers are correlated, and
a correlated panel is worth about two votes, so "this reviewer agreed" is close
to worthless information. What is worth something is the place where this
reviewer parts company with the recorded one -- and the tool reports that place
first, loudly, with the full distribution behind it.

    python3 second_opinion.py            # run the three recorded decisions
    python3 second_opinion.py --json

One API call per case, carrying a battery of questions about that one case.
(Do NOT put several cases in one shared state: the model scores the batch and
returns the same answer for every item. Measured, not theorised.)
"""
from __future__ import annotations

import argparse
import json
import sys

import jevc

VERDICTS = ["request changes: the evidence does not support the decision",
            "approve with a note: the evidence mostly supports it",
            "approve: the evidence clearly supports the decision"]

Q = {
    # what the evidence actually supports, judged on its own terms
    "independent": {"type": "choice",
                    "instructions":
                        "Reading ONLY the change description and the evidence it "
                        "states, what does the evidence support? Judge the "
                        "evidence, not the popularity of the conclusion.",
                    "criteria": {v: None for v in VERDICTS}},
    # what a generic reviewer would conclude -- the correlated-panel control
    "what_a_reviewer_says": {"type": "choice",
                             "instructions":
                                 "What would a typical reviewer conclude about "
                                 "this change, having read the description and "
                                 "the stated reasoning but not checked anything?",
                             "criteria": {v: None for v in VERDICTS}},
    # is the sample big enough to carry the causal claim
    "evidence_sufficiency": {"type": "score",
                             "instructions":
                                 "Is the evidence stated here sufficient to "
                                 "support the claim being made?",
                             "criteria": [
                                 "No evidence at all is stated",
                                 "Some evidence, but it does not reach the claim",
                                 "Evidence is stated and it largely supports the claim",
                                 "Evidence is stated, checked, and directly establishes the claim",
                             ]},
}

CASES = [
    {
        "name": "drop-retry-block",
        "change": "Delete the retry block from the payment webhook handler (40 "
                  "lines).",
        "stated_reasoning": "The retry caused duplicate charges in incident "
                            "4471, seen twice in 90 days, confirmed by the "
                            "support tickets.",
        "recorded": "approve",
        "recorded_reasoning": "Two tickets is enough. We should have removed "
                              "this earlier.",
    },
    {
        "name": "bump-lodash",
        "change": "Bump lodash 4.17.11 -> 4.17.21 to clear CVE-2020-8203.",
        "stated_reasoning": "CI reports one high-severity advisory with a "
                            "fixed version available. The upgrade is one "
                            "lockfile line and the test suite passes against "
                            "the patched version.",
        "recorded": "approve",
        "recorded_reasoning": "Security advisory, known fix, green tests. Ship "
                              "it.",
    },
    {
        "name": "weaken-session-check",
        "change": "Let a session cookie survive a password change.",
        "stated_reasoning": "Cleanup. The old check was annoying.",
        "recorded": "request changes",
        "recorded_reasoning": "This is a security regression. Revert.",
    },
    {
        "name": "rename-public-field",
        "change": "Rename the public JSON field `user_id` to `uid`.",
        "stated_reasoning": "Consistency with the other endpoints. Mechanical "
                            "change, covered by the existing migration note.",
        "recorded": "request changes",
        "recorded_reasoning": "Renaming a public field breaks every client "
                              "that has not migrated. We cannot do this in a "
                              "patch release.",
    },
]

SHORT = {v: i for i, v in enumerate(VERDICTS)}
LABEL = {0: "REQUEST CHANGES", 1: "APPROVE (note)", 2: "APPROVE"}
# the evidence-sufficiency `score` has four levels, not three
SUF_LABEL = {0: "NO EVIDENCE", 1: "EVIDENCE TOO THIN", 2: "SUPPORTS CLAIM",
             3: "ESTABLISHES CLAIM"}


def pmap(ans: dict) -> dict:
    return {k: float(v) for k, v in (ans.get("probabilities") or {}).items()}


def peak(ans: dict) -> int:
    p = pmap(ans)
    if not p:
        return -1
    top = max(p, key=lambda k: p[k])
    # THIRD CONTRACT DIFFERENCE, undocumented in JEV-CONTRACT.md:
    # `score` keys its probabilities map by INDEX ("0","1","2"), but `choice`
    # keys it by the LABEL STRING. Code written for one silently breaks on the
    # other -- int("approve with a note: ...") raises, which is at least loud.
    try:
        return int(top)
    except (TypeError, ValueError):
        return SHORT.get(top, -1)


def fmt(ans: dict, labels: dict = None) -> str:
    labels = labels or LABEL
    p = pmap(ans)
    if not p:
        return "(no distribution returned)"
    out = []
    for k, v in sorted(p.items(), key=lambda kv: kv[1], reverse=True):
        try:
            i = int(k)
            name = labels.get(i, str(k)[:24])
        except (TypeError, ValueError):
            name = str(k) if len(str(k)) < 24 else str(k)[:21] + "..."
        out.append(f"{name:>17} {v:.2f}")
    return "  ".join(out)


def run_one(case: dict):
    state = (
        f"CHANGE:\n{case['change']}\n\n"
        f"STATED REASONING:\n{case['stated_reasoning']}\n\n"
        f"RECORDED REVIEWER SAID: {case['recorded']}\n"
        f"RECORDED REVIEWER'S REASONING: {case['recorded_reasoning']}\n"
    )
    out = jevc.ask(state, Q)
    a = jevc.answers(out)
    ind = a.get("independent", {})
    gen = a.get("what_a_reviewer_says", {})
    suf = a.get("evidence_sufficiency", {})

    ind_i, gen_i = peak(ind), peak(gen)
    rec_i = 0 if case["recorded"] == "request changes" else 2

    # The correlated-panel control: how much did the generic-reviewer question
    # move toward whatever the recorded reviewer concluded? If it lands on the
    # recorded verdict more often than chance, this reviewer is adding very
    # little independent information.
    return {
        "name": case["name"],
        "recorded": case["recorded"],
        "independent": LABEL.get(ind_i, "?"),
        "independent_p": fmt(ind),
        "independent_conf": ind.get("confidence"),
        "generic_reviewer": LABEL.get(gen_i, "?"),
        "generic_p": fmt(gen),
        "recorded_p": pmap(ind).get(case["recorded"]) or
                     max(pmap(ind).values(), default=None),
        "evidence_score": suf.get("score"),
        "evidence_conf": suf.get("confidence"),
        "evidence_p": fmt(suf, SUF_LABEL),
        "disagrees": ind_i != rec_i,
        "agrees_with_generic": gen_i == ind_i,
        "generic_matches_recorded": gen_i == rec_i,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="independent second opinion on a "
                                             "decision already made")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = [run_one(c) for c in CASES]

    if args.json:
        print(json.dumps({"rows": rows, "cost": jevc.cost_note()}, indent=2))
        return 0

    print("SECOND OPINION -- disagreement first\n")
    for r in rows:
        flag = "  <<< DISAGREEMENT" if r["disagrees"] else ""
        print(f"[{r['name']}]  recorded: {r['recorded'].upper()}{flag}")
        print(f"   evidence sufficiency: score={r['evidence_score']} "
              f"conf={r['evidence_conf']}  {r['evidence_p']}")
        print(f"   what a generic reviewer would say : {r['generic_reviewer']}")
        print(f"   what the EVIDENCE supports        : {r['independent']} "
              f"(confidence {r['independent_conf']})")
        print(f"     {r['independent_p']}")
        print()

    dis = [r for r in rows if r["disagrees"]]
    print("-" * 74)
    print(f"DISAGREEMENTS: {len(dis)}/{len(rows)}")
    for r in dis:
        print(f"  {r['name']}: recorded said {r['recorded']}, "
              f"evidence supports {r['independent']}")
        print(f"    evidence sufficiency {r['evidence_p']}")

    # the correlation control, stated plainly
    same = sum(1 for r in rows if r["agrees_with_generic"])
    gmr = sum(1 for r in rows if r["generic_matches_recorded"])
    ind_gen = sum(1 for r in rows if r["agrees_with_generic"])
    print(f"\nCORRELATION CONTROL")
    print(f"  'what a typical reviewer says' matched what the EVIDENCE supports: "
          f"{ind_gen}/{len(rows)}")
    print(f"  'what a typical reviewer says' matched the RECORDED verdict:      "
          f"{gmr}/{len(rows)}")
    if ind_gen > gmr:
        print("  -> the generic-reviewer question tracks the evidence more than it "
              "tracks\n     the recorded reviewer, so it is a live control and not "
              "a\n     restatement of the panel.")
    else:
        print("  -> the generic-reviewer question tracks the recorded panel at "
              "least as\n     closely as it tracks the evidence. This reviewer is "
              "largely\n     correlated with the panel it is checking, which is the "
              "failure\n     mode this tool exists to catch.")
    print(f"\n{jevc.cost_note()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
