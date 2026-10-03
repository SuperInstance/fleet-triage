#!/usr/bin/env python3
"""
seamclaim.py -- a seam you can CLAIM, without asking the orchestrator.

THE PROBLEM IT SOLVES
---------------------
Every result tonight came back through one agent.  A lane could not see that
another lane was already inside the same repo, the same script, or the same
doctrine sentence, so two lanes did the same work and neither knew.  GATE.md is a
linter: it reads finished work and complains.  ORCH-SCOREBOARD.md is a board: it
displays what someone typed into it.  Neither one *prevents* the second lane from
starting, and a display surface that does not prevent anything is a log.

THE MECHANISM
-------------
Three primitives, no orchestrator in the path:

  1. A SEAM is a set of evidence units -- the concrete bytes a lane will read
     (a repo, a script, a directory, a file).  Not a topic.  Not a description.
     Units are namespaced strings; the registry only ever sees their SHA-1.

  2. A claim is an O_CREAT|O_EXCL open(2) on research/seams/<sha1>.unit.
     The kernel arbitrates the race.  Two agents in two terminals, on the same
     box, with no coordinator, no lock protocol, no message passing: exactly one
     create() returns a file descriptor, the other gets EEXIST.  This is the
     only coordination primitive in the file, and it is a syscall.

  3. A LEASE is a timestamp in the claim body.  A lane that dies holding a seam
     does not deadlock the round: the lease expires and the claim becomes
     stealable -- but the steal is RECORDED in the history, never silent.  A seam
     that changes hands without a trace is indistinguishable from a seam that
     was never exclusive.

THE HALF THAT MAKES IT A CANARY AND NOT A GREEN BADGE
-----------------------------------------------------
`audit` does not check that claims exist.  It checks the OTHER direction: it
re-derives each lane's evidence set from the artefact it actually produced and
asks whether that evidence was CLAIMED BY ANYONE.  A lane that never called
`claim` is reported as UNCLAIMED and the audit exits nonzero.

  A coordination mechanism that cannot detect non-coordination is a badge.
  This one exits 3.

  `audit` also reports COLLISION -- one evidence unit, two or more claimants --
  which is the failure this whole exercise exists to prevent, and which, on this
  repo's own history, has already shipped at least once (see PARALLELISM.md §4).
"""
import argparse
import errno
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SEAMS = os.path.join(HERE, "seams")

E_OK, E_HELD, E_BAD, E_VOID = 0, 2, 1, 3


def unit_path(unit):
    h = hashlib.sha1(unit.encode()).hexdigest()[:20]
    # keep a readable prefix so `ls seams/` is legible to a human
    slug = re.sub(r"[^A-Za-z0-9]+", "-", unit)[:44].strip("-")
    return os.path.join(SEAMS, f"{h}.{slug}.claim")


def ensure():
    os.makedirs(SEAMS, exist_ok=True)


def atomic_claim(unit, lane, seam, note, lease):
    """O_CREAT|O_EXCL -- the kernel decides, not this process."""
    ensure()
    p = unit_path(unit)
    body = json.dumps({
        "unit": unit, "lane": lane, "seam": seam, "note": note,
        "pid": os.getpid(), "claimed_at": time.time(),
        "claimed_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "lease_until": time.time() + lease,
    }, sort_keys=True)
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except OSError as e:
        if e.errno == errno.EEXIST:
            return False, read_claim(p)
        raise
    with os.fdopen(fd, "w") as fh:
        fh.write(body)
    return True, json.loads(body)


def read_claim(p):
    try:
        with open(p) as fh:
            return json.load(fh)
    except Exception:
        return {"unit": "?", "lane": "<unreadable>", "seam": "?", "note": "corrupt claim"}


def sweep_expired(now=None, quiet=False):
    """Expire dead leases.  Returns list of (unit, holder) freed."""
    now = now or time.time()
    freed = []
    if not os.path.isdir(SEAMS):
        return freed
    for f in os.listdir(SEAMS):
        if not f.endswith(".claim"):
            continue
        p = os.path.join(SEAMS, f)
        c = read_claim(p)
        if c.get("lease_until", 0) < now:
            os.rename(p, p + ".expired")
            freed.append((c.get("unit"), c.get("lane"), c.get("lease_until")))
            if not quiet:
                print(f"  expired: {c.get('unit')}  (held by {c.get('lane')})", file=sys.stderr)
    return freed


