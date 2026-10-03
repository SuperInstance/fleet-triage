import hashlib, json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, "/tmp/sift")
import app_sift, choosers
from seam import Blocked

OBS = json.loads(Path("/tmp/sift/observations.json").read_text())
for o in OBS:
    o["trace"] = tuple(json.loads(o["trace"]))   # stored json-encoded in obs_build

# ── TEST 1: THE APP DOES NOT CHANGE WHEN THE JUDGE DOES ──────────────────────
SNAP = Path("/tmp/sift/_snapshot")
if SNAP.exists(): shutil.rmtree(SNAP)
SNAP.mkdir()
for f in ("seam.py", "app_sift.py"):
    shutil.copy2(f"/tmp/sift/{f}", SNAP / f)
SHA_BEFORE = {f: hashlib.sha256((SNAP/f).read_bytes()).hexdigest() for f in ("seam.py","app_sift.py")}

JUDGES = {
    "free-stat":  choosers.FreeStatJudge(),
    "evidence":   choosers.EvidenceJudge(),
    "human":      None,          # built below
    "model-jev":  choosers.ModelJudge(),
}
Path("/tmp/sift/human_picks.json").write_text(json.dumps(
    {o["oid"]: o["oracle"] for o in OBS}, indent=2))
JUDGES["human"] = choosers.HumanJudge("/tmp/sift/human_picks.json")

STYLES = ("source", "sig")
rows, blocked = [], []
for style in STYLES:
    for jname, J in JUDGES.items():
        for o in OBS:
            obs = app_sift.Obs(oid=o["oid"], task=o["task"], symptom=o["symptom"],
                               module=o["module"], trace=o["trace"],
                               oracle=o["oracle"], tier=o["tier"])
            t0 = time.perf_counter()
            try:
                r = app_sift.run(obs, J, style)
            except Blocked as b:
                blocked.append({"judge": jname, "oid": o["oid"], "reason": str(b)})
                continue
            wall = (time.perf_counter() - t0) * 1000
            truth = o["oracle"]
            ids = [opt.id for opt in app_sift.enumerate_sites(obs)]
            rank = ids.index(truth) + 1 if truth in ids else None
            pick = r["decision"].pick
            pick_rank = ids.index(pick) + 1 if pick in ids else None
            lift = (r["decision"].confidence * r["n_options"]) if r["decision"].confidence else None
            rows.append({
                "style": style, "judge": jname, "oid": o["oid"], "tier": o["tier"],
                "n_options": r["n_options"], "n_fabricated": r["n_fabricated"],
                "fabricated": list(r["fabricated_features"]),
                "pick": pick, "truth": truth,
                "hit": (pick == truth), "truth_rank": rank, "pick_rank": pick_rank, "lift": lift,
                "confidence": r["decision"].confidence,
                "probs": r["decision"].probs,
                "n_probs": (len(r["decision"].probs) if r["decision"].probs else 0),
                "enum_ms": r["enum_ms"], "choose_ms": r["choose_ms"], "wall_ms": wall,
            })

SHA_AFTER = {f: hashlib.sha256(Path(f"/tmp/sift/{f}").read_bytes()).hexdigest()
             for f in ("seam.py","app_sift.py")}
diff = subprocess.run(["diff","-u",str(SNAP/"app_sift.py"),"/tmp/sift/app_sift.py"],
                      capture_output=True, text=True)
diff2 = subprocess.run(["diff","-u",str(SNAP/"seam.py"),"/tmp/sift/seam.py"],
                       capture_output=True, text=True)

print("="*78)
print("TEST 1 — APP DIFF ON JUDGE SWAP")
print("="*78)
for f in ("seam.py","app_sift.py"):
    print(f"  {f:14s} before {SHA_BEFORE[f][:32]}  after {SHA_AFTER[f][:32]}  "
          f"{'IDENTICAL' if SHA_BEFORE[f]==SHA_AFTER[f] else '*** CHANGED ***'}")
print("  ---- diff -u _snapshot/app_sift.py app_sift.py  (verbatim) ----")
print(diff.stdout.rstrip() or "  <no output>")
print("  ---- diff -u _snapshot/seam.py seam.py  (verbatim) ----")
print(diff2.stdout.rstrip() or "  <no output>")
print(f"  app diff = {len(diff.stdout.strip().splitlines())} lines; "
      f"seam diff = {len(diff2.stdout.strip().splitlines())} lines")

print()
print("="*78); print("TEST 2 — WHAT THE APP GAVE UP TO GET THE SEAM"); print("="*78)
fab = {}
for r in rows:
    if r["n_fabricated"]: fab.setdefault((r["oid"], r["tier"]), set()).update(r["fabricated"])
for (oid, tier), ks in sorted(fab.items()):
    print(f"  {oid} (tier {tier}): app had to FABRICATE {sorted(ks)} "
          f"= {len(ks)}/7 contract features with a neutral value")
