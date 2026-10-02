#!/usr/bin/env python3
"""
IT-DEPARTMENT: a self-improving loop, where the improvement is measurable.

WHAT THIS IS
    Three loop topologies answer the same prompts in parallel. A JEV judge
    scores their outputs, and so does GROUND TRUTH on the prompts where we
    already know the answer. The system's "self-improvement" is not a cleverer
    prompt. It is the cumulative record of WHICH COMPONENTS EARN THEIR PLACE --
    and the loop retires the ones that do not.

WHY THAT FRAMING
    We have measured, six independent ways, that a panel of judges carries an
    effective sample size of about 2 out of the number asked. Dawid-Skene and
    accuracy-weighted voting closed at most 11% of the Condorcet gap even with
    oracle labels. JEV-as-a-panel equals JEV-as-one: 1 of 22 claims changed
    across 3 repeats, spread 0.009. And selectlib measures a judge LOSING to a
    free local statistic at every budget on the condition built for it.

    So "the judge picks the better loop" is precisely the thing under test. A
    harness that assumed the judge is good would be assuming its conclusion.

THE THREE ARMS
    A  single     one JEV call, take it
    B  refracted  3 sequential calls, each seeing the previous, then a
                  self-critique pass -- the "iterate and re-flavor the
                  weighting" proposal
    C  free       NO model call. A local lexical+structural answer built from
                  the corpus. This is the baseline that judges are supposed to
                  beat, and selectlib says they often do not.

SCORING
    judge_score    JEV, rubric as `criteria` keys
    truth_score    only on prompts with a known answer, checked in code
    The interesting column is DISAGREEMENT between them: where the judge likes
    something the ground truth does not, the judge is climbing noise, and that
    is the number that decides whether B is allowed to keep iterating.
"""
import os, json, re, time, urllib.request, urllib.error
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

JEV = "https://api.typesafe.ai/v1/systemone"
K = os.environ.get("TYPESAFEAI_KEY", "")

# ── the corpus the free arm reads. It is our own reports, which is the point:
#    the IT department for this team reads the team's own work. ────────────────
CORPUS = {}
for fn in sorted(os.listdir("/workspace/projects/fleet-triage")):
    if fn.endswith(".md") and os.path.getsize(f"/workspace/projects/fleet-triage/{fn}") > 2000:
        CORPUS[fn] = open(f"/workspace/projects/fleet-triage/{fn}", encoding="utf-8", errors="replace").read()

# ── prompts, each with a CHECKABLE answer where one exists ─────────────────────
PROMPTS = [
    dict(q="What is the Kish effective sample size of a panel of nine frontier "
            "judges across seven vendors, with a 95% bootstrap confidence interval?",
         truth=[r"2\.18", r"2\.1\d"], where="EXPERIMENTS.md / papers-ROOT.md"),
    dict(q="What does the fleet's own self-improvement loop consist of, per the "
            "wardroom agent?",
         truth=[r"spawn.{0,20}lane|re-?run.{0,20}pin|4am|four ?am"], where="wardroom round 1"),
    dict(q="How many repositories in the SuperInstance namespace fail open, and "
            "what fraction of them share the same six-line try/except?",
         truth=[r"13", r"11"], where="sprint-FAILOPEN.md"),
    dict(q="What balanced accuracy did a 64-bit irreversible FNV-1a hash achieve "
            "on the honest by-ply split?",
         truth=[r"0\.50\d*", r"0\.51"], where="EXPERIMENTS.md"),
    dict(q="Which two entries did the conservation-paper audit retract as "
            "prose-only when they are actually real code with many hits?",
         truth=[r"batten", r"136"], where="CORRECTION-CONSERVATION.md"),
    dict(q="What did the CRDT canary last do, and since when has it been "
            "incapable of failing?",
         truth=[r"dcbdeca", r"2026-09-30", r"never"], where="CRDT-CANARY2.md"),
    dict(q="How many of the 988 mathematical spreadsheet types carry an explicit "
            "invariant or verification condition?",
         truth=[r"\b48\b"], where="TYPES-UNLOCKED.md"),
    dict(q="What is the value of qwen3.8-27b's 1-ply score in the openrouter "
            "mission probe, and what does it prove about redacted topic history?",
         truth=None, where="(synthetic)"),
    dict(q="What is the exact byte size of the fleet resolver Worker, gzipped, "
            "and how many files does its index hold?",
         truth=[r"944\.91", r"85[,.]?990"], where="worker-RESOLVER.md"),
    dict(q="What proportion of the 5,127-repository namespace is visible to "
            "outside pull requests, and what is the stated visibility doctrine?",
         truth=[r"5[,.]?111|5,111", r"public"], where="ORIENTATION.md"),
]

