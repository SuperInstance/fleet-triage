#!/usr/bin/env python3
"""
exp-01 / arm runner.  Executes the REAL experiments/it_department.py::main()
with the judge injected at the jev() seam.  No credentials, no network.

The only thing this file mutates is the GUARD TRIGGER, one line, reversibly.
Everything else -- judge(), truth_ok(), the tally, the ledger write -- is the
repo's own code, imported, not copied.
"""
import importlib.util, io, json, os, re, sys, threading, contextlib, hashlib

SRC = "/workspace/experiments/it_department.py"
LEDGER = "/workspace/it_department_ledger.json"
RUBRIC_KEYS = ["grounded_in_our_own_artifacts", "specific_numbers",
               "names_the_mechanism", "no_invented_sources",
               "honest_about_uncertainty"]

GUARD_RE = r"^(\s*)if not any\(v\.get\(\"judge\"\) for _, sc, _ in rows for v in sc\.values\(\)\):\s*$"
GUARD_OFF = "\\1if False and not any(v.get(\"judge\") for _, sc, _ in rows for v in sc.values()):"


def load(guard_enabled):
    """Load it_department.py verbatim; optionally neutralise the guard trigger."""
    src = open(SRC, encoding="utf-8").read()
    if not guard_enabled:
        new, n = re.subn(GUARD_RE, GUARD_OFF, src, flags=re.M)
        assert n == 1, f"guard line not found/ambiguous: {n} matches"
        src = new
    path = f"/tmp/exp01/_mod_{'on' if guard_enabled else 'off'}.py"
    open(path, "w", encoding="utf-8").write(src)
    spec = importlib.util.spec_from_file_location(f"itdep_{'on' if guard_enabled else 'off'}", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)          # builds CORPUS from the real reports
    return m


def make_fake(mode, lock, state):
    """Returns a jev() replacement.  Dispatches on the question key the module
    sends: 'q' = the arms, 'review' = the judge.  The arms always answer, so the
    judge is the ONLY thing that varies between mutants."""
    def jev(_state, questions, max_items=6):
        key = next(iter(questions))
        with lock:
            state["calls"] += 1
            n = state["calls"]
        if key == "q":
            return {"answers": {"q": {"answer": f"candidate answer {n} from the corpus"}}}
        # ---- the judge arm ----
        if mode == "dead":
            return {"__err__": "500"}                       # judge is down
        if mode == "empty_criteria":                        # structurally valid, zero scores
            return {"answers": {"review": {"probabilities":
                    {a: {k: 0.0 for k in RUBRIC_KEYS} for a in ("A_single","B_refracted","C_free")}}}}
        if mode == "healthy":                              # varies by arm AND by prompt
            out = {}
            for i, a in enumerate(("A_single","B_refracted","C_free")):
                out[a] = {k: round(0.15 + 0.6 * ((n + 3 * i) % 5) / 4.0, 3) for k in RUBRIC_KEYS}
            return {"answers": {"review": {"probabilities": out}}}
        if mode == "constant":                             # SAME map for every arm, every prompt
            out = {a: {k: 0.5 for k in RUBRIC_KEYS} for a in ("A_single","B_refracted","C_free")}
            return {"answers": {"review": {"probabilities": out}}}
        if mode == "rubric_blind":                         # 5/5 on everything, always
            out = {a: {k: 1.0 for k in RUBRIC_KEYS} for a in ("A_single","B_refracted","C_free")}
            return {"answers": {"review": {"probabilities": out}}}
        if mode == "partial":                              # scores ONE arm, omits two
            out = {"A_single": {k: 0.9 for k in RUBRIC_KEYS}}
            return {"answers": {"review": {"probabilities": out}}}
        if mode == "rating_1to5":                          # obeys the rubric's OWN text: "Rate 1-5"
            out = {"A_single": {k: 5 for k in RUBRIC_KEYS},
                   "B_refracted": {k: 1 for k in RUBRIC_KEYS},
                   "C_free": {k: 3 for k in RUBRIC_KEYS}}
            return {"answers": {"review": {"probabilities": out}}}
        if mode == "arm_constant":                         # constant ACROSS ARMS, varies by prompt
            v = round(0.2 + 0.1 * (n % 7), 3)
            out = {a: {k: v for k in RUBRIC_KEYS} for a in ("A_single","B_refracted","C_free")}
            return {"answers": {"review": {"probabilities": out}}}
        raise SystemExit(f"unknown mode {mode}")
    return jev


