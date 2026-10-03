import sys, hashlib, json
sys.path.insert(0, "/tmp/dspylibs"); sys.path.insert(0, "/workspace/projects/fleet-triage/repos/dspy"); sys.path.insert(0, "/tmp/optlab")
import dspy
from dspy.utils.dummies import DummyLM
from dspy.adapters.json_adapter import JSONAdapter
import app2 as A
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()

STAT = [{"move": {"probabilities":{"north":0.9,"south":0.1},"confidence":0.8},
         "can_act": {"noul": 0.99}}]*80
JUDGE = [{"move": {"probabilities":{"north":0.45,"south":0.55},"confidence":0.35},
          "can_act": {"noul": 0.50}}]*80

print("=== E1: THREE different choosers behind ONE app file ===")
before = sha("/tmp/optlab/app2.py")
results = {}
for name, pay in [("free statistic (DummyLM, no net, no key, no GPU)", STAT),
                  ("judgment model, 0.45/0.55 split, confidence 0.35", JUDGE)]:
    d = A.Dungeon(); d.pick.lm = DummyLM(pay, adapter=JSONAdapter())
    r = d(room="a damp cell with one exit north")
    results[name] = r
    print(f"\n  chooser: {name}")
    print("    move      =", r.move, " conf =", r.move.confidence)
    print("    can_act   =", r.can_act, " P(True) =", r.can_act.probability, " conf =", r.can_act.confidence)
after = sha("/tmp/optlab/app2.py")
print("\n  app2.py sha256 before :", before)
print("  app2.py sha256 after  :", after)
print("  APP DIFF ON SWAP      :", "ZERO" if before==after else "NONZERO")
json.dump({k: {"move": str(v.move), "move_conf": v.move.confidence,
               "can_act": str(v.can_act), "can_act_p": v.can_act.probability,
               "can_act_conf": v.can_act.confidence} for k,v in results.items()},
          open("/tmp/optlab/swaps.json","w"), indent=2)
