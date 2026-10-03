#!/usr/bin/env python3
"""English syllable counter, heuristic. Good enough to FAIL a line at 8 vs 7.

Deliberately not clever. A wrong count here changes a measurement, so the
heuristic is documented and the counting rule is stated in the report: this
counts vowel-groups, subtracts silent terminal e, and applies a small exception
list. Where it is uncertain it says so rather than guessing quietly.
"""
import re

VOWELS = set("aeiouy")

# words whose vowel-group count is not the spoken count
EXCEPTIONS = {
    # vowel groups, not syllables
    "every": 2, "business": 2, "chocolate": 3, "comfortable": 4,
    "several": 3, "anything": 3, "something": 2, "nothing": 2,
    "fire": 1, "hour": 1, "our": 1, "heaven": 2, "being": 2,
    "quiet": 2, "poem": 2, "science": 2, "area": 3, "idea": 3,
    "create": 2, "created": 3, "creature": 3, "fever": 2, "wire": 1,
    "tired": 1, "toward": 1, "towards": 1, "ninety": 2, "colours": 2,
    "coloured": 2, "hundred": 2, "measure": 2, "measured": 2, "pleasure": 2,
    "sure": 1, "pure": 1, "sures": 1, "fibre": 2, "acre": 2,
    "the": 1, "a": 1, "i": 1, "eye": 1, "aisle": 1, "iron": 2,
    "union": 3, "science": 2, "dozen": 2, "women": 2, "woman": 2,
    "value": 2, "values": 2, "argue": 2, "argue_": 2,
    "one": 1, "once": 1, "gone": 1, "only": 2, "every": 2, "even": 2,
    "given": 2, "living": 2, "having": 2, "making": 2,
}


def _vowel_groups(w):
    n, prev = 0, False
    for ch in w:
        isv = ch in VOWELS
        if isv and not prev:
            n += 1
        prev = isv
    return n


def syllables(word):
    w = re.sub(r"[^a-z']", "", word.lower())
    if not w:
        return 0
    if w in EXCEPTIONS:
        return EXCEPTIONS[w]
    n = _vowel_groups(w)
    # silent terminal e (not -le after a consonant, not the whole word 'e')
    if w.endswith("e") and not w.endswith(("le", "ee", "ye")) and n > 1:
        n -= 1
    # -ed is usually silent unless preceded by t/d
    if w.endswith("ed") and len(w) > 2 and w[-3] not in "td":
        n -= 1
        if n < 1:
            n = 1
    return max(1, n)


def line_syllables(line):
    """Count a lyric line. Bracketed tags like [CHORUS] are structure, not words."""
    line = re.sub(r"\[[^\]]*\]", " ", line)
    line = line.replace("—", " ").replace("–", " ")
    return sum(syllables(w) for w in line.split())


if __name__ == "__main__":
    import sys
    for arg in sys.argv[1:]:
        print(line_syllables(arg), arg)
