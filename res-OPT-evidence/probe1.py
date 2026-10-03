"""Res-OPT experiment 1: the ENUMERATION question, and the ABSTENTION question.
Runs against the cloned DSPy HEAD (stanfordnlp/dspy ba3f9198, v3.4.0). No network. No GPU."""
import sys, json, traceback
sys.path.insert(0, "/tmp/dspylibs")
sys.path.insert(0, "/workspace/projects/fleet-triage/repos/dspy")
import dspy
from dspy.experimental import Noul, Score, Choice

print("DSPy file:", dspy.__file__)

Color = Choice[("red", "warm"), ("green", "cool")]
print("Color criteria:", Color.criteria())

# --- A fake backend: returns whatever we tell it, including ILLEGAL label sets.
class FakeDecisionLM:
    supports_decision_requests = True
    def __init__(self, answers): self.answers = answers
    def dump_state(self): return {}
    @staticmethod
    def load_state(s, **k): return None
    def __call__(self, **req):
        print("   [wire] questions keys:", list(req["questions"].keys()))
        return {k: dict(v) for k, v in self.answers.items()}
    async def acall(self, **req): return self(**req)

class S(dspy.Signature):
    """What color is the barn?"""
    scene: str = dspy.InputField(desc="A scene.")
    c: Color = dspy.OutputField(desc="The color.")

print("\n=== A1: backend returns a legal, closed distribution ===")
lm_ok = FakeDecisionLM({"c": {"value": "red", "probabilities": {"red": 0.7, "green": 0.3}, "confidence": 0.6}})
p = dspy.Predict(S); p.lm = lm_ok
r = p(scene="a barn")
print("  value =", r.c, "| probabilities =", r.c.probabilities, "| confidence =", r.c.confidence)

print("\n=== A2: backend INVENTS a third option the signature never declared ===")
lm_gen = FakeDecisionLM({"c": {"value": "red",
          "probabilities": {"red": 0.5, "green": 0.2, "purple": 0.3}, "confidence": 0.4}})
p2 = dspy.Predict(S); p2.lm = lm_gen
try:
    r2 = p2(scene="a barn"); print("  ACCEPTED:", r2.c)
except Exception as e:
    print("  REJECTED ->", type(e).__name__, ":", e)

print("\n=== A3: can set_criteria / fields ADD an option to the enumeration? ===")
p3 = dspy.Predict(S)
for label, cfg in [("weights-extra", {"c": {"weights": {"purple": 2.0}}}),
                   ("criteria-extra", {"c": {"criteria": {"red": None, "green": None, "purple": None}}})]:
    try:
        p3.set_fields(**cfg) if hasattr(p3, "set_fields") else None
        st = dspy.adapters.decision_state.DecisionState(p3.signature, cfg["c"] and cfg)
    except Exception as e:
        print(f"  {label}: REJECTED -> {type(e).__name__}: {str(e)[:160]}")

print("\n=== B: can a Noul output DECLINE? ===")
N = Noul[(True, "blocked"), (False, "usable")]
class S2(dspy.Signature):
    """Is the customer blocked?"""
    msg: str = dspy.InputField(desc="A message.")
    blocked: N = dspy.OutputField(desc="Completely blocked?")
# backend is maximally unsure: 50/50
lm_unsure = FakeDecisionLM({"blocked": {"value": False, "noul": 0.5, "confidence": 0.0}})
q = dspy.Predict(S2); q.lm = lm_unsure
r3 = q(msg="hm")
print("  P(True) =", r3.blocked.probability, "-> value =", r3.blocked.value,
      "type =", type(r3.blocked.value).__name__, "| confidence =", r3.blocked.confidence)
print("  outcomes possible from Noul: True / False.  No third 'abstain' value exists in the schema.")
import inspect
print("  Noul.value annotation:", N.model_fields["value"].annotation)
