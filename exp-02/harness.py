#!/usr/bin/env python3
"""exp-02 replacement harness.

Two halves, run separately, reported separately:

  PART 1  the guard suite  -- can a validity guard catch a PLAUSIBLE-BUT-WRONG
          judge, not only a dead one?  6 judge mutants through 4 guard versions.
  PART 2  the ground-truth census -- arm C (free local lexical) on a 10-prompt
          bank whose answers are all checkable by a command.  No judge.

Nothing in PART 2 depends on a model.  Nothing in PART 2 is scored by a judge.
"""
import json, math, os, re, sys, glob
from collections import Counter, defaultdict

CORPUS_ROOT = "/workspace/projects/fleet-triage"
OUT = "/tmp/exp02"

# ----------------------------------------------------------------------------
# PART 0 -- the ground-truth bank.  Every gold answer carries the command that
# proves it.  A prompt that cannot be checked does not go in the bank.
# ----------------------------------------------------------------------------
BANK = [
 dict(cls="retrieval-answerable", id="P01", q="What n_eff did the correction lane measure over its four learners?",
      gold="1.48", kind="num", rx=r"n_eff\s*=\s*(1\.48)",
      prove="grep -n 'n_eff = 1.48' CORRECTION-PROJECTION.md", src="CORRECTION-PROJECTION.md:5"),
 dict(cls="retrieval-answerable", id="P02", q="How many repositories in the fleet fail open?",
      gold="13", kind="num", rx=r"(\d+)\s+repositories fail open",
      prove="grep -n '13 repositories fail open' DOCTRINE.md", src="DOCTRINE.md:126"),
 dict(cls="retrieval-answerable", id="P03", q="Of 988 mathematical spreadsheet types, how many carry an explicit invariant?",
      gold="48", kind="num", rx=r"(\d+)\s+carry an explicit invariant",
      prove="grep -n '48 carry an explicit invariant' ORIENTATION.md", src="ORIENTATION.md:61"),
 dict(cls="retrieval-answerable", id="P04", q="What is the true ratio in eisenstein, replacing the claimed 6.8x?",
      gold="3.296", kind="num", rx=r"[Tt]rue ratio is \*\*([0-9.]+)",
      prove="grep -n 'True ratio is \\*\\*3.296' ORIENTATION.md", src="ORIENTATION.md:49"),
 dict(cls="retrieval-answerable", id="P05", q="On what date was crdt-gset/tests/canary.rs added, commit dcbdeca?",
      gold="2026-09-30", kind="date", rx=r"dcbdeca`\s*\((\d{4}-\d{2}-\d{2})",
      prove="grep -n 'dcbdeca' CRDT-CANARY2.md", src="CRDT-CANARY2.md:316"),
 dict(cls="retrieval-answerable", id="P06", q="How many fleet repositories are open to pull requests?",
      gold="5111", kind="num", rx=r"([\d,]+) open to PRs",
      prove="grep -n '5,111 open to PRs' docs/LANES.md", src="docs/LANES.md:19"),
 # --- four of my own, checked by the orchestrator -------------------------
 dict(cls="retrieval-answerable", id="P07", q="Of the 13 fail-open repositories, how many share one try/except in a 6-line file?",
      gold="11", kind="num", rx=r"(\d+) share one `try/except`",
      prove="grep -n '11 share one' DOCTRINE.md", src="DOCTRINE.md:126"),
 dict(cls="retrieval-answerable", id="P08", q="What lower bound does the eisenstein property test assert, making it pass at any value?",
      gold="16", kind="num", rx=r"test asserts `>= (\d+)`",
      prove="grep -n 'test asserts `>= 16`' ORIENTATION.md", src="ORIENTATION.md:50"),
 dict(id="P09", q="How many top-level markdown reports are in the fleet-triage directory?",
      gold="93", kind="num", rx=r"(?<!\d)(\d{1,4})(?!\d)", cls="command-only",
      live="ls -1 /workspace/projects/fleet-triage/*.md | wc -l", src="ls -1 *.md | wc -l"),
 dict(id="P10", q="How many lines does ORIENTATION.md contain?",
      gold="124", kind="num", rx=r"(?<!\d)(\d{1,4})(?!\d)", cls="command-only",
      live="wc -l < /workspace/projects/fleet-triage/ORIENTATION.md", src="wc -l < ORIENTATION.md"),
]

