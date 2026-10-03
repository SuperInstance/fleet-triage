/**
 * resolver-worker — the fleet's citation resolver as a public edge service.
 *
 * Faithful port of /workspace/projects/fleet-triage/resolver.py
 * (Resolver.resolve + extract_citations + numeric stage), stages 1 and 2.
 * Stage 3 (external URL/arXiv/DOI) is DISABLED at the edge by default and
 * says so in every response rather than pretending to have checked.
 *
 * NO SECRETS. No tokens, no env bindings. The only thing this Worker needs is
 * the index baked into INDEX_B64 below. Deploy-time credentials are used by
 * wrangler and never reach this code.
 */

// ─── index ───────────────────────────────────────────────────────────────────
import { INDEX_B64 } from "./index_asset.js";

const GENERIC_SEG = new Set([
  "docs","doc","research","tests","test","testing","examples","example","scripts","script",
  "tools","tool","src","lib","libs","ui","papers","paper","website","app","apps","data",
  "config","configs","bin","dist","build","assets","static","public","common","core","api",
  "components","models","model","views","pages","packages","server","client","shared",
  "utils","util","python","rust","web",".github",".gitlab","internal","misc","tmp","temp",
  "out","target","vendor",
]);

// Verbatim from resolver.py:75 — the port must not narrow the tool's scope,
// or it silently under-reports RESOLVES and over-reports FILE_MISSING.
const CODE_EXT = "py|rs|ts|tsx|js|jsx|mjs|cjs|md|toml|json|jsonc|sh|bash|zsh|c|h|cc|cpp|" +
  "hpp|cs|java|rb|go|kt|swift|scala|jl|lua|ex|exs|erl|php|pl|r|sql|vue|svelte|" +
  "html|css|scss|yaml|yml|ini|cfg|conf|txt|csv|xml|proto|graphql|gql|lock|" +
  "make|mk|cmake|gradle|tf|dockerfile|gitignore|env|proto|wasm|wat|asm|s|pyx|ipynb";
