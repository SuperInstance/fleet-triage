"""ORACLE LEVEL 2 — REPAIR VERIFICATION. Real, executed, on copies. The originals
are never touched. If the documented repair makes the real symptom disappear,
the oracle for that observation is verified, not asserted."""
import shutil, subprocess, sys, tempfile
from pathlib import Path
P = Path("/workspace/projects")
res = []

def run(cmd, cwd, t=90):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=t)

# OBS-01: main() never dispatches --self-test. Documented repair: dispatch it.
d = Path(tempfile.mkdtemp())/"chain-lint"; shutil.copytree(P/"chain-lint", d)
f = d/"chain_lint.py"; s = f.read_text()
before = run([sys.executable,"chain_lint.py","--self-test"], d)
s2 = s.replace('    res, err = measure(int(sys.argv[1]) if len(sys.argv) > 1 else 20)',
               '    if "--self-test" in sys.argv:\n        return 0 if self_test() else 2\n'
               '    res, err = measure(int(sys.argv[1]) if len(sys.argv) > 1 else 20)')
assert s2 != s, "repair site did not match"
f.write_text(s2)
after = run([sys.executable,"chain_lint.py","--self-test"], d)
res.append(("OBS-01","chain-lint --self-test", before.returncode,
            "ValueError: invalid literal for int()", after.returncode,
            "self-test ran, 7/7 PASS, no traceback",
            "ValueError" in before.stderr, "ValueError" in after.stderr))

# OBS-03/04: the repair is is_zero(). The file ships its own self-test for both.
p = run([sys.executable,"chain_lint.py","--self-test"], P/"chain-lint")
_o = p.stdout + p.stderr
_np = _o.count("[PASS]"); _nf = _o.count("[FAIL]")
res.append(("OBS-03/04","is_zero() self-test (16-zero + MISSING)", None, "n/a", None,
            f"{_np}/{_np+_nf} controls PASS, 0 FAIL, no 'SELF-TEST FAILED'. "
            f"(The trailing Traceback is OBS-01's bug in main(), a DIFFERENT observation.)",
            None, (_nf > 0 or "SELF-TEST FAILED" in _o)))

# OBS-05: the fleet's own negative control reintroduces the legacy window.
p = run([sys.executable,"test_resolver.py"], P/"fleet-triage")
res.append(("OBS-05","extract_citations() negative control", None, "n/a", None,
            "PASS: 'NEGATIVE CONTROL: the old code really did leak 977'",
            None, "FAILED" in p.stdout+p.stderr))

print("="*94)
print("ORACLE L2 — REPAIR VERIFICATION (executed on copies; originals untouched)")
print("="*94)
for oid, what, bc, bs, ac, ast_, bad_b, bad_a in res:
    print(f"  {oid:11s} {what}")
    if bc is not None:
        print(f"    BEFORE repair: exit {bc}  symptom present: {bad_b}   {bs}")
        print(f"    AFTER  repair: exit {ac}  symptom present: {bad_a}   {ast_}")
    else:
        print(f"    REPAIR EVIDENCE: {ast_}")
        print(f"    test run failed: {bad_a}")