def run(arm_id, guard_enabled, mode, empty_prompts=False):
    m = load(guard_enabled)
    lock = threading.Lock()
    state = {"calls": 0}
    m.jev = make_fake(mode, lock, state)
    m.ThreadPoolExecutor = lambda max_workers=1, **k: __import__(
        "concurrent.futures", fromlist=["x"]).ThreadPoolExecutor(max_workers=1)
    if empty_prompts:
        m.PROMPTS = []

    if os.path.exists(LEDGER):
        os.remove(LEDGER)
    buf = io.StringIO()
    raised, exc, wrote, payload = None, None, False, None
    try:
        with contextlib.redirect_stdout(buf):
            m.main()
    except SystemExit as e:
        raised, exc = True, f"SystemExit({e.code})"
    except Exception as e:
        raised, exc = True, f"{type(e).__name__}: {e}"
    if os.path.exists(LEDGER):
        wrote = True
        payload = json.load(open(LEDGER))
    out = buf.getvalue()
    ledger_tbl = [l for l in out.splitlines() if re.search(r"A_single|B_refracted|C_free", l)]
    return dict(arm=arm_id, guard=guard_enabled, judge_mode=mode,
                raised=raised, exc=exc, wrote_ledger=wrote,
                judge_ge4=(payload or {}).get("judge_ge4"),
                judged=(payload or {}).get("judged"),
                truth_correct=(payload or {}).get("truth_correct"),
                liked_wrong=(payload or {}).get("judge_liked_wrong"),
                printed=[l.strip() for l in ledger_tbl])


ARMS = [
    # --- THE CONTROLS.  They run first.  A mutant result is meaningless without them.
    ("NC-A", False, "dead",            False),   # control: guard OFF, dead judge -> MUST complete
    ("NC-B", True,  "dead",            False),   # control: guard ON,  dead judge -> MUST raise
    ("NC-C", True,  "healthy",         False),   # control: guard ON,  good judge  -> MUST complete
    # --- the mutants
    ("M5-empty-criteria", True, "empty_criteria", False),
    ("M2-constant",      True,  "constant",       False),
    ("M3-rubric-blind",  True,  "rubric_blind",   False),
    ("M4-partial",       True,  "partial",        False),
    ("M6-no-prompts",    True,  "healthy",        True),
    ("M7-rating-1to5",   True,  "rating_1to5",    False),
    ("M8-arm-constant",  True,  "arm_constant",   False),
]

if __name__ == "__main__":
    os.makedirs("/tmp/exp01", exist_ok=True)
    pass
    results = []
    for arm_id, guard, mode, ep in ARMS:
        r = run(arm_id, guard, mode, ep)
        results.append(r)
        verdict = "RAISED " if r["raised"] else "COMPLETED"
        print(f"\n[{arm_id}] guard={'ON ' if guard else 'OFF'} judge={mode}")
        print(f"   outcome   : {verdict} {r['exc'] or ''}")
        print(f"   ledger    : {'WROTE' if r['wrote_ledger'] else 'not written'}"
              f"   judged={r['judged']}  judge_ge4={r['judge_ge4']}")
        for l in r["printed"]:
            print(f"   printed   : {l}")
    json.dump(results, open("/tmp/exp01/results.json", "w"), indent=1)
    print("\nsaved /tmp/exp01/results.json")
