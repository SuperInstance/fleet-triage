#!/usr/bin/env python3
import json, random, statistics
from collections import defaultdict, Counter

D = json.load(open("results2.json"))
claims = {c["id"]: c for c in D["claims"]}
R = D["results"]
by = defaultdict(list)
for r in R: by[(r["id"], r["arm"])].append(r)
T = lambda cid: claims[cid]["truth"]

print("=" * 78)
print("ROUND 2 — AUTHENTIC ARTEFACTS ONLY  (no corrective annotation)")
print("=" * 78)
fact = [c for c in claims.values() if c["truth"] is not None]
print(f"claims: {len(claims)}  | factual (scored): {len(fact)}  "
      f"TRUE={sum(1 for c in fact if c['truth'])} FALSE={sum(1 for c in fact if not c['truth'])}"
      f"  | non-factual (abstention test): {len(claims)-len(fact)}")
print(f"calls: {len(R)}  failures: {sum(1 for r in R if r.get('err'))}")

def arm_acc(arm, subset=None):
    ok = tot = abst = 0
    for cid in claims:
        if T(cid) is None: continue
        if subset and cid not in subset: continue
        rs = by[(cid, arm)]
        v = Counter(x["verdict"] for x in rs).most_common(1)[0][0]
        if v == "insufficient": abst += 1; continue
        tot += 1; ok += ((v == "correct") == T(cid))
    return ok, tot, abst

contested = {c for c in claims if claims[c]["family"] == "contested-authentic"}
statec = {c for c in claims if claims[c]["family"] == "state-authentic"}
print()
print("=" * 78)
print("1. ACCURACY BY ARM")
print("=" * 78)
print(f"{'arm':<10} {'ALL':>16} {'abst':>7} | {'CONTESTED':>16} | {'STATE':>16}")
for arm in ("choice", "shuffle", "mismatch"):
    o, t, ab = arm_acc(arm)
    o2, t2, _ = arm_acc(arm, contested); o3, t3, _ = arm_acc(arm, statec)
    f = lambda a, b: (f"{a}/{b} = {a/b:.0%}" if b else "n/a")
    print(f"{arm:<10} {f(o,t):>16} {ab:>4}/{len(fact)} | {f(o2,t2):>16} | {f(o3,t3):>16}")

print()
print("=" * 78)
print("2. ABSTENTION ON NON-FACTUAL CLAIMS  (opinion / value — no ground truth exists)")
print("=" * 78)
nonfact = [c for c in claims.values() if c["truth"] is None]
ok = 0
for c in nonfact:
    v = Counter(x["verdict"] for x in by[(c["id"], "choice")]).most_common(1)[0][0]
    p = max(x["p"] for x in by[(c["id"], "choice")])
    ok += (v == "insufficient")
    print(f"  {c['id']:<4} {v:<13} p={p:.2f}  {c['claim'][:70]}")
print(f"  -> abstained on {ok}/{len(nonfact)} unanswerable claims")

print()
print("=" * 78)
print("3. CONFIDENT ERRORS  (the headline)")
print("=" * 78)
errs = []
for cid in claims:
    if T(cid) is None: continue
    rs = by[(cid, "choice")]
    v = Counter(x["verdict"] for x in rs).most_common(1)[0][0]
    p = max(x["p"] for x in rs)
    if v != "insufficient" and (v == "correct") != T(cid): errs.append((p, cid, v))
errs.sort(reverse=True)
print(f"total errors: {len(errs)}/{len(fact)}")
for p, cid, v in errs:
    c = claims[cid]
    print(f"\n  p={p:.2f} {cid}  -> said '{v}'")
    print(f"    CLAIM    : {c['claim']}")
    print(f"    TRUTH    : {c['truth']}")
    print(f"    EVIDENCE : {c['evidence'][:300].replace(chr(10),' | ')}")

# the decisive subset
print()
print("=" * 78)
print("4. THE #32/#33 ADJUDICATION, ITEM BY ITEM")
print("=" * 78)
for cid in ("A1_pr32_counter", "A2_pr33_counter", "A3_both_agree", "A4_true_count",
            "A5_merged_state_verified", "A6_merged_state_pending", "B12_32_and_33_rival"):
    c = claims[cid]
    v = Counter(x["verdict"] for x in by[(cid, "choice")]).most_common(1)[0][0]
    p = max(x["p"] for x in by[(cid, "choice")])
    m = Counter(x["verdict"] for x in by[(cid, "mismatch")]).most_common(1)[0][0]
    mp = max(x["p"] for x in by[(cid, "mismatch")])
    ns = [x["p"] for x in by[(cid, "noul")]]
    good = "OK " if (v == "correct") == c["truth"] else "ERR"
    print(f"  {good} {cid:<24} truth={str(c['truth']):<5} choice={v:<12}(p={p:.2f})  "
          f"noul={statistics.mean(ns):.2f}  mismatch={m}(p={mp:.2f})")