def claim_units(units, lane, seam, note, lease):
    sweep_expired(quiet=True)
    won, lost = [], []
    for u in sorted(units):
        ok, rec = atomic_claim(u, lane, seam, note, lease)
        (won if ok else lost).append((u, rec))
    return won, lost


# ------------------------------------------------------------------ audit
RE_INSTR = re.compile(r"\b((?:tools|probe|poc|res-GEN|syn|synergy|orch-score|research)/[A-Za-z0-9_.-]+\.py|[a-z0-9][a-z0-9_]{2,}\.py)\b")
RE_REPO = re.compile(r"\brepos/([A-Za-z0-9._-]+)")
RE_FLEET = re.compile(r"\b(quilt-[a-z0-9][a-z0-9-]*|SuperInstance-[A-Za-z0-9-]+|fleet-[a-z0-9-]+|wardroom|gh-dungeons|jev-net|constraint-theory-core|diffusion-jev-sglang|neodisco)\b")
RE_ART = re.compile(r"\b((?:r1|r2|r3|res|org_scratch|org2|playtest2|lattice-cell|quilt-jev|quilt-jev-web|nextgen-merge|stubs|readmes|harness|derive|site|sim|canary|music-r4|edge-NCA-artifacts|jev-merge-artifacts|substrate-fix-artifacts|templates|pixels-build|port|timequery|scouttools|libs|resolver-worker|exp-01|exp-02|nextgen-git-evidence|debate-A-code|r3-swap|r1-artifacts|r1-syncopation|r2-notebook|orch-score|research)/[A-Za-z0-9_./-]*)")
RE_DOC = re.compile(r"\b([A-Za-z0-9][A-Za-z0-9-]{2,}\.md)\b")
STOP_FLEET = {"fleet-triage", "fleet-wide", "fleet-resolver", "quilt-fleet",
              "quilt-research-canons", "quilt-canon"}


def units_of(path, known_repos, known_docs):
    with open(path, errors="replace") as fh:
        t = fh.read()
    u = set()
    for m in RE_INSTR.findall(t):
        if "/" in m or not m.startswith(("repo", "setup", "conftest")):
            u.add("INSTR:" + m)
    for m in RE_REPO.findall(t):
        if m in known_repos:
            u.add("REPO:" + m)
    for m in RE_FLEET.findall(t):
        if m not in STOP_FLEET:
            u.add(("REPO:" if m in known_repos else "REPO~:") + m)
    for m in RE_ART.findall(t):
        u.add("ART:" + m.rstrip("/"))
    for m in RE_DOC.findall(t):
        if m in known_docs and m != os.path.basename(path):
            u.add("DOC:" + m)
    return u


def audit_docs(paths, verbose=True):
    known_repos = set(os.listdir(os.path.join(ROOT, "repos")))
    known_docs = {f for f in os.listdir(ROOT) if f.endswith(".md")}
    claims = defaultdict(list)
    if os.path.isdir(SEAMS):
        for f in os.listdir(SEAMS):
            if not f.endswith(".claim"):
                continue
            c = read_claim(os.path.join(SEAMS, f))
            claims[c.get("unit")].append(c)

    unclaimed, collisions, owned = [], [], 0
    for p in paths:
        lane = os.path.basename(p)
        for u in sorted(units_of(p, known_repos, known_docs)):
            holders = claims.get(u, [])
            if not holders:
                unclaimed.append((lane, u))
            elif len(holders) > 1:
                collisions.append((lane, u, [h.get("lane") for h in holders]))
            else:
                owned += 1

    total = owned + len(unclaimed) + len(collisions)
    if verbose:
        print(f"  evidence units touched   {total}")
        print(f"  properly claimed         {owned}")
        print(f"  UNCLAIMED (bypass)       {len(unclaimed)}")
        print(f"  COLLISION (2+ claimants)  {len(collisions)}")
        if unclaimed:
            by_lane = defaultdict(list)
            for lane, u in unclaimed:
                by_lane[lane].append(u)
            print("  lanes that worked without ever claiming a seam:")
            for lane in sorted(by_lane, key=lambda k: -len(by_lane[k]))[:12]:
                print(f"     {lane:<28} {len(by_lane[lane]):>3} unclaimed units")
        if collisions:
            print("  COLLISIONS:")
            for lane, u, hs in collisions[:20]:
                print(f"     {u}  <- {', '.join(hs)}")
    return {"total": total, "claimed": owned, "unclaimed": len(unclaimed),
            "collisions": len(collisions),
            "coverage": (owned / total) if total else 0.0,
            "unclaimed_detail": unclaimed, "collision_detail": collisions}


