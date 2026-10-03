#!/usr/bin/env python3
"""ROUND 2 — the arms that actually discriminate.

Round 1 failed its own bar: 100% accuracy, because my `evidence` strings
annotated the answer ("state=open, merged=false" -> claim "is open"). JEV was
doing reading comprehension, not adjudication.

Round 2 gives it the AUTHENTIC artefact and nothing else:
  authentic  the real PR body / real seed text, which ASSERTS 18 edges / 14 VERIFIED
  mismatch   the evidence of a DIFFERENT claim (does it read, or pattern-match wording?)
  nonfact    a claim with no ground truth in the evidence at all -- pure opinion
  noul-auth  calibrated P(true) on the authentic contested claim
"""
import json, random, statistics, urllib.error, urllib.request
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor

KEY = "apikey_2217d2c797da8a2d48d887bd713a67e1f235_e376d8a7b61fe16caf5645c0e53de638c87580d1bec9695f5edd0b1098728599"
URL, MODEL, REPEATS = "https://api.typesafe.ai/v1/systemone", "jev-1.13.0", 3
CRIT = {"correct": "The claim below is factually correct: it matches the evidence.",
        "incorrect": "The claim below is factually wrong: the evidence contradicts it.",
        "insufficient": "The evidence provided does not settle the claim either way."}
CRIT_SHUF = {"contradicted": CRIT["incorrect"], "cannot_tell": CRIT["insufficient"],
             "upheld": CRIT["correct"]}
MEAN = {"correct": "correct", "upheld": "correct", "incorrect": "incorrect",
        "contradicted": "incorrect", "insufficient": "insufficient", "cannot_tell": "insufficient"}
INSTR = ("Adjudicate the claim against the evidence. Answer 'correct' if the evidence "
         "supports it, 'incorrect' if the evidence contradicts it, and 'insufficient' "
         "if the evidence does not settle it.")

pr32 = json.load(open("pr32.json"))["body"]
pr33 = json.load(open("pr33.json"))["body"]
pr34 = json.load(open("pr34.json"))["body"]

AUTH32 = f"""GitHub pull request SuperInstance/quilt-tools #32
Title: referral-graph: edge #14 VERIFIED on delta-shape#1 merge - qe-eproc-witness -> ds-esign-drift
State: closed, merged=true, merged_at 2026-10-01T20:08:03Z, merge commit fb2e041

{pr32}"""

AUTH33 = f"""GitHub pull request SuperInstance/quilt-tools #33
Title: referral-graph: book edge #15 pq-named-refusals -> fm-refusal-ledger VERIFIED (fleet-murmur#8)
State: closed, merged=true, merged_at 2026-10-01T20:29:03Z, merge commit 0101409
Base of this PR: fb2e041 (which is PR #32's merge commit)

{pr33}"""

AUTH34 = f"""GitHub pull request SuperInstance/quilt-tools #34
Title: referral-graph: book edges #16+#17 - fleet-triage resolver census pair VERIFIED
State: open, merged=false

{pr34}"""

# The authentic seed text, exactly as it stands on merged main.
SEEDVIEW = open("seedview.txt").read()

C = []
def add(cid, claim, truth, evidence, fam, kind):
    C.append(dict(id=cid, claim=claim, truth=truth, evidence=evidence, family=fam, kind=kind))

# ---- A. CONTESTED WITH AUTHENTIC (WRONG) PROSE.  No corrective annotation. ----
add("A1_pr32_counter",
    "PR #32's own count is correct: after it landed, the referral graph held 18 edges, 14 VERIFIED and 4 PENDING.",
    False, AUTH32, "contested-authentic", "counter")
add("A2_pr33_counter",
    "PR #33's own count is correct: after it landed, the referral graph held 18 edges, 14 VERIFIED and 4 PENDING.",
    False, AUTH33, "contested-authentic", "counter")
add("A3_both_agree",
    "PRs #32 and #33 independently assert the same post-merge counter: 18 edges, 14 VERIFIED, 4 PENDING.",
    True, AUTH32 + "\n\n" + "=" * 60 + "\n\n" + AUTH33, "contested-authentic", "counter")
add("A4_true_count",
    "The referral graph on quilt-tools main holds 19 edges, 15 VERIFIED and 4 PENDING.",
    True, SEEDVIEW, "contested-authentic", "counter")
add("A5_merged_state_verified",
    "The seed text on merged main records 15 VERIFIED edges.", True, SEEDVIEW,
    "contested-authentic", "counter")
add("A6_merged_state_pending",
    "The seed text on merged main records 4 PENDING edges.", True, SEEDVIEW,
    "contested-authentic", "counter")
