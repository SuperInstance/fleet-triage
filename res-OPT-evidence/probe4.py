import sys, hashlib, inspect
sys.path.insert(0, "/tmp/dspylibs"); sys.path.insert(0, "/workspace/projects/fleet-triage/repos/dspy")
import dspy
from dspy.clients.base_lm import BaseLM
from dspy.utils.dummies import DummyLM
from dspy.experimental import Choice
from dspy.adapters.json_adapter import JSONAdapter
from dspy.dsp.utils.settings import settings

Move = Choice[("north","go"),("south","back")]
class Shd(dspy.Signature):
    """Pick a move."""
    room: str = dspy.InputField(desc="A room.")
    m: Move = dspy.OutputField(desc="Which move.")

print("=== C4: a FREE STATISTIC as the chooser, via DSPy's own DummyLM shim ===")
stat = DummyLM([{"m": {"probabilities":{"north":0.9,"south":0.1},"confidence":0.8}}]*40, adapter=JSONAdapter())
print("   isinstance(stat, BaseLM):", isinstance(stat, BaseLM))
p = dspy.Predict(Shd); p.lm = stat
r = p(room="a damp cell")
print("   ACCEPTED. no network, no key, no GPU.")
print("   m =", r.m)

print("\n=== C6: swap two choosers, measure the APP diff (r3-SWAP test #1) ===")
import textwrap
open("/tmp/optlab/app.py","w").write(textwrap.dedent('''
    import dspy
    from dspy.experimental import Choice
    Move = Choice[("north","go"),("south","back")]
    class Dungeon(dspy.Module):
        def __init__(self):
            super().__init__()
            self.legal = ["north","south"]
            self.pick = dspy.Predict("room -> move")
        def forward(self, room):
            return self.pick(room=room)
'''))
sys.path.insert(0,"/tmp/optlab")
import app as appmod
def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()
a0 = sha("/tmp/optlab/app.py")
d1 = Dungeon = appmod.Dungeon(); d1.pick.lm = stat
d2 = appmod.Dungeon(); d2.pick.lm = DummyLM([{"move": {"probabilities":{"north":0.2,"south":0.8},"confidence":0.7}}]*40, adapter=JSONAdapter())
a1 = sha("/tmp/optlab/app.py")
print("   app.py sha256 before any swap:", a0[:32])
print("   app.py sha256 after 2 swaps :", a1[:32])
print("   APP DIFF ON CHOOSER SWAP    :", "ZERO" if a0==a1 else "NONZERO")
print("   chooser1 says:", d1(room="cell").pick, "| chooser2 says:", d2(room="cell").pick)
print("   module.set_lm() exists ->", hasattr(d1,'set_lm'), "| map_named_predictors ->", hasattr(d1,'map_named_predictors'))

print("\n=== C5: what does Compile mutate? ===")
from dspy.teleprompt import BootstrapFewShot
dspy.configure(lm=stat)
stu = dspy.Predict(Shd)
b = stu.dump_state()
trainset=[dspy.Example(room=f"room{i}", m="north").with_inputs("room") for i in range(4)]
comp = BootstrapFewShot(metric=lambda ex,pr,tr=None: float(pr.m.value==ex.m),
                        max_bootstrapped_demos=2, max_labeled_demos=2).compile(stu, trainset=trainset)
a = comp.dump_state()
print("   state keys identical:", sorted(b)==sorted(a), sorted(a))
print("   demos injected:", len(comp.demos), "(few-shot examples)")
print("   instructions rewritten:", b['signature'].get('instructions')!=a['signature'].get('instructions'))
print("   structure identical:", [n for n,_ in stu.named_parameters()]==[n for n,_ in comp.named_parameters()])
print("   LM object swapped by compile?:", stu.lm is comp.lm, "| stu.lm:", type(stu.lm).__name__)
print("   student left uncompiled:", getattr(stu,'_compiled',False), "| compiled flag on result:", comp._compiled)
