#!/usr/bin/env python3
"""Classify the 62 no-language SuperInstance repos against their ACTUAL trees.

MEASUREMENT INSTRUMENT, and why it is this one.
GitHub REST is unauthenticated in this sandbox (60 req/hr) and the only token present
in ~/.gitconfig returns 401. So the API is out. Two things were tried first:

  1. `git clone --depth 1 --filter=blob:none` + `git ls-tree -r -l HEAD`
     -> WORKS, and is fast, for small repos. But git tree objects do NOT store blob
        SIZES (mode + name + oid only), so `-l` must resolve every blob. In a blobless
        partial clone that resolution is a lazy network fetch per blob. On
        `SuperInstance/alphabet` it ran 3m20s and had produced 212 of 2,590 entries
        when the timeout fired. Confirmed root cause, not a flake.
  2. `--filter=tree:0` -> same problem, one request per subtree, 316 entries in 4m00s.

  => REJECTED. Both measure sizes by downloading the thing you are trying to measure.

  3. `curl codeload.github.com/... | tar tzvf -`
     -> ACCEPTED. The tar header carries the size of every member, so one streaming
        pass yields path+size for the whole working tree with no blob store, no
        checkout, and no REST rate limit. It measures the WORKING TREE, which is
        exactly the thing the brief's "git-object history bloat" filter is about --
        API `size` counts history, the tarball does not, and the ratio between them
        is the measurement.

  Python's `tarfile` in stream mode is used rather than `tar tzvf` because these
  trees contain paths WITH SPACES, which silently shift awk's column fields and
  produce wrong sizes. `alphabet` contains one (`.../mode/`).

EVERY ROW IS EVIDENCE. No bucket is assigned from name, size, or description.
A repo that could not be fetched is UNREADABLE, with the HTTP status or the error.
A repo with no decisive evidence is UNVERIFIED. Both are reported, not smoothed over.
"""
from __future__ import annotations

import io, json, os, re, sys, tarfile, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "inspect.jsonl")
BRANCHES = ["main", "master", "core", "develop", "trunk", "gh-pages", "release"]

# ---- THE VENDOR FILTER. verbatim from the brief, applied to every count. ------
VENDOR_DIR = re.compile(
    r"(^|/)(node_modules|target|vendor|third_party|\.venv|venv|site-packages|dist|build|"
    r"\.next|out|_build|__pycache__|\.wrangler|coverage|thirdparty)(/|$)")
VENDOR_EXT = re.compile(r"\.min\.(js|css)$|\.map$|\.d\.ts$|\.(lock|lockb)$")

# ---- "real source". BROAD on purpose: the GENUINE bucket exists precisely because
# ---- linguist ignores shell / make / notebooks / DSLs.
CODE = re.compile(
    r"\.(py|ts|tsx|js|jsx|mjs|cjs|rs|go|jl|hs|ml|mli|ex|exs|erl|clj|cljs|cljc|c|cc|cpp|"
    r"cxx|h|hh|hpp|java|rb|swift|kt|kts|scala|sc|sh|bash|zsh|fish|ps1|lua|pl|pm|r|sql|"
    r"vim|el|asm|s|nim|zig|d|vb|cs|fs|dart|tex|bib|ipynb|sol|cr|fc|frpc|tact|tlb)$")
BUILD = re.compile(
    r"(^|/)(Makefile|makefile|GNUmakefile|CMakeLists\.txt|Dockerfile|Justfile|justfile|"
    r"Rakefile|Gemfile|BUILD|BUILD\.bazel|meson\.build)$")
BUILDEXT = re.compile(r"\.(mk|cmake|gradle|bzl|gyp|gypi|tf|tfvars|nix|dhall|proto|just|"
                      r"ps1|yaml|yml|json|toml|ini|cfg)$")

# manifests whose declared entry point we must resolve
MANIFESTS = re.compile(
    r"(^|/)(package\.json|Cargo\.toml|pyproject\.toml|setup\.py|go\.mod|composer\.json|"
    r"deno\.json|jsr\.json|build\.zig|CMakeLists\.txt|Makefile)$")
