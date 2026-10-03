#!/usr/bin/env python3
"""demo.py — the acceptance criterion, executed. Constructed panels, real output.

The canary is the one from CANARY-FICTION.md: FNV-1a-64 of "café Δ 日本語" in
UTF-8/NFC = 0x24a555471370b18d.  Its option set is the set of plausible things a
text-normalising pipeline could have handed the hash function instead.

Every non-canon option is built PROGRAMMATICALLY, never written as a literal.
A literal is how this file's first version produced two visually identical
strings that collided in a dict and kept the pin green on the wrong bytes.
"""
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from panel_canary import Canary, show, ci_exit  # noqa: E402

CANON = unicodedata.normalize("NFC", "café Δ 日本語")
NFD = unicodedata.normalize("NFD", CANON)
UNACCENTED = "".join(c for c in NFD if not unicodedata.combining(c))
NOSPACE = CANON.replace(" ", "")
DELTA = CANON.replace("Δ", "Delta")
LOWER = CANON.lower()
LABELS = [CANON, NFD, UNACCENTED, NOSPACE, DELTA, LOWER,
          UNACCENTED.replace(" ", "")]

BOM = CANON + "﻿"   # canon + BOM. Looks identical. Is NOT in the option set.

CANARY = Canary("fnv1a64-cafe", LABELS, pin=0)
PIN = CANARY.pin


def choice(d):
    """A JEV `choice` response: probabilities keyed by LABEL."""
    return {"type": "choice", "choice": max(d, key=d.get),
            "confidence": 0.98, "probabilities": d}


def spread(doubt, amount=0.10):
    """A panel member confident about the pin, doubtful in direction `doubt`."""
    d = {o: 0.0 for o in LABELS}
    d[CANON] = 1.0 - amount
    d[doubt] = amount
    return choice(d)


# ---- PANEL A: correlated. 5 ports, the same function, the same data, so the
# same distribution. This is the eleven-months-green panel from the fiction.
A = [choice({CANON: 0.97, NFD: 0.02, UNACCENTED: 0.01}) for _ in range(5)]

# ---- PANEL B: independent. Same canary, green for all five, but each member
# carries doubt in a direction none of the others have. Same verdict on the
# value, DIFFERENT structure.
B = [spread(NFD), spread(UNACCENTED), spread(NOSPACE), spread(DELTA), spread(LOWER)]

# ---- PANEL C: correlated AND WRONG. The normalising tool already ran. Five
# ports, unanimous, all confidently reporting the decomposed string. This is
# the case a refusal must NOT be able to launder.
C = [choice({NFD: 0.97, CANON: 0.02, UNACCENTED: 0.01}) for _ in range(5)]

# ---- PANEL D: the JEV `score` shape, whose probabilities are keyed by LEVEL
# INDEX and need the legend read to be meaningful at all. If this scores the
# same as A, the legend rebasing is real and not cosmetic.
D = [{"type": "score", "score": 0.02, "confidence": 0.35,
      "legend": {str(i): o for i, o in enumerate(LABELS)},
      "probabilities": {"0": 0.97, "1": 0.02, "2": 0.01}} for _ in range(5)]

# ---- PANEL E: a noul. No distribution. Refused at the door.
E = [{"type": "noul", "noul": 0.99}]

# ---- PANEL F: the real silent collision, in the `score` shape. The legend maps
# two level indices onto the SAME label — a level list with the same string
# pasted in twice. Two levels merged into one, no error anywhere. Refused.
F = [{"type": "score", "score": 0.02, "legend": {"0": CANON, "1": CANON},
      "probabilities": {"0": 0.97, "1": 0.02}} for _ in range(5)]

# ---- PANEL G: an option outside the closed set. The canary does not accept
# assertions about strings it never declared.
G = [choice({CANON: 0.9, "café Δ 日本語 with a BOM": 0.1}) for _ in range(5)]

# ---- PANEL H: NFC and NFD named TOGETHER, which is the whole subject of the
# canary. Under byte-exact identity these are two distinct options and the
# distribution is accepted. This is the case the first version of this file
# could not express at all.
H = [choice({CANON: 0.90, NFD: 0.10})]

