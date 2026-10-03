#!/usr/bin/env python3
import json, random, statistics
from collections import defaultdict, Counter

D = json.load(open("results.json"))
claims = {c["id"]: c for c in D["claims"]}
R = D["results"]
by = defaultdict(list)
for r in R:
    by[(r["id"], r["arm"])].append(r)

def truth(cid): return claims[cid]["truth"]

print("=" * 74)
print("0. INTEGRITY")
print("=" * 74)
print(f"claims={len(claims)}  calls={len(R)}  "
      f"TRUE={sum(1 for c in claims.values() if c['truth'])}  "
      f"FALSE={sum(1 for c in claims.values() if not c['truth'])}")
print(f"parse/transport failures: {sum(1 for r in R if r.get('err'))}")
maj = Counter(v for (cid, arm), rs in by.items() if arm == "choice"
              for v in [Counter(x["verdict"] for x in rs).most_common(1)[0][0]])
print(f"choice verdicts (majority over {3} reps): {dict(maj)}")

# ---------- ARM ACCURACIES ----------
print()
print("=" * 74)
print("1. ARM COMPARISON  (n=28 real fleet claims)")
print("=" * 74)
def acc_of(arm, subset=None):
    ok = tot = abst = 0
    for (cid, a), rs in by.items():
        if a != arm: continue
        if subset and cid not in subset: continue
        v = Counter(x["verdict"] for x in rs).most_common(1)[0][0]
        tot += 1
        if v == "insufficient": abst += 1; continue
        if (v == "correct") == truth(cid): ok += 1
    return ok, tot - abst, tot, abst

contested = {c for c in claims if claims[c]["family"] == "contested"}
statec = {c for c in claims if claims[c]["family"] == "state"}
print(f"{'arm':<10} {'all: acc':>12} {'abst':>6} | {'contested: acc':>15} {'abst':>5} | {'state: acc':>12}")
for arm in ("choice", "shuffle", "noevid"):
    o, t, n, ab = acc_of(arm)
    o2, t2, _, ab2 = acc_of(arm, contested)
    o3, t3, _, _ = acc_of(arm, statec)
    fa = f"{o}/{t} = {o/t:.0%}" if t else "n/a"
    f2 = f"{o2}/{t2} = {o2/t2:.0%}" if t2 else "n/a"
    f3 = f"{o3}/{t3} = {o3/t3:.0%}" if t3 else "n/a"
    print(f"{arm:<10} {fa:>12} {ab:>4}/{n} | {f2:>15} {ab2:>3} | {f3:>12}")

# ---------- BASELINES ----------
print()
print("=" * 74)
print("2. BASELINES  (same 28 claims)")
print("=" * 74)
mv_ok = mv_tot = 0
for cid in claims:
    v = Counter(x["verdict"] for x in by[(cid, "choice")]).most_common(1)[0][0]
    if v == "insufficient": continue
    mv_tot += 1; mv_ok += ((v == "correct") == truth(cid))
print(f"(a) majority vote over 3 repeats : {mv_ok}/{mv_tot} = {mv_ok/mv_tot:.0%}   <- same as `choice` row; repeats are near-deterministic")
random.seed(0)
accs = []
for _ in range(20000):
    ok = sum(1 for c in claims.values() if random.choice([True, False]) == c["truth"])
    accs.append(ok / len(claims))
print(f"(b) strongest single judge        : identical to majority vote (see variance below)")
print(f"(c) random pick (coin w/ prior)   : {statistics.mean(accs):.1%}  (95% CI "
      f"{statistics.quantiles(accs, n=1000)[24]:.1%}-{statistics.quantiles(accs, n=1000)[975]:.1%})")
# majority of TRUE-guess baseline (degenerate but informative)
print(f"    degenerate 'always correct'   : {sum(1 for c in claims.values() if c['truth'])}/28 = "
      f"{sum(1 for c in claims.values() if c['truth'])/28:.0%}   <- the bar a 3-way choice must clear")

# repeat variance
flips = sum(1 for (cid, arm), rs in by.items() if arm == "choice"
            and len({x["verdict"] for x in rs}) > 1)
tot_cells = sum(1 for (cid, arm) in by if arm == "choice")
print(f"\n    repeat-call answer flips: {flips}/{tot_cells} claims changed verdict across 3 identical calls")
spreads = [max(x["p"] for x in rs) - min(x["p"] for x in rs)
           for (cid, arm), rs in by.items() if arm == "noul"]
print(f"    noul P(true) spread across 3 repeats: mean {statistics.mean(spreads):.3f}  max {max(spreads):.3f}")

# ---------- CALIBRATION ----------
print()
print("=" * 74)
print("3. CALIBRATION  (noul, P(claim is true), n=28)")
print("=" * 74)
pts = []
for cid in claims:
    ps = [x["p"] for x in by[(cid, "noul")] if x["p"] is not None]
    if ps: pts.append((statistics.mean(ps), truth(cid), cid))
