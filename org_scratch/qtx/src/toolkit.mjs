// quilt-toolkit.mjs — the shared runtime for the Quilt Tools portfolio.
//
// One import gives a tool everything it needs so each tool stays small and
// single-purpose:
//
//   import { sheet, WitnessLog, check, done, panel, SysOne, localEmbed, cosine } from '../quilt-toolkit.mjs';
//
// Contents:
//   - QuiltEngine wiring (patched dist; QUILT_DIST env override for ports)
//   - WitnessLog: fnv1a64 / canon / makeRow / verifyChain — the fleet's receipt
//     idiom, ported line-for-line from quilt-cloudflare/src/ocean.ts
//   - check()/done(): the playtest harness every tool ends with
//   - panel(): minimal ANSI dashboard so output reads like a working product
//   - SysOne: Choice/Score/Noul with the fence in the adapter — real GLM when
//     reachable, deterministic heuristics when not (degrade honest, never 502)
//   - localEmbed/cosine: the deterministic one-geometry embedder (tidepool
//     "native fingerprint" idiom, widened to 64 dims)
//
// Every tool runs fully offline unless a live model is reachable; offline
// mode is labeled, never silent.

// Engine resolution order: QUILT_DIST env (ports/labs) → vendored dist
// shipped in this repo. The chart must suffice: no hidden laptop paths.
import { pathToFileURL, fileURLToPath } from 'node:url';
import path from 'node:path';

const here = path.dirname(fileURLToPath(import.meta.url));
export const QUILT_DIST = process.env.QUILT_DIST
  ?? path.resolve(here, '../vendor/quilt-core/dist/index.js');

const { QuiltEngine } = await import(pathToFileURL(QUILT_DIST).href);
export { QuiltEngine };

// ── witness idiom (quilt-cloudflare/src/ocean.ts, ported verbatim) ──────────
export const GENESIS_PREV = '0'.repeat(16);

export function fnv1a64(input) {
  let h = 0xcbf29ce484222325n;
  const prime = 0x100000001b3n, mask = 0xffffffffffffffffn;
  for (let i = 0; i < input.length; i++) {
    h ^= BigInt(input.charCodeAt(i));
    h = (h * prime) & mask;
  }
  return h.toString(16).padStart(16, '0');
}

export function canon(row) {
  const sorted = {};
  for (const k of Object.keys(row).sort()) sorted[k] = row[k];
  return JSON.stringify(sorted);
}

export function makeRow(prev, fields) {
  const seq = prev ? prev.seq + 1 : 0;
  const prev_hash = prev ? prev.row_hash : GENESIS_PREV;
  const f = { ...fields, seq, prev_hash };
  return { ...f, row_hash: fnv1a64(canon(f)) };
}

export function verifyChain(rows) {
  let prevHash = GENESIS_PREV;
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    const { row_hash, ...rest } = r;
    if (r.seq !== i || r.prev_hash !== prevHash || fnv1a64(canon(rest)) !== row_hash) {
      return { ok: false, brokenAt: i, expected: prevHash, got: r.prev_hash };
    }
    prevHash = row_hash;
  }
  return { ok: true, brokenAt: null, head: prevHash, count: rows.length };
}

// ── playtest harness ─────────────────────────────────────────────────────────
const state = { pass: 0, fail: 0, failures: [], tool: 'tool' };
export function setTool(name) { state.tool = name; }

export function check(name, ok, detail = '') {
  ok ? state.pass++ : state.fail++;
  if (!ok) state.failures.push(name);
  const mark = ok ? `${ANSI.green}✓${ANSI.reset}` : `${ANSI.red}✗${ANSI.reset}`;
  console.log(`  ${mark} ${name}${detail ? `${ANSI.dim} — ${detail}${ANSI.reset}` : ''}`);
  return ok;
}

export function done() {
  const total = state.pass + state.fail;
  const verdict = state.fail === 0
    ? `${ANSI.green}${state.pass}/${total} checks green — ready-to-go${ANSI.reset}`
    : `${ANSI.red}${state.fail}/${total} checks FAILED: ${state.failures.join(', ')}${ANSI.reset}`;
  console.log(`\n${ANSI.bold}  ══ ${state.tool}: ${verdict} ══${ANSI.reset}\n`);
  if (state.fail > 0) process.exitCode = 1;
}

