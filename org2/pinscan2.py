#!/usr/bin/env python3
"""
ORG2 task 2, stage 1 -- EXTRACT cross-repo SHA pins from fleet markdown.

Iteration 1's shascan.py used `any hex 7-40 within 400 chars of SuperInstance/<repo>`.
That grammar is too loose and produced date-like false positives: its
open_target_pairs.json contains the "sha" 20260824 (a date, not a commit).

A pin is only useful to us if the SHA is BOUND to the repo name. So this scanner
accepts a pin only in one of four adjacency-bound shapes:

  P1  <repo>@<sha>                              pong-quilt@d51631e
  P2  <repo> at <sha>  /  against <sha>         "verified against pong-quilt at d51631e"
  P3  github.com/SuperInstance/<repo>/(commit|tree|blob)/<sha>
  P4  "<sha> is <repo> HEAD" / "<repo> main <sha>"   -- both orders

Rejects: bare SHAs not bound to a name; all-digit SHAs (YYYYMMDD dates);
SHAs not in [7,40] hex; the scanning repo's own name.
"""
import io, json, os, re, sys, tarfile, subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.abspath(__file__))
OWNER = "SuperInstance"
MAXU = 60_000_000            # streaming cap; AI-Writings is a 658MB gzip bomb
MAXFILE = 2_000_000
SKIP = re.compile(rb"(node_modules/|\.git/|package-lock\.json|/dist/|\.venv/|"
                  rb"\.png$|\.jpg$|\.mp4$|\.gif$|/site-packages/|\.min\.js$)")
NAME = rb"[A-Za-z0-9._-]{2,60}"
HEX = rb"[0-9a-f]{7,40}"
CITED = re.compile(rb"SuperInstance/(" + NAME + rb")")

P1 = re.compile(rb"\b(" + NAME + rb")\s*@\s*(" + HEX + rb")")
P2 = re.compile(rb"\b(" + NAME + rb")\b[^.\n]{0,60}?\b(?:at|against|@)\s+(" + HEX + rb")")
P3 = re.compile(rb"SuperInstance/(" + NAME + rb")/(?:commit|tree|blob)/(" + HEX + rb")")
P4 = re.compile(rb"(" + HEX + rb")\s+(?:is\s+)?(?:the\s+)?(?:current\s+)?"
                rb"(?:HEAD|head|main)\s+(?:of\s+)?(" + NAME + rb")")
P4b = re.compile(rb"(" + NAME + rb")\b[^.\n]{0,30}?\b(?:HEAD|main)\b[^.\n]{0,30}?\b(" + HEX + rb")")

HEXY = re.compile(rb"^[0-9a-f]{7,40}$")


def plausible_sha(s: bytes) -> bool:
    """Drop YYYYMMDD / all-digit / date-ish shas. A real sha is not 8 decimal digits
    standing alone in prose next to a date, and never all-decimal 7+ digits."""
    if not HEXY.match(s):
        return False
    if s.isdigit():
        return False
    # 2026xxxx / 20260xxx date-like leading
    if s[:4] in (b"2025", b"2026", b"2027", b"2024"):
        return False
    return True


def shapes(data: bytes, self_repo: str):
    """Yield (target, sha, grammar_id) for adjacency-bound pins."""
    out = []
    for mid, rx in (("P1", P1), ("P2", P2), ("P3", P3), ("P4", P4), ("P4b", P4b)):
        for m in rx.finditer(data):
            g = m.groups()
            if mid == "P4":
                sha, tgt = g
            else:
                tgt, sha = g
            try:
                t = tgt.decode()
            except Exception:
                continue
            if t == self_repo or t.startswith("http") or t.endswith(".git"):
                continue
            if not plausible_sha(sha):
                continue
            out.append((t, sha.decode(), mid))
    return out


def ref_for(repo):
    p = os.path.join(BASE, "refs", repo + ".txt")
    if os.path.exists(p):
        s = open(p, "rb").read()
        if b"refs/heads/main" in s:
            return "main"
        if b"refs/heads/master" in s:
            return "master"
    return "main"


def scan(repo):
    ref = ref_for(repo)
    url = (f"https://codeload.github.com/{OWNER}/{repo}/tar.gz/refs/heads/{ref}")
    try:
        p = subprocess.Popen(["curl", "-sL", "-m", "120", url],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        buf, tot = io.BytesIO(), 0
        while True:
            c = p.stdout.read(1 << 20)
            if not c:
                break
            tot += len(c)
            if tot > MAXU:
                p.kill()
                break
            buf.write(c)
        p.wait()
        if len(buf.getvalue()) < 50:
            return repo, "EMPTY"
        tf = tarfile.open(fileobj=io.BytesIO(buf.getvalue()), mode="r:gz")
        pins, seen = [], set()
        for m in tf:
            if not m.isfile() or m.size > MAXFILE:
                continue
            if SKIP.search(m.name.encode()):
                continue
            if not m.name.lower().endswith((".md", ".mjs", ".js", ".py", ".txt", ".json",
                                            ".yml", ".yaml", ".toml", ".mdown", ".rst")):
                continue
            try:
                d = tf.extractfile(m).read()
            except Exception:
                continue
            if b"SuperInstance/" not in d:
                continue
            for (t, sha, g) in shapes(d, repo):
                k = (t, sha, g, m.name)
                if k in seen:
                    continue
                seen.add(k)
                pins.append({"src": repo, "target": t, "sha": sha,
                             "grammar": g, "file": m.name})
        json.dump(pins, open(os.path.join(BASE, "pins2", repo + ".json"), "w"))
        return repo, "ok"
    except Exception as e:
        return repo, f"ERR:{type(e).__name__}"


def main():
    os.makedirs(os.path.join(BASE, "pins2"), exist_ok=True)
    os.makedirs(os.path.join(BASE, "refs"), exist_ok=True)
    names = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    print("scanning", len(names), flush=True)
    done, errs, counts = 0, [], 0
    with ThreadPoolExecutor(max_workers=12) as ex:
        fs = {ex.submit(scan, r): r for r in names
              if not os.path.exists(os.path.join(BASE, "pins2", r + ".json"))}
        for f in as_completed(fs):
            r, st = f.result()
            done += 1
            if st.startswith("ERR") or st == "EMPTY":
                errs.append((r, st))
            if done % 50 == 0:
                print(" ", done, "errs", len(errs), flush=True)
    print("DONE", done, "errs", len(errs), errs[:12], flush=True)
    for n in names:
        p = os.path.join(BASE, "pins2", n + ".json")
        if os.path.exists(p):
            counts += len(json.load(open(p)))
    print("total pins:", counts)


if __name__ == "__main__":
    main()