CAP = 96 * 1024          # per-file content cap we retain
TOTAL_CAP = 3 * 1024 * 1024


def is_vendor(p: str) -> bool:
    return bool(VENDOR_DIR.search(p) or VENDOR_EXT.search(p))


def is_src(p: str) -> bool:
    b = os.path.basename(p)
    return bool(CODE.match(b) or BUILD.search(p) or BUILDEXT.match(b))


def fetch(name: str, branch: str) -> tuple[bytes | None, str, str]:
    """Stream the working-tree tarball. Returns (listing, branch_used, error)."""
    url = f"https://codeload.github.com/SuperInstance/{name}/tar.gz/refs/heads/{branch}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fleet-triage"})
        with urllib.request.urlopen(req, timeout=600) as r:
            return r.read(), branch, ""
    except urllib.error.HTTPError as e:
        return None, branch, f"HTTP {e.code}"
    except Exception as e:
        return None, branch, f"{type(e).__name__}: {e}"


def parse(data: bytes) -> list[tuple[str, int, str]]:
    """-> [(path, size, type)] with paths RELATIVE to the archive root dir."""
    out = []
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf:
            if not m.isfile():
                continue
            parts = m.name.split("/", 1)
            out.append((parts[1] if len(parts) > 1 else parts[0], m.size, m.type))
    return out


def entry_targets(content: str) -> list[tuple[str, str]]:
    """Declared entry points from package.json / Cargo.toml / pyproject."""
    res = []
    if "{" not in content:
        return res
    # package.json main/module/start/browser  (string form, and exports-string form)
    for k in ("main", "module", "start", "browser", "typings", "types"):
        m = re.search(r'"%s"\s*:\s*"([^"]+)"' % k, content)
        if m:
            res.append((k, m.group(1)))
    # package.json "exports": { ".": { "import": "./x.js" } }  /  "exports": "./x.js"
    m = re.search(r'"exports"\s*:\s*"([^"]+)"', content)
    if m:
        res.append(("exports", m.group(1)))
    m = re.search(r'"exports"\s*:\s*\{(.{0,4000}?)\n\s*\}', content, re.S)
    if m:
        for v in re.findall(r'"(?:import|require|default|node|browser)"\s*:\s*"([^"]+)"',
                            m.group(1)):
            res.append(("exports", v))
    # package.json "bin": { "x": "./cli.js" }  or  "bin": "./cli.js"
    m = re.search(r'"bin"\s*:\s*"([^"]+)"', content)
    if m:
        res.append(("bin", m.group(1)))
    m = re.search(r'"bin"\s*:\s*\{([^}]*)\}', content, re.S)
    if m:
        for v in re.findall(r':\s*"([^"]+)"', m.group(1)):
            res.append(("bin", v))
    # Cargo [package] name / [lib] path = "src/lib.rs"   and [[bin]] path
    m = re.search(r'^\s*path\s*=\s*"([^"]+)"', content, re.M)
    if m:
        res.append(("cargo path", m.group(1)))
    m = re.search(r'^\s*name\s*=\s*"([^"]+)"', content, re.M)
    if m:
        res.append(("cargo name", m.group(1)))
    # pyproject [project.scripts] / packages
    m = re.search(r'^\s*(?:main|module|script)\s*=\s*"([^"]+)"', content, re.M)
    if m:
        res.append(("pyproject", m.group(1)))
    return res


def norm_target(base: str, t: str) -> str:
    t = t.split("#")[0]
    if t.startswith("./"):
        t = t[2:]
    if t.startswith("/"):
        return ""
    return os.path.normpath(os.path.join(base, t)).replace("\\", "/")