// ── ANSI + panel ─────────────────────────────────────────────────────────────
export const ANSI = {
  green: '\x1b[32m', red: '\x1b[31m', amber: '\x1b[33m', cyan: '\x1b[36m',
  dim: '\x1b[2m', bold: '\x1b[1m', reset: '\x1b[0m',
};

const strip = s => String(s).replace(/\x1b\[[0-9;]*m/g, '');
const pad = (s, n) => {
  const clean = strip(s);
  return clean + ' '.repeat(Math.max(0, n - 1 - clean.length));
};

export function panel(title, rows, width = 62) {
  const clean = strip(title);
  const top = `┌─ ${clean} ${'─'.repeat(Math.max(0, width - clean.length - 4))}┐`;
  const body = rows.map(r => `│ ${pad(r, width - 3)}│`);
  const bottom = `└${'─'.repeat(width - 2)}┘`;
  console.log([top, ...body, bottom].join('\n'));
}

export function kv(k, v, kColor = ANSI.dim) {
  return `${kColor}${k}${ANSI.reset} ${v}`;
}

// ── convenience sheet builder ────────────────────────────────────────────────
export function sheet(id, cells, opts = {}) {
  const e = new QuiltEngine(id, { eager: true, ...opts });
  e.loadSheet({ id, cells });
  return e;
}

export const sleep = ms => new Promise(r => setTimeout(r, ms));

// ── deterministic embedder (one geometry, zero network) ─────────────────────
export const EMBED_DIMS = 64;
const STOP = new Set('a an the is are was were do does did how what why when who i you we my your our in on at to for of and or it its this that with as can will would should'.split(' '));
const stem = w => w.replace(/(ing|ed|es|s)$/, '');

export function localEmbed(text, dims = EMBED_DIMS) {
  const v = new Array(dims).fill(0);
  const words = String(text).toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/)
    .filter(w => w && !STOP.has(w)).map(stem);
  for (const w of words) {
    let h = 5381;
    for (let i = 0; i < w.length; i++) h = ((h << 5) + h + w.charCodeAt(i)) >>> 0;
    const idx = h % dims;
    const sign = (h >>> 31) & 1 ? -1 : 1;
    v[idx] += sign;
  }
  const norm = Math.sqrt(v.reduce((s, x) => s + x * x, 0)) || 1;
  return v.map(x => x / norm);
}

export const cosine = (a, b) => a.reduce((s, x, i) => s + x * b[i], 0);

// ── SysOne: schema-bounded decisions with the fence in the adapter ──────────
// Live GLM when reachable; deterministic heuristics when not. The sheet can
// only ever receive: one of the declared options, a clamped score, or a
// calibrated noul — never raw model text.
const extractJson = (text) => {
  const m = String(text).match(/\{[\s\S]*\}/);
  if (!m) return null;
  try { return JSON.parse(m[0]); } catch { return null; }
};

export class SysOne {
  constructor({ live = true } = {}) {
    this.zai = null;
    this.liveRequested = live;
    this.mode = 'offline';        // resolved by init()
    this.calls = 0;
    this.repairs = 0;
    this.refusals = 0;
  }

  async init() {
    if (!this.liveRequested) { this.mode = 'offline'; return this; }
    try {
      const { createRequire } = await import('node:module');
      const req = createRequire(path.resolve(here, '../package.json'));
      const ZAI = req('z-ai-web-dev-sdk');
      this.zai = await ZAI.create();
      this.mode = 'live';
    } catch {
      this.mode = 'offline';
    }
    return this;
  }