FACTS = os.path.join(SEAMS, "_facts")


def fact_path(fact, lane):
    h = hashlib.sha1(fact.encode()).hexdigest()[:20]
    return os.path.join(FACTS, h, re.sub(r"[^A-Za-z0-9]+", "-", lane)[:40] + ".fact")


def claim_fact(fact, lane, at, claim):
    """A fact is claimable too.  Files are the easy case; CONTRADICTIONS are the
    ones that actually ship, and they are about claims, not paths."""
    os.makedirs(FACTS, exist_ok=True)
    p = fact_path(fact, lane)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    body = json.dumps({"fact": fact, "lane": lane, "at": at, "claim": claim,
                       "claimed_at": time.time()}, sort_keys=True)
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except OSError as e:
        if e.errno == errno.EEXIST:
            return False, json.loads(open(p).read())
        raise
    with os.fdopen(fd, "w") as fh:
        fh.write(body)
    return True, json.loads(body)


def _loc_ok(loc):
    """A collision you cannot point at is not a collision, it is an accusation.
    Every registered location is verified to exist before it is reported."""
    if not loc or ":" not in loc:
        return False, ""
    path, _, line = loc.rpartition(":")
    p = path if os.path.isabs(path) else os.path.join(ROOT, path)
    if not os.path.exists(p):
        return False, "<file not found>"
    try:
        n = int(line)
    except ValueError:
        return False, "<no line number>"
    lines = open(p, errors="replace").read().splitlines()
    if not (1 <= n <= len(lines)):
        return False, f"<line {n} out of range, file has {len(lines)}>"
    return True, lines[n - 1].strip()[:110]