# ---- B. STATE claims, authentic API text only ----
add("B1_32_merged", "SuperInstance/quilt-tools PR #32 has been merged into main.", True, AUTH32, "state-authentic", "state")
add("B2_32_open", "SuperInstance/quilt-tools PR #32 is still open and awaiting review.", False, AUTH32, "state-authentic", "state")
add("B3_33_merged", "SuperInstance/quilt-tools PR #33 has been merged into main.", True, AUTH33, "state-authentic", "state")
add("B4_33_open", "SuperInstance/quilt-tools PR #33 is still open and awaiting review.", False, AUTH33, "state-authentic", "state")
add("B5_34_open", "SuperInstance/quilt-tools PR #34 is currently open and unmerged.", True, AUTH34, "state-authentic", "state")
add("B6_34_merged", "SuperInstance/quilt-tools PR #34 has been merged into main.", False, AUTH34, "state-authentic", "state")
add("B7_34_stacked", "PR #34 is based on PR #33's merge commit.", True, AUTH33 + "\n\n" + "=" * 60 + "\n\n" + AUTH34, "state-authentic", "state")
add("B8_33_is_fourteenth", "PR #33 describes itself as booking the fourteenth VERIFIED edge.", True, AUTH33, "state-authentic", "state")
add("B9_32_is_fourteenth", "PR #32's body states the graph reached 14 VERIFIED edges.", True, AUTH32, "state-authentic", "state")
add("B10_32_edge14", "PR #32 books edge #14 (qe-eproc-witness -> ds-esign-drift) at VERIFIED.", True, AUTH32, "state-authentic", "state")
add("B11_33_fm_triple", "PR #33 asserts fleet-murmur becomes the first triple-inbound repo.", True, AUTH33, "state-authentic", "state")
add("B12_32_and_33_rival", "PRs #32 and #33 are rival claims to the same counter; one of them must be wrong about the final number.", True, AUTH32 + "\n\n" + "=" * 60 + "\n\n" + AUTH33, "contested-authentic", "counter")
# ---- C. NON-FACTUAL: no ground truth in the evidence (pure opinion / value) ----
add("C1", "This PR is well written.", None, AUTH33, "nonfactual", "opinion")
add("C2", "This change should be merged quickly.", None, AUTH34, "nonfactual", "opinion")
add("C3", "The author of this PR is more trustworthy than the author of PR #32.", None, AUTH32 + "\n\n" + AUTH33, "nonfactual", "opinion")
add("C4", "19 edges is a better number than 18 edges.", None, SEEDVIEW, "nonfactual", "opinion")

# ---- D. MISMATCH control: evidence from a DIFFERENT claim (built at run time) ----
def call(state, qspec, tries=4):
    body = {"model": MODEL, "state": state, "questions": {"q": qspec}}
    if not isinstance(body.get("state"), str): raise ValueError("state must be str")
    q = body["questions"]
    for qid, s in q.items():
        if s.get("type") not in ("choice", "noul", "score"): raise ValueError("bad type")
        if "options" in s: raise ValueError("no options field")
        if s["type"] == "choice":
            if not isinstance(s.get("criteria"), dict) or len(s["criteria"]) < 2: raise ValueError("bad criteria")
            if not isinstance(s.get("instructions"), str): raise ValueError("bad instructions")
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json", "User-Agent": "jevmerge/2"})
    for a in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=50) as r: return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and a < tries - 1: time.sleep(.4 + random.random() * .3); continue
            return {"error": f"HTTP {e.code}"}
        except Exception:
            if a < tries - 1: time.sleep(.4); continue
            return {"error": "transport"}
    return {"error": "exhausted"}

def parse(resp, crit):
    a = (resp.get("answers") or {}).get("q")
    if not a: return None, None, resp.get("error", "no answer")
    pr = a.get("probabilities") or {}
    if not pr: return None, None, "no probabilities"
    d = {k: float(v) for k, v in pr.items()}
    k = max(d, key=d.get)
    return MEAN.get(k, k), d.get(k), d

def parse_noul(resp):
    a = (resp.get("answers") or {}).get("q")
    if not a: return None, resp.get("error", "no answer")
    n = a.get("noul")
    if isinstance(n, (int, float)): return float(n), None
    p = a.get("probabilities") or {}
    if p: k = max(p, key=p.get); return float(p[k]), None
    return None, "no parseable noul"

def one(t):
    cid, arm, rep, state, instr, crit = t
    if arm == "noul":
        r = call(state, {"type": "noul", "instructions": instr})
        p, err = parse_noul(r); return dict(id=cid, arm=arm, rep=rep, p=p, verdict=None, err=err)
    r = call(state, {"type": "choice", "instructions": instr, "criteria": crit})
    v, p, d = parse(r, crit); return dict(id=cid, arm=arm, rep=rep, p=p, verdict=v, dist=d, err=(None if v else "no parseable verdict"))

def main():
    tasks = []
    for c in C:
        st = f"EVIDENCE:\n{c['evidence']}\n\nCLAIM UNDER ADJUDICATION:\n{c['claim']}"
        for rep in range(REPEATS):
            tasks.append((c["id"], "choice", rep, st, INSTR, CRIT))
            tasks.append((c["id"], "shuffle", rep, st, INSTR, CRIT_SHUF))
            tasks.append((c["id"], "mismatch", rep,
                          f"EVIDENCE:\n{next(x['evidence'] for x in C if x['id']=='A1_pr32_counter')}\n\nCLAIM UNDER ADJUDICATION:\n{c['claim']}", INSTR, CRIT))
            if c["truth"] is not None:
                tasks.append((c["id"], "noul", rep, st, f"Is the following claim factually true?\n\nCLAIM: {c['claim']}", None))
    print(f"claims={len(C)} tasks={len(tasks)}", flush=True)
    out = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, r in enumerate(ex.map(one, tasks)):
            out.append(r)
            if (i+1) % 60 == 0: print(f"  {i+1}/{len(tasks)}", flush=True)
    json.dump({"claims": C, "results": out}, open("results2.json", "w"), indent=1)
    print(f"done | failures {sum(1 for r in out if r.get('err'))}/{len(out)}")

if __name__ == "__main__":
    main()