# ---- PANEL I: an option OUTSIDE the closed set, and it is the TOP assertion.
# This is the load-bearing case for the closed-set guard: coerce the unknown
# option onto the pin and the canary goes GREEN on a string it never declared.
# Removing the guard is then a laundering path, not a dead branch.
I = [choice({BOM: 0.90, NFD: 0.10}) for _ in range(5)]

if __name__ == "__main__":
    print("=" * 78)
    print("CANARY x n_eff — n_witness: how many INDEPENDENT witnesses back a green?")
    print("=" * 78)
    print(f"canary      : {CANARY.key}")
    print(f"option set  ({len(LABELS)} options, residual dim {len(LABELS)-1}):")
    for i, o in enumerate(LABELS):
        print(f"   [{i}]{'*' if i == PIN else ' '} {o!r}")
    print(f"pin         : [{PIN}] {CANON!r}")
    print("k (required): 3")
    print(f"identity floor: {CANARY.identity_floor() or 'none — no normalization collapses it'}")
    print()

    vA = show("PANEL A  correlated — 5 ports, identical distribution", CANARY, A)
    vB = show("PANEL B  independent — 5 members, doubt in 5 directions", CANARY, B)
    vC = show("PANEL C  correlated AND WRONG — normalising tool already ran", CANARY, C)
    vD = show("PANEL D  correlated, `score` shape (legend-keyed probabilities)", CANARY, D)
    vE = show("PANEL E  noul — no distribution to measure", CANARY, E)
    vF = show("PANEL F  `score` legend merging two levels onto one label", CANARY, F)
    vG = show("PANEL G  option outside the closed set", CANARY, G)
    vH = show("PANEL H  NFC and NFD named together — the canary's whole subject",
              CANARY, H)
    vI = show("PANEL I  undeclared option as the TOP assertion (BOM)",
              CANARY, I)

    print("\n" + "=" * 78)
    print("ACCEPTANCE")
    print("=" * 78)
    import panel_canary as pc
    nA = pc.n_witness([CANARY.parse(a) for a in A])[0]
    nB = pc.n_witness([CANARY.parse(a) for a in B])[0]
    checks = [
        ("A correlated green panel is REFUSED (green is not evidence)",
         vA == "REFUSED-CORRELATED"),
        ("B independent green panel is CONFIRMED (it is evidence)", vB == "CONFIRMED"),
        ("A and B disagree on verdict despite BOTH being green on the canary",
         vA != vB),
        (f"structure separates them ({nA:.2f} < {nB:.2f}), not just the outcome",
         nB > nA),
        ("C unanimous-WRONG is VIOLATED, not laundered into a refusal", vC == "VIOLATED"),
        ("D `score`-shape correlates the same as A `choice`-shape", vD == vA),
        ("E noul is refused at the door", vE == "EMPTY"),
        ("F a legend merging two levels is refused, not silently merged", vF == "EMPTY"),
        ("G an option outside the closed set is refused", vG == "EMPTY"),
        ("I an UNDECLARED option cannot be the witness that greens the canary",
         vI == "EMPTY"),
        ("H NFC and NFD are DISTINCT options — the canary can see the difference",
         vH != "EMPTY" and CANARY.parse(H[0])[0] != CANARY.parse(H[0])[1]),
        ("the canary declares an identity floor some normalizer would cross",
         CANARY.identity_floor() is not None),
        ("correlation NEVER downgrades a red into a non-red", vC == "VIOLATED"),
        ("only CONFIRMED exits 0 in CI — a refusal is BLOCKING, not green",
         ci_exit(vB) == 0 and ci_exit(vA) == 1 and ci_exit(vC) == 2
         and ci_exit(vE) == 1),
    ]
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    failed = [l for l, ok in checks if not ok]
    print(f"\n  {len(checks) - len(failed)}/{len(checks)} checks pass")
    print(f"  CI exit for this run's worst verdict: {max(ci_exit(v) for v in (vA, vB, vC, vD, vE, vF, vG, vH, vI))}")
    sys.exit(1 if failed else 0)