  async raw(system, user) {
    this.calls++;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        const completion = await this.zai.chat.completions.create({
          messages: [
            { role: 'assistant', content: system },
            { role: 'user', content: user },
          ],
          thinking: { type: 'disabled' },
        });
        return (completion.choices[0]?.message?.content ?? '').trim();
      } catch (e) {
        const transient = /429|Too many/i.test(String(e.message));
        if (!transient || attempt === 2) throw e;
        await sleep(12000 * (attempt + 1));
      }
    }
  }

  // Score — number clamped into [min, max]
  async score(text, { min = 1, max = 100, rubric = '', fallback } = {}) {
    if (this.mode === 'offline') {
      this.calls++;
      const v = fallback ? fallback(text) : Math.round((min + max) / 2);
      return { score: Math.min(max, Math.max(min, Math.round(v))), source: 'heuristic' };
    }
    const sys = `You are System One, a scoring function. Rubric: ${rubric}. Reply with ONLY strict JSON: {"score": <integer ${min}-${max}>}. No other keys, no prose.`;
    let parsed = extractJson(await this.raw(sys, text));
    if (!parsed || !Number.isFinite(Number(parsed.score))) {
      this.repairs++;
      parsed = extractJson(await this.raw(`${sys} Previous reply invalid — return ONLY the JSON object.`, text));
    }
    const n = Number(parsed?.score);
    if (!Number.isFinite(n)) { this.refusals++; return { __refused: true, reason: 'score unparseable' }; }
    return { score: Math.min(max, Math.max(min, Math.round(n))), source: 'glm' };
  }

  // Choice — exactly one declared option (letter-coded menu: A/B/C/…)
  async choice(text, { options, promptNote = '', fallback } = {}) {
    if (this.mode === 'offline') {
      this.calls++;
      const pick = fallback ? fallback(text, options) : options[0];
      return { choice: options.includes(pick) ? pick : options[0], source: 'heuristic' };
    }
    const menu = options.map((o, i) => `${String.fromCharCode(65 + i)} = ${o}`).join('\n');
    const sys = `You are System One, a decision function. The option menu is:\n${menu}\nReply with ONLY strict JSON: {"choice":"<letter>"} where <letter> is one of A-${String.fromCharCode(64 + options.length)}. No words, only the letter.${promptNote ? ' ' + promptNote : ''}`;
    const decode = v => {
      const i = String(v ?? '').trim().toUpperCase().charCodeAt(0) - 65;
      return i >= 0 && i < options.length ? options[i] : null;
    };
    let parsed = extractJson(await this.raw(sys, text));
    let value = decode(parsed?.choice);
    if (!value) {
      this.repairs++;
      parsed = extractJson(await this.raw(`${sys}\nPrevious reply invalid. Return ONLY {"choice":"<letter>"}.`, text));
      value = decode(parsed?.choice);
    }
    if (!value) { this.refusals++; return { __refused: true, reason: `not in schema (got ${JSON.stringify(parsed?.choice)})` }; }
    return { choice: value, source: 'glm' };
  }

  // Noul — yes/no with calibrated probability
  async noul(text, { question = '', fallback } = {}) {
    if (this.mode === 'offline') {
      this.calls++;
      const r = fallback ? fallback(text) : { noul: 'no', p: 0.5 };
      return { noul: r.noul === 'yes' ? 'yes' : 'no', p: Math.min(1, Math.max(0, Number(r.p) || 0)), source: 'heuristic' };
    }
    const sys = 'You are System One, a calibrated decider. Reply with ONLY strict JSON: {"noul": "yes"|"no", "p": <0-1 probability "yes" is correct>}. No prose.';
    let parsed = extractJson(await this.raw(sys, `${question ? question + '\n' : ''}${text}`));
    if (!parsed || !['yes', 'no'].includes(parsed.noul) || !Number.isFinite(Number(parsed.p))) {
      this.repairs++;
      parsed = extractJson(await this.raw(`${sys} Previous reply invalid — return ONLY the JSON object.`, text));
    }
    const p = Number(parsed?.p);
    if (!parsed || !['yes', 'no'].includes(parsed.noul) || !Number.isFinite(p)) {
      this.refusals++; return { __refused: true, reason: 'noul unparseable' };
    }
    return { noul: parsed.noul, p: Math.min(1, Math.max(0, p)), source: 'glm' };
  }
}

// ── witness-backed log: a hash-chained receipt ledger in a plain array ──────
export class WitnessLog {
  constructor(rows = []) { this.rows = rows; }
  append(fields) {
    const row = makeRow(this.rows[this.rows.length - 1] ?? null, fields);
    this.rows.push(row);
    return row;
  }
  verify() { return verifyChain(this.rows); }
  get head() { return this.rows[this.rows.length - 1]?.row_hash ?? GENESIS_PREV; }
  get length() { return this.rows.length; }
}
