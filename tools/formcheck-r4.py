#!/usr/bin/env python3
"""formcheck-r4 — COUNT the form. Do not assert it.

Three lyrics, three checkable constraints, one report. Every number printed here
is computed from the lyric text at run time. Nothing is hard-coded as "passes".

  T1 halyard-and-ledger         call-and-response: count response lines, verify rhyme
  T2 nine-bars-to-town          12-bar: 3 choruses x 4 lines, every line opens "Nine bars"
  T3 one-hundredth-of-the-value  HARD FORM: exactly 8 syllables per line, no exceptions

Exit 0 = every constraint met. Exit 1 = at least one miss, and the miss list is
printed. A miss is a result, not a crash.
"""
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sylcount import line_syllables  # noqa: E402

# ---------------------------------------------------------------- lyrics ----

T1 = """\
[VERSE 1 — LEAD]
One sound is not a chart, and one sound is not a chart at all,
Two instruments or nothing, that's the whole of what we call.

[VERSE 1 — CREW]
So haul the single reading up, let the taut wire be the sound,
And when the second joins the line, both ends are on the ground.

[VERSE 2 — LEAD]
What survives is bounded by what the looking carried down,
Nothing downstream recovers what the looking never found.

[VERSE 2 — CREW]
So hold the ledger open, boys, and let the columns show,
The cell that kept the colour keeps the row that we must know.

[CHORUS — LEAD]
Hey, the trace is not the claim, the trace is not the claim!
Hey, the seal is on the file, it never touched the game!

[CHORUS — CREW]
One sound is not a chart, boys — one sound is not a chart,
Two instruments or nothing, or it never even starts.

[OUTRO — CREW]
Haul it up and call it sound. Haul it down and call it ground.
"""

T2 = """\
[VERSE 1]
The truck has a rattle, a dust on the rail,
And a nine-dollar night for the work of the whole,
And the radio's hum is a low, low hum,
And the county road runs like a ribbon of bone.

[CHORUS]
Nine bars and the ledger is closed
Nine bars and the number is whole
Nine bars and the value's exposed
Nine bars and the mile to the goal

[VERSE 2]
My father said the ledger and the road were the same,
Both of them are only what the looking claimed,
One says what was spent and the other where it went,
And the difference is a colour that the counting left.

[CHORUS]
Nine bars and the ledger is closed
Nine bars and the number is whole
Nine bars and the value's exposed
Nine bars and the mile to the goal

[VERSE 3]
She said the money's a season, and seasons are short,
And September is coming and I'm not the sort
To leave on a Sunday when the pull is the sum,
So I take what the road gives and I give back to none.

[CHORUS]
Nine bars and the ledger is closed
Nine bars and the number is whole
Nine bars and the value's exposed
Nine bars and the mile to the goal

[OUTRO]
Nine bars and the radio's low
Nine bars and the headlights are showing
Nine bars and the year's running out
Nine bars and the night is still growing
"""

# exactly 8 syllables, every line. Verified by the checker, not by assertion.
T3 = """\
[VERSE 1]
The colour is what you can see
The value is what you can read
Just one part in ninety is gone
The colour is one bit, so cheap

[VERSE 2]
A hash is a perfect disguise
Sixty-four bits of even soup
The hash keeps no shape of the board
Sixty-four bits of noise, that's all

[VERSE 3]
Nothing made later brings it back
Nowhere down the line can it mend
It kept the shape, it lost the paint
Now drop the colour, keep the game

[OUTRO]
One part in ninety for the eye
The colour is what you can see
The value is what you can read
Now drop the colour, keep the game
"""


def sections(lyrics):
    """-> [(tag, [lines])]"""
    out, tag = [], None
    for raw in lyrics.strip().splitlines():
        raw = raw.strip()
        if not raw:
            continue
        m = re.match(r"^\[([^\]]+)\]$", raw)
        if m:
            tag = m.group(1)
            out.append((tag, []))
        else:
            out[-1][1].append(raw)
    return out


# ------------------------------------------------------------------ rhyme ---

_DIGRAPH = [("ai", "EY"), ("ay", "EY"), ("ea", "IY"), ("ee", "IY"), ("ie", "IY"),
            ("oa", "OW"), ("oe", "OW"), ("ou", "OW"), ("ow", "OW"), ("oo", "UW"),
            ("oi", "OY"), ("oy", "OY"), ("au", "AW"), ("aw", "AW"), ("ue", "UW")]
_SHORT = {"a": "AE", "e": "EH", "i": "IH", "o": "AA", "u": "AH"}