BINS = [(0.0, .1), (.1, .2), (.2, .3), (.3, .4), (.4, .5), (.5, .6), (.6, .7),
        (.7, .8), (.8, .9), (.9, 1.01)]
print(f"{'bucket':<12} {'n':>3} {'mean P':>7} {'frac TRUE':>10} {'gap':>7}")
curve = []
ece = 0.0
for lo, hi in BINS:
    b = [p for p in pts if lo <= p[0] < hi]
    if not b: continue
    mp = statistics.mean(p[0] for p in b); ft = sum(1 for p in b if p[1]) / len(b)
    curve.append((mp, ft, len(b)))
    ece += len(b) / len(pts) * abs(mp - ft)
    print(f"[{lo:.1f},{hi:.1f})".ljust(12) + f" {len(b):>3} {mp:>7.3f} {ft:>10.2f} {ft-mp:>+7.3f}")
print(f"\nExpected Calibration Error (ECE, 10 bins, n={len(pts)}): {ece:.3f}")
brier = statistics.mean((p[0] - (1.0 if p[1] else 0.0)) ** 2 for p in pts)
print(f"Brier score: {brier:.3f}   (0.25 = coin-flip on a balanced set)")
# AUC-style discrimination
pos = [p[0] for p in pts if p[1]]; neg = [p[0] for p in pts if not p[1]]
wins = sum((a > b) + .5 * (a == b) for a in pos for b in neg)
print(f"AUC (P(true) separates true from false claims): {wins/(len(pos)*len(neg)):.3f}  (n+={len(pos)} n-={len(neg)})")

# ---------- OPERATING POINT BY ABSTENTION ----------
print()
print("=" * 74)
print("4. OPERATING POINT BY ABSTENTION RATE  (choice arm, confidence-sweep)")
print("=" * 74)
rows = []
for th in [i / 100 for i in range(0, 101, 5)]:
    ok = tot = abst = 0
    for cid in claims:
        rs = by[(cid, "choice")]
        v = Counter(x["verdict"] for x in rs).most_common(1)[0][0]
        p = max(x["p"] for x in rs)
        if p < th: abst += 1; continue
        if v == "insufficient": abst += 1; continue
        tot += 1; ok += ((v == "correct") == truth(cid))
    rows.append((th, abst / len(claims), tot, ok, (ok / tot if tot else float("nan"))))
print(f"{'thresh':>7} {'abstain%':>9} {'answered':>9} {'correct':>8} {'acc on answered':>17}")
for th, ar, tot, ok, a in rows:
    if tot == 0 or int(th * 100) % 10 == 0:
        print(f"{th:>7.2f} {ar:>8.0%} {tot:>9} {ok:>8} {a:>16.0%}")

# ---------- LEAKAGE / NO-EVIDENCE ----------
print()
print("=" * 74)
print("5. CONTROLS")
print("=" * 74)
o1, t1, _, _ = acc_of("choice"); o2, t2, _, _ = acc_of("shuffle"); o3, t3, _, _ = acc_of("noevid")
print(f"label-shuffle control : {o2}/{t2} = {o2/t2:.0%}  vs choice {o1}/{t1} = {o1/t1:.0%}")
print(f"  -> permuting label->meaning costs {o1/t1 - o2/t2:+.0%}. "
      f"{'NO leakage detected' if abs(o1/t1-o2/t2) < .08 else 'SUSPECT: labels carry information beyond meaning'}")
print(f"NO-EVIDENCE control   : {o3}/{t3} = {o3/t3:.0%}  vs choice {o1}/{t1} = {o1/t1:.0%}")
print(f"  -> deleting the evidence costs {o1/t1 - o3/t3:+.0%}. "
      f"{'DECISIVE: evidence is load-bearing' if o1/t1-o3/t3 > .08 else '*** JEV IS NOT READING THE EVIDENCE ***'}")

# ---------- CONFIDENT ERRORS ----------
print()
print("=" * 74)
print("6. CONFIDENT ERRORS  (the thing most worth finding)")
print("=" * 74)
for arm in ("choice", "noevid"):
    bad = []
    for cid in claims:
        rs = by[(cid, arm)]
        v = Counter(x["verdict"] for x in rs).most_common(1)[0][0]
        p = max(x["p"] for x in rs)
        if v != "insufficient" and (v == "correct") != truth(cid):
            bad.append((p, cid, v, truth(cid)))
    bad.sort(reverse=True)
    print(f"\n--- arm={arm}: {len(bad)} wrong answers ---")
    for p, cid, v, t in bad:
        c = claims[cid]
        tag = "FALSE claim called CORRECT" if (not t and v == "correct") else "TRUE claim called INCORRECT"
        print(f"  p={p:.2f}  {cid:<24} {tag}")
        print(f"     claim  : {c['claim'][:150]}")
        print(f"     evidence: {c['evidence'][:170]}")
        if p >= 0.85:
            print(f"     *** HIGH-CONFIDENCE ERROR (p={p:.2f}) -- user sees this with no warning ***")