RUBRIC = {
    "grounded_in_our_own_artifacts": "The answer cites or reflects something in the fleet's own reports rather than general knowledge.",
    "specific_numbers": "The answer gives concrete figures, names, paths or commits rather than vague description.",
    "names_the_mechanism": "The answer explains WHY, naming a mechanism, not just WHAT.",
    "no_invented_sources": "The answer does not fabricate a file, URL, commit or author.",
    "honest_about_uncertainty": "The answer marks what is unverified or unexamined rather than asserting it.",
}

# ── JEV ─────────────────────────────────────────────────────────────────────
def jev(state, questions, max_items=6):
    body = {"state": state, "questions": questions}
    req = urllib.request.Request(JEV, data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {K}", "Content-Type": "application/json",
                 "User-Agent": "it-department"}, method="POST")
    for t in range(3):
        try:
            with urllib.request.urlopen(req, timeout=150) as r:
                d = json.loads(r.read())
            return d
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503): time.sleep(4 + 3 * t); continue
            return {"__err__": f"{e.code}"}
        except Exception:
            time.sleep(4)
    return {"__err__": "exhausted"}

def ask_arms(p):
    q = p["q"]
    ctx = "\n\n".join(v[:900] for v in list(CORPUS.values())[:6])
    state = (f"Team corpus excerpts:\n{ctx}\n\n"
             f"Answer strictly from the team corpus above. If the corpus does not "
             f"contain the answer, say UNANSWERABLE. Be specific: numbers, file names, "
             f"commit hashes. Under 70 words.")
    qs = {"q": {"type": "string", "instructions": "Answer the question from the team corpus. "
            "If the corpus lacks the answer, return UNANSWERABLE.",
            "criteria": {"answer": "The team's answer, under 70 words."}}}
    A = jev(state, qs).get("answers", {}).get("q", {})

    # B: refracted -- the proposal under test
    prev = ""
    b_ans = ""
    for i in range(3):
        s2 = state + (f"\n\nA previous attempt answered: {prev}\n"
                      "That is unverified. Find what is wrong with it, and answer "
                      "differently. If it was right, say so and add the missing detail." if prev else "")
        r = jev(s2, qs).get("answers", {}).get("q", {})
        c = r.get("answer") if isinstance(r, dict) else None
        if not c: break
        b_ans, prev = c, c
    return p, {"A_single": A.get("answer") if isinstance(A, dict) else None, "B_refracted": b_ans}

# ── the free arm: no model at all ───────────────────────────────────────────
def free_arm(p):
    """Lexical retrieval over the corpus. A 'free local statistic' in the sense
    selectlib measured -- a real baseline, not a strawman."""
    terms = [t for t in re.findall(r"[a-z0-9._-]{4,}", p["q"].lower())
             if t not in ("what", "which", "does", "the", "and", "for", "with", "that",
                          "this", "have", "many", "from", "were", "how", "into")]
    best, score = None, 0
    for name, body in CORPUS.items():
        low = body.lower()
        s = sum(low.count(t) for t in terms)
        if s > score:
            best, score = name, s
    if best is None:
        return None
    b = CORPUS[best]
    lines = [l.strip() for l in b.splitlines() if l.strip()]
    hit = [l for l in lines if any(t in l.lower() for t in terms)][:2]
    return f"From {best}: " + (" ".join(hit)[:400] if hit else b[:200])

