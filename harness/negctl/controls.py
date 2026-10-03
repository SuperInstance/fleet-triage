#!/usr/bin/env python3
"""
negctl/ — negative controls for both lint rules, as files on disk.

THE RULE THIS FILE ENFORCES
---------------------------
    A rule with no negative control has not been tested.

Every fixture below is a constructed repository with a declared verdict:

    FAIL  the fixture IS the defect. The rule MUST fire.
    OK    the fixture is a healthy repo. The rule MUST stay silent.

A control that only ever tests the FAIL direction is a smoke test wearing a control's
name. The OK fixtures are the harder half: they are the false-positive budget, and
every one of them exists because a real repo in this fleet looks like that.

The OK fixtures are drawn from actual over-fire incidents recorded in
fleetlint_failopen.py's calibration history (v1: 16 FPs in pong-quilt; v2: 49 repos
flagged) and from canfail.py's own documented traps. If those regressions are
reintroduced, a control here goes red.

CONTROL ORDER IS DELIBERATE
---------------------------
The plumbing controls (Y-*, P-*) run FIRST and are not about the rules' verdicts at
all. They assert that the harness can read a file, parse YAML, and reach the rule.
If a parser is broken, every downstream control fails for a reason that has nothing to
do with the rule under test, and the operator -- me, tonight -- is invited to blame the
rule. That is not hypothetical: it is exactly what happened during calibration of
harness/yaml.py v1, where a one-index argv bug made `can-fail-ci` appear to detect
nothing. See the CALIBRATION HISTORY block in harness/yaml.py.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))          # for `yaml` shim + the rules
sys.path.insert(0, str(HERE.parent.parent))

import yaml as yshim                          # noqa: E402  (the shim)
import canfail                                # noqa: E402
import fleetlint_failopen as fh               # noqa: E402
import rules                                    # noqa: E402  the SHIPPED rules

ROOT = HERE / "fixtures"


# ═══════════════════════════════════════════════════════ plumbing controls (Y/P)
# These assert the INSTRUMENT works before any rule's verdict is believed.

def ctl_y1_yaml_parses():
    """The YAML shim parses a minimal workflow. Guards the argv[1] regression."""
    doc = yshim.safe_load("jobs:\n  test:\n    steps:\n      - run: pytest -q\n")
    return (isinstance(doc, dict) and "test" in doc["jobs"]
            and doc["jobs"]["test"]["steps"][0]["run"].strip() == "pytest -q"), \
        "shim parsed a one-job workflow"


def ctl_y2_shim_raises_on_garbage():
    """A shim that cannot parse must RAISE. Returning {} here would make every
    workflow look job-less, and job-less looks exactly like can-not-fail."""
    try:
        yshim.safe_load("a:\n  - b\n :::not yaml:::\n\t\t\t- [")
    except yshim.YamlError:
        return True, "shim raised on malformed YAML (did not return an empty doc)"
    except Exception:
        return True, "shim raised on malformed YAML"
    return False, "shim ACCEPTED malformed YAML and returned a value"


def ctl_y3_cannot_fail_looks_unverifiable_not_clean():
    """canfail must distinguish 'parsed, no jobs' from 'could not parse'.
    Conflating them is the fail-open parser."""
    r = canfail.analyse_workflow("x", "name: ci\non: [push]\n")
    return (r["unverifiable"] is True and r["can_fail"] is None), \
        "job-less workflow reported unverifiable, not clean"


def ctl_p1_fire_on_a_deliberate_failure():
    """Positive control on the CONTROL SUITE. If canfail cannot flag a
    triple-semicolon workflow, nothing else in this file means anything."""
    wf = ("name: ci\non: [push]\njobs:\n  a:\n    runs-on: ubuntu-latest\n"
          "    steps:\n      - run: 'echo hi; echo there; echo x'\n")
    r = canfail.analyse_workflow("x", wf)
    return r["can_fail"] is False, "canfail fires on a pure-echo step"


def ctl_p2_fire_on_a_deliberate_harness_failure():
    """Positive control for the fail-open rule: the real substrate shape, verbatim."""
    src = ("try {\n  const r = require('./index.js');\n"
           "  console.log('OK: ' + Object.keys(r).join(', '));\n"
           "} catch (e) {\n  console.error('FAIL:', e.message);\n}\n")
    f = fh.check_fail_closed(src, "js")
    return bool(f), "failopen rule A fires on the verbatim substrate try/catch"


# ═══════════════════════════════════════════════════════ CI fixtures (can-fail-ci)

FIX_CI = {
    # ---- FAIL: the shape the brief named. 18 of 23 in the fleet audit.
    "FAIL_ci_echo_placeholder": (
        """\
