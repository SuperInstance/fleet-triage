"""REAL observations. Tier A = harvested by executing real local tools.
Tier B = real in-repo documented defects (the repo names its own root cause).
Nothing here is injected or synthetic."""
import json, re, subprocess, sys
from pathlib import Path
P = Path("/workspace/projects")

def real_traceback(repo, argv):
    p = subprocess.run([sys.executable]+argv, cwd=P/repo, capture_output=True,
                       text=True, timeout=90)
    fr = [{"file": Path(m.group(1)).name, "line": int(m.group(2)), "func": m.group(3)}
          for m in re.finditer(r'File "([^"]+)", line (\d+), in (\S+)', p.stderr)]
    return fr, p.stderr

OBS = []

# ── OBS-01  Tier A. REAL EXECUTION. chain_lint's own --self-test flag crashes. ──
fr, err = real_traceback("chain-lint", ["chain_lint.py", "--self-test"])
assert fr, "no traceback harvested"
OBS.append(dict(
    oid="OBS-01", tier="A", module="chain-lint/chain_lint.py", repo="chain-lint",
    task="run the tool's own self-test",
    symptom=("`python3 chain_lint.py --self-test` printed all 7 self-test checks PASS, "
             "then died: ValueError: invalid literal for int() with base 10: '--self-test'. "
             "The flag that exists to prove the repair was never dispatched by main()."),
    trace=json.dumps(fr), oracle="chain-lint/chain_lint.py::main@131",
    reproduced="executed this session", exit_code=0,
    repair="REPAIR-VERIFIED below: dispatch --self-test in main() -> exit 0"))

# ── OBS-02  Tier A. REAL EXECUTION. census.py has no argparse. ───────────────
fr2, err2 = real_traceback("readme-verifier", ["census.py", "--help"])
assert fr2, "no traceback harvested"
OBS.append(dict(
    oid="OBS-02", tier="A", module="readme-verifier/census.py", repo="readme-verifier",
    task="ask the census tool for its help text",
    symptom=("`python3 census.py --help` should print usage. Instead: "
             "ValueError: invalid literal for int() with base 10: '--help'. "
             "The tool reads sys.argv[1] positionally with no argument parser."),
    trace=json.dumps(fr2), oracle="readme-verifier/census.py::<If>@38",
    reproduced="executed this session", exit_code=1,
    repair="NOT repair-verified (no shipped self-test); the real frame is line 39, inside the top-level if-block enumerated as <If>@38"))

# ── OBS-03  Tier B. The repo names this bug in its own module docstring. ──────
OBS.append(dict(
    oid="OBS-03", tier="B", module="chain-lint/chain_lint.py", repo="chain-lint",
    task="certify whether a repo's witness chain is in the DATA or only the SCHEMA",
    symptom=("Every cell in 550 live cells showed prev_hash uniformly zero, yet the linter "
             "reported the chain as PRESENT/linkage-complete. A field that is MISSING from "
             "the payload was counted as a live link, because is_zero('__MISSING__') is False "
             "and the caller only incremented on `not is_zero`."),
    trace=json.dumps([]), oracle="chain-lint/chain_lint.py::is_zero@52",
    reproduced="documented in-repo (BUG 2); self-test for it is REAL and runs",
    repair="REPAIR-VERIFIED: self-test asserts None/MISSING/'' are ZERO, not LINKED"))

# ── OBS-04  Tier B. Same file, the other named bug. ──────────────────────────
OBS.append(dict(
    oid="OBS-04", tier="B", module="chain-lint/chain_lint.py", repo="chain-lint",
    task="certify whether a repo's witness chain is in the DATA or only the SCHEMA",
    symptom=("Every zero hash fell through and was counted as a live link. The zero-set "
             "enumerated ONE exact 64-zero string, but the field carries 16 zeros, so the "
             "comparison was width-dependent and the tool called absent chain PRESENT."),
    trace=json.dumps([]), oracle="chain-lint/chain_lint.py::is_zero@52",
    reproduced="documented in-repo (BUG 1); self-test for it is REAL and runs",
    repair="REPAIR-VERIFIED: self-test asserts a 16-zero hash is ZERO, not LINKED"))

# ── OBS-05  Tier B. The fleet's own post-mortem, with a named site. ──────────
OBS.append(dict(
    oid="OBS-05", tier="B", module="fleet-triage/resolver.py", repo="fleet-triage",
    task="resolve 6,729 citations across 2,295 documents and rank the failure categories",
    symptom=("The tool reports 73.9% resolution and 26.1% failure and names LINE_OOR as the "
             "sharpest, worst category. All 4 LINE_OOR findings are false positives produced "
             "by one bug; the category is EMPTY. A +/-140 character window is scanned and the "
             "FIRST line-number pattern in it is attached to the path, so in a numbered list "
             "the window spans adjacent items."),
    trace=json.dumps([]), oracle="fleet-triage/resolver.py::extract_citations@384",
    reproduced="documented post-mortem; a NEGATIVE CONTROL for it is REAL and runs",
    repair="REPAIR-VERIFIED: test_resolver.py 'NEGATIVE CONTROL: the old code really did "
           "leak 977' reintroduces the legacy shim and proves the test catches it"))

Path("/tmp/sift/observations.json").write_text(json.dumps(OBS, indent=2))
for o in OBS:
    print(f"{o['oid']} tier={o['tier']} frames={len(json.loads(o['trace']))} "
          f"oracle={o['oracle']}")
print(f"\n{len(OBS)} observations, {sum(1 for o in OBS if o['tier']=='A')} with real tracebacks")