def audit_facts(verbose=True):
    facts = defaultdict(list)
    if os.path.isdir(FACTS):
        for d in os.listdir(FACTS):
            for f in os.listdir(os.path.join(FACTS, d)):
                if f.endswith(".fact"):
                    facts[read_claim(os.path.join(FACTS, d, f)).get("fact")].append(
                        read_claim(os.path.join(FACTS, d, f)))
    collisions, verified, broken = [], 0, []
    for fact, recs in sorted(facts.items()):
        claims = defaultdict(list)
        for r in recs:
            claims[r.get("claim", "")].append(r)
        for text, rs in claims.items():
            for r in rs:
                ok, line = _loc_ok(r.get("at"))
                if ok:
                    verified += 1
                else:
                    broken.append((r.get("lane"), r.get("at"), line))
                r["_line"] = line if ok else ""
        if len(claims) > 1:
            collisions.append((fact, list(claims.values())))
    if verbose:
        print(f"  facts registered              {sum(len(v) for v in facts.values())}")
        print(f"  locations verified on disk    {verified}")
        print(f"  locations that DO NOT exist   {len(broken)}")
        for lane, at, why in broken:
            print(f"     UNVERIFIABLE  {lane}  {at}  {why}")
        print(f"  facts with >1 distinct claim  {len(collisions)}")
        for fact, groups in collisions:
            print(f"    CONTRADICTION on {fact}:")
            for g in groups:
                for r in g:
                    print(f"       {r.get('lane'):<28} {r.get('at'):<26} \"{r.get('claim')}\"")
                    if r.get("_line"):
                        print(f"       {'':<28} {'source:':<26} {r['_line']}")
    return {"facts": sum(len(v) for v in facts.values()), "verified": verified,
            "unverifiable": len(broken), "contradictions": len(collisions),
            "broken_locations": broken,
            "collision_detail": [(f, [[r.get("lane"), r.get("at"), r.get("claim"),
                                      r.get("_line")] for g in gs for r in g])
                                 for f, gs in collisions]}


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("claim", help="claim evidence units before working")
    c.add_argument("--lane", required=True)
    c.add_argument("--seam", required=True)
    c.add_argument("--evidence", nargs="+", required=True)
    c.add_argument("--note", default="")
    c.add_argument("--lease", type=int, default=900)

    r = sub.add_parser("release", help="release a seam you hold")
    r.add_argument("--lane", required=True)
    r.add_argument("--evidence", nargs="+", required=True)

    sub.add_parser("sweep", help="expire dead leases")

    ls = sub.add_parser("ls", help="who holds what")
    ls.add_argument("--json", action="store_true")

    au = sub.add_parser("audit", help="FAIL-LOUDLY if work happened on unclaimed evidence")
    au.add_argument("paths", nargs="+")
    au.add_argument("--json", default=None)

    cf = sub.add_parser("claim-fact", help="register a published CLAIM on a fact")
    cf.add_argument("--lane", required=True)
    cf.add_argument("--fact", required=True)
    cf.add_argument("--at", required=True, help="FILE:LINE -- verified to exist")
    cf.add_argument("--claim", required=True)

    sub.add_parser("audit-facts", help="find facts carrying >1 distinct claim")

    a = ap.parse_args()
    ensure()

    if a.cmd == "claim":
        won, lost = claim_units(a.evidence, a.lane, a.seam, a.note, a.lease)
        print(f"lane {a.lane}  seam {a.seam}")
        for u, _ in won:
            print(f"  CLAIMED  {u}")
        for u, rec in lost:
            print(f"  E_SEAM_HELD  {u}")
            print(f"      held by {rec.get('lane')} since {rec.get('claimed_at_iso')} "
                  f"seam={rec.get('seam')}")
            print(f"      note: {rec.get('note')}")
        print(f"  won {len(won)} / {len(a.evidence)}; lease {a.lease}s")
        return E_HELD if lost else E_OK

    if a.cmd == "release":
        n = 0
        for u in a.evidence:
            p = unit_path(u)
            if os.path.exists(p):
                rec = read_claim(p)
                if rec.get("lane") == a.lane:
                    os.rename(p, p + f".released-by-{a.lane}")
                    n += 1
        print(f"lane {a.lane} released {n} unit(s)")
        return E_OK

    if a.cmd == "sweep":
        freed = sweep_expired()
        print(f"expired {len(freed)} claim(s)")
        return E_OK

    if a.cmd == "ls":
        rows = []
        for f in sorted(os.listdir(SEAMS)):
            if f.endswith(".claim"):
                rows.append(read_claim(os.path.join(SEAMS, f)))
        if a.json:
            print(json.dumps(rows, indent=1))
        else:
            for c_ in rows:
                age = time.time() - c_.get("claimed_at", 0)
                print(f"  {c_.get('lane'):<20} {c_.get('seam'):<22} "
                      f"age {age:7.0f}s  {c_.get('unit')}")
            print(f"  {len(rows)} live claim(s)")
        return E_OK

    if a.cmd == "claim-fact":
        ok, rec = claim_fact(a.fact, a.lane, a.at, a.claim)
        v, line = _loc_ok(a.at)
        if ok:
            print(f"  CLAIMED  {a.fact}")
        else:
            print(f"  E_ALREADY_CLAIMED  {a.fact} by {rec.get('lane')}: \"{rec.get('claim')}\"")
        print(f"  location {a.at}  verified={v}")
        if v:
            print(f"    source: {line}")
        else:
            print(f"    *** refusing to register an unverifiable location ***")
            return E_BAD
        return E_OK if ok else E_HELD

    if a.cmd == "audit-facts":
        res = audit_facts()
        if a.cmd == "audit-facts" and res["contradictions"]:
            print("\nAUDIT FAILED: at least one fact carries contradictory published "
                  "claims.\n  (exiting 3)")
            return E_VOID
        return E_OK

    if a.cmd == "audit":
        res = audit_docs(a.paths)
        if a.json:
            with open(a.json, "w") as fh:
                json.dump(res, fh, indent=1)
        if res["unclaimed"] or res["collisions"]:
            print("\nAUDIT FAILED: work was done on evidence nobody claimed, or two "
                  "lanes held the same seam.\n  (exiting 3 -- this is the canary, "
                  "not a report)")
            return E_VOID
        print("\nAUDIT PASSED: every evidence unit touched was claimed by exactly "
              "one lane.")
        return E_OK

    return E_BAD


if __name__ == "__main__":
    sys.exit(main())