name: ci
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: status
        run: echo "No CI configured for this repository yet"
"""),
    # ---- FAIL: producer | consumer. Producer can die; the pipeline reports the
    #      status of its LAST element, so the job is green over an empty artifact.
    "FAIL_ci_pipeline_tail": (
        """\
name: ci
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: ./build.sh --all 2>&1 | tail -1
"""),
    # ---- FAIL: a real command, neutralised at the end of the step.
    "FAIL_ci_or_true": (
        """\
name: ci
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: pytest -q || true
"""),
    # ---- FAIL: continue-on-error at the JOB level exempts every step in it.
    "FAIL_ci_continue_on_error": (
        """\
name: ci
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    continue-on-error: true
    steps:
      - run: pytest -q
"""),
    # ---- OK (REGRESSION, REFINEMENT 3): env-var-prefixed commands are real gates.
    #      canfail skipped any line starting `VAR=`, so it called
    #      `PYTHONPATH=src pytest -q` "no executable command" -- the fail-detector
    #      failing open. Shape taken from quilt-crabbox's apple-vm job.
    "OK_ci_env_prefixed_command": (
        """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: PYTHONPATH=src pytest -q
      - run: RUST_BACKTRACE=1 cargo test
      - run: PATH="/usr/bin:/bin:$PATH" node --test scripts/mint-aws-devt
      - run: FOO=bar
"""),
    # ---- OK: an ordinary, real gate.
    "OK_ci_real_gate": (
        """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m pytest -q
"""),
    # ---- OK (FALSE-POSITIVE TRAP 1): pipefail lives in the SAME step as the pipe.
    #      A per-file checker that sees one `set -o pipefail` anywhere in the file
    #      and exempts the whole file is the bug canfail.py was written to avoid.
    "OK_ci_pipefail_same_step": (
        """\
name: ci
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: |
          set -o pipefail
          ./build.sh --all 2>&1 | tail -1
"""),
    # ---- OK (FALSE-POSITIVE TRAP 2): guarded step FIRST, unguarded pipe in step 2.
    #      Each `run:` is its own shell. `set -o pipefail` does not carry across.
    #      CALIBRATION NOTE: this fixture's FILE-level verdict is `can fail`, because
    #      step 0 (`./configure.sh`) is a real gate. My first draft expected the file
    #      to fire and the control went red -- correctly. The trap is real but it is a
    #      PER-STEP trap; the per-step assertion below is where it belongs, and it
    #      asserts step 1 is flagged even though the file is green.
    "OK_ci_pipefail_does_not_carry": (
        """\
name: ci
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - run: |
          set -o pipefail
          ./configure.sh
      - run: ./build.sh 2>&1 | tail -1
"""),
    # ---- KNOWN FALSE POSITIVE, pinned deliberately.
    #      canfail reports a job of only `uses:` steps as "cannot fail", because it
    #      cannot read inside a composite action. But a composite action absolutely
    #      can fail -- the rule is asserting less than it knows. Measured on the
    #      fleet: 2 of 66 can-fail-ci findings are this shape.
    #      The control asserts the CURRENT behaviour so the regression is visible,
    #      and harness_check.py downgrades it to UNVERIFIABLE rather than FAIL.
    "FP_ci_uses_only_composite": (
        """\
name: ci
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: ./.github/actions/build@v1
"""),
    # ---- OK (FALSE-POSITIVE TRAP 4): a `continue-on-error: true` job sitting
    #      NEXT TO a real gate. The neighbour must not inherit the exemption and
    #      the real gate must not exempt the neighbour.
    "OK_ci_mixed_guarded_and_not": (
        """\
name: ci
on: [push]
jobs:
  guarded:
    runs-on: ubuntu-latest
    steps:
      - run: pytest -q
  unguarded:
    runs-on: ubuntu-latest
    steps:
      - run: echo "no gate here"