print()
print("=" * 78)
print("5. CALIBRATION (noul on authentic contested claims)")
print("=" * 78)
pts = []
for cid in claims:
    if T(cid) is None: continue
    ps = [x["p"] for x in by[(cid, "noul")] if x["p"] is not None]
    if ps: pts.append((statistics.mean(ps), T(cid), cid))
BINS = [(0,.1),(.1,.2),(.2,.3),(.3,.4),(.4,.5),(.5,.6),(.6,.7),(.7,.8),(.8,.9),(.9,1.01)]
print(f"{'bucket':<12}{'n':>3}{'mean P':>8}{'frac TRUE':>11}{'gap':>8}")
ece = 0.0
for lo, hi in BINS:
    b = [p for p in pts if lo <= p[0] < hi]
    if not b: continue
    mp = statistics.mean(p[0] for p in b); ft = sum(1 for p in b if p[1])/len(b)
    ece += len(b)/len(pts)*abs(mp-ft)
    print(f"[{lo:.1f},{hi:.1f})".ljust(12)+f"{len(b):>3}{mp:>8.3f}{ft:>11.2f}{ft-mp:>+8.3f}")
print(f"\nECE (10 bins) = {ece:.3f}   Brier = {statistics.mean((p[0]-(1.0 if p[1] else 0.0))**2 for p in pts):.3f}")
pos=[p[0] for p in pts if p[1]]; neg=[p[0] for p in pts if not p[1]]
print(f"AUC = {sum((a>b)+.5*(a==b) for a in pos for b in neg)/(len(pos)*len(neg)):.3f}  (n+={len(pos)} n-={len(neg)})")

print()
print("=" * 78)
print("6. OPERATING POINT BY ABSTENTION RATE")
print("=" * 78)
print(f"{'thresh':>7}{'abstain%':>10}{'answered':>10}{'correct':>9}{'acc answered':>15}")
for th in [i/20 for i in range(0, 21)]:
    ok = tot = ab = 0
    for cid in claims:
        if T(cid) is None: continue
        rs = by[(cid, "choice")]
        v = Counter(x["verdict"] for x in rs).most_common(1)[0][0]
        p = max(x["p"] for x in rs)
        if p < th or v == "insufficient": ab += 1; continue
        tot += 1; ok += ((v == "correct") == T(cid))
    if tot == 0 or abs(th*20) % 4 == 0:
        print(f"{th:>7.2f}{ab/len(fact):>9.0%}{tot:>10}{ok:>9}{(ok/tot if tot else float('nan')):>14.0%}")

print()
print("=" * 78)
print("7. CONTROLS")
print("=" * 78)
o1,t1,_ = arm_acc("choice"); o2,t2,_ = arm_acc("shuffle"); o3,t3,_ = arm_acc("mismatch")
print(f"label-shuffle : {o2}/{t2} = {o2/t2:.0%}   vs choice {o1}/{t1} = {o1/t1:.0%}   (delta {o1/t1-o2/t2:+.0%})")
print(f"mismatched-evid: {o3}/{t3} = {o3/t3:.0%}   vs choice {o1}/{t1} = {o1/t1:.0%}   (delta {o1/t1-o3/t3:+.0%})")
print(f"  -> if the delta is large, the evidence is load-bearing: JEV is READING, not pattern-matching.")
# does it collapse to the prior when evidence is wrong?
mc = sum(1 for cid in claims if T(cid) is not None
         and Counter(x["verdict"] for x in by[(cid,"mismatch")]).most_common(1)[0][0] != "insufficient")
print(f"  -> on mismatched evidence it still ANSWERS (not 'insufficient') on {mc}/{len(fact)} claims.")
flips = sum(1 for (cid,a),rs in by.items() if a=="choice" and len({x["verdict"] for x in rs})>1)
print(f"repeat-call flips: {flips}/{sum(1 for (c,a) in by if a=='choice')} claims")
random.seed(1)
print(f"random baseline  : ~{sum(1 for c in fact)/len(fact):.0%}  |  'always correct' baseline: {sum(1 for c in fact if c['truth'])}/{len(fact)} = {sum(1 for c in fact if c['truth'])/len(fact):.0%}")
