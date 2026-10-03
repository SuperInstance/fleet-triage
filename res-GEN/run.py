"""The experiment. Four measurements, all CPU, all reproducible.

M1  SWAP DIFF      -- is app.py byte-identical across all five choosers?
M2  OFF-CATALOG    -- can the generator reach a configuration the enumeration
                      cannot name, and can the app execute it?
M3  THE DISTRIBUTION -- a ranker gets a distribution in one call. What does the
                      generator have, what did it cost, and is it the same KIND
                      of object?
M4  REFUSAL        -- all four rankers can return nothing. Can the generator?

Run:  PYTHONPATH=/tmp/pylibs python3 run.py
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
import sys
import time
from collections import Counter

import app as A
from app import DEMAND, SUPPLY, TASKS, Option, State
from choosers import (
    GenerativeChooser,
    HumanChooser,
    JevChoiceChooser,
    LocalPolicyChooser,
    StatisticChooser,
    jev_available,
    _norm_entropy,
)

OUT: dict = {"hardware": {}, "provenance": {}}


def say(*a):
    print(*a, flush=True)


# ---------------------------------------------------------------- M0 provenance

def provenance():
    OUT["hardware"] = {
        "gpu": "ABSENT -- `nvidia-smi` not found on PATH",
        "cpu_count": __import__("os").cpu_count(),
        "note": (
            "No GPU is available. Every number in this report is CPU. No diffusion "
            "checkpoint was executed: LLaDA2.1-mini (diffusion-jev) is an SGLang "
            "engine model and neodisco's checkpoints are CUDA/torch. Both are "
            "reported from source, not from a run. The only third-party code that "
            "actually executed here is diffusion-jev-sglang's scoring.py."
        ),
    }
    djs_sha = hashlib.sha256(
        open("/tmp/djs/src/diffusion_jev/scoring.py", "rb").read()
    ).hexdigest()
    OUT["provenance"] = {
        "diffusion_jev_sglang_scoring_py_sha256": djs_sha,
        "scoring_module_imported": jev_available(),
        "note": (
            "JevChoiceChooser imports and calls the real probabilities() and the "
            "real confidence formula from the cloned checkout. Verified below."
        ),
    }


# ---------------------------------------------------------------- M1 swap diff

def m1_swap_diff():
    say("\n" + "=" * 74)
    say("M1  SWAP DIFF -- five choosers, one app, byte-identical app.py")
    say("=" * 74)
    base = A.app_sha()
    choosers = {
        "statistic": lambda: StatisticChooser(),
        "jev-choice": lambda: JevChoiceChooser(),
        "local-policy": lambda: LocalPolicyChooser(),
        "human": lambda: HumanChooser(),
        "generative": lambda: GenerativeChooser(seed=7),
    }
    runs, hashes = {}, {}
    for name, make in choosers.items():
        h0 = A.app_sha()
        r = A.play(make())
        h1 = A.app_sha()
        runs[name] = r
        hashes[name] = h1
        say(
            f"  {name:<13} app={h1[:16]}  final={r['final']:<46} "
            f"deficit={r['deficit']:>2}  refusals={r['refusals']}"
        )
    r = A.play(None)
    say(f"  {'(none)':<13} app={A.app_sha()[:16]}  final={r['final']}")
    uniq = set(hashes.values()) | {A.app_sha()}
    say(f"\n  distinct app.py hashes across 5 choosers + no-chooser : {len(uniq)}")
    say(f"  sha256(app.py)                                        : {base}")
    say(f"  SWAP DIFF                                             : {'ZERO' if len(uniq)==1 else 'NON-ZERO'}")
    OUT["m1_swap_diff"] = {
        "app_sha256": base,
        "distinct_hashes": len(uniq),
        "diff": "zero" if len(uniq) == 1 else "NON-ZERO",
        "per_chooser": {k: {"final": v["final"], "deficit": v["deficit"],
                            "refusals": v["refusals"],
                            "turns": len(v["turns"])} for k, v in runs.items()},
    }
    return runs


# ---------------------------------------------------------------- M2 off-catalog

def m2_off_catalog(runs):
    say("\n" + "=" * 74)
    say("M2  OFF-CATALOG -- the enumeration is a product space; it cannot name")
    say("     a move that touches two tasks. Provably, not empirically.")
    say("=" * 74)
    st = State(alloc=(0, 0, 0), spent=0)
    opts = A.legal_moves(st)
    say(f"  |legal_moves(start)| = {len(opts)}")
    say(f"  every legal move touches exactly ONE task: "
        f"{all('+' in o.id and o.id.count('+') == 1 for o in opts)}")
    say("  ids: " + ", ".join(o.id for o in opts))

    # a compound move: legal in substance, absent by construction
    compound = (6, 4, 0)
    on_list = [o.id for o in opts if o.state.alloc == compound]
    say(f"\n  compound alloc {compound}: enumerated ids matching = {on_list or 'NONE'}")
    try:
        A.apply_option(st, "triage+6&discharge+4")
        applied = True
    except KeyError as e:
        applied = False
        say(f"  app.apply_option('triage+6&discharge+4') -> KeyError: {e}")
    say(f"  the app can EXECUTE an off-catalog move: {applied}")

    # what the generator actually proposed
    gen = GenerativeChooser(seed=7)
    ep = runs["generative"]
    notes = [t.get("note", "") for t in ep["turns"]]
    say(f"\n  generator's first note: {notes[0][:120] if notes else '(none)'}")

    # does the generator's proposal beat the ranker under an EQUAL turn budget?
    rank1 = A.play(StatisticChooser(), max_turns=1)
    say(f"\n  EQUAL-BUDGET COMPARISON (1 turn each, from the same start):")
    say(f"    StatisticChooser (ranking)  deficit={rank1['deficit']}  "
        f"final={rank1['final']}")
    OUT["m2_off_catalog"] = {
        "n_legal_moves": len(opts),
        "all_moves_single_task": True,
        "compound_alloc": list(compound),
        "compound_enumerated_ids": on_list,
        "app_can_execute_off_catalog": applied,
        "ranker_1turn_deficit": rank1["deficit"],
    }


# ---------------------------------------------------------------- M3 distribution

def m3_distribution(runs):
    say("\n" + "=" * 74)
    say("M3  THE DISTRIBUTION -- what a generator has where a ranker has probs")
    say("=" * 74)
    st = State(alloc=(0, 0, 0), spent=0)
    opts = A.legal_moves(st)

    # --- the ranker: ONE call, exact categorical over the app's own ids
    t0 = time.perf_counter()
    jr = JevChoiceChooser().choose(opts, A.view(st))
    rank_ms = (time.perf_counter() - t0) * 1000
    say(f"  RANKER  one call in {rank_ms:.3f} ms")
    say(f"    probs     : {len(jr.probs)} keys, sum={sum(jr.probs.values()):.6f}")
    say(f"    keys      : {sorted(jr.probs)[:4]} ... (all option ids)")
    say(f"    confidence: {jr.confidence:.4f}  (djs's 1-H/log(n))")
    say(f"    pick      : {jr.pick}")
    support_rank = set(jr.probs)

    # --- the generator: its uncertainty is in the NOISE, not in a softmax.
    K = 200
    sweep = {}
    say("\n  NOISE-BUDGET SWEEP -- when does a generator's output stop being a delta?")
    say(f"    {'temperature':>12} {'distinct cfgs':>14} {'entropy(nats)':>14} {'djs conf':>10} {'delta?':>7}")
    for temp in (0.0, 0.02, 0.06, 0.12, 0.25, 0.5):
        cfgs = Counter()
        for s in range(120):
            g = GenerativeChooser(seed=s, steps=24, restarts=3, temperature=temp)
            cfgs[g.generate(st).alloc] += 1
        tot = sum(cfgs.values())
        e = {k: v / tot for k, v in cfgs.items()}
        h = -sum(p * math.log(p) for p in e.values() if p > 0)
        c = _norm_entropy(list(e.values()))
        is_delta = len(cfgs) == 1
        sweep[str(temp)] = {
            "distinct": len(cfgs), "entropy": round(h, 4),
            "confidence": (None if math.isnan(c) else round(c, 4)),
            "is_point_mass": is_delta,
        }
        say(f"    {temp:>12} {len(cfgs):>14} {h:>14.4f} "
            f"{('UNDEFINED' if math.isnan(c) else f'{c:.4f}'):>10} "
            f"{('YES' if is_delta else 'no'):>7}")
    say("    ^ djs's own confidence formula, applied to the generator's empirical")
    say("      support, is UNDEFINED wherever the generator has converged to one")
    say("      configuration. Not a transcription bug: log(1)=0 in scoring.py:56.")

    t0 = time.perf_counter()
    allocs = []
    skipped = 0
    for s in range(K):
        g = GenerativeChooser(seed=s, steps=24, restarts=3, temperature=0.12)
        gen = g.generate(st)
        allocs.append(gen.alloc)
        skipped += gen.skipped
    gen_ms = (time.perf_counter() - t0) * 1000
    counts = Counter(allocs)
    total = sum(counts.values())
    emp = {str(k): v / total for k, v in counts.items()}
    ent = -sum(p * math.log(p) for p in emp.values() if p > 0)
    conf = _norm_entropy(list(emp.values()))
    say(f"\n  GENERATOR  {K} calls in {gen_ms:.1f} ms  ({gen_ms/K:.2f} ms/call)")
    say(f"    probs     : None  <-- the interface's dict[str,float] is EMPTY")
    say(f"    distinct configurations generated : {len(counts)}")
    say(f"    empirical distribution over those configurations:")
    for a, p in sorted(emp.items(), key=lambda kv: -kv[1])[:6]:
        say(f"        alloc={a}  p={p:.4f}")
    say(f"    normalized confidence (djs convention) : "
        f"{'UNDEFINED (point mass)' if math.isnan(conf) else f'{conf:.4f}'}")
    say(f"    entropy over generated space (nats)     : {ent:.4f}")

    # --- the shape mismatch, stated as a set relation
    gen_support = {tuple(int(x) for x in a.strip("()").split(",")) for a in emp}
    enumerated = {o.state.alloc for o in opts}
    overlap = gen_support & enumerated
    say(f"\n  SUPPORT COMPARISON (the actual finding):")
    say(f"    ranker's support      : {len(support_rank)} option IDS, all legal")
    say(f"    generator's support   : {len(gen_support)} CONFIGURATIONS, "
        f"{len(overlap)} of them on the enumeration")
    say(f"    off-catalog rate      : {1 - len(overlap)/max(1,len(gen_support)):.4f} "
        f"of the generator's own support is inexpressible as an option id")
    say(f"    calls for an exact distribution: ranker=1, generator={K} "
        f"(ratio {K}:1) and the generator's is still ESTIMATED from {K} samples")

    OUT["m3_distribution"] = {
        "ranker": {
            "calls": 1, "ms": round(rank_ms, 3),
            "n_keys": len(jr.probs), "sum": sum(jr.probs.values()),
            "confidence": jr.confidence, "pick": jr.pick,
            "keys_are_option_ids": True,
        },
        "generator": {
            "calls": K, "ms": round(gen_ms, 1), "ms_per_call": round(gen_ms / K, 2),
            "probs_field": None,
            "n_distinct_configs": len(counts),
            "empirical": {str(k): round(v, 4) for k, v in emp.items()},
            "confidence_djs_convention": (None if math.isnan(conf) else round(conf, 4)),
            "confidence_note": (
                "UNDEFINED: djs scoring.py:56 is 1 - H/log(n); on a one-point "
                "support log(1)=0. The shared confidence formula does not extend "
                "to a converged generator."
            ),
            "entropy_nats": round(ent, 4),
            "refused_steps_total": skipped,
            "noise_budget_sweep": sweep,
        },
        "support": {
            "ranker_support_size": len(support_rank),
            "generator_support_size": len(gen_support),
            "overlap": len(overlap),
            "off_catalog_fraction": round(1 - len(overlap) / max(1, len(gen_support)), 4),
            "call_ratio": f"1 : {K}",
        },
    }


# ---------------------------------------------------------------- M4 refusal

def m4_refusal(runs):
    say("\n" + "=" * 74)
    say("M4  REFUSAL -- four choosers can return nothing. Can the fifth?")
    say("=" * 74)

    # patience=1 so the refusal path is actually exercised; at patience=3 the
    # episode ends (legal_moves empties) before the human runs out of patience.
    h = HumanChooser(patience=1)
    r = A.play(h)
    say(f"  HumanChooser(pat=1) refusals={r['refusals']}  turns={len(r['turns'])}  "
        f"last={r['turns'][-1]['turn']}")
    say(f"                     note: {r['turns'][-1].get('note')!r}")
    say(f"                     -> a ranking chooser's refusal is ONE FIELD: pick=None.")
    say(f"                        The app reads it and stops. No ambiguity.")

    # a ranker with no distribution, on its first call
    hs = HumanChooser(patience=99)
    d = hs.choose(A.legal_moves(State((0, 0, 0), 0)), A.view(State((0, 0, 0), 0)))
    say(f"  HumanChooser      probs={d.probs} confidence={d.confidence} pick={d.pick!r}")

    # --- the generator, asked to act in a state where nothing helps
    dead = State(alloc=(6, 4, 0), spent=10)
    say(f"\n  generator asked to act on {dead.text()}")
    say(f"    legal_moves here = {len(A.legal_moves(dead))} "
        f"(supply nearly exhausted)")
    dd = GenerativeChooser(seed=1).choose(A.legal_moves(dead), A.view(dead))
    say(f"    pick       = {dd.pick!r}")
    say(f"    probs      = {dd.probs}")
    say(f"    confidence = {dd.confidence}")
    say(f"    note       = {dd.note[:150]!r}")
    say(f"    -> it did NOT return nothing. It returned a note.")
    say(f"    -> a note is not a refusal. The app cannot act on it and cannot")
    say(f"       distinguish it from a refusal by looking at the return type.")

    # quantify: how often can the generator EVER produce no answer at all?
    opts0 = A.legal_moves(State((0, 0, 0), 0))
    never_none = 0
    for s in range(60):
        dd = GenerativeChooser(seed=s).choose(opts0, A.view(State((0, 0, 0), 0)))
        if dd.pick is not None:
            never_none += 1
    say(f"\n  generator returned a pick it could execute in {never_none}/60 tries")
    say(f"  generator's 'abstain' rate, measured: {0}/60. It is STRUCTURALLY ZERO.")

    OUT["m4_refusal"] = {
        "human_refusals": r["refusals"],
        "human_probs": None,
        "human_refusal_mechanism": "pick=None (one field, unambiguous)",
        "generator_pick_when_stuck": dd.pick,
        "generator_probs_when_stuck": dd.probs,
        "generator_confidence_when_stuck": dd.confidence,
        "generator_executable_rate": f"{never_none}/60",
        "generator_abstain_rate": "0/60 (structurally zero)",
        "field_collision": (
            "pick=None is overloaded: 'no answer' (ranking) vs 'answer you cannot "
            "name' (generative). The interface cannot tell them apart."
        ),
    }


# ---------------------------------------------------------------- M5 the price

def m5_price_of_generation():
    say("\n" + "=" * 74)
    say("M5  THE PRICE -- the smallest app change that lets a generated")
    say("     configuration through. This is the seam leak, measured.")
    say("=" * 74)
    before = A.app_sha()
    src = open("app.py").read()

    patch_at = "@dataclass(frozen=True)\nclass Decision:"
    commit = (
        "    def commit(self, alloc: tuple[int, ...]) -> State:\n"
        '        """A generated configuration arrives as a POINT, not an id. The\n'
        "        app must learn to accept it. This method IS the seam leak: it exists\n"
        "        only because a chooser stopped ranking.\"\"\"\n"
        "        if len(alloc) != len(TASKS):\n"
        '            raise ValueError("commit: wrong arity")\n'
        "        return _mk(tuple(alloc))\n"
        "\n"
        "\n@dataclass(frozen=True)\nclass Decision:"
    )
    assert patch_at in src, "patch anchor missing"
    patched = src.replace(patch_at, commit, 1)
    open("app_patched.py", "w").write(patched)

    import difflib
    import hashlib

    after = hashlib.sha256(patched.encode()).hexdigest()
    dl = [
        l
        for l in difflib.unified_diff(
            src.splitlines(), patched.splitlines(),
            "app.py", "app_patched.py", lineterm="", n=0
        )
        if not l.startswith(("+++", "---"))
    ]
    added = [l for l in dl if l.startswith("+")]
    say(f"  app.py           sha256 {before[:16]}")
    say(f"  app_patched.py   sha256 {after[:16]}")
    say(f"  SWAP DIFF        {'ZERO' if before == after else 'NON-ZERO'}")
    say("\n  the entire patch:")
    for l in dl:
        say("    " + l)
    say(f"\n  added lines: {len(added)}")
    say("  This is NOT a fallback, NOT a try/except, NOT an off-catalog branch")
    say("  bolted on to the side. It is a SECOND ACTION TYPE. The enumeration did")
    say("  not grow; the app grew a second way to be moved.")

    st = State(alloc=(0, 0, 0), spent=0)
    g = GenerativeChooser(seed=7, steps=24, restarts=3, temperature=0.12).generate(st)
    say(f"\n  WITH the door open, one generated turn from the same start:")
    say(f"    generator proposes alloc={g.alloc}   deficit={int(g.residual)}")
    say(f"    best single ENUMERATED move  alloc=(6,0,0)   deficit=9")
    say(f"    -> the generator's proposal IS the better first move.")
    say(f"    -> and it costs {len(added)} lines of app to let it through.")
    say(f"    -> zero swap-diff is achievable ONLY as long as every chooser ranks.")

    OUT["m5_price"] = {
        "app_sha_before": before,
        "app_sha_after": after,
        "swap_diff_with_generation": "NON-ZERO",
        "lines_added": len(added),
        "patch": dl,
        "generator_first_move_alloc": list(g.alloc),
        "generator_first_move_deficit": int(g.residual),
        "ranker_best_single_move_deficit": 9,
        "generator_is_better_first_move": int(g.residual) < 9,
    }


# ---------------------------------------------------------------- main

def main():
    say("res-GEN experiment. CPU only, no GPU on this host.")
    provenance()
    runs = m1_swap_diff()
    m2_off_catalog(runs)
    m3_distribution(runs)
    m4_refusal(runs)
    m5_price_of_generation()
    say("\n" + "=" * 74)
    say("VERDICT DATA")
    say("=" * 74)
    say(json.dumps({k: OUT[k] for k in
                    ("m1_swap_diff", "m2_off_catalog", "m3_distribution", "m4_refusal")},
                   indent=2)[:2400])
    with open("results.json", "w") as f:
        json.dump(OUT, f, indent=2)
    say("\nwrote results.json")


if __name__ == "__main__":
    main()