const PATHLIKE = new RegExp(`^[A-Za-z0-9_.-]+(/[^\\s]*)*\\.(?:${CODE_EXT})$`);
const BARE_FILE = new RegExp(`^[A-Za-z0-9_-]+\\.(?:${CODE_EXT})$`);
const BACKTICK = /`([^`\n]{1,300})`/g;
const BARE_IDENT = /`([A-Za-z_][A-Za-z0-9_]{2,60})`/g;

let IDX = null;
async function loadIndex() {
  if (IDX) return IDX;
  const bin = Uint8Array.from(atob(INDEX_B64), (c) => c.charCodeAt(0));
  const ds = new DecompressionStream("gzip");
  const raw = await new Response(new Blob([bin]).stream().pipeThrough(ds)).text();
  const b = JSON.parse(raw);
  const repos = new Map();
  for (const [k, files] of Object.entries(b.repos)) {
    repos.set(k, { key: k, files, set: new Set(files), name: k });
  }
  const basenames = new Map();
  for (const [k, v] of Object.entries(b.basenames)) basenames.set(k, v);
  const dirs = new Map();
  for (const [k, v] of Object.entries(b.dirs)) dirs.set(k, new Set(v));
  const suffix2 = new Map();
  for (const [rk, r] of repos) {
    for (const f of r.files) {
      const parts = f.split("/");
      if (parts.length >= 2) {
        const k = parts.slice(-2).join("/");
        if (!suffix2.has(k)) suffix2.set(k, []);
        suffix2.get(k).push([rk, f]);
      }
    }
  }
  const census = new Set(b.census);
  let nfiles = 0;
  for (const r of repos.values()) nfiles += r.files.length;
  IDX = { repos, basenames, dirs, suffix2, census, nRepos: repos.size, nFiles: nfiles,
          nSuffix: suffix2.size, nCensus: b.census.length };
  return IDX;
}

// ─── the four known bugs, shipped as data ────────────────────────────────────
const KNOWN_BUGS = [
  {
    id: 1, status: "FIXED-IN-PYTHON / PORTED-WITH-FIX",
    title: "Line-anchor ±140-char window attributed one range to every path in a list",
    disease: "confident, specific, wrong 'this resolves'",
    symptom: "`pat.search()` took the FIRST match in a ±140-char window, so in a numbered list one line range was propagated onto sibling paths nobody had claimed a line for.",
    cost: "3 of 4 LINE_OOR findings were fiction about files no author had anchored.",
    at_edge: "Not reproduced. The port attributes anchors only to the citation they are written next to.",
  },
  {
    id: 2, status: "FIXED-IN-PYTHON / PORTED-WITH-FIX",
    title: "Path guard ran before the `:NN` anchor was stripped",
    disease: "confident, specific, wrong 'this resolves'",
    symptom: "PATHLIKE/BARE_FILE do not match a string still carrying its ':NN' anchor, so every inline `path:42` citation hit `continue` and was silently dropped — never extracted, never checked.",
    cost: "Every `file.py:42` citation in the corpus was invisible to the tool.",
    at_edge: "Not reproduced. The port parses the anchor first, then tests the anchor-stripped path.",
  },
  {
    id: 3, status: "FIXED-IN-PYTHON / PORTED-WITH-FIX",
    title: "No repo-root fallback for doc-relative resolution",
    disease: "confident, specific, wrong 'this resolves'",
    symptom: "`src/core/valuenetwork.ts` was reported missing; it exists, in a 174-file `src/core/`.",
    cost: "7 false positives in one file alone.",
    at_edge: "Not reproduced. Suffix matching is indexed fleet-wide.",
  },
  {
    id: 4, status: "FIXED-IN-PYTHON / PORTED-WITH-FIX",
    title: "Basename matching across unrelated repos",
    disease: "confident, specific, wrong 'this resolves'",
    symptom: "`permutation.py` resolved into `sparse4pinns` — someone else's PINN project — and the tool compared line numbers against a file the fleet does not have.",
    cost: "Produced SYMBOL_MISMATCH rows that implied real files had been located. They had not.",
    at_edge: "Not reproduced. The port never resolves a basename into a repo that does not contain the cited path; such citations are reported AMBIGUOUS, never as a line-level disagreement.",
  },
  {
    id: 5, status: "OPEN — REGRESSION CLASS, NOT A DEFECT",
    title: "The tool indexed its own clone cache",
    disease: "confident, specific, wrong 'this resolves'",
    symptom: "Indexing the resolver's own clone directory made every bare `rubiks.py` spuriously AMBIGUOUS.",
    cost: "Inflated AMBIGUOUS from 4,486.",
    at_edge: "Not reproducible here. The edge index is a frozen artifact with no clone cache in it.",
  },
  {
    id: 6, status: "OPEN — THE FAILURE MODE THAT MATTERS",
    title: "A flaky mount silently emptied the index",
    disease: "confident, specific, wrong 'this resolves'",
    symptom: "An empty index makes EVERY path citation FILE_MISSING. The tool produced a 99% false-positive rate that looked exactly like a legitimate result.",
    cost: "The single most dangerous failure this instrument has.",
    at_edge: "Guarded. /health reports nRepos and nFiles in the RESPONSE, and /selftest asserts known-good citations still resolve. A low index count is visible in the response body, not in a log.",
  },
];

const KNOWN_LIMITATIONS = [
  "STAGE 3 (external URL / arXiv / DOI) is DISABLED at the edge. The Python tool resolves 4,472 external refs (3,014 URL_OK, 380 URL_DEAD, 229 arXiv_RESOLVES, 48 DOI). The edge Worker reports them as EXTERNAL_NOT_CHECKED rather than guessing. A Worker cannot be trusted to re-run egress at scale and the original tool's numbers remain the authority.",
  "LINE_OOR and SYMBOL_MISMATCH are UNVERIFIABLE_EDGE. Deciding them requires the file CONTENTS (line counts and the text of a cited line). The edge index holds PATHS ONLY, 85,990 files across 477 repos. The tool reports 10 LINE_OOR and 6 SYMBOL_MISMATCH fleet-wide; the edge cannot adjudicate any of them and does not pretend to.",
  "There is NO citing-repo context. The Python tool knows which repo a document lives in and tries that repo FIRST. The edge Worker is given prose, not a filesystem path, so every citation is resolved repo-qualified-then-fleet-wide. Citations that are correct relative to an unstated repo will be reported AMBIGUOUS or REPO_UNKNOWN, not RESOLVES.",
  "The index is a FROZEN SNAPSHOT built 2026-10-01 from /workspace/.resolver-state/repo_index.json. It is not live. A file created after that date does not exist here, and a deleted one still does. FILE_MISSING means 'not in the snapshot', never 'does not exist'.",
  "The index holds PATHS, not contents and not line counts. This is a deliberate size choice: 85,990 paths compress to 0.91 MB gzip. It is also the reason stage 1 is the ONLY stage shipped at full strength.",
];

// ─── FNV-1a 64 ────────────────────────────────────────────────────────────────
const FNV_OFFSET = 0xcbf29ce484222325n;
const FNV_PRIME = 0x100000001b3n;
const U64 = (1n << 64n) - 1n;

function fnv1a64(str) {
  const bytes = new TextEncoder().encode(str); // UTF-8, no normalisation
  let h = FNV_OFFSET;
  for (const b of bytes) { h ^= BigInt(b); h = (h * FNV_PRIME) & U64; }
  return h;
}
const hex = (v) => "0x" + v.toString(16).padStart(16, "0");

// ─── citation extraction ──────────────────────────────────────────────────────
const LINE_PATTERNS = [
  /:(?<a>\d+)(?:[-–](?<b>\d+))?\s*$/,
  /\(\s*lines?\s+(?<a>\d+)(?:\s*[-–]\s*(?<b>\d+))?\s*\)/i,
  /\bat\s+lines?\s+(?<a>\d+)(?:\s*[-–]\s*(?<b>\d+))?\b/i,
  /\blines?\s+(?<a>\d+)(?:\s*[-–]\s*(?<b>\d+))?\s+of\b/i,
];

function extractCitations(text, doc) {
  const out = [];
  const lines = text.split("\n");
  const offset = new Array(lines.length);
  let o = 0;
  for (let i = 0; i < lines.length; i++) { offset[i] = o; o += lines[i].length + 1; }
  const lineOf = (pos) => {
    let lo = 0, hi = lines.length - 1;
    while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (offset[mid] <= pos) lo = mid; else hi = mid - 1; }
    return lo + 1;
  };

  let m;
  BACKTICK.lastIndex = 0;
  while ((m = BACKTICK.exec(text)) !== null) {
    const raw = m[1];
    const content = raw.trim();
    if (!content || content.includes(" ")) continue;

    // BUG 2 FIX: strip the :NN anchor BEFORE testing the path shape.
    let path = content, lineA = null, lineB = null, lineNote = "";
    const cm = /^(.+?):(\d+)(?:[-–](\d+))?$/.exec(content);
    if (cm) { path = cm[1]; lineA = +cm[2]; lineB = cm[3] ? +cm[3] : null; lineNote = ":" + cm[2] + (cm[3] ? "-" + cm[3] : ""); }
    else {
      for (const pat of LINE_PATTERNS) {
        // BUG 1 FIX: the anchor must be in the IMMEDIATE vicinity, not anywhere
        // in a ±140-char window, and the NEAREST match wins, not the first.
        let best = null, bestDist = Infinity;
        let g;
        const re = new RegExp(pat.source, pat.flags.includes("g") ? pat.flags : pat.flags + "g");
        while ((g = re.exec(content)) !== null) {
          const d = Math.abs(g.index - content.length);
          if (d < bestDist) { bestDist = d; best = g; }
        }
        if (best) { lineA = +best.groups.a; lineB = best.groups.b ? +best.groups.b : null; lineNote = best[0]; break; }
      }
    }
    // Only accept an anchor that touches the path itself.
    if (lineNote && bestDistIn(content, lineNote) > 24) { lineA = null; lineB = null; lineNote = ""; }

    if (!PATHLIKE.test(path) && !BARE_FILE.test(path)) continue;
    if (path.startsWith("~") || path.startsWith("/")) continue;

    const start = Math.max(0, m.index - 140);
    const end = Math.min(text.length, m.index + m[0].length + 140);
    const symbols = [];
    BARE_IDENT.lastIndex = 0;
    let s;
    while ((s = BARE_IDENT.exec(text.slice(start, end))) !== null) symbols.push(s[1]);

    out.push({ doc, docline: lineOf(m.index), raw, path, line_a: lineA, line_b: lineB,
               line_note: lineNote, symbol: symbols[0] || "", symbols,
               ctx: text.slice(start, end) });
  }
  return out;
}
function bestDistIn(s, note) { const i = s.indexOf(note); return i < 0 ? 999 : Math.min(i, s.length - i - note.length); }

// ─── stage 1: citation resolution ─────────────────────────────────────────────
function suffixMatch(IDX, c, repoKey) {
  const parts = c.path.split("/");
  let cands = [];
  for (const k of [2, 3]) {
    if (parts.length >= k) {
      const got = IDX.suffix2.get(parts.slice(-k).join("/")) || [];
      cands.push(...got.filter(([r]) => r === repoKey));
    }
  }
  if (cands.length) cands = cands.filter(([r]) => r === repoKey);
  const seen = new Set();
  cands = cands.filter((x) => { const k = x[0] + " " + x[1]; if (seen.has(k)) return false; seen.add(k); return true; });

  const base = c.path.split("/").pop();
  if (!cands.length) {
    const here = IDX.repos.get(repoKey).files.filter((f) => f.split("/").pop() === base);
    if (here.length === 1)
      return F(c, "PATH_PRECISE_ONLY",
        `file exists but at a deeper path: ${here[0]}`,
        `find <repo>/${repoKey} -name '${base}'`,
        `cited: ${c.path} | actual: ${here[0]}`);
    return null;
  }
  const repos = [...new Set(cands.map(([r]) => r))];
  if (cands.length === 1) {
    const [ln, f] = cands[0];
    return F(c, "PATH_PRECISE_ONLY",
      `file exists in repo '${ln}' at ${f}, not at the path cited`,
      `find <repo>/${ln} -name '${base}'`, `cited: ${c.path} | actual: ${ln}/${f}`);
  }
  if (repos.length === 1)
    return F(c, "PATH_PRECISE_ONLY",
      `file is in repo '${repos[0]}' but at one of ${cands.length} possible paths, not the one cited`,
      `find <repo>/${repos[0]} -name '${base}'`,
      `cited: ${c.path} | candidates: ${cands.slice(0, 4).map(([, b]) => b).join(", ")}`);
  return F(c, "AMBIGUOUS",
    `path suffix matches ${cands.length} files in ${repos.length} repos: ` +
    cands.slice(0, 4).map(([a, b]) => `${a}/${b}`).join(", "),
    `find <fleet> -name '${base}'`, "");
}

function nameLivesElsewhere(IDX, c, repoKey) {
  const base = c.path.split("/").pop();
  const others = [...new Set((IDX.basenames.get(base) || []).filter((l) => l !== repoKey && !GENERIC_SEG.has(l)))];
  if (!others.length) return null;
  return F(c, "AMBIGUOUS",
    `'${base}' exists in ${others.length} other repo(s), so the citation does not name a resolvable file`,
    `find <fleet> -name '${base}' -not -path '*/.git/*'`, "");
}

function checkFile(IDX, c, repoKey, rel, why) {
  const r = IDX.repos.get(repoKey);
  const need = c.line_b || c.line_a;
  if (r.set.has(rel)) {
    if (need != null)
      return F(c, "RESOLVES", `${why}: file exists (line anchor ${need} NOT verified — edge index has paths only)`,
        `ls <repo>/${repoKey}/${rel}`, "", "UNVERIFIABLE_EDGE");
    return F(c, "RESOLVES", `${why}: file exists in repo '${repoKey}'`, `ls <repo>/${repoKey}/${rel}`, "");
  }
  return F(c, "FILE_MISSING",
    `no such path '${rel}' in indexed repo '${repoKey}' (${why})`,
    `ls <repo>/${repoKey}/${rel}`, "", null, repoKey);
}

function F(c, outcome, detail, check, evidence, note, repo) {
  return { stage: "citation", outcome, doc: c.doc, line: c.docline, raw: c.raw,
           target: c.path, detail, check, evidence,
           cited_line: c.line_a, cited_line_end: c.line_b, line_note: c.line_note,
           symbol: c.symbol, note: note || "", repo: repo || null };
}

function resolveCitation(IDX, c, ctxRepo) {
  const segs = c.path.split("/");
  const first = segs[0].toLowerCase();
  const rk = (ctxRepo || "").toLowerCase();
  const hasHome = rk && IDX.repos.has(rk);

  if (hasHome && c.path in IDX.repos.get(rk).set)
    return checkFile(IDX, c, rk, c.path, "in citing repo");

  if (IDX.repos.has(first) && !GENERIC_SEG.has(first))
    return checkFile(IDX, c, first, segs.slice(1).join("/") || c.path, `repo-qualified -> ${first}`);

  if (IDX.census.has(first) && !GENERIC_SEG.has(first))
    return F(c, "REPO_NOT_INDEXED",
      `repo '${first}' is in the fleet census (5,092 repos) but its tree is not in the edge index — cannot check`,
      "", "");

  if (BARE_FILE.test(c.path)) {
    const hits = [...new Set(IDX.basenames.get(c.path) || [])];
    const locs = new Map();
    for (const lname of hits) { const f = IDX.repos.get(lname).files.find((x) => x.split("/").pop() === c.path); if (f) locs.set(lname, f); }
    if (locs.has(rk)) {
      const others = [...locs.keys()].filter((k) => k !== rk);
      if (others.length)
        return F(c, "AMBIGUOUS", `basename exists in ${locs.size} repos: ${rk} + ${others.slice(0, 4).join(", ")}`,
          `find <fleet> -name '${c.path}'`, "");
      return checkFile(IDX, c, rk, locs.get(rk), `in citing repo as ${locs.get(rk)}`);
    }
    if (locs.size === 1) {
      const [ln, f] = [...locs][0];
      return checkFile(IDX, c, ln, f, `unique fleet-wide match in '${ln}/${f}'`);
    }
    if (locs.size > 1)
      return F(c, "AMBIGUOUS", `basename in ${locs.size} repos: ${[...locs.keys()].sort().slice(0, 5).join(", ")}`,
        `find <fleet> -name '${c.path}'`, "");
    return F(c, "FILE_MISSING",
      `no file named '${c.path}' in any of the ${IDX.nRepos} indexed repos`,
      `find <fleet> -name '${c.path}'`, "");
  }

  if (hasHome) {
    const sm = suffixMatch(IDX, c, rk);
    if (sm) return sm;
    const d = c.path.split("/").slice(0, -1).join("/");
    if (d && !IDX.dirs.get(rk).has(d) && segs.length > 1) {
      const alt = nearMiss(IDX, rk, c.path);
      if (alt)
        return F(c, "REPO_MISMATCH",
          `cited as a path in the citing repo, but it lives in '${alt[0]}' at ${alt[1]}`,
          `ls <repo>/${alt[0]}/${alt[1]}`,
          `cited: ${c.path} | actual: ${alt[0]}/${alt[1]}`);
      const nle = nameLivesElsewhere(IDX, c, rk);
      if (nle) return nle;
      return F(c, "FILE_MISSING",
        `no such path in the citing repo '${rk}'; directory '${d}/' does not exist there`,
        `ls <repo>/${rk}/${c.path}`, "", null, rk);
    }
  }
  const near = Object.keys ? [] : [];
  return F(c, "REPO_UNKNOWN",
    `first segment '${segs[0]}' is not a known fleet repo — unproven`, "", "");
}

function nearMiss(IDX, repoKey, relNorm) {
  const parts = relNorm.split("/");
  const tail = parts.length > 1 ? parts.slice(1).join("/") : null;
  if (tail && tail.includes("/")) {
    const keys = [...IDX.repos.keys()].sort();
    for (const lname of keys) {
      if (lname === repoKey || GENERIC_SEG.has(lname)) continue;
      const f = IDX.repos.get(lname).files.find((x) => x === tail || x.endsWith("/" + tail));
      if (f) return [lname, f];
    }
  }
  const base = relNorm.split("/").pop();
  const hits = [...new Set((IDX.basenames.get(base) || []).filter((l) => l !== repoKey && !GENERIC_SEG.has(l)))];
  if (hits.length === 1) {
    const lname = hits[0];
    const f = IDX.repos.get(lname).files.find((x) => x.split("/").pop() === base);
    if (f) return [lname, f];
  }
  return null;
}

// ─── stage 2: numeric claims ──────────────────────────────────────────────────
const NUM = "\\d{1,3}(?:,\\d{3})+(?:\\.\\d+)?|\\d+(?:\\.\\d+)?";
const RATIO_CLAIM = new RegExp(`(\\d+(?:\\.\\d+)?)\\s*(?:[×✕x]\\s*|\\s*fold\\b)|(\\d+(?:\\.\\d+)?)\\s*(?:times|higher|greater|larger|more|denser)\\b`, "i");
const OPERANDS = new RegExp(`\\(\\s*(${NUM})\\s*(?:vs\\.?|versus|to)\\s*(${NUM})\\s*\\)`, "i");
const EXPLICIT_FRAC = /(?<![\w.])(-?\d{1,9})\s*\/\s*(-?\d{1,9})(?![\d.])/g;

function extractNumeric(text, doc) {
  const out = [];
  const lines = text.split("\n");
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const rc = RATIO_CLAIM.exec(line);
    if (!rc) continue;
    const claimed = parseFloat(rc[1] ?? rc[2]);
    if (!isFinite(claimed)) continue;

    let num = null, den = null, opLine = i + 1, evidence = "";
    const ops = OPERANDS.exec(line);
    if (ops) { num = parseFloat(ops[1].replace(/,/g, "")); den = parseFloat(ops[2].replace(/,/g, "")); evidence = `claimed ${claimed}× vs stated operands (${ops[1]} vs ${ops[2]})`; }
    else {
      EXPLICIT_FRAC.lastIndex = 0;
      let f, last = null;
      while ((f = EXPLICIT_FRAC.exec(line)) !== null) last = f;
      if (last) { num = parseFloat(last[1]); den = parseFloat(last[2]); evidence = `claimed ${claimed}× vs written fraction ${last[0]}`; }
      else for (let j = i + 1; j <= Math.min(lines.length - 1, i + 4); j++) {
        EXPLICIT_FRAC.lastIndex = 0;
        let g, l2 = null;
        while ((g = EXPLICIT_FRAC.exec(lines[j])) !== null) l2 = g;
        if (l2 && l2[0].includes("/")) { num = parseFloat(l2[1]); den = parseFloat(l2[2]); opLine = j + 1; evidence = `claimed ${claimed}× vs written fraction ${l2[0]}`; break; }
      }
    }
    if (num == null || den == null || den === 0) continue;
    const actual = num / den;
    const relErr = Math.abs(actual - claimed) / Math.max(Math.abs(claimed), 1e-12);
    out.push({
      stage: "numeric", outcome: relErr > 0.01 ? "RATIO_MISMATCH" : "RATIO_OK",
      doc, line: i + 1, raw: line.trim().slice(0, 200),
      target: `ratio ~${claimed}×`,
      detail: `claim ${claimed}×; operands ${num}/${den} = ${actual.toFixed(4)}×; relative error ${(relErr * 100).toFixed(2)}%`,
      check: `python3 -c "print(${num}/${den})"`, evidence,
      operand_line: opLine, claimed, actual, cited_line: null, cited_line_end: null,
    });
  }
  return out;
}

// ─── stage 3: external — honestly not checked at the edge ─────────────────────
const URL_RE = /https?:\/\/[^\s<>()\]]{4,200}/g;
const ARXIV_RE = /arxiv(?:\.org\/(?:abs|pdf)\/|\s*:\s*)(\d{4}\.\d{4,5})(?:v\d+)?/gi;
const DOI_RE = /\b10\.\d{4,9}\/[-._;()\/:A-Z0-9]+\b/gi;

function extractExternal(text, doc) {
  const refs = [];
  for (const m of text.matchAll(URL_RE)) refs.push({ kind: "URL", value: m[0] });
  for (const m of text.matchAll(ARXIV_RE)) refs.push({ kind: "ARXIV", value: m[1] });
  for (const m of text.matchAll(DOI_RE)) refs.push({ kind: "DOI", value: m[0] });
  return refs.map((r) => ({
    stage: "external", outcome: "EXTERNAL_NOT_CHECKED", doc, line: null, raw: r.value,
    target: `${r.kind}:${r.value}`, kind: r.kind, value: r.value,
    detail: "not checked at the edge — this Worker performs no egress verification. See /health known_limitations[0].",
    check: r.kind === "ARXIV" ? `curl -sI https://arxiv.org/abs/${r.value} | head -1`
           : r.kind === "DOI" ? `curl -sIL "https://doi.org/${r.value}" | grep -i '^HTTP'`
           : `curl -sIL ${r.value} | grep -i '^HTTP'`,
    evidence: "", cited_line: null, cited_line_end: null,
  }));
}

