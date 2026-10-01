#!/usr/bin/env python3
"""
resolver_selftest.py — positive and negative controls for resolver.py.

A resolver that flags everything is worthless and a resolver that flags
nothing is worse. Every check below states, in advance, whether the line
SHOULD fire. The playtest lane's negative control over-fired four times
before it passed; this is the same discipline applied to claim resolution.

Run:  python3 resolver_selftest.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import resolver as R  # noqa: E402

CASES = [
    # ---- NUMERIC: true claims must NOT fire -------------------------------
    ("num-true-frac",
     r"The ratio is $\frac{2}{\sqrt{3}} \approx 1.155$ per unit area.", 0),
    ("num-true-frac2",
     r"we have $\frac{1}{2} = 0.5$ exactly, and $\frac{2}{\sqrt{3}} \approx 1.155$.", 0),
    ("num-true-arith", "59841/10428 = 5.74", 0),
    ("num-true-ratio",
     "produces triples with 5.74x higher density than Pythagorean triples "
     "at the same bound (59,841 vs 10,428).", 0),
    # ---- NUMERIC: false claims MUST fire ----------------------------------
    ("num-false-arith", "59841/10428 = 6.8", 1),
    ("num-false-approx", "59841/10428 \\approx 6.8", 1),
    ("num-false-sqrt", r"$\frac{2}{\sqrt{3}} = 2.0$", 1),
    ("num-false-ratio",
     "produces triples with 6.8x higher density than Pythagorean triples "
     "at the same bound (59,841 vs 10,428).", 1),
    # ---- NUMERIC: near-misses that LOOK like the above --------------------
    ("num-fp-runlabel", "run 1 = 16/18 pairs within 1 level; run 2 = 18/18.", 0),
    ("num-fp-ranklabel", "- **P4 mean label rank 2.0 (random 1.5; rank-3 = 24/64)**", 0),
    ("num-fp-exponent", r"$\tau^2 = 1/4$", 0),
    ("num-fp-tau", r"At $\tau = 1/2$, the distribution is $p_i$.", 0),
    ("num-fp-two-metrics",
     "On GPU, **Qwen wins both speed (2.33x) AND quality (12.4 vs 11.8).**", 0),
    ("num-fp-conjunction",
     "beats the reported regression (0.0153 vs 0.0206) and out-correlates it 4.5x", 0),
    ("num-fp-prose", r"since $\bar{c}(1-\bar{c}) \leq \frac{1}{4}$ by AM-GM, with equality", 0),
    # ---- NUMERIC: unit / percent / partial-expression conversions ---------
    ("num-fp-percent", "Overlap: 4/15 = 27%", 0),
    ("num-fp-percent2", "The Mandelbrot Fraction is **8/20 = 40%**.", 0),
    ("num-fp-percent3", "occupancy = 1536/1536 = 100% (register-bound)", 0),
    ("num-fp-unit", "- At 20kHz, lambda \u2248 343/20000 \u2248 17mm", 0),
    ("num-fp-partial",
     "$$N(\u03b1+\u03b2) \\leq 49 + 49 + 2 \\times 49 \\times \\frac{4}{3} = 98 + 130.6$$", 0),
    ("num-fp-round", "// Precision: 1/32768 \u2248 0.000031", 0),
    ("num-fp-precedence", "But consider all 14\u00d713/2 = 91 pairs.", 0),
]

# ---- CITATION extraction controls ----------------------------------------
CITE_CASES = [
    # (line, expected_path, expected_line_a, expected_symbol)
    ("The PTT (`murmur/transforms/rubiks.py`) implements a tensor.",
     "murmur/transforms/rubiks.py", None, ""),
    ("The layer count function from `rubiks.py` (line 437):",
     "rubiks.py", 437, ""),
    ("In the `propagate_change` method of `PermutationTensor` (line 295 of `permutation.py`):",
     "permutation.py", 295, None),   # both symbols are candidates
    ("(confirmed in `update_certainty` at line 281 of `rubiks.py`)",
     "rubiks.py", 281, "update_certainty"),
    ("see `src/api/middleware.ts:15-30` for details",
     "src/api/middleware.ts", 15, ""),
    ("run `npm run build` then deploy", None, None, None),   # not a path
    ("the value `3.14` and `v2.0` are constants", None, None, None),
]


def main() -> int:
    failures = []
    print("NUMERIC CONTROLS")
    print("-" * 78)
    for name, line, expect in CASES:
        got = len(R.extract_numeric_claims(line, "selftest.md"))
        ok = got == expect
        print(f"  [{'ok  ' if ok else 'FAIL'}] {name:22} expect {expect}  got {got}")
        if not ok:
            failures.append(name)

    print("\nCITATION EXTRACTION CONTROLS")
    print("-" * 78)
    for line, path, la, sym in CITE_CASES:
        cs = R.extract_citations(line, "selftest.md")
        if path is None:
            ok = len(cs) == 0
            got = f"{len(cs)} citations (want none)"
            want = "none"
        else:
            c = next((x for x in cs if x.path == path), None)
            sym_ok = sym in (None, "") or (c is not None and sym in (c.symbols or []))
            ok = c is not None and c.line_a == la and sym_ok
            got = (f"path={c.path} line={c.line_a} syms={c.symbols}" if c else "NOT FOUND")
            want = f"path={path} line={la} syms~={sym}"
        print(f"  [{'ok  ' if ok else 'FAIL'}] {line[:44]:46} {got}")
        if not ok:
            print(f"         want: {want}")
            failures.append(line[:40])

    print("\n" + "=" * 78)
    if failures:
        print(f"FAILED {len(failures)}/{len(CASES) + len(CITE_CASES)} controls: {failures}")
        return 1
    print(f"all {len(CASES) + len(CITE_CASES)} controls passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