"""),
    # ---- OK (FALSE-POSITIVE TRAP 5): exit 0 explicitly is success; bare `exit` or
    #      `exit 1` is not. A checker that treats all `exit` as a gate over-fires.
    "OK_ci_explicit_exit_codes": (
        """\
name: ci
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: |
          pytest -q
          if [ $? -ne 0 ]; then exit 1; fi
"""),
}

# ═══════════════════════════════════════════════════ harness fixtures (fail-open)

FIX_HARNESS = {
    # ---- FAIL: THE NAMED SHAPE, copied VERBATIM from repos/substrate-bundle/test.js.
    #      My first draft of this fixture was a Python file with a `try/except` nested
    #      inside a function, and the rule correctly stayed silent -- a nested catch is
    #      the legitimate idiom that calibration v1 had to allow. I had invented a
    #      shape instead of copying the real one, and the control caught me.
    #      LESSON PINNED HERE: build fixtures from the real artifact, byte for byte.
    "FAIL_harness_swallows_exception": {
        "test.js": (
            "try {\n"
            "  const r = require('./index.js');\n"
            "  console.log('OK: ' + Object.keys(r).join(', '));\n"
            "} catch (e) {\n"
            "  console.error('FAIL:', e.message);\n"
            "}\n"
        ),
    },
    # ---- FAIL: the 7-line variant, verbatim from repos/substrate-contest/test.js.
    #      Cosmetic difference only -- proves the rule is not keyed to line count.
    "FAIL_harness_js_swallows_7line": {
        "test.js": (
            "// quick smoke test\n"
            "try {\n"
            "  const result = require('./index.js');\n"
            "  console.log('OK: ' + Object.keys(result).join(', '));\n"
            "} catch (e) {\n"
            "  console.error('FAIL:', e.message);\n"
            "}\n"
        ),
    },
    # ---- FAIL: the OTHER shape in the family. No try/catch at all -- it exits 1 on
    #      a crash -- but it never calls the product under test in any way that can
    #      fail, and it has zero assertions. Rule B. Verbatim shape from
    #      repos/substrate-attest/test.js.
    "FAIL_harness_no_assert_standalone": {
        "test.js": (
            "const { Observation } = require('@superinstance/observation-primitive');\n"
            "const { attest, aggregateTrust } = require('./index.js');\n"
            "\n"
            "const o = new Observation({\n"
            "  subject: 'substrate',\n"
            "  predicate: 'has_primitive',\n"
            "  object: 'observation',\n"
            "  issuer: 'casey',\n"
            "});\n"
            "\n"
            "const a1 = attest(o, { id: 'jane' }, { trust: 0.9 });\n"
            "console.log('aggregate trust:', aggregateTrust([a1]).toFixed(3));\n"
            "console.log('irrevocable:', a1.is_irrevocable);\n"
        ),
    },
    # ---- OK (FALSE-POSITIVE TRAP 6, regression from v1): a NESTED catch inside a
    #      test body is the correct idiom -- capture a subprocess failure, assert on
    #      it afterwards. Firing here produced 16 false positives in pong-quilt.
    "OK_harness_nested_catch_is_legitimate": {
        "test_runner.py": (
            "import subprocess\n"
            "\n"
            "\n"
            "def test_bad_input_exits_nonzero():\n"
            "    try:\n"
            "        r = subprocess.run(['false'], capture_output=True)\n"
            "    except OSError as e:\n"
            "        raise AssertionError('could not run') from e\n"
            "    assert r.returncode != 0\n"
            "\n"
            "\n"
            "def test_math():\n"
            "    assert 1 + 1 == 2\n"
        ),
    },
    # ---- OK (FALSE-POSITIVE TRAP 7, regression from v2): a pytest file with zero
    #      explicit asserts whose assertion is "this did not raise". A RUNNER
    #      collects it and supplies the implicit fail-on-exception. Firing here is
    #      most of the 49-repo over-fire.
    "OK_harness_smoke_test_collected_by_runner": {
        "tests/test_import_smoke.py": (
            "import mypackage\n"
            "\n"
            "\n"
            "def test_import_does_not_raise():\n"
            "    mypackage.load()\n"
        ),
    },
    # ---- OK (FALSE-POSITIVE TRAP 8, regression from v2): conftest/__init__/fixtures
    #      are not harnesses.
    "OK_harness_conftest_is_not_a_harness": {
        "conftest.py": (
            "import pytest\n"
            "\n"
            "\n"
            "@pytest.fixture\n"
            "def db():\n"
            "    print('connecting')\n"
            "    return object()\n"
        ),
        "tests/fixtures/sample.py": (
            "DATA = [1, 2, 3]\n"
        ),
    },
    # ---- OK (FALSE-POSITIVE REGRESSION, found by hand on 2026-10-01): a real,
    #      working, fail-closed harness that rolls its own tally with `FAIL += 1` and
    #      exits `1 if FAIL else 0`. Shape taken from gpu_bpe4quilt/tests/
    #      test_quilt_bpe.py, which REFINEMENT 2 wrongly flagged before
    #      declares_own_failure() existed. ~40 assertions, genuinely fail-closed.
    "OK_harness_own_tally_augmented_assign": {
        "tests/test_quilt_bpe.py": (
            "import sys\n"
            "\n"
            "PASS = 0\n"
            "FAIL = 0\n"
            "\n"
            "\n"
            "def check(name, got, want):\n"
            "    global PASS, FAIL\n"
            "    if got == want:\n"
            "        PASS += 1\n"
            "    else:\n"
            "        FAIL += 1\n"
            "        print('FAIL %s' % name)\n"
            "\n"
            "\n"
            "check('genesis', 1, 1)\n"
            "print('%d passed, %d failed' % (PASS, FAIL))\n"
            "sys.exit(1 if FAIL else 0)\n"
        ),
    },
    # ---- OK: a real harness with real assertions and a real non-zero path.
    "OK_harness_real_gate": {
        "test_thing.py": (
            "import sys\n"
            "\n"
            "\n"
            "def test_add():\n"
            "    assert 1 + 1 == 2\n"
            "\n"
            "\n"
            "if __name__ == '__main__':\n"
            "    try:\n"
            "        test_add()\n"
            "    except AssertionError:\n"
            "        sys.exit(1)\n"
            "    print('ok')\n"
            "    sys.exit(0)\n"
        ),
    },
    # ---- FAIL: rule B, a Python harness with no assertion primitive, collected by
    #      nobody, at a name the harness predicate accepts (`test_*.py`).
    "FAIL_harness_py_no_assert": {
        "test_verify.py": (
            "import subprocess\n"
            "\n"
            "\n"
            "subprocess.run(['make', 'all'], check=True)\n"
            "print('build verified')\n"
        ),
    },
}


# ═══════════════════════════════════════════════════════════════════ materialise

def build():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    for name, wf in FIX_CI.items():
        d = ROOT / name / ".github" / "workflows"
        d.mkdir(parents=True, exist_ok=True)
        (d / "ci.yml").write_text(wf)
    for name, files in FIX_HARNESS.items():
        d = ROOT / name
        d.mkdir(parents=True, exist_ok=True)
        for rel, src in files.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(src)
    return len(FIX_CI) + len(FIX_HARNESS)


# ═══════════════════════════════════════════════════════════════════ run

def run_ci_controls():
    """can-fail-ci. Returns (rows, failures)."""
    rows, fails = [], []
    for name in FIX_CI:
        d = ROOT / name
        wf = (d / ".github/workflows/ci.yml").read_text()
        verdict, jobs = rules.workflow_verdict(str(d / ".github/workflows/ci.yml"), wf)
        got = (verdict == "FIRE")
        r = {"error": None, "jobs": jobs}
        if name.startswith("FP_"):
            # A known false positive: the rule currently fires and should not. The
            # control pins the CURRENT behaviour so the regression stays visible, and
            # it is reported as FP -- never as a pass.
            ok, kind = got is True, "FP"
        else:
            expect_fire = name.startswith("FAIL_")
            ok = got == expect_fire
            kind = "ok" if ok else "FAIL"
        rows.append(("can-fail-ci", name, got, ok, kind,
                     r.get("error") or "; ".join(
                         f"s{i['index']}:{';'.join(i['reasons'])}"
                         for j in r["jobs"] for i in j["steps"]
                         if i["can_fail"] is False) or "-"))
        if not ok:
            fails.append(name)
    # per-step / per-job precision controls
    p = canfail.analyse_workflow("x", FIX_CI["OK_ci_pipefail_does_not_carry"])
    bad = [s["index"] for s in p["jobs"][0]["steps"] if s["can_fail"] is False]
    ok = bad == [1]
    rows.append(("can-fail-ci", "PER-STEP: pipefail does not cross run: shells", True, ok,
                 "ok" if ok else "FAIL", f"flagged steps={bad} expected=[1]"))
    if not ok:
        fails.append("per-step")

    m = canfail.analyse_workflow("x", FIX_CI["OK_ci_mixed_guarded_and_not"])
    badj = [j["job"] for j in m["jobs"] if not j["can_fail"]]
    ok = badj == ["unguarded"]
    rows.append(("can-fail-ci", "PER-JOB: guarded job must not exempt its neighbour", True, ok,
                 "ok" if ok else "FAIL", f"flagged={badj} expected=['unguarded']"))
    if not ok:
        fails.append("per-job")
    return rows, fails


def run_harness_controls():
    """fail-open-harness, driven through the same lint_repo() the fleet run uses."""
    import tempfile
    rows, fails = [], []
    for name in FIX_HARNESS:
        d = ROOT / name
        expect_fire = name.startswith("FAIL_")
        fs = rules.fail_open_harness(str(d))['findings']
        got = bool(fs)
        ok = got == expect_fire
        detail = "; ".join(f"{f['rule']}@{f['file']}:{f['line']}" for f in fs) or "silent"
        rows.append(("fail-open-harness", name, got, ok,
                     "ok" if ok else "FAIL", detail))
        if not ok:
            fails.append(name)
    return rows, fails


def main():
    n = build()
    ci_rows, ci_f = run_ci_controls()
    h_rows, h_f = run_harness_controls()
    allrows = ci_rows + h_rows
    fails = ci_f + h_f

    print("=" * 104)
    print("NEGATIVE CONTROLS - every rule, both directions")
    print("=" * 104)
    print(f"{n} constructed repositories on disk under {ROOT}")
    print("Every FAIL_ fixture is copied VERBATIM from a real fleet artifact.\n")
    print(f"{'RULE':<19} {'FIXTURE':<46} {'GOT':<6} {'':<5} DETAIL")
    print("-" * 104)
    for rule, name, got, ok, kind, detail in allrows:
        print(f"{rule:<19} {name:<46} {str(got):<6} {kind:<5} {detail[:62]}")

    nfp = sum(1 for r in allrows if r[4] == "FP")
    nfire = sum(1 for r in allrows if r[2] and r[4] == "ok")
    nquiet = sum(1 for r in allrows if not r[2] and r[4] == "ok")

    # plumbing controls
    print("\n" + "=" * 104)
    print("PLUMBING CONTROLS — run FIRST, because a broken instrument looks exactly")
    print("like a clean bill of health. These assert the harness can read at all.")
    print("-" * 100)
    plumbing = [ctl_y1_yaml_parses, ctl_y2_shim_raises_on_garbage,
                ctl_y3_cannot_fail_looks_unverifiable_not_clean,
                ctl_p1_fire_on_a_deliberate_failure,
                ctl_p2_fire_on_a_deliberate_harness_failure]
    pfail = []
    for fn in plumbing:
        ok, note = fn()
        print(f"  [{'ok ' if ok else 'FAIL'}] {fn.__name__:<46} {note}")
        if not ok:
            pfail.append(fn.__name__)

    print("\n" + "=" * 104)
    print(f"rule controls : {len(allrows)} total, {len(fails)} mismatch")
    print(f"  fires on a constructed FAILURE  : {nfire}/{sum(1 for r in allrows if r[2])}")
    print(f"  silent on a constructed SUCCESS : {nquiet}/{sum(1 for r in allrows if not r[2])}")
    print(f"  known FALSE POSITIVES pinned    : {nfp}")
    if fails or pfail:
        print(f"\nCONTROL SUITE RED: {fails + pfail}")
        return 1
    print("\nCONTROL SUITE GREEN — every rule fires on a constructed failure and stays")
    print("quiet on a constructed success. The rules may now be pointed at the fleet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
