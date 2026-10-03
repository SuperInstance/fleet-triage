#!/usr/bin/env python3
"""mutation_test.py — is that acceptance suite vacuous?

A suite that passes proves the code runs.  It does not prove the suite constrains
the SEMANTICS.  So: break the implementation six different ways, each of which
keeps it running, keeps it plausible, and must turn the suite red.

  M1  allow correlation to downgrade a red  (the exact laundering failure)
  M2  n_witness := number of members       (the naive "5 votes" a canary makes)
  M3  collapse the distribution to argmax  (the "never collapse to a scalar" sin)
  M4  NFC-normalise option identity        (my first, wrong, design)
  M5  drop the closed-set check            (unknown options silently accepted)
  M6  CI exit code: REFUSED exits 0        (the tool wired in so scary == green)

  M1, M2, M3, M4, M5 break SEMANTICS and must be caught.
  M6 breaks WIRING, not semantics -- every verdict is still correct, but a tool
  that can be wired so a REFUSAL exits 0 has added the failure mode it was built
  to remove.  The suite catches that too, and both kinds count.
"""
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "panel_canary.py")

MUTANTS = [
    ("M1 correlation launders a red into a refusal",
     'return "VIOLATED", "no member names the pinned option; hard fail, unanimity or not"',
     'return "REFUSED-CORRELATED", "MUTANT: correlation laundered a red"'),
    ("M2 n_witness is just the headcount",
     "n, _sv, ceiling = n_witness(vectors)",
     "n, ceiling = float(len(vectors)), min(len(vectors), 5)"),
    ("M3 distribution collapsed to argmax",
     "return [v / total for v in vec]                    # never a scalar, always a vector",
     "return [1.0 if v == max(vec) else 0.0 for v in vec]  # MUTANT: argmax"),
    ("M4 option identity is NFC, not byte-exact",
     "idx = self._index.get(label)                  # byte-exact",
     "idx = self._index.get(_nfc(label))           # MUTANT: NFC identity"),
    ("M5 closed-set check removed",
     "if idx is None:                               # option outside the set\n                return None",
     "if idx is None:\n                idx = 0       # MUTANT: silently coerce"),
    ("M6 CI exit: REFUSED is green",
     'return {"CONFIRMED": 0, "REFUSED-CORRELATED": 1, "EMPTY": 1, "VIOLATED": 2}[v]',
     'return 0  # MUTANT: every verdict is green'),
]


def run(tmpdir, src_text, name):
    d = os.path.join(tmpdir, name.replace(" ", "_").replace("/", "_"))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "panel_canary.py"), "w") as fh:
        fh.write(src_text)
    with open(os.path.join(d, "demo.py"), "w") as fh:
        fh.write(open(os.path.join(HERE, "demo.py")).read())
    r = subprocess.run([sys.executable, "demo.py"], cwd=d,
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    original = open(SRC).read()
    with tempfile.TemporaryDirectory() as tmpdir:
        rc, out = run(tmpdir, original, "baseline")
        print(f"BASELINE  exit={rc}  {'PASS' if rc == 0 else 'FAIL'}")
        if rc != 0:
            print(out[-2000:])
            return 1
        print("\n" + "=" * 74)
        print("MUTATIONS — every one must turn the suite RED")
        print("=" * 74)
        killed, survived = [], []
        for name, find, repl in MUTANTS:
            if find not in original:
                print(f"  [ANCHOR-ROTTED] {name}  -- pattern not found, cannot test")
                survived.append(name)
                continue
            rc, _ = run(tmpdir, original.replace(find, repl, 1), name)
            if rc != 0:
                print(f"  [KILLED  ] {name}")
                killed.append(name)
            else:
                print(f"  [SURVIVED] {name}   <-- the suite does not constrain this")
                survived.append(name)
        print(f"\n  killed {len(killed)}/{len(MUTANTS)}   survived {len(survived)}")
        if survived:
            print("  SURVIVORS: " + "; ".join(survived))
        return 1 if survived else 0


if __name__ == "__main__":
    sys.exit(main())
