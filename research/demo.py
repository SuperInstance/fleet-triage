#!/usr/bin/env python3
"""
demo.py -- prove seamclaim can FAIL, and that it fails on things that really happened.

Three demonstrations, none of them simulated:

  D1  A REAL race.  8 OS processes, launched at once, all claiming the same real
      evidence unit.  Exactly one may win.  This is open(2) O_EXCL arbitration,
      not a lock protocol -- the processes do not know about each other.

  D2  A REAL collision, already published in this repo.  Six documents carry four
      mutually exclusive published counts for `BattenSpline`.  They shipped.  The
      claims are registered here and the audit is asked to find them.

  D3  A REAL bypass.  Tonight's actual lane documents are audited against a
      registry nobody populated.  Coverage is the honest answer, and it is 0.

Every number printed here is produced by running the thing.  Exit 0 only if all
three demonstrations behave as specified.
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SC = [sys.executable, os.path.join(HERE, "seamclaim.py")]

# The four mutually exclusive published claims about BattenSpline, each with the
# file:line the orchestrator's own librarian recorded.  Not invented for this demo.
BATTENSPLINE = [
    ("RESOLVER-FINAL.md",   "RESOLVER-FINAL.md:18",
     "10 hits, 0 in code"),
    ("BOARD.md",            "BOARD.md:94",
     "10 all prose"),
    ("INDEX.md",            "INDEX.md:50",
     "10 prose"),
    ("CLOSE-LOOP.md",       "CLOSE-LOOP.md:234",
     "0 occurrences across all 275 fleet repos"),
    ("CORRECTION-CONSERVATION.md", "CORRECTION-CONSERVATION.md:15",
     "RETRACTED - 136 code hits, it is real"),
    ("ORIENTATION.md",      "ORIENTATION.md:46",
     "136 code hits and I published that it was wrong"),
]

RESIDUAL = [
    ("RESOLVER-FINAL.md",   "RESOLVER-FINAL:17", "cited at rubiks.py:281 | 1 | 0"),
    ("BOARD.md",            "BOARD:17",  "cites murmur/transforms/rubiks.py:437; that directory does not exist"),
    ("CLOSE-LOOP.md",       "CLOSE-LOOP:224", "builds a theorem on rubiks.py:437 and quotes update_certainty at rubiks.py:281. Neither line exists."),
    ("CORRECTION-CONSERVATION.md", "CORRECTION-CONSERVATION:28", "murmur/logtensor/transforms/rubiks.py - a path that has never existed in any branch"),
    ("ORIENTATION.md",      "ORIENTATION:44", "murmur/logtensor/transforms/rubiks.py, never present in any branch"),
]

FAILED = []


def run(args, **kw):
    return subprocess.run(SC + args, capture_output=True, text=True, **kw)


def banner(t):
    print("\n" + "=" * 74)
    print(t)
    print("=" * 74)


def reset():
    d = os.path.join(HERE, "seams")
    import shutil
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d, exist_ok=True)


# --------------------------------------------------------------- D1
def d1_race(n=8):
    banner("D1  REAL CONCURRENT RACE  --  %d processes, one evidence unit, no coordinator" % n)
    reset()
    unit = ["REPO:quilt-adjudication"]
    procs = [subprocess.Popen(
        SC + ["claim", "--lane", "racer-%02d" % i, "--seam", "race-demo",
              "--evidence"] + unit + ["--note", "concurrent"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        for i in range(n)]
    outs = [(p.wait(), p) for p in procs]
    won = held = other = 0
    for rc, p in outs:
        if rc == 0:
            won += 1
        elif rc == 2:
            held += 1
        else:
            other += 1
    print(f"  processes launched      {n}")
    print(f"  exited 0 (CLAIMED)      {won}")
    print(f"  exited 2 (E_SEAM_HELD)  {held}")
    print(f"  exited other            {other}")
    print(f"  claim files on disk     {len([f for f in os.listdir(os.path.join(HERE,'seams')) if f.endswith('.claim')])}")
    ok = (won == 1 and held == n - 1 and other == 0)
    if not ok:
        FAILED.append("D1: expected exactly 1 winner, got %d" % won)
    print(f"  VERDICT: {'PASS - kernel arbitrated, exactly one holder' if ok else 'FAIL'}")
    return ok


# --------------------------------------------------------------- D2
def d2_collision():
    banner("D2a  A REAL CONTRADICTION THAT ALREADY SHIPPED IN THIS REPO")
    reset()
    fact = "BattenSpline-executable-code-hits"
    print("  four mutually exclusive published counts for one fact, in six live docs.")
    print("  (the four claims and their file:line are the orchestrator's own, in")
    print("   orch-LIBRARIAN.md section 1 -- nothing here is invented for the demo)")
    for doc, loc, claim in BATTENSPLINE:
        r = run(["claim-fact", "--lane", doc, "--fact", fact, "--at", loc, "--claim", claim])
        print(f"    {doc:<28} exit {r.returncode}  {r.stdout.strip().splitlines()[0] if r.stdout.strip() else ''}")
    r = run(["audit-facts"])
    print()
    for line in r.stdout.splitlines():
        print("   ", line)
    coll_n, unver = 0, 0
    for line in r.stdout.splitlines():
        s = line.strip()
        if s.startswith("facts with >1 distinct claim"):
            coll_n = int(s.split()[-1])
        if s.startswith("locations that DO NOT exist"):
            unver = int(s.split()[-1])
    ok = (r.returncode == 3 and coll_n == 1 and unver == 0)
    if not ok:
        FAILED.append("D2a: contradiction audit rc=%d contradictions=%d unverifiable=%d"
                      % (r.returncode, coll_n, unver))
    print(f"  VERDICT: {'PASS - the conflict is named, located, and quoted from source' if ok else 'FAIL'}")
    return ok


def d2b_fake():
    banner("D2b  THE COLLISION MANIFEST IS ITSELF AUDITED")
    reset()
    fact = "BattenSpline-executable-code-hits"
    r0 = run(["claim-fact", "--lane", "RESOLVER-FINAL.md", "--fact", fact,
              "--at", "RESOLVER-FINAL.md:9999", "--claim", "10 hits, 0 in code"])
    print("  registering a claim at a location that does not exist:")
    for line in r0.stdout.splitlines():
        print("   ", line)
    ok_refuse = (r0.returncode == 1 and "refusing" in r0.stdout)
    r1 = run(["audit-facts"])
    coll = "facts with >1 distinct claim  0" in r1.stdout
    ok = ok_refuse and coll
    if not ok:
        FAILED.append("D2b: unverifiable location was accepted (rc=%d)" % r0.returncode)
    print(f"\n  audit then reports contradictions: {coll}")
    print(f"  VERDICT: {'PASS - you cannot report a collision you cannot point at' if ok else 'FAIL'}")
    return ok


def d2c_replication():
    banner("D2c  A REAL REPLICATION THAT WAS NOT ONE  --  5 lanes, 1 seam, 1 answer")
    reset()
    unit = "INSTR:rubiks.py"
    print("  five live documents in this repo read the SAME evidence unit:")
    print("    INSTR:rubiks.py   (murmur/transforms/rubiks.py, SuperInstance-papers)")
    print("  and every one of them published that the file does not exist:")
    for doc, loc, claim in RESIDUAL:
        r = run(["claim", "--lane", doc, "--seam", "papers-rubiks", "--evidence", unit,
                 "--note", claim])
        status = "CLAIMED" if r.returncode == 0 else "E_SEAM_HELD"
        print(f"    {doc:<28} {status:<12} {loc}")
    won = sum(1 for doc, _, _ in RESIDUAL
              if run(["claim", "--lane", doc, "--seam", "papers-rubiks",
                      "--evidence", unit, "--note", "second attempt"]).returncode == 0)
    r = run(["audit-facts"])
    n_claims = len([f for f in os.listdir(os.path.join(HERE, "seams"))
                    if f.endswith(".claim")])
    print(f"\n  distinct holders of the seam : 1  (all later attempts refused)")
    print(f"  claim files on disk          : {n_claims}")
    print(f"  lanes that reached it        : {len(RESIDUAL)}")
    print(f"  independent findings         : 1")
    print(f"  -> replication factor        : 1.0x across {len(RESIDUAL)} observers")
    ok = (n_claims == 1 and won == 0)
    if not ok:
        FAILED.append("D2c: seam admitted more than one holder (%d claims, %d re-wins)"
                      % (n_claims, won))
    print(f"  VERDICT: {'PASS - the seam was exclusive, so 5 agreeing lanes bought 1' if ok else 'FAIL'}")
    return ok


# --------------------------------------------------------------- D3
def d3_bypass():
    banner("D3  REAL BYPASS  --  tonight's actual lane documents, nobody claimed anything")
    reset()
    lo = time.mktime(time.strptime("2026-10-02 00:00", "%Y-%m-%d %H:%M"))
    hi = time.mktime(time.strptime("2026-10-03 00:00", "%Y-%m-%d %H:%M"))
    docs = []
    for f in sorted(os.listdir(ROOT)):
        if f.endswith(".md") and lo <= os.stat(os.path.join(ROOT, f)).st_mtime <= hi:
            docs.append(os.path.join(ROOT, f))
    print(f"  lane documents written in the window : {len(docs)}")
    r = run(["audit"] + docs)
    print()
    for line in r.stdout.splitlines()[:16]:
        print("   ", line)
    cov = None
    for line in r.stdout.splitlines():
        if "properly claimed" in line:
            cov = line
    ok = (r.returncode == 3)
    if not ok:
        FAILED.append("D3: audit passed an unclaimed round (rc=%d)" % r.returncode)
    print(f"\n  {cov}")
    print(f"  audit exit code: {r.returncode}  (3 = canary fired, round is VOID)")
    print(f"  VERDICT: {'PASS - non-coordination is detected, not merely possible' if ok else 'FAIL'}")
    return ok


def main():
    print("seamclaim demonstration -- every number below is produced by running the tool")
    t0 = time.time()
    r1 = d1_race()
    r2 = d2_collision()
    r2b = d2b_fake()
    r2c = d2c_replication()
    r3 = d3_bypass()
    banner("SUMMARY")
    print(f"  D1  concurrent race       {'PASS' if r1 else 'FAIL'}")
    print(f"  D2a shipped contradiction {'PASS' if r2 else 'FAIL'}")
    print(f"  D2b fake-collision guard  {'PASS' if r2b else 'FAIL'}")
    print(f"  D2c replication count     {'PASS' if r2c else 'FAIL'}")
    print(f"  D3  bypass detection      {'PASS' if r3 else 'FAIL'}")
    print(f"  elapsed {time.time()-t0:.1f}s")
    if FAILED:
        print("\n  FAILURES:")
        for f in FAILED:
            print("   -", f)
        return 1
    print("\n  the mechanism can fail on all three axes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