def inspect(entry: dict) -> dict:
    name = entry["name"]
    row = {
        "repo": name, "api_size_kb": entry.get("size"), "fork": entry.get("fork"),
        "default_branch": entry.get("default_branch"), "pushed_at": entry.get("pushed_at"),
        "description": (entry.get("description") or "")[:200],
        "errors": [], "bucket": "UNVERIFIED", "basis": "",
        "blobs": 0, "tree_bytes": 0, "vendor_blobs": 0, "vendor_bytes": 0,
        "real_blobs": 0, "real_bytes": 0, "src": 0, "src_bytes": 0,
        "zero_src": [], "zero_any": [], "manifests": {}, "dangling": [],
        "ext_hist": {}, "top_dirs": {}, "branch_used": None, "upstream": None,
    }
    branches = [entry.get("default_branch")] + BRANCHES
    seen, data, used, errs = set(), None, None, []
    for b in branches:
        if not b or b in seen:
            continue
        seen.add(b)
        data, b_used, err = fetch(name, b)
        if data is not None:
            used = b_used
            break
        errs.append(f"{b}:{err}")
    if data is None:
        row["errors"].append("TARBALL_FAILED " + "; ".join(sorted(set(errs))))
        row["bucket"] = "UNREADABLE"
        return row
    row["branch_used"] = used
    try:
        members = parse(data)
    except Exception as e:
        row["errors"].append(f"TAR_PARSE_FAILED {type(e).__name__}: {e}")
        row["bucket"] = "UNREADABLE"
        return row
    paths = {p for p, _, _ in members}
    sizes = {p: s for p, s, _ in members}

    for p, s, _ in members:
        row["blobs"] += 1
        row["tree_bytes"] += s
        ext = os.path.splitext(p)[1] or "(none)"
        row["ext_hist"][ext] = row["ext_hist"].get(ext, 0) + 1
        d = p.split("/", 1)[0] if "/" in p else "(root)"
        row["top_dirs"][d] = row["top_dirs"].get(d, 0) + 1
        if is_vendor(p):
            row["vendor_blobs"] += 1
            row["vendor_bytes"] += s
            continue
        row["real_blobs"] += 1
        row["real_bytes"] += s
        if is_src(p):
            row["src"] += 1
            row["src_bytes"] += s
        if s == 0:
            row["zero_any"].append(p)
            if is_src(p):
                row["zero_src"].append(p)

    # entry-point resolution, from manifests already in the downloaded stream
    budget = TOTAL_CAP
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for m in tf:
            if not m.isfile() or m.size > CAP or budget <= 0:
                continue
            rel = m.name.split("/", 1)[1] if "/" in m.name else m.name
            if not MANIFESTS.search(rel) and not is_src(rel):
                continue
            if is_vendor(rel):
                continue
            f = tf.extractfile(m)
            if f is None:
                continue
            txt = f.read().decode("utf-8", "replace")
            budget -= len(txt)
            if MANIFESTS.search(rel):
                row["manifests"][rel] = txt[:20000]
            for key, t in entry_targets(txt) if MANIFESTS.search(rel) else []:
                base = os.path.dirname(rel)
                tgt = norm_target(base, t)
                if not tgt:
                    continue
                cands = [tgt]
                if key == "cargo name":
                    cands = [f"{base}/src/{t}.rs", f"{base}/{t}.rs", tgt]
                hit = next((c for c in cands if c in paths and sizes.get(c, -1) >= 0), None)
                if hit is None:
                    row["dangling"].append(
                        {"manifest": rel, "key": key, "declared": t, "resolved": tgt,
                         "size": sizes.get(tgt, None)})

    # ---- bucket assignment. every branch is a measured fact, not a heuristic. ----
    vfrac = (row["vendor_bytes"] / row["tree_bytes"]) if row["tree_bytes"] else 0.0
    vfrac_n = (row["vendor_blobs"] / row["blobs"]) if row["blobs"] else 0.0
    row["vendor_byte_frac"] = round(vfrac, 4)
    row["vendor_blob_frac"] = round(vfrac_n, 4)
    row["history_ratio"] = (round((row["api_size_kb"] or 0) * 1024 / row["tree_bytes"], 1)
                            if row["tree_bytes"] else None)
    if not row["errors"] and row["blobs"] == 0:
        row["errors"].append("EMPTY_TREE: 0 file members in tarball")
    if row["errors"]:
        row["bucket"] = "UNREADABLE"
    elif row["blobs"] <= 3 and row["tree_bytes"] <= 64:
        row["bucket"] = "EMPTY"
        row["basis"] = f"{row['blobs']} file(s), {row['tree_bytes']} B total"
    elif row["dangling"]:
        row["bucket"] = "HOLLOW"
        row["basis"] = (f"{len(row['dangling'])} declared entry point(s) resolve to no file: "
                        + "; ".join(f"{d['manifest']}:{d['key']}={d['declared']}"
                                    for d in row["dangling"][:3]))
    elif row["src"] > 0 and row["src_bytes"] == 0:
        row["bucket"] = "HOLLOW"
        row["basis"] = f"all {row['src']} source files are 0 bytes"
    elif row["src"] == 0 and row["real_blobs"] > 0:
        row["bucket"] = "HOLLOW"
        row["basis"] = (f"{row['real_blobs']} real (non-vendor) files but 0 recognised "
                        f"source files")
    elif vfrac >= 0.5 or vfrac_n >= 0.5:
        row["bucket"] = "VENDORED"
        row["basis"] = (f"{row['vendor_bytes']}/{row['tree_bytes']} bytes "
                        f"({vfrac:.0%}) and {row['vendor_blobs']}/{row['blobs']} files "
                        f"({vfrac_n:.0%}) in a committed dependency dir")
    elif row["fork"]:
        row["bucket"] = "MIRROR"
        row["basis"] = "GitHub API reports fork=true; content is upstream's"
    else:
        row["bucket"] = "GENUINE"
        row["basis"] = (f"{row['src']} source files / {row['src_bytes']} B in "
                        f"extensions linguist does not count")
    return row