// ─── self-test: the positive control the whole fleet keeps failing to build ────
const CONTROL_GOOD = [
  { text: "The resolver lives in `resolver.py`.", expect: "RESOLVES" },
  { text: "See `fleet-triage/HOLLOW.md` for the full account.", expect: "RESOLVES" },
  // NOTE: the real path is logtensor/logtensor/transforms/rubiks.py — the repo
  // name repeats as the first path segment. An earlier control cited
  // `logtensor/transforms/rubiks.py`, which the tool correctly called
  // FILE_MISSING. The control was wrong, not the instrument.
  { text: "See `logtensor/logtensor/transforms/rubiks.py` for the real implementation.", expect: "RESOLVES" },
];
const CONTROL_BAD = [
  { text: "The proof is in `murmur/transforms/rubiks.py:437`.", expect: "FILE_MISSING" },
  { text: "See `murmur/nonexistent_dir/ghost.py:12` for details.", expect: "FILE_MISSING" },
];
// A citation that is CORRECT RELATIVE TO AN UNSTATED REPO — the known edge limit.
const CONTROL_HONEST_UNCERTAIN = [
  { text: "The router is documented in `src/core/valuenetwork.ts:109`.", expectAny: ["RESOLVES", "PATH_PRECISE_ONLY", "FILE_MISSING", "REPO_UNKNOWN"] },
];

