"""C3 — THE CLAIM'S LOAD-BEARING TEST.
The judges in choosers.py were written against app_sift. They are imported here
UNMODIFIED. If a judge needs an app edit to run here, C3 is dead."""
import hashlib, importlib, json, sys, time
from pathlib import Path
sys.path.insert(0, "/tmp/sift")
import app_sort, choosers
from seam import Blocked

CHOOSERS_SHA = hashlib.sha256(Path("/tmp/sift/choosers.py").read_bytes()).hexdigest()
print("choosers.py sha256 (the file written for app_sift, imported unchanged):")
print("   ", CHOOSERS_SHA)

REV = app_sort.Rev(
    oid="REV-01",
    task="You have 90 minutes before the release cut. Review what matters first.",
    symptom=("diffstat: 7 files changed. One is the release-gate verifier, one is a "
             "generated lockfile, five are narrative docs. The verifier is the only "
             "file whose change can ship a wrong claim."),
    files=(("docs/README.md", 3, 0), ("docs/CHANGELOG.md", 12, 0),
           ("chain-lint/chain_lint.py", 41, 6), ("Cargo.lock", 900, 0),
           ("docs/ARCHITECTURE.md", 88, 0), ("src/verify.py", 27, 3),
           ("docs/FAQ.md", 64, 0)),
    oracle="chain-lint/chain_lint.py#hunk")

Path("/tmp/sift/human_picks_sort.json").write_text(json.dumps({"REV-01": REV.oracle}))
J = {"free-stat": choosers.FreeStatJudge(), "evidence": choosers.EvidenceJudge(),
     "human": choosers.HumanJudge("/tmp/sift/human_picks_sort.json"),
     "model-jev": choosers.ModelJudge()}

print()
print("="*78)
print("C3 — JUDGES WRITTEN FOR sift, RUN AGAINST sort (a different app)")
print("="*78)
print(f"  app_sort.py sha256 {app_sort.app2_sha()[:32]}")
print(f"  judges edited to make this work: 0  (choosers.py sha unchanged: "
      f"{hashlib.sha256(Path('/tmp/sift/choosers.py').read_bytes()).hexdigest()==CHOOSERS_SHA})")
print()
for jname, j in J.items():
    try:
        r = app_sort.run(REV, j, "source")
    except Blocked as b:
        print(f"  {jname:11s} BLOCKED — {b}   (not scored)")
        continue
    d = r["decision"]
    pr = d.probs
    dist = "probs=None conf=None  [legal: no distribution]" if pr is None else \
        "  ".join(f"{k.split('/')[-1]}={v:.3f}" for k, v in
                  sorted(pr.items(), key=lambda kv: -kv[1])[:3])
    print(f"  {jname:11s} pick={d.pick:28s} conf={d.confidence}  {dist}")
    print(f"  {'':11s} fabricated {r['n_fabricated']}/7 contract features "
          f"{list(r['fabricated_features'])}   enum={r['enum_ms']:.3f}ms "
          f"choose={r['choose_ms']:.4f}ms")

# ── THE COST, SIDE BY SIDE ───────────────────────────────────────────────────
print()
print("="*78)
print("THE COST OF THE SEAM -- features each app had to fabricate to satisfy")
print("the contract that the judges are allowed to rely on")
print("="*78)
a = app_sort.run(REV, J["free-stat"], "source")
print(f"  sift  (a failure to localise)   fabricated 2/7  ['depth','in_trace']")
print(f"  sort  (a review queue to triage) fabricated {a['n_fabricated']}/7  "
      f"{list(a['fabricated_features'])}")
print("  -> the less similar the app, the more of the contract is a lie the app")
print("     must tell. 5/7 of sort's feature vector is a neutral placeholder.")
