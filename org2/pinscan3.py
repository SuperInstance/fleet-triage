#!/usr/bin/env python3
"""
ORG2 task 2, scanner v3 -- fixed after the negative control failed.

WHAT WENT WRONG IN v2 (this is the finding, not a footnote):
  v2 bound the TARGET from an adjacent word, so the pin
      ## The fleet corpus (SuperInstance/pong-quilt, main `d51631e`)
  was extracted as target="main" / target="corpus" / target="kind" -- the repo
  name is in the CITED PATH, 40+ chars away from the sha, with prose between.
  The negative control (does the method rediscover fleet-murmur -> pong-quilt
  d51631e?) answered NO. 399 of 768 extracted "pins" named a target that is not
  a repo at all ("main", "kind", "source", "feat", "cocapn.ai").

THE FIX: the target is only ever taken from a CITATION -- SuperInstance/<name>
or github.com/SuperInstance/<name>. The sha must appear within a window after
it, AND the window must contain a currency marker (main|HEAD|at|@|pin|merge|
verified against|as of), so a bare content hash near a repo name is not a pin.
The plausible-sha filter (no all-digit, no 20xx prefix) still applies.

This version also CACHES the extracted text per repo, so re-tuning the grammar
never re-downloads the fleet.
"""
import io, json, os, re, sys, tarfile, subprocess, hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = os.path.dirname(os.path.abspath(__file__))
OWNER = "SuperInstance"
MAXU = 60_000_000
MAXFILE = 2_000_000
CACHE = os.path.join(BASE, "mdcache")
os.makedirs(CACHE, exist_ok=True)

SKIP = re.compile(rb"(node_modules/|\.git/|package-lock\.json|/dist/|\.venv/|"
                  rb"\.png$|\.jpg$|\.mp4$|\.gif$|/site-packages/|\.min\.js$)")
EXT = (".md", ".mjs", ".js", ".py", ".txt", ".json", ".yml", ".yaml", ".toml",
       ".mdown", ".rst", ".html", ".sh")

CITE = re.compile(r"(?:github\.com/)?SuperInstance/([A-Za-z0-9._-]{2,60})")
# FIX A: a hex run adjacent to "-" is a UUID fragment, not a commit. The fleet logs
# are full of 8-4-4-4-12 UUIDs and every one of their segments matched as a "sha".
HEX = re.compile(r"(?<![0-9a-f-])([0-9a-f]{7,40})(?![0-9a-f-])")
CURRENCY = re.compile(
    r"\b(main|master|HEAD|head|at|@|pin(?:ned)?|merge[ds]?|verified against|"
    r"as of|commit|tree|blob|re-?verified|anchor(?:ed)?)\b", re.I)
WINDOW = 400


def plausible(s):
    if not re.fullmatch(r"[0-9a-f]{7,40}", s):
        return False
    if s.isdigit():
        return False
    if s[:4] in ("2024", "2025", "2026", "2027"):
        return False
    return True


def ref_for(repo):
    p = os.path.join(BASE, "refs", repo + ".txt")
    if os.path.exists(p):
        s = open(p, "rb").read()
        if b"refs/heads/main" in s:
            return "main"
        if b"refs/heads/master" in s:
            return "master"
    return "main"


def fetch_texts(repo):
    """Download once, cache the eligible text blobs, never download twice."""
    cpath = os.path.join(CACHE, repo + ".json")
    if os.path.exists(cpath):
        try:
            return json.load(open(cpath))
        except Exception:
            pass
    ref = ref_for(repo)
    url = f"https://codeload.github.com/{OWNER}/{repo}/tar.gz/refs/heads/{ref}"
    out = {}
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
            json.dump({"__status": "EMPTY"}, open(cpath, "w"))
            return {"__status": "EMPTY"}
        tf = tarfile.open(fileobj=io.BytesIO(buf.getvalue()), mode="r:gz")
        for m in tf:
            if not m.isfile() or m.size > MAXFILE:
                continue
            if SKIP.search(m.name.encode()) or not m.name.lower().endswith(EXT):
                continue
            try:
                d = tf.extractfile(m).read()
            except Exception:
                continue
            if b"SuperInstance/" not in d:
                continue
            out[m.name] = d.decode("utf-8", "replace")
    except Exception as e:
        json.dump({"__status": f"ERR:{type(e).__name__}"}, open(cpath, "w"))
        return {"__status": f"ERR:{type(e).__name__}"}
    json.dump(out, open(cpath, "w"))
    return out