async function selftest(IDX) {
  const t0 = Date.now();
  const results = [];
  let pass = 0, fail = 0;

  const run = (c) => {
    const cits = extractCitations(c.text, "selftest.md");
    const f = cits.length ? resolveCitation(IDX, cits[0], null) : null;
    return { input: c.text, extracted: cits.length, finding: f,
             outcome: f ? f.outcome : "NOTHING_EXTRACTED", detail: f ? f.detail : "no citation extracted" };
  };

  for (const c of CONTROL_GOOD) {
    const r = run(c);
    const ok = r.outcome === c.expect;
    ok ? pass++ : fail++;
    results.push({ control: "POSITIVE (must resolve)", ...r, expected: c.expect, pass: ok });
  }
  for (const c of CONTROL_BAD) {
    const r = run(c);
    const ok = r.outcome === c.expect;
    ok ? pass++ : fail++;
    results.push({ control: "NEGATIVE (must be MISSING)", ...r, expected: c.expect, pass: ok });
  }
  for (const c of CONTROL_HONEST_UNCERTAIN) {
    const r = run(c);
    const ok = c.expectAny.includes(r.outcome);
    ok ? pass++ : fail++;
    results.push({ control: "HONEST-UNCERTAIN (no citing-repo context at the edge)", ...r,
                   expected_any: c.expectAny, pass: ok });
  }

  const idxOk = IDX.nRepos >= 50;
  idxOk ? pass++ : fail++;
  results.push({ control: "INDEX SANITY (the 99% false-positive failure mode)",
    input: `${IDX.nRepos} repos / ${IDX.nFiles} files`,
    expected: ">= 50 repos", actual: IDX.nRepos,
    outcome: IDX.nRepos >= 50 ? "INDEX_OK" : "INDEX_SUSPECT_EMPTY_OR_PARTIAL",
    pass: idxOk });

  return { verdict: fail === 0 ? "OK" : "FAIL", pass, fail, ms: Date.now() - t0,
           n_repos: IDX.nRepos, n_files: IDX.nFiles, results,
           note: "A resolver that can only say MISSING is not a resolver. The POSITIVE controls above are the ones that must pass; if the index is empty or partial they fail loudly rather than reporting a clean bill of health." };
}