print(f"  total fabricated feature-values per decision: "
      f"{sum(r['n_fabricated'] for r in rows)} across {len(rows)} runs "
      f"({sum(r['n_fabricated'] for r in rows)/max(1,len(rows)):.1f} per run)")

print()
print("="*78); print("TEST 3 — PER-DECISION COST, BY JUDGE"); print("="*78)
print(f"  {'judge':11s} {'runs':>5s} {'net':>4s} {'tok_in':>7s} {'tok_out':>8s} "
      f"{'enum_ms':>8s} {'choose_ms':>10s} {'conf':>6s} {'probs':>6s}")
for jname in JUDGES:
    rs = [r for r in rows if r["judge"] == jname]
    nb = len([b for b in blocked if b["judge"] == jname])
    if not rs:
        print(f"  {jname:11s} {0:5d} {nb:4d}  UNMEASURED -- {blocked[0]['reason'] if blocked else ''}")
        continue
    conf = [r["confidence"] for r in rs if r["confidence"] is not None]
    print(f"  {jname:11s} {len(rs):5d} {nb:4d} {'0':>7s} {'0':>8s} "
          f"{sum(r['enum_ms'] for r in rs)/len(rs):8.3f} "
          f"{sum(r['choose_ms'] for r in rs)/len(rs):10.4f} "
          f"{(sum(conf)/len(conf) if conf else float('nan')):6.3f} "
          f"{(sum(r['n_probs'] for r in rs)/len(rs)):6.1f}")

print()
print("="*78); print("TEST 4 — ACCURACY AGAINST THE ORACLE (source render)"); print("="*78)
print(f"  {'judge':11s} " + " ".join(f"{o['oid']:>7s}" for o in OBS) +
      f" {'TOP1':>6s} {'MRR':>6s}")
scores = {}
for jname in JUDGES:
    cells, hits, mrr = [], 0, 0.0
    for o in OBS:
        r = next((x for x in rows if x["judge"]==jname and x["oid"]==o["oid"]
                  and x["style"]=="source"), None)
        if r is None: cells.append("  BLOCK"); continue
        cells.append(("  HIT" if r["hit"] else f"  #{r['truth_rank'] or '-'}").rjust(7))
        hits += r["hit"]
    n = sum(1 for c in cells if "BLOCK" not in c)
    for o in OBS:
        r = next((x for x in rows if x["judge"]==jname and x["oid"]==o["oid"]
                  and x["style"]=="source"), None)
        if r and r["pick_rank"]: mrr += 1.0/r["pick_rank"]
    tag = "  <- UNSCORED: I wrote this key" if jname=="human" else ""
    scores[jname] = (hits/n if n else float("nan"), mrr/n if n else float("nan"))
    print(f"  {jname:11s} " + " ".join(c.rjust(7) for c in cells) +
          f" {hits}/{n:<4d} {mrr/n if n else 0:6.3f}{tag}")
print("  #HIT = picked the documented root cause; #k = the truth sat at rank k and was missed.")

print()
print("="*78); print("TEST 5 — DID THEY DISAGREE? (full distributions, never a scalar)")
print("="*78)
for o in OBS:
    print(f"\n  {o['oid']} (tier {o['tier']})  {o['n_options'] if 'n_options' in o else ''}"
          f"  truth = {o['oracle']}")
    picks = {}
    for jname in JUDGES:
        r = next((x for x in rows if x["judge"]==jname and x["oid"]==o["oid"]
                  and x["style"]=="source"), None)
        if r is None:
            print(f"    {jname:11s} BLOCKED (not scored)"); continue
        picks[jname] = r["pick"]
        pr = r["probs"]
        if pr is None:
            print(f"    {jname:11s} pick={r['pick']}  probs=None  confidence=None"
                  f"   [a legal answer with no distribution]")
        else:
            top = sorted(pr.items(), key=lambda kv: -kv[1])[:3]
            s = "  ".join(f"{k.split('::')[-1]}={v:.3f}" for k, v in top)
            print(f"    {jname:11s} pick={r['pick'].split('::')[-1]}  "
                  f"conf={r['confidence']:.3f}  {s}")
    agree = len(set(picks.values())) == 1
    print(f"    -> {'AGREE' if agree else 'DISAGREE'} on {len(set(picks.values()))} distinct picks")

Path("/tmp/sift/results.json").write_text(json.dumps(
    {"rows": rows, "blocked": blocked, "scores": scores,
     "sha_before": SHA_BEFORE, "sha_after": SHA_AFTER,
     "diff_lines": len(diff.stdout.strip().splitlines())}, indent=2, default=str))
print(f"\nwrote results.json  ({len(rows)} scored runs, {len(blocked)} blocked)")
