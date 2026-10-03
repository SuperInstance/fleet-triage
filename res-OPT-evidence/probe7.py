import sys
sys.path.insert(0,"/tmp/dspylibs"); sys.path.insert(0,"/workspace/projects/fleet-triage/repos/dspy"); sys.path.insert(0,"/tmp/optlab")
import dspy
from dspy.utils.dummies import DummyLM
from dspy.adapters.json_adapter import JSONAdapter
import app2 as A

def run(move_probs, move_conf, noul_p):
    d = A.Dungeon()
    d.pick.lm = DummyLM([{"move": {"probabilities": move_probs, "confidence": move_conf},
                         "can_act": {"noul": noul_p}}]*60, adapter=JSONAdapter())
    r = d(room="cell")
    return r.move.confidence, r.move.value, r.can_act.confidence, r.can_act.value, r.can_act.probability

print("=== F: is `confidence` CHECKED, or passed through from the chooser? ===")
P = {"north":0.5,"south":0.5}
for stated in [0.05, 0.5, 0.99]:
    mc, mv, nc, nv, np_ = run(P, stated, 0.5)
    print(f"  SAME distribution {P}, chooser STATES confidence={stated}"
          f" -> reported move.confidence={mc}, noul.confidence={nc} (derived), noul.value={nv} P={np_}")

print("\n  -> Choice.confidence is whatever the chooser said. Nothing correlates it to the distribution.")
print("  -> Noul.confidence is DERIVED: |p-threshold|/max(threshold,1-threshold) = 0.0 at p=0.5.")
print("  -> At p=0.5 DSPy still emits value=True. The uncertainty survives only as a number nobody must read.")

print("\n=== G: does an out-of-range confidence get caught? ===")
try:
    print("  ->", run(P, 5.0, 0.5)[0])
except Exception as e:
    print("  REJECTED ->", type(e).__name__, str(e)[:120])