def phone_key(word):
    """Coarse phonetic key for rhyme checking.

    Handles the two things that make letter-rhyme fail: vowel DIGRAPHS
    (claim/game, down/found) and MAGIC E (game vs cat). Without these the
    checker reports real rhymes as misses — which is worse than useless,
    because it teaches you to ignore it.
    """
    w = re.sub(r"[^a-z]", "", word.lower())
    w = re.sub(r"^(the|a|an)h?$", "", w) or w
    w = w.lstrip("h")
    if not w:
        return ""
    magic_e = len(w) > 3 and w.endswith("e") and w[-2] not in "aeiou"
    if magic_e:
        w = w[:-1]
    out, i, vs = [], 0, []
    while i < len(w):
        two = w[i:i + 2]
        hit = next((v for d, v in _DIGRAPH if d == two), None)
        if hit:
            vs.append(hit)
            i += 2
            continue
        if w[i] in "aeiou":
            j = i
            while j < len(w) and w[j] in "aeiouy":
                j += 1
            vs.append(_SHORT.get(w[i], "AE"))
            i = j
        else:
            out.append(w[i])
            i += 1
    if magic_e and vs:                       # cat vs game
        vs[-1] = {"a": "EY", "e": "IY", "i": "AY", "o": "OW", "u": "UW"}[vs[-1][0].lower()] \
            if len(vs[-1]) == 2 else {"AE": "EY", "EH": "IY", "IH": "AY",
                                      "AA": "OW", "AH": "UW"}.get(vs[-1], vs[-1])
    if not vs:
        return ""
    coda = re.sub(r"[bcdfghjklmnpqrstvwxyz]", "C", "".join(out))
    return "".join(vs) + "-" + coda[:2]


def last_word(line):
    w = re.sub(r"[^A-Za-z'’\- ]", " ", line).split()
    return w[-1].lower().strip("'-") if w else ""


def rhymes(a, b):
    ka, kb = phone_key(a), phone_key(b)
    if not ka or not kb:
        return False
    # accept exact-tail match or shared stressed-vowel class + same coda
    return ka == kb or (ka.split("-")[0] == kb.split("-")[0] and ka.split("-")[1] == kb.split("-")[1])


# ------------------------------------------------------------------ checks ---

def check_t1(lyrics):
    print("### T1  halyard-and-ledger  —  sea shanty, call-and-response")
    sec = sections(lyrics)
    lead = [(t, l) for t, ls in sec for l in ls if "LEAD" in t]
    crew = [(t, l) for t, ls in sec for l in ls if "CREW" in t]
    print(f"  lead lines            : {len(lead)}")
    print(f"  RESPONSE (crew) lines : {len(crew)}   <- the call-and-response count")
    n_crew_sections = sum(1 for t, _ in sec if "CREW" in t)
    print(f"  crew sections         : {n_crew_sections}")
    print("  per-half rhyme (last word -> phone key):")
    bad = 0
    for tag, ls in sec:
        if len(ls) < 2:
            continue
        a, b = last_word(ls[0]), last_word(ls[1])
        ok = rhymes(a, b)
        bad += 0 if ok else 1
        print(f"    {'rhyme ' if ok else 'MISS  '} {tag:<16} {a!r:<14} {b!r:<14} "
              f"{phone_key(a)} / {phone_key(b)}")
    print(f"  rhyme misses          : {bad}")
    print(f"  RESULT: {'PASS' if bad == 0 and len(crew) >= 4 else 'FAIL'}")
    return bad == 0 and len(crew) >= 4


def check_t2(lyrics):
    print("### T2  nine-bars-to-town  —  country, 12-bar")
    sec = sections(lyrics)
    chor = [ls for t, ls in sec if "CHORUS" in t]
    n = sum(len(ls) for ls in chor)
    print(f"  chorus sections       : {len(chor)}   (need 3)")
    print(f"  chorus lines          : {n}   (need 12 = 12 bars)")
    print(f"  lines per chorus      : {[len(ls) for ls in chor]}")
    print("  opening-word test — every line must open on 'Nine bars':")
    bad = 0
    for i, ls in enumerate(chor, 1):
        for j, l in enumerate(ls, 1):
            ok = l.lower().startswith("nine bars")
            bad += 0 if ok else 1
            print(f"    {'ok  ' if ok else 'MISS'} chorus{i}.line{j}: {l[:44]}")
    print(f"  opening-word misses   : {bad}")
    ok = len(chor) == 3 and n == 12 and bad == 0
    print(f"  RESULT: {'PASS' if ok else 'FAIL'}")
    return ok


def check_t3(lyrics, target=8):
    print(f"### T3  one-hundredth-of-the-value  —  HARD FORM, exactly {target} syllables/line")
    sec = sections(lyrics)
    rows, misses = [], []
    for tag, ls in sec:
        for l in ls:
            n = line_syllables(l)
            rows.append((tag, l, n))
            if n != target:
                misses.append((tag, l, n))
    for tag, l, n in rows:
        mark = "   " if n == target else "<<<"
        print(f"  {n:3d}{mark} [{tag}] {l}")
    tot = sum(n for _, _, n in rows)
    print(f"  lines                 : {len(rows)}")
    print(f"  total syllables       : {tot}")
    print(f"  mean syllables/line   : {tot / len(rows):.3f}")
    print(f"  lines NOT at {target}      : {len(misses)}")
    for tag, l, n in misses:
        print(f"    MISS {tag}: {n} syl (delta {n - target:+d}) — {l}")
    print(f"  RESULT: {'PASS' if not misses else 'FAIL'}")
    return not misses


if __name__ == "__main__":
    print("=" * 78)
    print("formcheck-r4 — measured, not asserted")
    print("=" * 78)
    r = [check_t1(T1), "", check_t2(T2), "", check_t3(T3)]
    print()
    print(f"OVERALL: {'ALL CONSTRAINTS MET' if all([x for x in r if isinstance(x, bool)]) else 'ONE OR MORE MISS'}")
    sys.exit(0 if all(x for x in r if isinstance(x, bool)) else 1)