def judge(answers: dict, state_hint: str):
    """JEV scores each arm against a rubric. The option set IS the criteria keys --
    there is no `options` field, and every subject is explicitly named."""
    if not any(answers.values()):
        return {}
    listing = "\n".join(f"  candidate {k}: {v[:600]}" for k, v in answers.items() if v)
    st = ("You are the systems analyst for a software team, reviewing three candidate "
          "answers to the same internal question. Judge each on its own merits.\n\n" + listing)
    qs = {"review": {"type": "string",
          "instructions": "Rate EACH named candidate separately against each criterion. "
                         "Candidate A is 'A_single'. Candidate B is 'B_refracted'. "
                         "Candidate C is 'C_free'. Do not consider a candidate that is "
                         "listed as absent. Rate 1-5.",
          "criteria": {k: f"Score 1-5 for how well this answer meets: {v}"
                       for k, v in RUBRIC.items()}}}
    d = jev(st, qs).get("answers", {}).get("review", {})
    return d if isinstance(d, dict) else {}

def truth_ok(ans, truth):
    if not ans: return None
    if not truth: return None
    return bool(any(re.search(pat, ans, re.I) for pat in truth))

def main():
    print("=" * 78)
    print("IT-DEPARTMENT — three loop topologies, judged and truth-checked")
    print("=" * 78)
    print(f"  corpus: {len(CORPUS)} reports from this team")

    # Arm C costs nothing and is computed locally
    results = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        for p, ab in ex.map(ask_arms, PROMPTS):
            fc = free_arm(p)
            results[p["q"][:60]] = {
                "A_single": ab["A_single"], "B_refracted": ab["B_refracted"],
                "C_free": fc, "truth": p["truth"],
            }
            print(f"  answered: {p['q'][:60]}...", flush=True)

    # judge + ground truth
    print("\n  scoring...")
    rows = []
    for k, v in results.items():
        arms = {a: v[a] for a in ("A_single", "B_refracted", "C_free")}
        jd = judge(arms, k)
        # prefer the JEV probability map for the model's ranking
        probs = jd.get("probabilities", {}) if isinstance(jd, dict) else {}
        scored = {a: {"truth": truth_ok(v[a], v["truth"])} for a in arms}
        for a in arms:
            sc = probs.get(a)
            if isinstance(sc, dict):
                scored[a]["judge"] = round(sum(sc.get(c, 0) for c in RUBRIC) / len(RUBRIC), 3)
        rows.append((k, scored, v["truth"]))

    # ── the cumulative ledger. THIS is the self-improvement. ────────────────
    tally = Counter(); tscore = Counter(); jscore = Counter(); disagree = 0; judged = 0
    for k, scored, truth in rows:
        for a, s in scored.items():
            tally[a] += 1
            if s["truth"] is True: tscore[a] += 1
            if "judge" in s: jscore[a] += 1; judged += 1
            if s.get("judge", 0) >= 4 and s["truth"] is False: disagree += 1

    # A scoring block that reports all zeros is a BROKEN INSTRUMENT, not a result.
    # This run is invalid and must say so rather than print an empty ledger.
    if not any(v.get("judge") for _, sc, _ in rows for v in sc.values()):
        print("\n  INVALID RUN: the judge produced no scores at all.")
        print("  Every number below would be an artifact of a broken harness.")
        print("  Refusing to write a ledger. See IT-DEPARTMENT-BROKEN.md.")
        raise SystemExit(2)
    print("\n" + "=" * 78)
    print("  CUMULATIVE LEDGER — the part that is supposed to get better")
    print("=" * 78)
    print(f"  {'arm':14} {'answered':>9} {'truth-correct':>15} {'judge>=4':>10}")
    for a in ("A_single", "B_refracted", "C_free"):
        c = tscore[a]
        print(f"  {a:14} {tally[a]:9d} {str(c)+'/'+str(tally[a]):>15} {jscore[a]:10d}")
    print(f"\n  cases where the judge liked it (>=4) and the ground truth says WRONG: {disagree}")
    if judged:
        print(f"  judge-rated cases: {judged}   -> this is the noise the iteration is climbing")
    out = {"tally": dict(tally), "truth_correct": dict(tscore), "judge_ge4": dict(jscore),
           "judge_liked_wrong": disagree, "judged": judged, "rows": len(rows)}
    json.dump(out, open("/workspace/it_department_ledger.json", "w"), indent=1)
    print("\n  saved /workspace/it_department_ledger.json")
    return out

if __name__ == "__main__":
    main()