def extract(repo):
    texts = fetch_texts(repo)
    if "__status" in texts:
        return repo, texts["__status"], []
    census = CENSUS
    pins, seen = [], set()
    for path, body in texts.items():
        for cm in CITE.finditer(body):
            tgt = cm.group(1)
            if tgt == repo or tgt not in census:
                continue
            # v3 bugfix: a 400-char window SPANS MARKDOWN TABLE ROWS, so a sha from
            # row 2 was attached to the citation in row 1. fleet-murmur's
            # ci-enabler-log.md produced 71 such phantom pins. A pin binds the sha
            # to the citation on the SAME LINE, or the immediately following line
            # (prose wraps), never further.
            ls = body.rfind("\n", 0, cm.start()) + 1
            le = body.find("\n", cm.start())
            le = len(body) if le < 0 else le
            same = body[ls:le]
            nxt = body[le:le + 200].lstrip("\n").split("\n")[0] if le < len(body) else ""
            win = same if not CURRENCY.search(same) else same
            if not CURRENCY.search(win):
                win = same + "\n" + nxt
            if not CURRENCY.search(win):
                continue
            for s in set(HEX.findall(win)):
                if not plausible(s):
                    continue
                # FIX B: a line can carry SEVERAL citations (minified HTML, a long
                # markdown line). A sha belongs to the NEAREST citation, not to
                # every citation on the line. Without this, one sha in a 3-project
                # <select> is reported as a pin for all three projects.
                sh_pos = win.find(s)
                if sh_pos < 0:
                    continue
                nxt = CITE.search(win, cm.start() + len(tgt) + len(OWNER) + 1)
                if nxt and (nxt.start() - cm.start()) < abs(sh_pos - cm.start()):
                    continue   # a closer citation owns this sha
                k = (tgt, s)
                if k in seen:
                    continue
                seen.add(k)
                pins.append({"src": repo, "target": tgt, "sha": s,
                             "file": path, "ctx": win[:220].replace("\n", " ")})
    return repo, "ok", pins


CENSUS = set()


def main():
    global CENSUS
    CENSUS = {r["name"] for r in json.load(open(os.path.join(BASE, "..", "fleet_meta.json")))
              if not r.get("fork")}
    print("census targets:", len(CENSUS), flush=True)
    names = [l.strip() for l in open(sys.argv[1]) if l.strip()]
    allpins, done, errs = [], 0, []
    with ThreadPoolExecutor(max_workers=12) as ex:
        fs = {ex.submit(extract, r): r for r in names}
        for f in as_completed(fs):
            repo, st, pins = f.result()
            done += 1
            if st != "ok":
                errs.append((repo, st))
            else:
                allpins.extend(pins)
            if done % 100 == 0:
                print("  ", done, "pins so far", len(allpins), flush=True)
    json.dump(allpins, open(os.path.join(BASE, os.path.basename(sys.argv[1]).replace(".txt","")+"_pins.json"), "w"))
    print("DONE", done, "errs", len(errs), errs[:10])
    print("PINS:", len(allpins), "over", len({p['src'] for p in allpins}), "source repos")
    tg = {}
    for p in allpins:
        tg[p["target"]] = tg.get(p["target"], 0) + 1
    print("top targets:", sorted(tg.items(), key=lambda x: -x[1])[:15])
    # NEGATIVE CONTROL
    ctl = [p for p in allpins if p["src"] == "fleet-murmur" and p["target"] == "pong-quilt"]
    print("\nNEGATIVE CONTROL fleet-murmur -> pong-quilt:", len(ctl), "pin(s)")
    for p in ctl:
        print("   ", p["sha"], p["file"])


if __name__ == "__main__":
    main()
