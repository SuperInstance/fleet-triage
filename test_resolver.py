"""Regression tests for the resolver's line-anchor attribution.

The bug this guards against (see RESOLVER-DEFECT.md) is the worst kind for a
claim-resolver: it made the tool confidently report that a file was wrong when
the document had made no claim about that file at all. It produced 3 of the 4
LINE_OOR findings on the first real corpus scan.

Run:  python3 test_resolver.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import resolver as R

FAILS: list[str] = []


def check(name: str, got, want) -> None:
    if got == want:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}\n          got  {got!r}\n          want {want!r}")
        FAILS.append(name)


def anchors(doc: str) -> dict[str, str]:
    """path -> 'a-b' | 'a' | '' for every citation in doc."""
    out = {}
    for c in R.extract_citations(doc, "test"):
        if c.line_b:
            out[c.path] = f"{c.line_a}-{c.line_b}"
        elif c.line_a:
            out[c.path] = str(c.line_a)
        else:
            out[c.path] = ""
    return out


# ── 1. THE REGRESSION. Verbatim from agent-messages/onboarding/
#       build_test_engineer_round6.md:150-155. One range, three paths.
LIST = """3. **Implementation**: `src/gpu/RateBasedChangeEngine.ts` (lines 1-977)
4. **GPU Engine**: `src/gpu/GPUEngine.ts`
5. **Sensation System**: `src/spreadsheet/core/Sensation.ts` (lines 1-580)"""

got = anchors(LIST)
check("range stays with its own item (1-977)", got.get("src/gpu/RateBasedChangeEngine.ts"), "1-977")
check("path with no claimed range stays unanchored", got.get("src/gpu/GPUEngine.ts"), "")
check("second range is not stolen by the first", got.get("src/spreadsheet/core/Sensation.ts"), "1-580")

# ── 2. The inline form must still work, or the fix over-corrected.
check("inline colon form", anchors("see `a/b/c.py:42` here").get("a/b/c.py"), "42")
check("inline colon range form", anchors("see `a/b/c.py:42-50` here").get("a/b/c.py"), "42-50")
check("prose form on its own line", anchors("`x.py` (line 437)").get("x.py"), "437")

# ── 3. Nearest wins, not first: the anchor AFTER the path must beat an
#       earlier one on the same line.
NEAR = "`a/one.py` was wrong; `a/two.py` (lines 20-30) is right"
g = anchors(NEAR)
check("nearest anchor wins when two are on one line", g.get("a/two.py"), "20-30")

# ── 4. A path on a line with no anchor anywhere must never get one.
check("no anchor on the line -> no anchor", anchors("`a/clean.py` is fine").get("a/clean.py"), "")

# ── 5. The anchor must not leak ACROSS a list boundary in either direction.
check(
    "no leak downward across a list item",
    anchors("1. `a/first.py` (lines 1-500)\n2. `a/second.py`").get("a/second.py"),
    "",
)
check(
    "no leak upward across a list item",
    anchors("1. `a/first.py`\n2. `a/second.py` (lines 1-500)").get("a/first.py"),
    "",
)

# ── 6. line_line_count must handle a missing trailing newline. This is the
#       hypothesis I had and was wrong about -- the counter was already
#       correct -- so it gets a test to keep it that way.
import tempfile
with tempfile.TemporaryDirectory() as d:
    with_nl = Path(d) / "with_nl.txt"
    with_nl.write_text("a\nb\nc\n")
    no_nl = Path(d) / "no_nl.txt"
    no_nl.write_text("a\nb\nc")  # no trailing newline
    empty = Path(d) / "empty.txt"
    empty.write_text("")
    check("trailing newline counted", R.file_line_count(with_nl), 3)
    check("MISSING trailing newline still counts its last line", R.file_line_count(no_nl), 3)
    check("empty file is 0, not None", R.file_line_count(empty), 0)

# ── 7. The control: a check that cannot fail is worse than no check.
#       Prove the test would have CAUGHT the original bug by reintroducing it.
_orig = R.LINE_PATTERNS
try:
    # The old behaviour, expressed as a shim over the same input.
    def _legacy(text: str, doc: str):
        out = {}
        for m in R.BACKTICK.finditer(text):
            content = m.group(1).strip()
            if not content or " " in content:
                continue
            if not (R.PATHLIKE.match(content) or R.BARE_FILE.match(content)):
                continue
            win = text[max(0, m.start() - 140): m.end() + 140]
            for pat in _orig:
                lm = pat.search(win)
                if lm:
                    out[content] = lm.group(0)
                    break
        return out

    legacy = _legacy(LIST, "test")
    check(
        "NEGATIVE CONTROL: the old code really did leak 977",
        legacy.get("src/gpu/GPUEngine.ts", "").find("977") != -1,
        True,
    )
finally:
    R.LINE_PATTERNS = _orig

print()
if FAILS:
    print(f"  {len(FAILS)} FAILED: {FAILS}")
    sys.exit(1)
print("  all resolver anchor tests pass")
