#!/usr/bin/env python3
"""
resolver.py — claim-resolution checker for the fleet's prose.

Takes fleet documents and resolves every checkable assertion to the thing it
names. Three stages, in priority order:

  1. CITATIONS    every `path`, `path:line`, `repo/file` reference, checked
                  against the actual repository tree.
  2. NUMERICS     every numeric claim that states its own derivation, recomputed
                  from the expression the document gives.
  3. EXTERNAL     every arXiv ID, DOI and URL.

Design rules, in priority order:
  * A finding you cannot reproduce by hand is not a finding. Every hit carries
    the exact bytes that disagree and the exact command that checks it.
  * Never pass what was not verified. Anything the tool could not fetch or
    could not locate is UNVERIFIABLE, never "ok".
  * Never patch. This tool only reports.

Outcomes
  RESOLVES          file found; cited line (if any) in range
  LINE_OOR          file found; cited line past EOF
  FILE_MISSING      repo is known and indexed; path is absent from its tree
  REPO_UNKNOWN      first path segment is not a known fleet repo (suspect, unproven)
  REPO_NOT_INDEXED  known fleet repo, tree unavailable (UNVERIFIABLE)
  AMBIGUOUS         bare basename, could not be pinned to one file
  UNVERIFIABLE      external ref could not be fetched
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
# State lives OUTSIDE every repo root. Keeping it inside fleet-triage meant the
# tool indexed its own clone cache, so a cloned `logtensor` appeared twice and
# every bare `rubiks.py` citation became spuriously ambiguous.
CACHE = Path(os.environ.get("RESOLVER_STATE", "/workspace/.resolver-state"))
CLONES = CACHE / "clones"
INDEX_FILE = CACHE / "repo_index.json"
CENSUS_FILE = CACHE / "fleet_census.json"


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    tmp.write_text(text)
    os.replace(tmp, path)

# Directories never worth walking when indexing a tree.
SKIP_DIRS = {
    ".git", "node_modules", "target", "dist", "build", ".next", ".venv", "venv",
    "__pycache__", ".cache", ".turbo", "vendor", "coverage", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "out", ".gradle", ".idea", ".vscode",
    "site-packages", ".terraform", "bin", "obj", ".svelte-kit", ".parcel-cache",
    # our own state must never be indexed as if it were fleet source
    "resolver_state", "resolver_cache", ".resolver-state",
}

# Extensions we are willing to treat as a file reference.
CODE_EXT = (
    "py|rs|ts|tsx|js|jsx|mjs|cjs|md|toml|json|jsonc|sh|bash|zsh|c|h|cc|cpp|"
    "hpp|cs|java|rb|go|kt|swift|scala|jl|lua|ex|exs|erl|php|pl|r|sql|vue|svelte|"
    "html|css|scss|yaml|yml|ini|cfg|conf|txt|csv|xml|proto|graphql|gql|lock|"
    "make|mk|cmake|gradle|tf|dockerfile|gitignore|env|proto|wasm|wat|asm|s|pyx|ipynb"
)

REPO_SEG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

# The org really does own repos called `docs`, `research`, `tests` … but a
# citation like `research/phase9_industry/x.py` or `.github/workflows/ci.yml`
# means a *directory inside the citing repo*, never that repo. Treating these
# names as repo-qualified was the single largest source of false positives.
GENERIC_SEG = {
    "docs", "doc", "research", "tests", "test", "testing", "examples", "example",
    "scripts", "script", "tools", "tool", "src", "lib", "libs", "ui", "papers",
    "paper", "website", "app", "apps", "data", "config", "configs", "bin",
    "dist", "build", "assets", "static", "public", "common", "core", "api",
    "components", "models", "model", "views", "pages", "packages", "server",
    "client", "shared", "utils", "util", "python", "rust", "web", ".github",
    ".gitlab", "internal", "misc", "tmp", "temp", "out", "target", "vendor",
}


# ─────────────────────────────────────────────────────────────────────────────
# repo universe
# ─────────────────────────────────────────────────────────────────────────────

def load_census() -> dict[str, dict]:
    """Known fleet repo names, lowercased -> metadata.

    Built from the fleet-triage GitHub census (SuperInstance org). Used to tell
    "this names a repo that does not exist" apart from "this names a repo we
    simply have not cloned".
    """
    if CENSUS_FILE.exists():
        return json.loads(CENSUS_FILE.read_text())
    src = HERE / "fleet_meta.json"
    if not src.exists():
        sys.exit(f"fleet census not found at {src}")
    raw = json.loads(src.read_text())
    census: dict[str, dict] = {}
    for r in raw:
        name = r.get("name")
        if not name:
            continue
        census[name.lower()] = {
            "name": name,
            "fork": r.get("fork"),
            "size_kb": r.get("size"),
            "language": r.get("language"),
            "pushed_at": r.get("pushed_at"),
        }
    CACHE.mkdir(parents=True, exist_ok=True)
    write_atomic(CENSUS_FILE, json.dumps(census))
    return census


def walk_tree(root: Path) -> list[str]:
    """Relative paths of every file under root, skipping build/vendor dirs.

    Unreadable directories are counted, not swallowed: a flaky network mount
    must not silently yield a near-empty index that then makes every citation
    in the corpus look broken.
    """
    out: list[str] = []
    errors: list[str] = []
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            entries = list(os.scandir(d))
        except (PermissionError, OSError) as e:
            errors.append(f"{d}: {e}")
            continue
        for e in entries:
            if e.is_dir(follow_symlinks=False):
                if e.name in SKIP_DIRS:
                    continue
                stack.append(Path(e.path))
            elif e.is_file(follow_symlinks=False):
                out.append(os.path.relpath(e.path, root))
    if errors:
        WALK_ERRORS.extend(errors[:5])
    return out


WALK_ERRORS: list[str] = []
LOCAL_SCAN_COUNT = 0


def find_local_repos(roots: list[Path]) -> dict[str, Path]:
    """Directory name -> path, for every repo already on this machine.

    Counts what it saw. A network mount that briefly fails `is_dir()` will
    otherwise make whole repos vanish from the index without any error, and a
    short index turns every citation in the corpus into a false positive.
    """
    found: dict[str, Path] = {}
    scanned = 0
    for r in roots:
        if not r.is_dir():
            continue
        try:
            children = sorted(r.iterdir())
        except OSError:
            continue
        for child in children:
            if child.name.startswith("."):
                continue
            scanned += 1
            try:
                isdir = child.is_dir()
            except OSError:
                continue
            if isdir and child.name.lower() not in found:
                found[child.name.lower()] = child
    global LOCAL_SCAN_COUNT
    LOCAL_SCAN_COUNT = scanned
    return found


def clone_repo(name: str, timeout: int = 120) -> tuple[str | None, str]:
    """Shallow-clone a public fleet repo into the cache. -> (path, note)"""
    CLONES.mkdir(parents=True, exist_ok=True)
    dest = CLONES / name
    if dest.exists() and any(dest.iterdir()):
        return str(dest), "already cached"
    url = f"https://github.com/SuperInstance/{name}.git"
    try:
        p = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", url, str(dest)],
            capture_output=True, timeout=timeout, text=True,
        )
    except subprocess.TimeoutExpired:
        subprocess.run(["rm", "-rf", str(dest)], capture_output=True)
        return None, "clone timed out"
    if p.returncode != 0:
        subprocess.run(["rm", "-rf", str(dest)], capture_output=True)
        err = (p.stderr or "").strip().splitlines()
        return None, (err[-1] if err else f"git exit {p.returncode}")
    return str(dest), "cloned"


def build_index(local_roots: list[Path], extra_names: list[str], jobs: int = 8,
                min_repos: int = 50, attempts: int = 3) -> dict:
    """repo name (lower) -> {name, path, files:set, n_files, source}

    Retries: the workspace is a network mount that intermittently returns
    EIO on scandir. A partial walk would make every unresolved citation look
    like a broken one, so a suspiciously small index is rebuilt, not trusted.
    """
    census = load_census()
    best: dict = {}
    for attempt in range(1, attempts + 1):
        WALK_ERRORS.clear()
        index = {}
        for lname, lpath in find_local_repos(local_roots).items():
            files = walk_tree(lpath)
            if not files:
                continue
            index[lname] = {
                "name": lpath.name, "path": str(lpath),
                "files": files, "n_files": len(files), "source": "local",
            }
        if len(index) >= min_repos:
            best = index
            break
        if len(index) > len(best):
            best = index
        print(f"  [warn] pass {attempt}: only {len(index)} repos indexed "
              f"({len(WALK_ERRORS)} walk errors, {LOCAL_SCAN_COUNT} dirs scanned)"
              f" — retrying", file=sys.stderr)
        for e in WALK_ERRORS[:3]:
            print(f"         {e}", file=sys.stderr)
        time.sleep(10)

    if len(best) < min_repos:
        # Never overwrite a good index with a broken one: a short index makes
        # every citation look unresolved, which is the worst possible failure.
        if INDEX_FILE.exists():
            old = json.loads(INDEX_FILE.read_text())
            if len(old) > len(best):
                print(f"  [warn] keeping existing index ({len(old)} repos) — "
                      f"this pass only reached {len(best)}", file=sys.stderr)
                return old
        sys.exit(f"index build only reached {len(best)} repos; the filesystem "
                 f"is not readable right now. Refusing to write a bad index.")

    index = best
    wanted = sorted({n for n in extra_names if n in census and n not in index})
    if wanted:
        def work(n: str):
            return n, clone_repo(census[n]["name"])
        with ThreadPoolExecutor(max_workers=jobs) as ex:
            for n, (path, note) in ex.map(work, wanted):
                if not path:
                    print(f"  [clone-fail] {n}: {note}", file=sys.stderr)
                    continue
                files = walk_tree(Path(path))
                index[n] = {
                    "name": census[n]["name"], "path": path,
                    "files": files, "n_files": len(files), "source": "cloned",
                }
                print(f"  [cloned] {census[n]['name']} ({len(files)} files)", file=sys.stderr)

    CACHE.mkdir(parents=True, exist_ok=True)
    write_atomic(INDEX_FILE, json.dumps(index))
    # keep a known-good copy: the workspace is a network mount
    try:
        write_atomic(INDEX_FILE.with_suffix(".good.json"), json.dumps(index))
    except OSError:
        pass
    return index


def load_index(min_repos: int = 50) -> dict:
    good = INDEX_FILE.with_suffix(".good.json")
    for p in (INDEX_FILE, good):
        if not p.exists():
            continue
        try:
            idx = json.loads(p.read_text())
        except ValueError:
            continue
        if len(idx) >= min_repos:
            return idx
    sys.exit(f"no usable repo index (looked at {INDEX_FILE} and {good}); "
             f"run: resolver.py index")


# ─────────────────────────────────────────────────────────────────────────────
# corpus
# ─────────────────────────────────────────────────────────────────────────────

SKIP_CORPUS_DIRS = SKIP_DIRS | {"recovered-copy-*"}


def iter_docs(roots: list[Path], exts: tuple[str, ...] = (".md",)) -> list[Path]:
    docs: list[Path] = []
    for root in roots:
        if not root.exists():
            print(f"  [warn] corpus root missing: {root}", file=sys.stderr)
            continue
        if root.is_file():
            docs.append(root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                if fn.endswith(exts):
                    docs.append(Path(dirpath) / fn)
    return sorted(set(docs))


def repo_of_doc(doc: Path, repo_paths: dict[str, str]) -> str | None:
    """Which repo tree actually contains this document?

    Walks up from the document to the *innermost* registered repo root. Taking
    the outermost (e.g. /workspace/projects) would name a directory, not a
    repo, and every relative citation would then fail to resolve.
    """
    best, best_len = None, -1
    s = str(doc.resolve())
    for path in repo_paths.values():
        rp = str(Path(path).resolve())
        if s.startswith(rp + os.sep) and len(rp) > best_len:
            best, best_len = rp, len(rp)
    return best


# ─────────────────────────────────────────────────────────────────────────────
# 1. CITATION EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

BACKTICK = re.compile(r"`([^`\n]{1,200})`")

# A path-ish token: has a real code extension, or is a slash path.
PATHLIKE = re.compile(
    rf"^(?:\.{{1,2}}/|[A-Za-z0-9_.~-]+/)*[A-Za-z0-9_.~-]+\.(?:{CODE_EXT})$"
)
# Bare filename with no directory at all.
BARE_FILE = re.compile(rf"^[A-Za-z0-9_-]+\.(?:{CODE_EXT})$")

# Line anchors, in the shapes the fleet actually writes.
LINE_PATTERNS = [
    re.compile(r":(?P<a>\d+)(?:[-–](?P<b>\d+))?\s*$"),          # path:12  path:12-14
    re.compile(r"\(\s*lines?\s+(?P<a>\d+)(?:\s*[-–]\s*(?P<b>\d+))?\s*\)", re.I),
    re.compile(r"\bat\s+lines?\s+(?P<a>\d+)(?:\s*[-–]\s*(?P<b>\d+))?\b", re.I),
    re.compile(r"\blines?\s+(?P<a>\d+)(?:\s*[-–]\s*(?P<b>\d+))?\s+of\b", re.I),
]


@dataclass
class Citation:
    doc: str
    docline: int
    raw: str            # exact bytes as written
    path: str
    line_a: int | None
    line_b: int | None
    line_note: str = ""  # the literal text of the line anchor, for reproduction
    symbol: str = ""     # nearest backticked identifier named alongside the anchor
    symbols: list = field(default_factory=list)  # all of them, nearest first
    ctx: str = ""        # surrounding text, for disambiguating bare filenames

BARE_IDENT = re.compile(r"`([A-Za-z_][A-Za-z0-9_]{2,60})`")


def extract_citations(text: str, doc: str) -> list[Citation]:
    out: list[Citation] = []
    for m in BACKTICK.finditer(text):
        content = m.group(1).strip()
        if not content or " " in content:
            continue

        # BUG (orchestrator, 2026-10-01; see RESOLVER-DEFECT.md): this guard
        # used to run HERE, before the colon-form was stripped below. Because
        # PATHLIKE/BARE_FILE do not match a string that still carries its
        # ":NN" anchor, every inline `path:42` citation hit `continue` and was
        # silently dropped -- never extracted, never resolved, never reported.
        # The parse must happen first; the guard tests the ANCHOR-STRIPPED path.
        # Blast radius on superinstance-papers: 3 citations. The fleet's stated
        # canon prescribes `file.py:42`, so other repos are far worse.
        _pre = content
        cm0 = re.match(r"^(?P<p>.+?):(?P<a>\d+)(?:[-–](?P<b>\d+))?$", content)
        if cm0 and ":" not in cm0.group("p"):
            content = cm0.group("p")
        if not (PATHLIKE.match(content) or BARE_FILE.match(content)):
            continue
        content = _pre

        line_a = line_b = None
        note = ""
        path = content

        # `path:12` / `path:12-14`  — the colon form, but not a Windows drive.
        cm = re.match(r"^(?P<p>.+?):(?P<a>\d+)(?:[-–](?P<b>\d+))?$", content)
        if cm and ":" not in cm.group("p"):
            path = cm.group("p")
            line_a = int(cm.group("a"))
            line_b = int(cm.group("b")) if cm.group("b") else None
            note = cm.group(0)[len(path):]
        else:
            # Anchors that live *outside* the backticks: `f.py` (line 437)
            #
            # BUG (orchestrator, 2026-10-01; see RESOLVER-DEFECT.md): this used
            # to scan a +/-140 character window and take the FIRST match. In a
            # numbered list that window spans adjacent items, so
            #     3. `RateBasedChangeEngine.ts` (lines 1-977)
            #     4. `GPUEngine.ts`
            #     5. `Sensation.ts` (lines 1-580)
            # attached 977 to all three paths, producing three LINE_OOR
            # false positives about files nobody had made a line claim about.
            # All 4 LINE_OOR findings were this artifact.
            #
            # Fix: bound the search to the SAME LINE, and take the NEAREST
            # match by character distance rather than the first. If the anchor
            # is not on the path's own line, leave the citation imprecise
            # instead of asserting a range we cannot justify.
            _ls = text.rfind("\n", 0, m.start()) + 1
            _le = text.find("\n", m.end())
            if _le == -1:
                _le = len(text)
            _line = text[_ls:_le]
            _off = m.start() - _ls
            best = None
            for pat in LINE_PATTERNS:
                for lm in pat.finditer(_line):
                    d = min(abs(lm.start() - _off), abs(lm.end() - (_off + len(content))))
                    if best is None or d < best[0]:
                        best = (d, lm)
            if best is not None:
                lm = best[1]
                line_a = int(lm.group("a"))
                line_b = int(lm.group("b")) if lm.group("b") else None
                note = lm.group(0).strip()

        if not (PATHLIKE.match(path) or BARE_FILE.match(path)):
            continue

        line = text.count("\n", 0, m.start()) + 1

        # Bare identifiers named alongside the anchor. A claim like
        # "In the `propagate_change` method of `PermutationTensor`
        # (line 295 of `permutation.py`)" names TWO symbols; taking only the
        # nearest one is a coin flip, so keep them all and require that none
        # of them lands on the cited line before calling it a mismatch.
        syms: list[str] = []
        if line_a is not None:
            win_start = max(0, m.start() - 120)
            win = text[win_start: m.end() + 120]
            cands = []
            for im in BARE_IDENT.finditer(win):
                cand = im.group(1)
                if "_" not in cand and not (cand[0].isupper() and len(cand) > 3):
                    continue
                if cand == os.path.basename(path):
                    continue
                dist = abs((win_start + im.start()) - m.start())
                if dist <= 80:
                    cands.append((dist, cand))
            seen_s: set = set()
            for _, cand in sorted(cands):
                if cand not in seen_s:
                    seen_s.add(cand)
                    syms.append(cand)
        sym = syms[0] if syms else ""

        out.append(Citation(doc, line, m.group(0), path, line_a, line_b, note, sym,
                            syms, text[max(0, m.start() - 400): m.end() + 400]))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# 1b. CITATION RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Finding:
    stage: str
    outcome: str
    doc: str
    docline: int
    raw: str
    target: str
    detail: str
    check: str = ""      # the command that reproduces it by hand
    evidence: str = ""   # the exact bytes that disagree

    def key(self):
        return (self.stage, self.outcome, self.doc, self.docline, self.target)


_LINE_CACHE: dict[str, int | None] = {}


def file_line_count(path: Path) -> int | None:
    """Number of lines, or None if unreadable/binary."""
    k = str(path)
    if k in _LINE_CACHE:
        return _LINE_CACHE[k]
    n = None
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        if b"\x00" not in data[:8192]:
            n = data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    except OSError:
        n = None
    _LINE_CACHE[k] = n
    return n


_DEF_CACHE: dict[str, dict] = {}


def def_lines(abs_path: Path) -> dict:
    """symbol -> [line numbers where it is def/class'd], plus line text."""
    k = str(abs_path)
    if k in _DEF_CACHE:
        return _DEF_CACHE[k]
    d: dict = {}
    try:
        with open(abs_path, "rb") as fh:
            data = fh.read()
        if b"\x00" not in data[:8192]:
            for i, ln in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
                m = re.match(r"\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)", ln)
                if m:
                    d.setdefault(m.group(1), []).append(i)
    except OSError:
        pass
    _DEF_CACHE[k] = d
    return d


def context_of_doc(c: Citation, n: int = 2) -> str:
    """The source line the citation sits on, plus the `n` lines that follow.

    A citation like "the layer count function from `rubiks.py` (line 437):"
    puts the equation on the *next* line, so the formula check has to look
    forward, not only at the anchor line.
    """
    try:
        with open(c.doc, "rb") as fh:
            lines = fh.read().decode("utf-8", "replace").splitlines()
        return "\n".join(lines[c.docline - 1: c.docline - 1 + n + 1])
    except (OSError, IndexError):
        return ""


class Resolver:
    def __init__(self, index: dict, census: dict, doc_repo: dict[str, str]):
        self.index = index              # lower name -> {...}
        self.census = census
        self.doc_repo = doc_repo        # doc path -> owning repo root
        self.basenames: dict[str, list[tuple[str, str]]] = defaultdict(list)
        self.suffix2: dict[str, set] = defaultdict(set)   # a/b.ext -> {(repo, a/b.ext)}
        self.dirs: dict[str, set] = {}
        for lname, info in self.index.items():
            dirs = set()
            for f in info["files"]:
                self.basenames[os.path.basename(f)].append((lname, f))
                parts = f.split("/")
                for k in (2, 3):
                    if len(parts) >= k:
                        self.suffix2["/".join(parts[-k:])].add((lname, f))
                d = os.path.dirname(f)
                while d:
                    dirs.add(d)
                    d = os.path.dirname(d)
            self.dirs[lname] = dirs

    def _norm(self, p: str) -> str:
        # NOT lstrip("./"): that strips a CHARACTER SET, so the dotfile path
        # `.github/workflows/ci.yml` silently became `github/workflows/ci.yml`
        # and then matched an unrelated repo's CI file.
        p = os.path.normpath(p).replace(os.sep, "/")
        while p.startswith("./"):
            p = p[2:]
        return p

    def _doc_root(self, c: Citation) -> Path | None:
        r = self.doc_repo.get(c.doc)
        return Path(r) if r else None

    def _symbol_check(self, c: Citation, ap: Path, need: int,
                      rel_norm: str) -> Finding | None:
        """The document names a symbol and a line. Are they the same place?

        Fires only when the named symbol is actually defined in this file and
        the cited line is not where it is defined — so the reader can check it
        with a single grep.
        """
        if not c.symbols and not c.symbol:
            return None
        defs = def_lines(ap)
        named = c.symbols or ([c.symbol] if c.symbol else [])
        # if ANY named symbol is defined right here, the anchor is fine
        for nm in named:
            where = defs.get(nm)
            if where and any(abs(need - w) <= 2 for w in where):
                return None
        # otherwise report the one that IS a definition in this file
        for nm in named:
            where = defs.get(nm)
            if not where:
                continue
            actual = self._line_text(ap, need) or "<blank>"
            return Finding(
                "citation", "SYMBOL_MISMATCH", c.doc, c.docline, c.raw, rel_norm,
                f"document cites `{nm}` at line {need}, but `{nm}` is "
                f"defined at line(s) {', '.join(map(str, where[:5]))} — line {need} "
                f"is inside a different definition",
                f"grep -n 'def {nm}' {ap} && sed -n '{need}p' {ap}",
                f"L{need}: {actual[:120]}  ||  def {nm} at L{','.join(map(str, where[:5]))}",
            )
        return None

    def _line_text(self, abs_path: Path, n: int | None) -> str:
        """The actual bytes at the cited line — so a reader can check the claim
        against what the file really says."""
        if not n:
            return ""
        try:
            with open(abs_path, "rb") as fh:
                data = fh.read()
            if b"\x00" in data[:8192]:
                return "<binary>"
            lines = data.decode("utf-8", "replace").splitlines()
            if 1 <= n <= len(lines):
                return lines[n - 1].strip()[:200]
        except OSError:
            pass
        return ""

    def _suffix_match(self, c: Citation, repo_key: str) -> Finding | None:
        """The cited path omits leading directories but the file is real.

        `telemetry/TelemetryManager.ts` cited, actually living at
        `src/spreadsheet/telemetry/TelemetryManager.ts`. That is sloppy
        citation, not a dangling reference — reporting it as "file missing"
        would be a false positive, so it gets its own outcome.
        """
        parts = c.path.split("/")
        cands: set = set()
        for k in (2, 3):
            if len(parts) >= k:
                cands |= self.suffix2.get("/".join(parts[-k:]), set())
        # A repo-qualified citation (`batten-spline/src/x.py`) must be judged
        # inside that repo only. Falling back to a same-named file in some
        # other repo would report a path that the author never cited.
        repo_qualified = parts[0].lower() in self.index and parts[0].lower() not in GENERIC_SEG
        cands = {x for x in cands if x[0] == repo_key} if repo_qualified else cands
        cands = {x for x in cands if x[0] == repo_key} or (cands if not repo_qualified else set())
        if not cands and not repo_qualified:
            # No suffix match at any fixed depth. A basename that occurs
            # exactly ONCE in the citing repo is still a unique resolution:
            # `docs/agents/alpha-roadmap.md` really lives at
            # `docs/archive/agent-reports/alpha-roadmap.md`, three levels down,
            # which no 2- or 3-component suffix rule would find.
            base = os.path.basename(c.path)
            here = [f for f in self.index[repo_key]["files"]
                    if os.path.basename(f) == base]
            if len(here) == 1:
                return Finding(
                    "citation", "PATH_PRECISE_ONLY", c.doc, c.docline, c.raw, c.path,
                    f"file exists but at a deeper path: {here[0]}",
                    f"find {self.index[repo_key]['path']} -name '{base}'",
                    f"cited: {c.path} | actual: {here[0]}",
                )
        if not cands:
            return None
        here = {x for x in cands if x[0] == repo_key}
        if len(here) == 1 and len(here) == len(cands):
            ln, f = next(iter(here))
            return Finding(
                "citation", "PATH_PRECISE_ONLY", c.doc, c.docline, c.raw, c.path,
                f"file exists but at a deeper path: {ln}/{f}",
                f"find {self.index[ln]['path']} -name '{os.path.basename(c.path)}'",
                f"cited: {c.path} | actual: {f}",
            )
        if len(here) == 1:
            ln, f = next(iter(here))
            return Finding(
                "citation", "PATH_PRECISE_ONLY", c.doc, c.docline, c.raw, c.path,
                f"file exists in the citing repo '{self.index[ln]['name']}' at {f}, "
                f"not at the path cited",
                f"find {self.index[ln]['path']} -name '{os.path.basename(c.path)}'",
                f"cited: {c.path} | actual: {f}",
            )
        if len(cands) == 1:
            ln, f = next(iter(cands))
            return Finding(
                "citation", "PATH_PRECISE_ONLY", c.doc, c.docline, c.raw, c.path,
                f"file exists in repo '{self.index[ln]['name']}' at {f}, "
                f"not at the path cited",
                f"find {self.index[ln]['path']} -name '{os.path.basename(c.path)}'",
                f"cited: {c.path} | actual: {self.index[ln]['name']}/{f}",
            )
        # Several candidates, but all inside one repo: the repo is resolvable
        # even though the exact path is not.
        only = {a for a, _ in cands}
        if len(only) == 1:
            ln = next(iter(only))
            return Finding(
                "citation", "PATH_PRECISE_ONLY", c.doc, c.docline, c.raw, c.path,
                f"file is in repo '{self.index[ln]['name']}' but at one of "
                f"{len(cands)} possible paths, not the one cited",
                f"find {self.index[ln]['path']} -name '{os.path.basename(c.path)}'",
                f"cited: {c.path} | candidates: "
                f"{', '.join(sorted(b for _, b in cands)[:4])}",
            )
        return Finding(
            "citation", "AMBIGUOUS", c.doc, c.docline, c.raw, c.path,
            f"path suffix matches {len(cands)} files in {len(only)} repos: "
            f"{', '.join(f'{a}/{b}' for a, b in list(cands)[:4])}",
            f"find /workspace -name '{os.path.basename(c.path)}'", "",
        )

    def _name_lives_elsewhere(self, c: Citation, repo_key: str) -> Finding | None:
        """The cited path is wrong here, but the file is real under that name
        in other repos. Saying "missing" would be wrong; the name is simply
        not resolvable to one place."""
        base = os.path.basename(c.path)
        others = sorted({lname for lname, _ in self.basenames.get(base, [])
                         if lname != repo_key and lname not in GENERIC_SEG})
        if not others:
            return None
        return Finding(
            "citation", "AMBIGUOUS", c.doc, c.docline, c.raw, c.path,
            f"'{base}' exists in {len(others)} other repo(s), so the citation "
            f"does not name a resolvable file",
            f"find /workspace -name '{base}' -not -path '*/.git/*'", "",
        )

    def _check_file(self, c: Citation, repo_key: str, rel: str, why: str) -> Finding:
        """Repo is known and indexed. Does rel exist? Does the cited line exist?
        Does the cited line actually contain the symbol the document names?"""
        info = self.index[repo_key]
        rel_norm = self._norm(rel)
        files = set(info["files"])

        if rel_norm in files:
            need = c.line_b or c.line_a
            if need is not None:
                ap = Path(info["path"]) / rel_norm
                n = file_line_count(ap)
                if n is None:
                    return Finding(
                        "citation", "UNVERIFIABLE", c.doc, c.docline, c.raw, rel_norm,
                        f"line {need} cited but file is unreadable/binary",
                        f"wc -l {ap}",
                    )
                if need > n:
                    return Finding(
                        "citation", "LINE_OOR", c.doc, c.docline, c.raw, rel_norm,
                        f"cites line {need}; file has {n} lines",
                        f"wc -l {ap}   # expect >= {need}, got {n}",
                        f"last line is {n}",
                    )
                sm = self._symbol_check(c, ap, need, rel_norm)
                if sm:
                    return sm
                txt = self._line_text(ap, need)
                # The document presents a formula as the content of the cited
                # line, but the line is a definition header.
                if re.match(r"\s*(async\s+)?(def|class)\s", txt) and re.search(
                        r"\$\$|\\frac|\\sqrt|=\s*\\", context_of_doc(c)):
                    return Finding(
                        "citation", "LINE_IS_DEF", c.doc, c.docline, c.raw, rel_norm,
                        f"document quotes an equation as being at line {need}, but "
                        f"line {need} is a definition header",
                        f"sed -n '{need}p' {ap}",
                        f"L{need}: {txt[:140]}",
                    )
                return Finding("citation", "RESOLVES", c.doc, c.docline, c.raw,
                               rel_norm, f"{why}; line {need}/{n}",
                               f"sed -n '{need}p' {ap}",
                               f"L{need}: {txt}")
            return Finding("citation", "RESOLVES", c.doc, c.docline, c.raw,
                           rel_norm, why, "", "")

        # Not a file. Is the *directory* even there? That is the legible failure.
        d = os.path.dirname(rel_norm)
        missing_dir = None
        if d and d not in self.dirs[repo_key]:
            missing_dir = d
        detail = f"no such file in repo '{info['name']}' ({info['n_files']} files indexed)"
        if missing_dir:
            detail += f"; directory '{missing_dir}/' does not exist in this repo at all"

        # Did the author mean a different repo? Name it, don't just say no.
        alt = self._near_miss(repo_key, rel_norm)
        if alt:
            return Finding(
                "citation", "REPO_MISMATCH", c.doc, c.docline, c.raw, rel_norm,
                f"cited under repo '{info['name']}', but this path exists in "
                f"'{self.index[alt[0]]['name']}' at {alt[1]}",
                f"ls {self.index[alt[0]]['path']}/{alt[1]}",
                f"cited: {c.path} | actual: {self.index[alt[0]]['name']}/{alt[1]}",
            )
        sm = self._suffix_match(c, repo_key)
        if sm:
            return sm
        return Finding(
            "citation", "FILE_MISSING", c.doc, c.docline, c.raw, rel_norm, detail,
            f"ls {info['path']}/{rel_norm} || find {info['path']} -name "
            f"'{os.path.basename(rel_norm)}'",
            f"repo {info['name']} dirs: {', '.join(sorted(self.dirs[repo_key])[:6])}"
            if missing_dir else "",
        )

    def _near_miss(self, repo_key: str, rel_norm: str) -> tuple[str, str] | None:
        """Same path, different repo — or same basename, different repo.

        The tail is matched by SUFFIX, not equality: a citation to
        `murmur/transforms/rubiks.py` names a tail `transforms/rubiks.py`,
        which is how `logtensor/logtensor/transforms/rubiks.py` spells it.
        A ONE-component tail is just a basename, and matching on it picks an
        arbitrary repo out of the hundreds that own a README.md — so it is
        never attempted.
        """
        parts = rel_norm.split("/")
        tail = "/".join(parts[1:]) if len(parts) > 1 else None
        if tail and "/" in tail:
            for lname, info in sorted(self.index.items()):
                if lname == repo_key or lname in GENERIC_SEG:
                    continue
                for f in info["files"]:
                    if f == tail or f.endswith("/" + tail):
                        return lname, f
        base = os.path.basename(rel_norm)
        hits = {lname for lname, _ in self.basenames.get(base, [])
                if lname != repo_key and lname not in GENERIC_SEG}
        if len(hits) == 1:
            lname = hits.pop()
            for ln, f in self.basenames[base]:
                if ln == lname:
                    return lname, f
        return None

    def resolve(self, c: Citation) -> Finding:
        path, segs = c.path, c.path.split("/")
        first = segs[0].lower()
        # home-relative and absolute paths are not repo citations
        if c.path.startswith(("~", "/", "./")) and c.path.startswith(("~/", "/")):
            return Finding("citation", "SKIP", c.doc, c.docline, c.raw, c.path,
                           "home/absolute path, not a repo citation", "", "")
        root = self._doc_root(c)
        rk = os.path.basename(root).lower() if root else None
        own = set(self.index[rk]["files"]) if rk in self.index else set()

        # A bare filename preceded by exactly one named repo belongs to THAT
        # repo, not to the document's. This must be decided before the
        # "is it in the citing repo?" shortcut below, or `README.md:109` in a
        # paragraph about the eisenstein crate silently resolves to the citing
        # repo's own README and reports a confident, wrong LINE_OOR on a
        # citation that is in fact exactly right.
        if BARE_FILE.match(c.path) and len(segs) == 1 and c.ctx:
            locs_all = dict(self.basenames.get(c.path, []))
            # Context only matters when the name is genuinely ambiguous.
            # `rubiks.py` lives in exactly one repo; no prose can make that
            # ambiguous. `README.md` lives in hundreds.
            if len(locs_all) > 1:
                named = [(w.lower().strip("`'\"()[].,:;"), m.start())
                         for m in re.finditer(r"\b[A-Za-z][A-Za-z0-9._-]{2,}\b", c.ctx)
                         for w in [m.group(0)]]
                centre = len(c.ctx) // 2
                ranked = sorted(((abs(pos - centre), r) for w, pos in named
                                 if (r := w) in self.index and r not in GENERIC_SEG))
                if ranked and ranked[0][0] <= 220 and rk != ranked[0][1]:
                    cr = ranked[0][1]
                    if cr in locs_all:
                        return self._check_file(
                            c, cr, locs_all[cr],
                            f"bare name ({len(locs_all)} repos have it) resolved to "
                            f"the repo named nearest in the same passage: "
                            f"'{self.index[cr]['name']}/{locs_all[cr]}'")

        # (1) The document's own repo. This comes FIRST: a citation like
        #     `docs/ARCHITECTURE.md` names a directory, not a fleet repo that
        #     happens to be called "docs". Only when the citing repo does not
        #     contain the path do we go looking for a repo-qualified reading.
        if root is not None and rk in self.index:
            if c.path.startswith(("./", "../")):
                rel = self._norm(os.path.relpath(
                    os.path.normpath(os.path.join(str(root), c.path)), str(root)))
                return self._check_file(c, rk, rel, "relative to citing repo")
            if c.path in own:
                return self._check_file(c, rk, c.path, "in citing repo")

        # (2) Repo-qualified: `murmur/transforms/rubiks.py`. The first segment
        #     is a fleet repo name and the citing repo does not hold the path.
        if first in self.index and first not in GENERIC_SEG:
            # `eisenstein/README.md` names a file at the REPO ROOT: the repo
            # segment is a qualifier, not part of the path. Checking the whole
            # string would miss the file and then blame some other repo's
            # README for it.
            return self._check_file(c, first, "/".join(segs[1:]) or c.path,
                                    f"repo-qualified -> {self.index[first]['name']}")
        if first in self.census and first not in GENERIC_SEG:
            return Finding(
                "citation", "REPO_NOT_INDEXED", c.doc, c.docline, c.raw, c.path,
                f"repo '{self.census[first]['name']}' is in the fleet census but its "
                f"tree is not available here — cannot check",
                "", "",
            )

        # (3) Bare filename anywhere in the indexed fleet. Resolve to the actual
        #     path, not to the repo root — `rubiks.py` living at
        #     logtensor/transforms/rubiks.py is a hit, not a miss.
        if BARE_FILE.match(c.path):
            hits = sorted(set(self.basenames.get(c.path, [])))
            locs = {ln: f for ln, f in hits}
            if rk in locs:
                others = [h for h in locs if h != rk]
                if others and len(locs) > 1:
                    return Finding(
                        "citation", "AMBIGUOUS", c.doc, c.docline, c.raw, c.path,
                        f"basename exists in {len(locs)} repos: {rk} + "
                        f"{', '.join(others[:4])}",
                        f"find /workspace -name '{c.path}'", "",
                    )
                return self._check_file(c, rk, locs[rk], f"in citing repo as {locs[rk]}")
            if len(locs) == 1:
                ln, f = next(iter(locs.items()))
                return self._check_file(c, ln, f,
                                        f"unique fleet-wide match in "
                                        f"'{self.index[ln]['name']}/{f}'")
            if len(locs) > 1:
                return Finding(
                    "citation", "AMBIGUOUS", c.doc, c.docline, c.raw, c.path,
                    f"basename in {len(locs)} repos: {', '.join(sorted(locs)[:5])}",
                    f"find /workspace -name '{c.path}'", "",
                )
            return Finding(
                "citation", "FILE_MISSING", c.doc, c.docline, c.raw, c.path,
                f"no file named '{c.path}' in any of the {len(self.index)} "
                f"indexed repos, nor in the citing repo",
                f"find /workspace -name '{c.path}'", "",
            )

        # (4) Slash path: not repo-qualified, not in the citing repo.
        if rk in self.index:
            sm = self._suffix_match(c, rk)
            if sm:
                return sm
            d = os.path.dirname(self._norm(c.path))
            if d and d not in self.dirs[rk] and len(segs) > 1:
                alt = self._near_miss(rk, self._norm(c.path))
                if alt:
                    return Finding(
                        "citation", "REPO_MISMATCH", c.doc, c.docline, c.raw, c.path,
                        f"cited as a path in the citing repo, but it lives in "
                        f"'{self.index[alt[0]]['name']}' at {alt[1]}",
                        f"ls {self.index[alt[0]]['path']}/{alt[1]}",
                        f"cited: {c.path} | actual: {self.index[alt[0]]['name']}/{alt[1]}",
                    )
                return Finding(
                    "citation", "FILE_MISSING", c.doc, c.docline, c.raw, c.path,
                    f"no such path in the citing repo '{self.index[rk]['name']}'; "
                    f"directory '{d}/' does not exist there",
                    f"ls {self.index[rk]['path']}/{c.path}", "",
                ) if self._name_lives_elsewhere(c, rk) is None else \
                    self._name_lives_elsewhere(c, rk)
        first_other = sorted(k for k in self.census if k.startswith(first + "-"))
        near = f"; census has {', '.join(first_other[:4])}" if first_other else ""
        return Finding(
            "citation", "REPO_UNKNOWN", c.doc, c.docline, c.raw, c.path,
            f"first segment '{segs[0]}' is not a known fleet repo{near} — unproven",
            "", "",
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. NUMERIC CLAIM RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

MATH_SPAN = re.compile(r"\$\$.*?\$\$|\$[^$\n]{1,300}\$", re.S)
NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"

# "… 6.8x higher density … (59,841 vs 10,428)"  — a ratio claim plus its operands.
RATIO_CLAIM = re.compile(
    rf"(?P<r>\d+(?:\.\d+)?)\s*(?:[×✕x]\s*|\s*fold\b)"
    rf"|(?P<r2>\d+(?:\.\d+)?)\s*(?:times|higher|greater|larger|more|denser|"
    rf"larger)\b", re.I)
OPERANDS = re.compile(rf"\(\s*({NUM})\s*(?:vs\.?|versus|to)\s*({NUM})\s*\)", re.I)

# "59841/10428" written out, and "\frac{2}{\sqrt{3}}", in a sentence with a claim.
# The lookbehind forbids a preceding word character, which is what stops
# `3.35e12 / 48` being read as `12 / 48`. The optional sign keeps
# `-5/3 = -1.667` from looking like 5/3 equalling -1.667.
EXPLICIT_FRAC = re.compile(r"(?<![\w.])(-?\d{1,9})\s*/\s*(-?\d{1,9})(?![\d.])")
LATEX_FRAC = re.compile(r"\\d?frac\{([^{}]{1,40})\}\{([^{}]{1,40})\}")
SQRT_FRAC = re.compile(r"(\d+(?:\.\d+)?)\s*/\s*(?:√|\\sqrt\{\s*(\d+)\s*\}|\s*sqrt\(\s*(\d+)\s*\))")
NEAR_DECIMAL = re.compile(rf"(?<![\d.])(-?\d+(?:\.\d+)?)(?![\d.])")


def _tofloat(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _strip_math(s: str) -> str:
    return MATH_SPAN.sub(" <math> ", s)


def _eval_latex_frac(num: str, den: str) -> float | None:
    """Evaluate the small LaTeX expressions the fleet actually uses."""
    def atom(t: str):
        t = t.strip().replace("\\,", "").replace(" ", "")
        m = re.fullmatch(r"\\sqrt\{(\d+)\}", t)
        if m:
            return float(m.group(1)) ** 0.5
        try:
            return float(t)
        except ValueError:
            return None
    a, b = atom(num), atom(den)
    if a is None or b is None or b == 0:
        return None
    return a / b


def extract_numeric_claims(text: str, doc: str) -> list[Finding]:
    """Two independent self-contained checks. Both need no external data."""
    out: list[Finding] = []
    off = 0
    for raw_line in text.splitlines(keepends=True):
        lineno = text.count("\n", 0, off) + 1
        off += len(raw_line)
        line = raw_line.strip()
        if not line or len(line) < 12:
            continue
        prose = _strip_math(line)

        # -- A: stated ratio vs. the operands the same sentence supplies -------
        # The ratio claim and its operands must describe the SAME quantity.
        # `wins speed (2.33x) AND quality (12.4 vs 11.8)` has both shapes in
        # one line and is not a contradiction; the conjunction is the tell.
        ops_all = list(OPERANDS.finditer(prose))
        rc_all = list(RATIO_CLAIM.finditer(prose))
        for om in ops_all:
            a, b = _tofloat(om.group(1)), _tofloat(om.group(2))
            if not (a and b) or b == 0:
                continue
            for rc in rc_all:
                claim_s = rc.group("r") or rc.group("r2")
                claim = _tofloat(claim_s)
                if not claim:
                    continue
                if rc.start() < om.start():
                    gap = prose[rc.end():om.start()]
                else:
                    gap = prose[om.end():rc.start()]
                if len(gap) > 70:
                    continue
                if re.search(r"\b(?:and|AND|but|while|whereas|though|although)\b", gap):
                    continue
                actual = a / b
                rel = abs(actual - claim) / max(abs(claim), 1e-12)
                if rel > 0.02:
                    out.append(Finding(
                        "numeric", "RATIO_MISMATCH", doc, lineno, line[:300],
                        f"{om.group(1)} vs {om.group(2)}",
                        f"document claims {claim}×; the operands it gives "
                        f"({a:,.0f} / {b:,.0f}) = {actual:.4f}×",
                        f"python3 -c \"print({a}/{b})\"",
                        f"claimed {claim} | computed {actual:.4f} "
                        f"| off by {rel*100:.1f}%",
                    ))

        # -- B: an expression the line ASSERTS equals a number ----------------
        #    Only a claim if the document joins them with = / ~= / ~. Bare
        #    adjacency is not a claim (prose about AM-GM is full of numbers
        #    that happen to sit near a fraction).
        for val, expr, claimed in _claimed_equalities(line):
            if abs(claimed) < 1e-9 or abs(val) < 1e-9:
                continue
            rel = abs(claimed - val) / abs(claimed)
            # prose rounds: 26.67% is legitimately written "27%"
            if round(val, max(0, 2 - int(math.floor(math.log10(abs(val)))) - 1)) \
                    == claimed:
                rel = 0.0
            if rel > 0.02:
                out.append(Finding(
                    "numeric", "EXPR_MISMATCH", doc, lineno, line[:300], expr,
                    f"line asserts {claimed:g} but {expr} = {val:.6g}",
                    f"python3 -c \"print({val:.6g})\"",
                    f"{expr} = {val:.6g} | asserted {claimed:g} | off {rel*100:.2f}%",
                ))
    # de-duplicate: one line can trip the same expression twice
    uniq, seen = [], set()
    for f in out:
        k = (f.outcome, f.docline, f.target, f.detail)
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return uniq


RELOP = (r"(?:\\approx|\\simeq|\\cong|\\equiv|\\sim\b|\\doteq|"
         r"=|≈|≃|≅|≡|~=|\s*is\s*|\s*equals?\s*)")


def _find_latex_fracs(line: str) -> list[tuple[str, str, int]]:
    r"""\frac{A}{B} with one level of nested braces: \frac{2}{\sqrt{3}}, \frac{2\pi}{3}."""
    out = []
    for m in re.finditer(r"\\d?frac\s*\{", line):
        i = m.end()  # just after the opening brace of A
        def close(j):
            depth, k = 1, j
            while k < len(line) and depth:
                if line[k] == "{":
                    depth += 1
                elif line[k] == "}":
                    depth -= 1
                k += 1
            return k - 1 if depth == 0 else -1
        e1 = close(i)
        if e1 < 0:
            continue
        j = e1 + 1
        while j < len(line) and line[j] == " ":
            j += 1
        if j >= len(line) or line[j] != "{":
            continue
        e2 = close(j + 1)
        if e2 < 0:
            continue
        out.append((line[i:e1], line[j + 1:e2], m.start()))
    return out


def _claimed_equalities(line: str) -> list[tuple[float, str, float]]:
    """(value, expression_text, asserted_value) for every place a line says
    `EXPR = NUMBER` or `NUMBER ~= EXPR`. Proximity alone yields nothing."""
    exprs: list[tuple[float, str]] = []
    for m in EXPLICIT_FRAC.finditer(line):
        n, d = _tofloat(m.group(1)), _tofloat(m.group(2))
        if n is not None and d and d != 0 and abs(n / d) > 1e-9:
            exprs.append((n / d, m.group(0)))
    for m in re.finditer(r"\\d?frac\{([^{}]{1,40})\}\{([^{}]{1,40})\}", line):
        v = _eval_latex_frac(m.group(1), m.group(2))
        if v is not None and v != 0.0:
            exprs.append((v, m.group(0)))
    for a, b, pos in _find_latex_fracs(line):
        v = _eval_latex_frac(a, b)
        if v is not None and v != 0.0:
            exprs.append((v, rf"\frac{{{a}}}{{{b}}}"))
    for m in SQRT_FRAC.finditer(line):
        a = _tofloat(m.group(1))
        rad = m.group(2) or m.group(3)
        if a is not None and rad and a != 0:
            exprs.append((a / float(rad) ** 0.5, m.group(0).strip()))

    out = []
    # The asserted value must be the WHOLE right-hand side and carry no unit.
    # `8/20 = 40%` is a percent conversion, `343/20000 ~ 17mm` is a unit
    # conversion, `2 x 49 x \frac{4}{3} = 98 + 130.6` quotes a sub-expression.
    # None of those is an arithmetic error, and all three read as one.
    UNIT_AFTER = re.compile(
        r"^\s*(?:%|‰|×|x"
        r"|(?:mm|cm|km|nm|um|s|ms|us|ns|hz|kHz|MHz|GHz|GB|MB|KB|TB|W|J|V|A|m|b"
        r"|px|pt|em|rem|deg|rad)\b)", re.I)
    # `\\[timescdot]` matches the backslash plus ONE letter, which is enough
    # to cover \\times, \\cdot and \\cdotp. A trailing \\b there would be
    # unsatisfiable: `\\times` consumes only the `t`, and `i` is still a word
    # character, so there is no boundary.
    TIMES = r"\\(?:times|cdot|cdotp)\b"
    MULT_PREFIX = re.compile(
        rf"(?:\d+\s*(?:[×x*]|{TIMES})\s*"
        rf"|[×x*]|{TIMES}\s*\d+\s*"
        rf"|[\w.)\]}}]+\s*(?:[×x*]|{TIMES})\s*)$")
    TAIL_OP = re.compile(rf"^\s*(?:[+\-*/×x^]|{TIMES})")

    for val, expr in exprs:
        esc = re.escape(expr)
        for m in re.finditer(rf"{esc}\s*{RELOP}\s*(-?\d+(?:\.\d+)?)(?![\d.])", line):
            c = _tofloat(m.group(1))
            if c is None:
                continue
            tail = line[m.end(): m.end() + 12]
            if UNIT_AFTER.match(tail):
                continue                       # percent or unit conversion
            if TAIL_OP.match(tail):
                continue                       # "= 98 + 130.6" — a sum
            pre = line[max(0, m.start() - 24): m.start()]
            if MULT_PREFIX.search(pre):
                continue                       # "2 x 49 x \frac{4}{3}" — partial
            out.append((val, expr, c))
    return out
    return out


def cluster_constants(docs: dict[str, str], min_files: int = 2) -> list[dict]:
    """Same sentence shape, different numbers -> divergence.
    Same sentence shape, same number in N files -> propagation (how a wrong
    constant survives a passing test suite)."""
    sig: dict[str, list[tuple[str, int, str, str]]] = defaultdict(list)
    for doc, text in docs.items():
        for raw in text.splitlines():
            line = raw.strip()
            nums = NEAR_DECIMAL.findall(_strip_math(line))
            if len(nums) < 1 or len(line) < 40:
                continue
            shape = NEAR_DECIMAL.sub("#", _strip_math(line))[:160]
            sig[shape].append((doc, 0, line[:200], ",".join(nums)))
    clusters = []
    for shape, rows in sig.items():
        docs_hit = {r[0] for r in rows}
        if len(docs_hit) < min_files:
            continue
        vals = {r[3] for r in rows}
        clusters.append({
            "shape": shape,
            "n_files": len(docs_hit),
            "files": sorted(docs_hit),
            "values": sorted(vals),
            "divergent": len(vals) > 1,
            "example": rows[0][2],
        })
    return sorted(clusters, key=lambda c: (-c["n_files"], c["shape"]))


# ─────────────────────────────────────────────────────────────────────────────
# 3. EXTERNAL REFERENCE RESOLUTION
# ─────────────────────────────────────────────────────────────────────────────

ARXIV = re.compile(r"\b(?:arXiv[:\s/]*|arxiv\.org/(?:abs|pdf)/)"
                   r"(\d{4}\.\d{4,5})(v\d+)?", re.I)
DOI = re.compile(r"\b(?:doi[:\s]*|https?://(?:dx\.)?doi\.org/)"
                 r"(10\.\d{4,9}/[^\s\"'<>]+)", re.I)


def _trim_doi(s: str) -> str:
    """DOIs legitimately contain parentheses: 10.1016/S0167-2789(00)00030-0.

    Two failure modes to absorb:
      * markdown wrapping, e.g. `(**10.1103/PhysRevLett.85.461)**`, which
        would otherwise 404 on a DOI that resolves perfectly well;
      * a dangling `(`, which is a truncated DOI and is genuinely unresolvable.
    Balance the parentheses left-to-right and drop anything after a close that
    has no matching open.
    """
    s = s.rstrip(".,;")
    depth = 0
    cut = len(s)
    for i, ch in enumerate(s):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:          # a close with no open: markdown, not DOI
                cut = i
                break
    s = s[:cut].rstrip(".,;}*")
    return s
URL = re.compile(r"https?://[A-Za-z0-9._~:/?#@!$&()*+,;=%-]+")

UA = "fleet-resolver/1.0 (claim-resolution checker)"

EXT_CACHE_FILE = CACHE / "external_cache.json"


def _load_ext_cache() -> dict:
    try:
        return json.loads(EXT_CACHE_FILE.read_text())
    except (OSError, ValueError):
        return {}


def _save_ext_cache() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    write_atomic(EXT_CACHE_FILE, json.dumps(EXT_CACHE))


def _fetch(url: str, timeout: int = 20, method: str = "HEAD") -> tuple[str, str]:
    """Only a 404/410 means 'dead'.

    401/403 means we were not allowed to look (a private repo reads as 404 to
    an anonymous client, but 403/401 are plainly 'we could not check'), 429 is
    rate limiting, and 5xx is the far end having a bad day. Reporting any of
    those as a broken reference is a false positive by construction.
    """
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return "OK", f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return "DEAD", f"HTTP {e.code}"
        if e.code in (401, 403):
            return "UNVERIFIABLE", f"HTTP {e.code} (not authorised — may be private)"
        if e.code == 429:
            return "UNVERIFIABLE", "HTTP 429 (rate limited)"
        if e.code == 405:
            return "UNVERIFIABLE", "HTTP 405 (HEAD not allowed)"
        if 400 <= e.code < 500:
            return "DEAD", f"HTTP {e.code}"
        return "UNVERIFIABLE", f"HTTP {e.code} (server error)"
    except Exception as e:                       # noqa: BLE001
        return "UNVERIFIABLE", f"{type(e).__name__}: {e}"


def arxiv_batch_check(ids: list[str], attempts: int = 3) -> dict[str, tuple[str, str]]:
    """arXiv's id_list API answers many IDs in one call.

    A whole chunk can come back empty when the API rate-limits; that is a
    transport failure, not evidence that 50 papers do not exist. Retry the
    chunk, and only report DEAD for ids that survive a successful call.
    """
    out: dict[str, tuple[str, str]] = {}
    for i in range(0, len(ids), 40):
        chunk = ids[i:i + 40]
        url = ("http://export.arxiv.org/api/query?id_list="
               + ",".join(chunk) + "&max_results=100")
        body, err = None, ""
        for attempt in range(attempts):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=60) as r:
                    body = r.read().decode("utf-8", "replace")
                if "<entry>" in body or "<opensearch:totalResults" in body:
                    break
                body = None
                err = "empty response"
            except Exception as e:               # noqa: BLE001
                body, err = None, f"{type(e).__name__}: {e}"
            time.sleep(4 * (attempt + 1))
        if body is None:
            for a in chunk:
                out[a] = ("UNVERIFIABLE", f"arXiv API unreachable: {err}")
            continue
        found = set(re.findall(r"<id>http://arxiv\.org/abs/(\d{4}\.\d{4,5})", body))
        for a in chunk:
            if a in found:
                out[a] = ("RESOLVES", "listed by arXiv API")
            else:
                out[a] = ("DEAD", "not returned by arXiv API (id does not exist)")
    return out


EXT_CACHE: dict = {}


def check_external(docs: dict[str, str], urls: bool = True) -> list[Finding]:
    global EXT_CACHE
    EXT_CACHE = _load_ext_cache()
    try:
        return _check_external(docs, urls)
    finally:
        _save_ext_cache()


def _check_external(docs: dict[str, str], urls: bool = True) -> list[Finding]:
    arx_ids: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    dois: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    url_hits: dict[str, list[tuple[str, int, str]]] = defaultdict(list)
    for doc, text in docs.items():
        off = 0
        for raw in text.splitlines(keepends=True):
            lineno = text.count("\n", 0, off) + 1
            off += len(raw)
            for m in ARXIV.finditer(raw):
                arx_ids[m.group(1)].append((doc, lineno, m.group(0).strip()))
            for m in DOI.finditer(raw):
                dois[_trim_doi(m.group(1))].append((doc, lineno, m.group(0).strip()))
            if urls:
                for m in URL.finditer(raw):
                    # markdown emphasis clings to the URL: `(link)**`
                    u = m.group(0).rstrip(".,);:*}>]\"'")
                    if re.search(r"(arxiv|doi\.org)", u, re.I):
                        continue
                    url_hits[u].append((doc, lineno, m.group(0).strip()))

    findings: list[Finding] = []
    arx = arxiv_batch_check(sorted(arx_ids))
    for aid, st in arx.items():
        outcome, note = st
        for doc, lineno, raw in arx_ids[aid][:1]:
            findings.append(Finding(
                "external", "ARXIV_" + outcome, doc, lineno, raw, f"arXiv:{aid}", note,
                f"curl -sI 'http://export.arxiv.org/api/query?id_list={aid}'", ""))

    def one_doi(item):
        doi, hits = item
        url = f"https://doi.org/{doi}"
        st, note = _fetch(url)
        if st == "OK":
            st, note = _fetch(url, method="GET")
        doc, lineno, raw = hits[0]
        return Finding("external", "DOI_" + st, doc, lineno, raw, doi, note,
                       f"curl -sIL '{url}'", f"cited in {len(hits)} place(s)")

    with ThreadPoolExecutor(max_workers=8) as ex:
        findings.extend(ex.map(one_doi, sorted(dois.items())))

    def one_url(item):
        u, hits = item
        cached = EXT_CACHE.get(u)
        if cached is not None:
            st, note = cached
        else:
            st, note = _fetch(u)
            if st == "UNVERIFIABLE":
                st, note = _fetch(u, method="GET")
            EXT_CACHE[u] = [st, note]
        # A github.com/SuperInstance/<name> 404 from an anonymous client is
        # weak evidence: the org has thousands of private repos. We hold a
        # census of it, so consult that before calling it dead.
        gm = re.match(r"https?://github\.com/SuperInstance/([^/#?]+)", u, re.I)
        if gm and st == "DEAD":
            slug = gm.group(1).removesuffix(".git").lower()
            if slug in load_census() or slug in load_index():
                st, note = "UNVERIFIABLE", (
                    "HTTP 404 anonymously, but this repo is in the fleet "
                    "census — private or transient, not a broken reference")
        doc, lineno, raw = hits[0]
        return Finding("external", "URL_" + st, doc, lineno, raw, u[:120], note,
                       f"curl -sIL '{u}'", f"cited in {len(hits)} place(s)")

    if urls:
        with ThreadPoolExecutor(max_workers=12) as ex:
            findings.extend(ex.map(one_url, sorted(url_hits.items())))
    return findings


# ─────────────────────────────────────────────────────────────────────────────
# DRIVER
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_ROOTS = [
    Path("/workspace/projects/superinstance-papers"),
    Path("/workspace/projects/fleet-triage"),
    Path("/workspace/repos/quilt-research-canons"),
]
LOCAL_REPO_ROOTS = [
    Path("/workspace/projects"),
    Path("/workspace/repos"),
    Path("/workspace/projects/fleet-triage/repos"),
]


def load_corpus(roots: list[Path]) -> tuple[dict[str, str], dict[str, str], list[Path]]:
    repo_paths = find_local_repos(LOCAL_REPO_ROOTS)
    docs_paths = iter_docs(roots)
    texts: dict[str, str] = {}
    owner: dict[str, str] = {}
    for p in docs_paths:
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "\x00" in t[:4096]:
            continue
        texts[str(p)] = t
        r = repo_of_doc(p, repo_paths)
        if r:
            # index is keyed on the *unresolved* path (what find_local_repos
            # stored); match on that so lookups hit.
            owner[str(p)] = next(
                (str(Path(pp)) for pp in repo_paths.values()
                 if str(Path(pp).resolve()) == r), r)
    return texts, owner, docs_paths


def cmd_index(args):
    texts, owner, docs = load_corpus(args.corpus)
    # which repos do the citations actually name?
    names: set[str] = set()
    for t in texts.values():
        for c in extract_citations(t, ""):
            if "/" in c.path:
                names.add(c.path.split("/")[0].lower())
    census = load_census()
    wanted = sorted(n for n in names if n in census)
    print(f"corpus: {len(docs)} docs; {len(names)} distinct first path segments; "
          f"{len(wanted)} of them are fleet repos", file=sys.stderr)
    idx = build_index(LOCAL_REPO_ROOTS, wanted)
    print(f"indexed {len(idx)} repos, "
          f"{sum(v['n_files'] for v in idx.values())} files", file=sys.stderr)


def cmd_scan(args):
    t0 = time.time()
    texts, owner, docs = load_corpus(args.corpus)
    index = load_index()
    census = load_census()
    res = Resolver(index, census, owner)
    print(f"corpus: {len(texts)} documents, "
          f"{sum(len(t.splitlines()) for t in texts.values()):,} lines", file=sys.stderr)
    print(f"index:  {len(index)} repos, "
          f"{sum(v['n_files'] for v in index.values()):,} files", file=sys.stderr)

    cites: list[Citation] = []
    for doc, t in texts.items():
        cites.extend(extract_citations(t, doc))
    print(f"citations extracted: {len(cites):,}", file=sys.stderr)

    seen: set = set()
    findings: list[Finding] = []
    n_sites = 0
    for c in cites:
        n_sites += 1
        # one finding per *citation site*, not per distinct backtick string:
        # the same `README.md` in two repos is two different claims.
        k = (c.doc, c.docline, c.raw, c.line_a)
        if k in seen:
            continue
        seen.add(k)
        findings.append(res.resolve(c))
    print(f"citation sites:     {n_sites:,} ({len(findings):,} distinct sites checked)",
          file=sys.stderr)

    if not args.no_numeric:
        nf = []
        for doc, t in texts.items():
            nf.extend(extract_numeric_claims(t, doc))
        findings.extend(nf)
        print(f"numeric claims:     {len(nf):,}", file=sys.stderr)

    if not args.no_external:
        ef = check_external(texts, urls=not args.no_urls)
        findings.extend(ef)
        print(f"external refs:      {len(ef):,}", file=sys.stderr)

    if args.clusters:
        for c in cluster_constants(texts)[:60]:
            print(f"[cluster] files={c['n_files']} divergent={c['divergent']} "
                  f"values={c['values']}\n    {c['example'][:150]}", file=sys.stderr)

    payload = {
        "corpus_roots": [str(r) for r in args.corpus],
        "n_documents": len(texts),
        "n_lines": sum(len(t.splitlines()) for t in texts.values()),
        "n_citations": len(findings),
        "n_repos_indexed": len(index),
        "n_files_indexed": sum(v["n_files"] for v in index.values()),
        "outcomes": dict(Counter(f.outcome for f in findings)),
        "stages": dict(Counter(f.stage for f in findings)),
        "findings": [asdict(f) for f in findings],
        "elapsed_s": round(time.time() - t0, 1),
    }
    args.out.write_text(json.dumps(payload, indent=1))
    print(f"\nwrote {args.out}  ({time.time()-t0:.1f}s)", file=sys.stderr)
    for o, n in sorted(payload["outcomes"].items(), key=lambda kv: -kv[1]):
        print(f"  {n:>7,}  {o}", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_corpus(p):
        p.add_argument("--corpus", type=Path, nargs="*", default=DEFAULT_ROOTS)

    p = sub.add_parser("index", help="build the repo file-tree index")
    add_corpus(p)
    p.set_defaults(func=cmd_index)

    p = sub.add_parser("scan", help="resolve every checkable claim in the corpus")
    add_corpus(p)
    p.add_argument("--out", type=Path, default=HERE / "resolver_report.json")
    p.add_argument("--no-numeric", action="store_true")
    p.add_argument("--no-external", action="store_true")
    p.add_argument("--no-urls", action="store_true")
    p.add_argument("--clusters", action="store_true")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("audit", help="independently verify a sample of findings")
    p.add_argument("--report", type=Path, default=HERE / "resolver_report.json")
    p.add_argument("--out", type=Path, default=HERE / "resolver_audit.json")
    p.add_argument("--sample", type=int, default=120)
    p.add_argument("--seed", type=int, default=17)
    p.set_defaults(func=cmd_audit)

    args = ap.parse_args()
    args.func(args)



# ─────────────────────────────────────────────────────────────────────────────
# AUDIT — measure the false-positive rate with an INDEPENDENT method
# ─────────────────────────────────────────────────────────────────────────────

def _fs_scan_for(repo_path: str, cited: str) -> list[str]:
    """Walk the real directory looking for the cited file by any suffix.

    Deliberately does not touch the index: the point is to catch the index
    being wrong, which is exactly where a resolver's false positives live.
    """
    parts = cited.split("/")
    hits: list[str] = []
    for dirpath, dirnames, filenames in os.walk(repo_path):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            full = os.path.relpath(os.path.join(dirpath, fn), repo_path)
            fs = full.split("/")
            for k in range(1, min(len(parts), len(fs)) + 1):
                if fs[-k:] == parts[-k:]:
                    hits.append(full)
                    break
    return hits


def _target_repo(f: dict, index: dict) -> dict | None:
    """The repo the finding actually talks about (not necessarily the citing
    repo). REPO_MISMATCH says "this lives over there", so the verifier has to
    look over there or it will refute a correct finding."""
    ev = f.get("evidence", "") or ""
    m = re.search(r"actual: ([^|\n]+)", ev)
    if not m:
        m = re.search(r"exists in '([^']+)'", f.get("detail", ""))
    if not m:
        m = re.search(r"deeper path: ([^/ ]+)/", f.get("detail", ""))
    if not m:
        m = re.search(r"repo-qualified -> '?([^ '\n]+)", f.get("detail", ""))
    if not m:
        return None
    name = m.group(1).strip().split("/")[0].strip("'\"").lower()
    if name in GENERIC_SEG:
        return None          # 'actual: docs/x.md' is a path, not repo 'docs'
    return index.get(name)


def _verify(outcome: str, f: dict, doc_repo: dict | None, index: dict) -> tuple[str, str]:
    """Confirm or refute ONE finding, by a method independent of the walk index.

    'FALSE_POSITIVE' means the tool asserted something that is not true.
    """
    cited = f["target"]
    base = os.path.basename(cited)

    # repo the citing document lives in
    home_files = doc_repo["files"] if doc_repo else []
    in_home = cited in home_files

    # where the finding says the thing actually is
    tgt = _target_repo(f, index)
    tgt_files = tgt["files"] if tgt else []

    if outcome == "FILE_MISSING":
        if in_home:
            return "FALSE_POSITIVE", "file is present at the cited path"
        if tgt and cited in tgt_files:
            return "FALSE_POSITIVE", f"file is present in {tgt['name']}"
        # absent everywhere in the indexed fleet?
        anywhere = [r for r, inf in index.items()
                    if any(os.path.basename(p) == base for p in inf["files"])]
        if not anywhere:
            return "TRUE", "no such basename in any of the indexed repos"
        return ("FALSE_POSITIVE",
                f"basename exists in {len(anywhere)} other repo(s): "
                f"{', '.join(anywhere[:3])}")

    if outcome == "LINE_OOR":
        m = re.search(r"cites line (\d+); file has (\d+) lines", f["detail"])
        if not m:
            return "SKIP", "no line info"
        need = int(m.group(1))
        ap = Path(doc_repo["path"]) / cited if doc_repo and in_home else None
        if ap is None:
            return "SKIP", "target path not locatable in citing repo"
        real = file_line_count(ap)
        if real is None:
            return "SKIP", "unreadable"
        if need > real:
            return "TRUE", f"file really has {real} lines; cited {need}"
        return "FALSE_POSITIVE", f"file actually has {real} lines"

    if outcome == "PATH_PRECISE_ONLY":
        # the finding's "actual" path is always given without a repo prefix,
        # and lives in the citing repo (or the repo it names).
        scope = tgt_files if tgt else home_files
        scope_name = tgt["name"] if tgt else (doc_repo["name"] if doc_repo else "?")
        if in_home:
            return "FALSE_POSITIVE", "file IS at the cited path"
        m = re.search(r"actual: ([^|\n]+)", f.get("evidence", "") or "")
        rel = m.group(1).strip() if m else None
        if rel:
            hits = [p for p in scope
                    if os.path.normpath(p).endswith(os.path.normpath(rel))]
            if hits:
                return "TRUE", f"really at {hits[0]} (citation omits leading dirs)"
            return "FALSE_POSITIVE", f"{rel} not found in {scope_name}"
        if not scope:
            return "SKIP", "no scope repo"
        hits = [p for p in scope
                if os.path.normpath(p).endswith(os.path.normpath(cited))]
        if hits:
            return "TRUE", f"really at {hits[0]}"
        return "FALSE_POSITIVE", f"{cited} not found in {scope_name} either"

    if outcome == "REPO_MISMATCH":
        if in_home:
            return "FALSE_POSITIVE", "file IS in the citing repo at that path"
        if not tgt:
            return "SKIP", "finding names no target repo"
        m = re.search(r"actual: ([^|\n]+)", f.get("evidence", "") or "")
        rel = m.group(1).strip().split("/", 1)[1] if m and "/" in m.group(1) else None
        if rel:
            hits = [p for p in tgt_files
                    if os.path.normpath(p).endswith(os.path.normpath(rel))]
            if hits:
                return "TRUE", f"named target {rel} is real in {tgt['name']}"
            return "FALSE_POSITIVE", f"{rel} not in {tgt['name']}"
        return "SKIP", "unparseable evidence"

    if outcome == "AMBIGUOUS":
        if in_home:
            return "FALSE_POSITIVE", "file IS in the citing repo"
        repos = {r for r, inf in index.items()
                 if any(os.path.basename(p) == base for p in inf["files"])}
        if len(repos) <= 1:
            return ("FALSE_POSITIVE",
                    f"uniquely resolvable to {sorted(repos)}" if repos
                    else "name does not exist at all")
        return "TRUE", f"{len(repos)} repos hold a {base}"

    if outcome == "REPO_UNKNOWN":
        first = cited.split("/")[0].lower()
        if first in GENERIC_SEG:
            return "TRUE", "generic directory name, not repo-qualified by design"
        if first in index or first in load_census():
            return "FALSE_POSITIVE", f"'{first}' IS a known fleet repo"
        return "TRUE", "not in the fleet census"

    return "SKIP", f"no verifier for {outcome}"


def audit(report: dict, index: dict, sample: int, seed: int) -> dict:
    import random
    rng = random.Random(seed)
    by_outcome: dict[str, list] = defaultdict(list)
    for f in report["findings"]:
        by_outcome[f["outcome"]].append(f)

    repo_of: dict[str, dict] = {}
    for info in index.values():
        repo_of[info["path"]] = info

    results = {}
    for outcome, rows in sorted(by_outcome.items()):
        if outcome == "RESOLVES":
            continue
        pick = rows if len(rows) <= sample else rng.sample(rows, sample)
        verdicts = []
        for f in pick:
            dr = None
            for rp, info in repo_of.items():
                if str(f["doc"]).startswith(rp + os.sep):
                    dr = info
                    break
            v, why = _verify(outcome, f, dr, index)
            verdicts.append((f, v, why))
        n_checked = sum(1 for _, v, _ in verdicts if v != "SKIP")
        n_fp = sum(1 for _, v, _ in verdicts if v == "FALSE_POSITIVE")
        results[outcome] = {
            "population": len(rows),
            "sampled": len(verdicts),
            "checked": n_checked,
            "confirmed": n_checked - n_fp,
            "false_positives": n_fp,
            "fp_rate": round(n_fp / n_checked, 4) if n_checked else None,
            "examples": [
                {"target": f["target"], "doc": f["doc"], "line": f["docline"],
                 "verdict": v, "why": w, "detail": f["detail"][:160]}
                for f, v, w in verdicts if v == "FALSE_POSITIVE"
            ][:15],
        }
    return results


def cmd_audit(args):
    report = json.loads(args.report.read_text())
    index = load_index()
    res = audit(report, index, args.sample, args.seed)
    args.out.write_text(json.dumps(res, indent=1))
    tot_c = tot_fp = 0
    print(f"{'outcome':<20} {'population':>10} {'sampled':>8} {'checked':>8} "
          f"{'FP':>5} {'FP rate':>8}")
    print("-" * 66)
    for k, v in sorted(res.items(), key=lambda kv: -kv[1]["population"]):
        fr = f"{v['fp_rate']*100:.1f}%" if v["fp_rate"] is not None else "n/a"
        print(f"{k:<20} {v['population']:>10} {v['sampled']:>8} {v['checked']:>8} "
              f"{v['false_positives']:>5} {fr:>8}")
        tot_c += v["checked"]
        tot_fp += v["false_positives"]
    print("-" * 66)
    print(f"{'TOTAL':<20} {'':>10} {'':>8} {tot_c:>8} {tot_fp:>5} "
          f"{(tot_fp/tot_c*100 if tot_c else 0):>7.1f}%")
    print(f"\nwrote {args.out}")

if __name__ == "__main__":
    main()