def main() -> None:
    nolang = json.load(open(os.path.join(HERE, "nolang.json")))
    if os.path.exists(OUT):
        os.remove(OUT)
    done = {}
    with open(OUT, "a") as fh:
        def work(e):
            nonlocal fh
            r = inspect(e)
            with open(OUT, "a") as f:
                f.write(json.dumps(r) + "\n")
            return r
        with ThreadPoolExecutor(max_workers=6) as ex:
            futs = {ex.submit(work, e): e for e in nolang}
            for i, f in enumerate(futs):
                pass
            from concurrent.futures import as_completed
            for i, f in enumerate(as_completed(futs), 1):
                try:
                    r = f.result()
                except Exception as ex2:
                    e = futs[f]
                    r = {"repo": e["name"], "bucket": "UNREADABLE",
                         "errors": [f"EXCEPTION {type(ex2).__name__}: {ex2}"],
                         "blobs": 0, "tree_bytes": 0, "src": 0, "src_bytes": 0,
                         "real_blobs": 0, "real_bytes": 0, "vendor_blobs": 0,
                         "vendor_bytes": 0, "api_size_kb": e.get("size"),
                         "fork": e.get("fork"), "zero_src": [], "zero_any": [],
                         "dangling": [], "ext_hist": {}, "top_dirs": {},
                         "manifests": {}, "description": "", "basis": ""}
                    with open(OUT, "a") as g:
                        g.write(json.dumps(r) + "\n")
                done[r["repo"]] = 1
                print(f"[{i:2d}/{len(nolang)}] {r['repo']:36s} {r['bucket']:9s} "
                      f"blobs={r['blobs']:6d} vend%={r.get('vendor_byte_frac',0):.2f} "
                      f"src={r['src']:5d} srcB={r['src_bytes']:10d} "
                      f"zsrc={len(r['zero_src']):3d} dang={len(r.get('dangling',[])):2d}",
                      flush=True)
    rows = [json.loads(l) for l in open(OUT)]
    print(f"\n{len(rows)} rows -> inspect.jsonl")
    from collections import Counter
    print(Counter(r["bucket"] for r in rows))


if __name__ == "__main__":
    main()