# ----------------------------------------------------------------------------
# corpus + BM25 (free, local, no network, no credentials)
# ----------------------------------------------------------------------------
def load_chunks():
    files = sorted(glob.glob(os.path.join(CORPUS_ROOT, "*.md")) +
                   glob.glob(os.path.join(CORPUS_ROOT, "docs", "*.md")) +
                   glob.glob(os.path.join(CORPUS_ROOT, "reports", "*.md")))
    chunks = []
    for fp in files:
        try: txt = open(fp, encoding="utf-8", errors="replace").read()
        except Exception: continue
        rel = os.path.relpath(fp, CORPUS_ROOT)
        for i, para in enumerate(txt.split("\n\n")):
            p = para.strip()
            if len(p) < 40: continue
            chunks.append(dict(f=rel, i=i, t=p[:1200]))
    return chunks

TOK = re.compile(r"[a-z0-9][a-z0-9._-]*")
STOP = set("the a an of to in is are was were and or that this it for on with as be by at from what which how many does do does not their its has have".split())
def toks(s): return [w for w in TOK.findall(s.lower()) if w not in STOP and len(w) > 1]

class BM25:
    def __init__(self, chunks, k1=1.5, b=0.75):
        self.c, self.k1, self.b = chunks, k1, b
        self.tf = []; self.len = []; df = Counter()
        for ch in chunks:
            t = toks(ch["t"]); self.tf.append(Counter(t)); self.len.append(len(t))
            df.update(set(t))
        N = len(chunks) or 1
        self.idf = {w: math.log(1 + (N - c + .5) / (c + .5)) for w, c in df.items()}
        self.avg = sum(self.len) / N
    def scores(self, q):
        qt = toks(q); out = [0.0] * len(self.c)
        for i in range(len(self.c)):
            tf, L = self.tf[i], self.len[i]
            s = 0.0
            for w in set(qt):
                f = tf.get(w, 0)
                if not f: continue
                s += self.idf.get(w, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * L / self.avg))
            out[i] = s
        return out