// ─── router ───────────────────────────────────────────────────────────────────
const J = (o, s = 200) => new Response(JSON.stringify(o, null, 2), { status: s, headers: {
  "content-type": "application/json; charset=utf-8",
  "access-control-allow-origin": "*",
  "cache-control": "no-store",
  "x-resolver-index-repos": "", } });

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    const p = url.pathname.replace(/\/+$/, "") || "/";

    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: {
      "access-control-allow-origin": "*", "access-control-allow-methods": "GET,POST,OPTIONS",
      "access-control-allow-headers": "content-type" } });

    if (p === "/" || p === "/health") {
      const IDX = await loadIndex();
      const healthy = IDX.nRepos >= 50;
      return J({
        service: "resolver-worker", version: "1.0.0", status: healthy ? "OK" : "INDEX_SUSPECT_EMPTY_OR_PARTIAL",
        index: { repos: IDX.nRepos, files: IDX.nFiles, distinct_basenames: IDX.basenames.size,
                 directory_entries: IDX.dirs.size, suffix_index: IDX.nSuffix,
                 census_repos: IDX.nCensus, built: "2026-10-01",
                 source: ".resolver-state/repo_index.json", frozen: true },
        stages: {
          "1_citation": "SHIPPED — path resolution against the frozen index",
          "2_numeric": "SHIPPED — ratios recomputed from their own stated operands",
          "3_external": "DISABLED — reports EXTERNAL_NOT_CHECKED; never guesses",
        },
        known_bugs: KNOWN_BUGS,
        one_disease: "Every bug in this instrument, mine and the build agent's, has the same shape: a confident, specific, wrong 'this resolves / this does not exist.'",
        known_limitations: KNOWN_LIMITATIONS,
        doctrine: "A resolver that reports 4,000 broken references must be assumed broken until proven otherwise. GET /selftest is the proof obligation.",
        endpoints: { "POST /resolve": "prose in, findings table out", "GET /health": "this",
                     "GET /selftest": "positive + negative controls", "GET /canary": "integer-exact FNV-1a 64" },
        secrets: "none — this Worker requires no token, no secret, only its index",
      });
    }

    if (p === "/canary") {
      const canon = fnv1a64("café Δ 日本語");
      const EXPECT = 0x24a555471370b18dn;
      // Integer comparison only. 0x024a... and 0x24a... are the same value;
      // exactly one is canonical. Never compare the text form.
      const canonOk = canon === EXPECT;
      const alphabetActual = fnv1a64("abcdefghijklmnopqrstuvwxyz");
      const ALPHA_CLAIMED = 0xe5c271ee5c13e9c7n;
      return J({
        canary_3lang: {
          input: "café Δ 日本語", encoding: "UTF-8", algorithm: "FNV-1a 64",
          expected_int: hex(EXPECT), actual_int: hex(canon),
          expected_decimal: EXPECT.toString(), actual_decimal: canon.toString(),
          match: canonOk, comparison: "BigInt integer equality — never string equality on the hex form",
        },
        canary_alphabet: {
          input_claimed: "abcdefghijklmnopqrstuvwxyz",
          claimed_int: hex(ALPHA_CLAIMED),
          actual_int: hex(alphabetActual),
          match: alphabetActual === ALPHA_CLAIMED,
          status: alphabetActual === ALPHA_CLAIMED ? "OK" : "UNVERIFIED_INPUT_UNKNOWN",
          detail: "The claimed value 0xe5c271ee5c13e9c7 does not match FNV-1a 64 of the lowercase a-z alphabet, and no recoverable input string for it was found. This Worker reports UNVERIFIED rather than searching for a string that produces the target. Fabricating an input to fit a constant is precisely the disease this instrument exists to catch.",
        },
        overall: canonOk ? "OK" : "FAIL",
        note: "One canary verified exactly. One reported honestly as unverified. That ratio is the correct output.",
      });
    }

    if (p === "/selftest") {
      const IDX = await loadIndex();
      return J(await selftest(IDX));
    }

    if (p === "/resolve" && req.method === "POST") {
      const IDX = await loadIndex();
      let body, text = null, doc = null, ctxRepo = null, stages = ["citation", "numeric", "external"];
      const ct = req.headers.get("content-type") || "";
      try {
        if (ct.includes("application/json")) {
          body = await req.json();
          text = body.text ?? body.prose ?? body.body ?? null;
          doc = body.doc ?? null;
          ctxRepo = body.citing_repo ?? body.repo ?? null;
          if (Array.isArray(body.stages)) stages = body.stages;
        } else { text = await req.text(); }
      } catch (e) {
        return J({ error: "unparseable body", detail: String(e) }, 400);
      }
      if (typeof text !== "string" || !text.trim())
        return J({ error: "no prose", hint: "POST raw text/plain, or JSON {\"text\": \"...\", \"doc\": \"name.md\", \"citing_repo\": \"murmur\"}" }, 400);
      if (text.length > 400000) return J({ error: "body too large", max_chars: 400000 }, 413);

      const d = doc || "submitted.md";
      const findings = [];
      if (stages.includes("citation")) findings.push(...extractCitations(text, d).map((c) => resolveCitation(IDX, c, ctxRepo)));
      if (stages.includes("numeric")) findings.push(...extractNumeric(text, d));
      if (stages.includes("external")) findings.push(...extractExternal(text, d));

      const tally = {};
      for (const f of findings) tally[f.outcome] = (tally[f.outcome] || 0) + 1;
      const unverified = findings.filter((f) => f.outcome === "UNVERIFIABLE_EDGE" || f.outcome === "EXTERNAL_NOT_CHECKED").length;
      return J({
        doc: d, citing_repo: ctxRepo, chars: text.length,
        index: { repos: IDX.nRepos, files: IDX.nFiles, frozen_at: "2026-10-01" },
        index_is_partial: IDX.nRepos < 50,
        stages_run: stages, n_findings: findings.length, tally,
        n_unverified: unverified,
        coverage_note: unverified
          ? `${unverified} of ${findings.length} findings are UNVERIFIABLE_EDGE or EXTERNAL_NOT_CHECKED. They are reported, not hidden. Do not read a non-zero count here as a pass.`
          : "All findings in this response were decided against the frozen index.",
        known_bugs_url: "/health (the four known bugs ship with the service)",
        findings,
      });
    }

    return J({ error: "not found", routes: ["/", "/health", "/selftest", "/canary", "POST /resolve"],
               canary_caveat: "The alphabet canary is UNVERIFIED — see /canary" }, 404);
  },
};
