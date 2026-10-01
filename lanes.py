#!/usr/bin/env python3
"""lanes.py — multi-beam instrumentation for the agent's OWN work.

WHY THIS EXISTS, in the order the reasons actually bit.

1. I declared nine subagent dispatches "dead, zero artifacts" at 15 minutes. They were
   producing the whole time. **A lane's status is a claim, and I checked it with one beam.**

2. `voxelglyph` shipped seven green pins that never executed the experiment they verified.
   The product was wrong and the suite was 7/7. **A green signal is not a sounding.**

3. I nearly edited a solver to match an assertion I had never independently established. **The
   one-beam check would have said the solver was wrong.**

So: every lane gets FOUR independent beams, and **a lane is DONE only when the beams agree**.
When they disagree, the disagreement is the finding — which is the entire lesson of
`voxelglyph`, `F1-AUDIT.md`, and the corrected `F1-F2-DIFFUSION.md`.

THE FOUR BEAMS, each answering a different question so that no single failure mode can
satisfy more than one:

  B1 EXISTS     does the artifact physically exist, and is it non-trivial?
  B2 SAYS       does it contain the specific claims we are relying on? (grep, not vibes)
  B3 REPRODUCES does the number still hold when recomputed from source?
  B4 CONTROL    would this lane's own check have failed on a known-bad input?

A single beam is a sounding at one point. Two agreeing beams are a position. **B3 and B4 are
the ones that catch `voxelglyph`**, and B1+B2 are the ones that catch a file that exists and
says nothing — which is what "zero artifacts" looked like for fifteen minutes.

Stdlib only. No network. Runs anywhere.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict

# ── the four beams ────────────────────────────────────────────────────────────

def beam_exists(path: str) -> dict:
    """B1. Does it exist, and is it big enough to be a thing rather than a stub?"""
    if not os.path.exists(path):
        return {"beam": "EXISTS", "ok": False, "detail": "no file at %s" % path}
    n = os.path.getsize(path)
    if n < 200:
        return {"beam": "EXISTS", "ok": False,
                "detail": "%d bytes — below the 200 floor, this is a stub not a result" % n}
    return {"beam": "EXISTS", "ok": True, "detail": "%d bytes" % n}


def beam_says(path: str, must_contain: list) -> dict:
    """B2. Does it actually contain the claims we are relying on?

    A grep, not a vibe. The failure this catches is the file that exists and says nothing
    relevant -- which is what a lane that produced no result looks like from the outside.
    """
    if not os.path.exists(path):
        return {"beam": "SAYS", "ok": False, "detail": "cannot read"}
    try:
        body = open(path, encoding="utf-8", errors="replace").read()
    except Exception as e:
        return {"beam": "SAYS", "ok": False, "detail": "read error %s" % e}
    missing = [c for c in (must_contain or []) if c not in body]
    if missing:
        return {"beam": "SAYS", "ok": False,
                "detail": "missing %d/%d required claims: %s"
                          % (len(missing), len(must_contain or []), missing[:3])}
    return {"beam": "SAYS", "ok": True,
            "detail": "all %d required claims present" % len(must_contain or [])}


def beam_reproduces(cmd: list, cwd: str = None, expect_rc: int = 0) -> dict:
    """B3. Run the thing. `succeeded` is not a deliverable."""
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        return {"beam": "REPRODUCES", "ok": False, "detail": "timed out at 180s"}
    except Exception as e:
        return {"beam": "REPRODUCES", "ok": False, "detail": "%s: %s" % (type(e).__name__, e)}
    ok = r.returncode == expect_rc
    tail = (r.stdout or r.stderr or "").strip().splitlines()[-3:]
    return {"beam": "REPRODUCES", "ok": ok,
            "detail": "rc=%d (want %d) %s" % (r.returncode, expect_rc, " / ".join(tail))[:200]}


def beam_control(repro_ok, control_failed_as_expected) -> dict:
    """B4. The control arm. This is the beam that catches `voxelglyph`.

    THE CONTRACT, stated so the branch order cannot be got wrong again:
      `control_failed_as_expected` is True when the control run -- which was fed a
      DELIBERATELY BROKEN input -- exited non-zero. That is the GOOD outcome.
      It is False when the control run succeeded on broken input, which means the check
      cannot fail and everything it "verified" is decoration.

    The first version of this function had the two branches swapped: it reported
    "the control PASSED on broken input" for a control that had correctly failed, and the
    demo showed a falsifiable check being rejected. Found by running the demo, which is
    the only reason it was found at all -- the function reads correctly in both directions
    when you are looking at it and you already believe what it says.
    """
    if control_failed_as_expected is None:
        return {"beam": "CONTROL", "ok": False,
                "detail": "no control ran — a check that was never shown to fail is not a check"}
    if not control_failed_as_expected:
        return {"beam": "CONTROL", "ok": False,
                "detail": "the control SUCCEEDED on deliberately-broken input; "
                          "the check cannot fail"}
    return {"beam": "CONTROL", "ok": True,
            "detail": "control correctly FAILED on broken input — the check is falsifiable"}


# ── the lane ──────────────────────────────────────────────────────────────────

@dataclass
class Lane:
    name: str
    path: str = ""
    must_contain: list = field(default_factory=list)
    repro_cmd: list = field(default_factory=list)
    repro_cwd: str = None
    repro_rc: int = 0
    control_cmd: list = field(default_factory=list)
    control_cwd: str = None
    control_rc: int = 0
    born: float = 0.0
    min_age_s: int = 300
    beams: list = field(default_factory=list)

    def instrument(self) -> dict:
        self.beams = []
        if self.path:
            self.beams.append(beam_exists(self.path))
            if self.must_contain:
                self.beams.append(beam_says(self.path, self.must_contain))
        if self.repro_cmd:
            self.beams.append(beam_reproduces(self.repro_cmd, self.repro_cwd, self.repro_rc))
        if self.control_cmd:
            if self.control_cmd == self.repro_cmd:
                # THE DEMO CAUGHT THIS. A lane whose "control" is the same command as its
                # repro cannot falsify itself: it will agree with the repro by construction,
                # and beam_control will then report "correctly failed" for a run that never
                # failed. That is the `voxelglyph` error at the orchestration layer -- a
                # green control arm that has never been red.
                self.beams.append({"beam": "CONTROL", "ok": False,
                    "detail": "control_cmd is identical to repro_cmd: this control cannot "
                              "falsify anything and its 'agreement' is a tautology"})
            else:
                c = beam_reproduces(self.control_cmd, self.control_cwd, self.control_rc)
                # invert: the control is EXPECTED to fail
                self.beams.append(beam_control(True, not c["ok"]))
        return self.verdict()

    def verdict(self) -> dict:
        if not self.beams:
            return {"state": "NOT_INSTRUMENTED",
                    "why": "no beams — a lane with no beams is a claim, not a measurement"}
        age = time.time() - (self.born or time.time())
        # The age guard applies ONLY to a lane that was supposed to write an artifact.
        # The first version applied it to any lane without an EXISTS beam, so a lane whose
        # beams were REPRODUCES + CONTROL never ran them and was reported TOO_EARLY. That is
        # the exact defect this file exists to catch -- a control that never executed,
        # reported as if it had. Found by running the demo, not by reading the code.
        if self.path:
            present = [b for b in self.beams if b["beam"] in ("EXISTS", "SAYS")]
            if not present:
                return {"state": "TOO_EARLY" if age < self.min_age_s else "MISSING",
                        "why": "no artifact after %ds (floor is %ds). A lane that looks dead "
                               "at 15 minutes is not a dead lane — I have made that mistake."
                               % (int(age), self.min_age_s),
                        "beams": self.beams}
        failed = [b for b in self.beams if not b["ok"]]
        if failed:
            names = ", ".join(b["beam"] for b in failed)
            return {"state": "DISAGREEMENT",
                    "why": "beams disagree: %s" % names,
                    "detail": [b["detail"] for b in failed],
                    "beams": self.beams}
        return {"state": "DONE",
                "why": "%d beams agree" % len(self.beams),
                "beams": self.beams}


# ── a runnable demonstration, so this file is not a claim about itself ──────────

def _demo():
    import tempfile
    d = tempfile.mkdtemp()
    good = os.path.join(d, "good.md")
    open(good, "w").write("# result\n\n" + "the digest is 0x4ef8351a5c319637 and the count is 54,166\n" * 8)
    stub = os.path.join(d, "stub.md")
    open(stub, "w").write("ok")
    liar = os.path.join(d, "liar.md")
    open(liar, "w").write("# result\n\n" + "nothing relevant here at all\n" * 30)

    # a check that CAN fail: it reads a file and exits non-zero if the digest is wrong
    check = os.path.join(d, "check.py")
    open(check, "w").write(
        "import sys\n"
        "good = open(sys.argv[1]).read()\n"
        "print('all 94 checks green' if '0x4ef8351a5c319637' in good else 'DIGEST MISMATCH')\n"
        "raise SystemExit(0 if '0x4ef8351a5c319637' in good else 1)\n")
    # a check that CANNOT fail: it always exits 0, even on a broken input
    neverfails = os.path.join(d, "neverfails.py")
    open(neverfails, "w").write("print('all 94 checks green'); raise SystemExit(0)\n")
    broken = os.path.join(d, "broken.md")
    open(broken, "w").write("# result\n\n" + "wrong digest entirely\n" * 30)

    print("  instrumenting four lanes, one of which is a lie:\n")
    cases = [
        ("honest: exists, says the claims, reproduces",
         Lane("honest", good, ["0x4ef8351a5c319637", "54,166"])),
        ("stub: file exists, too small to be a result",
         Lane("stub", stub)),
        ("liar: 2 KB of prose, none of it the claim",
         Lane("liar", liar, ["0x4ef8351a5c319637"])),
        ("falsifiable check, control correctly red",
         Lane("good-check", path=good, must_contain=["0x4ef8351a5c319637"],
              repro_cmd=["python3", check, good],
              control_cmd=["python3", check, broken])),
        ("UNFAILABLE check: green on a broken input",
         Lane("unfailable", path=good, must_contain=["0x4ef8351a5c319637"],
              repro_cmd=["python3", neverfails],
              control_cmd=["python3", neverfails])),
        ("tautological control: same command as the repro",
         Lane("tautology", path=good,
              repro_cmd=["python3", check, good],
              control_cmd=["python3", check, good])),
        ("no beams at all: a status, not a measurement",
         Lane("unmeasured")),
    ]
    for label, lane in cases:
        v = lane.instrument()
        print(f"    {label}")
        print(f"      -> {v['state']}: {v['why']}")
        if v.get("detail"):
            print(f"         {v['detail']}")
    print("\n  The liar and the stub both EXIST. Only B2 and B4 catch them,")
    print("  which is the whole reason a single beam is not a sounding.")


if __name__ == "__main__":
    if "--demo" in sys.argv or len(sys.argv) == 1:
        _demo()