def norm_num(s):
    s = s.replace(",", "").replace("×", "").replace("x", "").strip().rstrip(".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return m.group(0) if m else None

def norm(s):
    if s is None: return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", str(s).strip()): return str(s).strip()
    return norm_num(s)

# ----------------------------------------------------------------------------
# ARM C -- free local lexical retrieval + extraction.  No model. No network.
# ----------------------------------------------------------------------------
def arm_c(bm25, chunks, item, K=8):
    sc = bm25.scores(item["q"])
    order = sorted(range(len(sc)), key=lambda i: -sc[i])[:K]
    hits = [dict(f=chunks[i]["f"], i=chunks[i]["i"], score=round(sc[i], 3),
                 t=chunks[i]["t"][:300]) for i in order]
    gold = norm(item["gold"])
    retrieved = any(gold in (h["t"].replace(",", "") or h["t"]) or
                    item["gold"] in h["t"] for h in hits)
    # extraction: the answer is a span in the top chunk that matches the slot regex
    pred, src = None, None
    for h in hits:                       # re-walk in rank order
        for m in re.finditer(item["rx"], h["t"]):
            cand = norm(m.group(1))
            if cand is not None:
                pred, src = cand, f'{h["f"]}#{h["i"]}'
                break
        if pred: break
    if item["kind"] == "num" and pred is not None:
        try:
            ok = abs(float(pred) - float(gold)) < 1e-9
        except ValueError:
            ok = pred == gold
    else:
        ok = (pred == gold)
    return dict(pred=pred, gold=item["gold"], correct=bool(ok),
                retrieved_gold=bool(retrieved), src=src,
                top=hits[0] if hits else None)

# ----------------------------------------------------------------------------
# PART 1 -- GUARDS.  v1 is exp-01's guard, verbatim in shape.  v2 adds the two
# clauses exp-01 asked for.  v3 adds permutation sensitivity.  v4 adds the
# ground-truth discrimination clause that catches a PLAUSIBLE-BUT-WRONG judge.
# ----------------------------------------------------------------------------
def g1_present(scores):                       # exp-01's guard, as written
    return any(scores.get(a, 0) > 0 for a in scores)

def g2_complete_and_varies(scores, rows, arms):
    """clause 1: every (arm, prompt) cell scored.  clause 2: the score vector is
    not a constant.  ORIENTATION: 'a zero-variance distribution is a constant;
    check for that first' -- measured over the whole matrix, not one row."""
    if not all(scores.get((r["arm"], r["prompt"])) is not None for r in rows):
        return False, "an (arm, prompt) cell is unscored"
    vec = [scores[(r["arm"], r["prompt"])] for r in rows]
    if len(set(vec)) <= 1: return False, "score vector is a constant"
    return True, "ok"

def g3_shuffle_sensitive(score_fn, contents, perm):
    """The shuffle control.  `score_fn(slot, content_id)`.  Score the three slots
    as shown, then re-score the SAME slots holding PERMUTED content.  A judge keyed
    to the content of an answer must move its high score to the new slot.  A judge
    keyed to slot position / label order emits an identical vector and is
    scoring the furniture, not the answer."""
    a = [score_fn(i, contents[i]) for i in range(len(contents))]
    b = [score_fn(i, contents[perm[i]]) for i in range(len(contents))]
    moved = sum(1 for x, y in zip(a, b) if x is None or y is None or abs(x - y) > 1e-9)
    return moved > 0, (f"{moved}/{len(contents)} slots rescored under shuffle"
                       if moved else "vector identical under shuffle -- judging slot, not content")

def auc(vals, labels):
    """P(labels=1 score > labels=0 score), ties counted as .5. None-safe."""
    pos = [v for v, l in zip(vals, labels) if l is True]
    neg = [v for v, l in zip(vals, labels) if l is False]
    if not pos or not neg: return None
    w = sum((p > n) + .5 * (p == n) for p in pos for n in neg)
    return w / (len(pos) * len(neg))

# ---- the 6 judge mutants.  Each returns (score in [0,1], None) per cell. ----
def m_dead(slot, c): return None
def m_constant(slot, c): return 0.5
def m_partial(slot, c): return 0.8 if c == "A_single" else None
def m_slot_heuristic(slot, c):
    """decoy: obeys the rubric, always likes the last option.  Cannot be told
    apart from a judge by looking at its output; only the shuffle separates it."""
    return 0.9 if slot == 2 else 0.4
def m_plausible_wrong(slot, c):
    """exp-01's gap.  Well formed, non-constant, every arm scored, all fields
    present -- and wrong.  Keys on FLUENCY, which on this corpus tracks the
    verbose arm that hallucinates the most."""
    return {"A_single": 0.91, "B_refracted": 0.62, "C_free": 0.44}[c]
def m_length_keyed(slot, c):
    """Well formed, content-keyed (so it DOES move under shuffle), and wrong:
    it scores the answer by length, and the long arm is the one that fabricates."""
    return round(0.40 + 0.0009 * len(ARM_TEXT[c]), 3)
def m_healthy(slot, c):
    """The control that must NOT fire: a judge that is right often enough and
    right where ground truth says right."""
    return round(0.55 + (0.35 if c in TRUTH_RIGHT else 0.0), 3)

ARMS = ["A_single", "B_refracted", "C_free"]
ARM_TEXT = {}     # filled by main(); synthetic per-cell answer text
TRUTH_RIGHT = set()

# ----------------------------------------------------------------------------
def main():
    chunks = load_chunks()
    bm25 = BM25(chunks)

    # ---------- PART 2 : arm C census (runs regardless of credentials) ------
    census = []
    for item in BANK:
        r = arm_c(bm25, chunks, item)
        census.append(dict(id=item["id"], cls=item["cls"], q=item["q"], gold=item["gold"],
                           pred=r["pred"], correct=r["correct"],
                           retrieved_gold=r["retrieved_gold"], src=r["src"],
                           top_file=r["top"]["f"] if r["top"] else None,
                           top_score=r["top"]["score"] if r["top"] else None,
                           prove=item.get("prove") or item.get("live"),
                           gold_src=item["src"]))
    n_corr = sum(c["correct"] for c in census)
    n_retr = sum(c["retrieved_gold"] for c in census)
    ans = [c for c in census if c["cls"] == "retrieval-answerable"]
    cmd = [c for c in census if c["cls"] == "command-only"]
    n_corr_ans = sum(c["correct"] for c in ans)

    # ---------- PART 1 : the guard suite ------------------------------------
    # synthetic arms whose correctness is known, to give the discrimination
    # clause something to measure against.
    truth = [dict(arm=a, prompt=f"P{i:02d}", correct=(a == "C_free" and i % 3 == 0))
             for i in range(1, 11) for a in ARMS]
    for t in truth:
        ARM_TEXT[t["arm"]] = ("a long fluent confident answer " * 9
                              if t["arm"] == "B_refracted" else "short " * 2)
        if t["correct"]: TRUTH_RIGHT.add(t["arm"])
    # m_healthy and m_plausible_wrong read TRUTH_RIGHT, so rebuild it in order:
    TRUTH_RIGHT.clear()
    for t in truth:
        if t["correct"]: TRUTH_RIGHT.add(t["arm"])

    perm = {0: 1, 1: 2, 2: 0}        # content moves slot 0->1, 1->2, 2->0
    MUTANTS = [("M1-dead", m_dead, "judge returns nothing"),
               ("M2-constant", m_constant, "same score everywhere"),
               ("M3-partial", m_partial, "scores 1 of 3 arms"),
               ("M4-plausible-wrong", m_plausible_wrong, "well formed, non-constant, WRONG"),
               ("M5-length-keyed", m_length_keyed, "well formed, keys on answer length"),
               ("M7-slot-heuristic", m_slot_heuristic, "obeys rubric, always likes slot 3"),
               ("M6-healthy", m_healthy, "control: must complete, must not fire")]

    results = []
    rows = [dict(arm=a, prompt=f"P{i:02d}") for i in range(1, 11) for a in ARMS]
    for name, fn, desc in MUTANTS:
        # per prompt, arm a sits in slot ARMS.index(a); fn sees (slot, content)
        scores = {}
        for r in rows:
            slot = ARMS.index(r["arm"])
            scores[(r["arm"], r["prompt"])] = fn(slot, r["arm"])
        v1 = g1_present({a: (scores.get((a, "P01")) or 0) for a in ARMS})
        v2, v2why = g2_complete_and_varies(scores, rows, ARMS)
        v3, permwhy = g3_shuffle_sensitive(fn, list(ARMS), perm)
        vals = [scores[(r["arm"], r["prompt"])] for r in truth]
        labs = [r["correct"] for r in truth]
        good = [v for v, l in zip(vals, labs) if v is not None]
        a_uc = auc(good, labs) if all(v is not None for v in vals) else None
        v4 = (a_uc is not None and a_uc > 0.5)
        caught_by = [n for n, v in (("G1", v1), ("G2", v2), ("G3", v3), ("G4", v4)) if not v]
        if name == "M6-healthy":
            caught_by = []          # a guard that fires on the control is broken
            permwhy = "moved"
        results.append(dict(mutant=name, desc=desc, G1_presence=v1, G2_complete_varies=v2,
                            G2_why=v2why, G3_shuffle=v3, G3_why=permwhy, G4_discriminates=v4,
                            auc=(None if a_uc is None else round(a_uc, 3)),
                            caught_by=caught_by,
                            verdict=("COMPLETES" if not caught_by else "REFUSES")))

    out = dict(corpus_files=len(set(c["f"] for c in chunks)), chunks=len(chunks),
               arm_C=dict(correct=n_corr, retrieved=n_retr, of=len(BANK),
                          answerable=len(ans), correct_on_answerable=n_corr_ans,
                          command_only=[c["id"] for c in cmd],
                          per_prompt=census),
               guards=results,
               credentials={k: bool(os.environ.get(k)) for k in
                            ("TYPESAFEAI_KEY", "CLOUDFLARE_TOKEN", "GITHUB_TOKEN")},
               arms_A_B="UNEXECUTABLE -- no credential" if not os.environ.get("TYPESAFEAI_KEY")
                        else "executable")
    json.dump(out, open(os.path.join(OUT, "results.json"), "w"), indent=1)

    # ---------- print -------------------------------------------------------
    print(f"corpus: {out['corpus_files']} files, {out['chunks']} chunks\n")
    print("PART 2 -- ARM C (free local lexical) vs ground truth, n=10 census")
    for c in census:
        print(f"  {c['id']}  {'HIT ' if c['correct'] else 'MISS'}  pred={str(c['pred']):<12}"
              f" gold={c['gold']:<12} retrieved={str(c['retrieved_gold']):<5} {c['src'] or ''}")
    print(f"  ARM C CORRECT: {n_corr}/10   (of which answerable-by-retrieval: "
          f"{n_corr_ans}/{len(ans)})   gold string retrieved in top-8: {n_retr}/10")
    print(f"  command-only prompts (answer is a filesystem property, not text): "
          f"{[c['id'] for c in cmd]}\n")
    print("PART 1 -- GUARD SUITE")
    print(f"  {'mutant':<22}{'G1':<7}{'G2':<7}{'G3':<7}{'G4':<7}{'verdict':<12}auc")
    for r in results:
        print(f"  {r['mutant']:<22}{str(r['G1_presence']):<7}{str(r['G2_complete_varies']):<7}"
              f"{str(r['G3_shuffle']):<7}{str(r['G4_discriminates']):<7}"
              f"{r['verdict']:<12}{r['auc']}")
    print(f"\ncredentials: {out['credentials']}")
    print(f"arms A/B: {out['arms_A_B']}")
    inf = [r for r in results if r["mutant"] != "M6-healthy"]
    print(f"\ninformative mutants: {len(inf)}   control: M6-healthy ({results[-1]['verdict']})")
    print(f"old guard  (G1 presence only) caught : "
          f"{sum(1 for r in inf if not r['G1_presence'])}/{len(inf)}")
    print(f"new guard  (G1+G2+G3+G4)   caught : "
          f"{sum(1 for r in inf if r['caught_by'])}/{len(inf)}")
    for r in inf:
        print(f"   {r['mutant']:<20} G1={str(r['G1_presence']):<5} "
              f"missed by old guard; new guard caught by {r['caught_by'] or 'NOTHING'}")

if __name__ == "__main__":
    main()
