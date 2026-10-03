#!/usr/bin/env python3
"""Can JEV adjudicate a merge? The competition entry's one untested assumption.

ARMS
  noul      P(claim is TRUE) given evidence. -> calibration curve.
  choice    3-way verdict {correct, incorrect, insufficient}. -> abstention channel.
  shuffle   same as `choice` but the label->meaning map is ROTATED. -> leakage control.
  noevid    same as `choice` with the evidence REMOVED. -> the decisive control.

`noevid` is the one that matters. An adjudicator that scores the same with the
evidence deleted was never adjudicating; it was pattern-matching claim wording.
"""
import json, random, statistics, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

KEY = "apikey_2217d2c797da8a2d48d887bd713a67e1f235_e376d8a7b61fe16caf5645c0e53de638c87580d1bec9695f5edd0b1098728599"
URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-1.13.0"
REPEATS = 3
TYPES = ("choice", "noul", "score")

CRIT = {
    "correct":      "The claim below is factually correct: it matches the evidence.",
    "incorrect":    "The claim below is factually wrong: the evidence contradicts it.",
    "insufficient": "The evidence provided does not settle the claim either way.",
}
# rotated: same three MEANINGS, different key names
CRIT_SHUF = {
    "contradicted":  CRIT["incorrect"],
    "cannot_tell":   CRIT["insufficient"],
    "upheld":        CRIT["correct"],
}
MEAN = {"correct": "correct", "upheld": "correct",
        "incorrect": "incorrect", "contradicted": "incorrect",
        "insufficient": "insufficient", "cannot_tell": "insufficient"}


def preflight(body):
    if not isinstance(body.get("state"), str):
        raise ValueError("state must be a STRING")
    q = body.get("questions")
    if not isinstance(q, dict) or not q:
        raise ValueError("questions must be a non-empty object")
    for qid, spec in q.items():
        if spec.get("type") not in TYPES:
            raise ValueError(f"{qid}: bad type")
        if "options" in spec:
            raise ValueError(f"{qid}: there is NO options field")
        if spec["type"] == "choice":
            cr = spec.get("criteria")
            if not isinstance(cr, dict) or len(cr) < 2:
                raise ValueError(f"{qid}: choice needs >=2 criteria")
            if not isinstance(spec.get("instructions"), str):
                raise ValueError(f"{qid}: instructions must be a string")
        if spec["type"] == "noul" and not spec.get("instructions"):
            raise ValueError(f"{qid}: noul needs instructions")


def call(state, qspec, tries=4):
    body = {"model": MODEL, "state": state, "questions": {"q": qspec}}
    preflight(body)
    req = urllib.request.Request(
        URL, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json",
                 "User-Agent": "jevmerge/1"})
    for a in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=50) as r:
                return json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            if e.code in (502, 503, 504) and a < tries - 1:
                time.sleep(0.4 + random.random() * 0.3); continue
            return {"error": f"HTTP {e.code}"}
        except Exception:
            if a < tries - 1:
                time.sleep(0.4); continue
            return {"error": "transport"}
    return {"error": "exhausted"}


def parse_choice(resp, crit):
    ans = (resp.get("answers") or {}).get("q")
    if not ans:
        return None, None, resp.get("error", "no answer")
    probs = ans.get("probabilities") or {}
    if not probs:
        return None, None, "no probabilities"
    d = {k: float(v) for k, v in probs.items()}
    key = max(d, key=d.get)
    return MEAN.get(key, key), d.get(key), d


def parse_noul(resp):
    ans = (resp.get("answers") or {}).get("q")
    if not ans:
        return None, resp.get("error", "no answer")
    n = ans.get("noul")
    if isinstance(n, (int, float)):
        return float(n), None
    p = ans.get("probabilities") or {}
    if p:
        k = max(p, key=p.get)
        return float(p[k]), None
    return None, "no parseable noul"


def one(task):
    cid, arm, rep, state, instr, crit = task
    if arm == "noul":
        r = call(state, {"type": "noul", "instructions": instr})
        p, err = parse_noul(r)
        return dict(id=cid, arm=arm, rep=rep, p=p, verdict=None, err=err, raw=r)
    r = call(state, {"type": "choice", "instructions": instr, "criteria": crit})
    v, p, d = parse_choice(r, crit)
    return dict(id=cid, arm=arm, rep=rep, p=p, verdict=v, dist=d, err=(
        None if v else "no parseable verdict"), raw=r)


def build(claims):
    tasks = []
    for c in claims:
        state = f"EVIDENCE:\n{c['evidence']}\n\nCLAIM UNDER ADJUDICATION:\n{c['claim']}"
        bare = f"CLAIM UNDER ADJUDICATION:\n{c['claim']}"
        instr = ("Adjudicate the claim against the evidence. Answer 'correct' if the evidence "
                 "supports it, 'incorrect' if the evidence contradicts it, and 'insufficient' "
                 "if the evidence does not settle it.")
        for rep in range(REPEATS):
            tasks.append((c["id"], "noul", rep, state,
                          f"Is the following claim factually true?\n\nCLAIM: {c['claim']}", None))
            tasks.append((c["id"], "choice", rep, state, instr, CRIT))
            tasks.append((c["id"], "shuffle", rep, state, instr, CRIT_SHUF))
            tasks.append((c["id"], "noevid", rep, bare, instr, CRIT))
    return tasks


def main():
    claims = json.load(open("claims.json"))
    tasks = build(claims)
    print(f"claims={len(claims)} tasks={len(tasks)}", flush=True)
    t0 = time.time()
    out = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, r in enumerate(ex.map(one, tasks)):
            out.append(r)
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(tasks)}  {time.time()-t0:.0f}s", flush=True)
    for r in out:
        r.pop("raw", None)
    json.dump({"claims": claims, "results": out}, open("results.json", "w"), indent=1)
    fails = [r for r in out if r.get("err")]
    print(f"done in {time.time()-t0:.0f}s | transport/parse failures: {len(fails)}/{len(out)}")
    for f in fails[:5]:
        print("  FAIL", f["arm"], f["id"], f["err"])


if __name__ == "__main__":
    main()
