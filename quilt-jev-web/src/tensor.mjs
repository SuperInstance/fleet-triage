// quilt-jev-web :: tensor.mjs
// VENDORED-DERIVED from SuperInstance/jev-quilt (Python) — see PROVENANCE.md.
// Rules carried over from the source:
//   cell.py  Law 1  identity never floats        -> coord is integer (x,y)
//   cell.py  Law 5  viability is binary          -> conf > 0 is viable
//   q16.py   identity is exact rational, floats are display projections only
// THE POINT OF CHANGE: the source's Cell holds a *decision* (a payload). This
// file holds a *distribution*. Law 3 says "decide here, project elsewhere"; the
// web lane takes that literally and never lets a scalar stand in for a map.

export const SCHEMA = 'quilt-jev/1';

// ---------------------------------------------------------------- canonical
// Round-trip identity needs a byte-stable serializer. Two rules do the work:
// sorted keys, and floats pinned to 9dp. No float ever reaches a file.
const F9 = (f) => (Math.round(f * 1e9) / 1e9).toFixed(9);
const enc = (v) => {
  if (v === null || v === undefined) return 'null';
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : F9(v);
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'string') return JSON.stringify(v);
  if (Array.isArray(v)) return '[' + v.map(enc).join(',') + ']';
  const keys = Object.keys(v).sort();
  return '{' + keys.map((k) => JSON.stringify(k) + ':' + enc(v[k])).join(',') + '}';
};
export const serialize = (grid) => enc(grid);

// FNV-1a over the canonical bytes. Not a security hash -- it is a *content
// address* so the UI can print one short string proving two views are one
// tensor. Same doctrine as the source's fold.py: integrity, not adversaries.
export function sha(bytes) {
  let h = 0x811c9dc5 >>> 0;
  const s = typeof bytes === 'string' ? bytes : new TextDecoder().decode(bytes);
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i) & 0xff;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return ('00000000' + h.toString(16)).slice(-8);
}
export const tensorSha = (grid) => sha(serialize(grid));

// ---------------------------------------------------------------- the cell
// A cell is VOID or it is a full distribution. There is no third state. This is
// the central failure mode of the whole project -- a canvas with no data must
// never be mistakable for a canvas full of zeros -- so it is a *type* question,
// not a rendering question.
export function cell(c) {
  if (c.origin === 'void') {
    return { x: c.x, y: c.y, origin: 'void', history: [] };
  }
  const probs = c.probabilities;
  const labels = Object.keys(probs);
  if (!labels.length) throw new CellError(`cell(${c.x},${c.y}): empty probability map`);
  const sum = labels.reduce((a, l) => a + probs[l], 0);
  if (!(sum > 0.99 && sum < 1.01)) throw new CellError(`cell(${c.x},${c.y}): probabilities sum ${sum}`);
  if (typeof c.confidence !== 'number') {
    throw new CellError(`cell(${c.x},${c.y}): confidence missing -- a scalar alone is a bug`);
  }
  const cellHistory = c.history && c.history.length
    ? c.history
    : [{ judge: c.judge || 'unattributed', at: c.at || null, probabilities: { ...probs }, confidence: c.confidence }];
  return {
    x: c.x, y: c.y, origin: c.origin || 'judgment',
    labelSet: labels.slice().sort(),          // THIS cell's vocabulary
    choice: argmax(probs),                     // derived, never stored alone
    confidence: c.confidence,                  // JEV's field. NOT p(argmax).
    probabilities: sortedMap(probs),           // the whole map. this is the content.
    ...derived(probs, c.confidence),
    history: cellHistory.map((h) => normalizeJudgment(h)),
  };
}

export class CellError extends Error {}

// ---------------------------------------------------------------- derived
// Four numbers, four *different questions*. Collapsing them is the bug the
// source's relief-by-entropy commits: entropy is one of these four and it is
// not the one that says "decided".
export function derived(probs, confidence) {
  const labels = Object.keys(probs).sort();
  const vals = labels.map((l) => probs[l]).sort((a, b) => b - a);
  const top1 = vals[0] || 0, top2 = vals[1] || 0;
  let H = 0;
  for (const v of vals) if (v > 0) H -= v * Math.log2(v);
  const Hmax = Math.log2(labels.length) || 1;
  return {
    entropy: H,
    entropyNorm: H / Hmax,          // 0 = one label, 1 = perfectly flat
    margin: top1 - top2,            // decided-ness, independent of loudness
    pArgmax: top1,
    // the contract's paradox, made executable: the judge's stated confidence
    // exceeds the probability it assigned to the answer it chose.
    overclaim: confidence - top1,
  };
}

export function argmax(probs) {
  let best = null, bv = -Infinity;
  for (const l of Object.keys(probs).sort()) {   // sorted: ties are deterministic
    if (probs[l] > bv) { bv = probs[l]; best = l; }
  }
  return best;
}
const sortedMap = (m) => Object.fromEntries(Object.keys(m).sort().map((k) => [k, m[k]]));
const normalizeJudgment = (h) => {
  const p = { ...h.probabilities };
  // labelSet travels WITH each judgment: a judgment recorded on 3 labels is
  // not the same judgment as one recorded on 5, and a stitch that assumes a
  // shared vocabulary would quietly invent the missing mass.
  return { judge: h.judge || 'unattributed', at: h.at || null, confidence: h.confidence,
           labelSet: Object.keys(p).sort(), probabilities: sortedMap(p), ...derived(p, h.confidence) };
};

// ---------------------------------------------------------------- the grid
export function grid({ width, height, cells, meta = {} }) {
  if (!(Number.isInteger(width) && Number.isInteger(height))) throw new CellError('grid size must be an integer pair -- identity never floats');
  if (cells.length !== width * height) throw new CellError(`grid ${width}x${height} needs ${width * height} cells, got ${cells.length}`);
  // the grid's vocabulary is a first-class field: one palette, one legend,
  // one place where "which labels exist" is answerable.
  const labelSet = [...new Set(cells.flatMap((c) => c.labelSet || []))].sort();
  const g = {
    schema: SCHEMA, width, height,
    labels: labelSet,
    cells: cells.slice().sort((a, b) => a.y - b.y || a.x - b.x),
    meta: {
      source: meta.source || 'unknown',          // 'typesafe-api' | 'synthetic' | ...
      model: meta.model || null,
      api_key: meta.api_key === true,            // NEVER the key itself
      // provenance of the *dial*, not the tensor: a fold is a projection of
      // the same field, so the source tensor's address travels with the fold.
      foldedFrom: meta.foldedFrom || null,       // {width,height,sha}
      created: meta.created || null,
      ...meta,
    },
  };
  return g;
}

export const at = (g, x, y) => g.cells[y * g.width + x];
export const isVoid = (c) => c.origin === 'void';

// ---------------------------------------------------------------- fold (dial 4)
// "changing the grid size is a coarsening of the same field, not a new image."
// So: a coarse cell carries the block it covers. Variance across the block is
// NOT discarded -- it moves from inside-cell entropy to between-cell grain,
// which is why a 3x3 fold can look rougher than a 1x1 fold of the same data.
export function fold(g, w, h) {
  if (!((w <= g.width && h <= g.height) && w >= 1 && h >= 1)) throw new CellError(`fold ${w}x${h} does not divide ${g.width}x${g.height}`);
  if (g.width % w || g.height % h) throw new CellError(`fold ${w}x${h} does not divide ${g.width}x${g.height}`);
  const sx = g.width / w, sy = g.height / h;
  const cells = [];
  for (let cy = 0; cy < h; cy++) for (let cx = 0; cx < w; cx++) {
    const block = [];
    for (let y = cy * sy; y < (cy + 1) * sy; y++) for (let x = cx * sx; x < (cx + 1) * sx; x++) block.push(at(g, x, y));
    const judged = block.filter((c) => c.origin !== 'void');
    if (!judged.length) { cells.push({ x: cx, y: cy, origin: 'void', history: [] }); continue; }
    // mean distribution over the block (a display projection -- see q16.py)
    const labels = [...new Set(judged.flatMap((c) => c.labelSet))].sort();
    const mean = {};
    for (const l of labels) mean[l] = judged.reduce((a, c) => a + (c.probabilities[l] || 0), 0) / judged.length;
    const norm = judged.reduce((a, c) => a + c.entropyNorm, 0) / judged.length;
    const mvar = judged.reduce((a, c) => a + Math.pow(c.entropyNorm - norm, 2), 0) / judged.length;
    const conf = judged.reduce((a, c) => a + c.confidence, 0) / judged.length;
    const spread = Math.sqrt(mvar);                 // between-cell disagreement
    const history = judged.flatMap((c) => c.history);
    cells.push(cell({
      x: cx, y: cy, confidence: conf, probabilities: mean, history,
      meta_block: { n: block.length, judged: judged.length, entropyNorm: norm, spread },
    }));
    // A mean of four contested cells is a bland cell. The disagreement has to
    // survive the fold SOMEWHERE or invariant 4 is a lie told to make the dial
    // look cheap: it survives as a COUNT of the contested cells inside, and as
    // the between-cell spread, which the renderer turns into grain amplitude.
    const contestedInside = judged.filter((c) => c.entropyNorm > 0.55 && c.margin > 0.20).length;
    const voidInside = block.length - judged.length;
    cells[cells.length - 1].block = {
      n: block.length, judged: judged.length, spread, entropyNorm: norm,
      contestedInside, voidInside,
      sourceCoords: block.map((c) => [c.x, c.y]),
    };
  }
  const f = grid({ width: w, height: h, cells, meta: { ...g.meta, source: g.meta.source, foldedFrom: { width: g.width, height: g.height, sha: tensorSha(g) } } });
  return f;
}

// ---------------------------------------------------------------- disagreement
// Jensen-Shannon divergence, base 2. Bounded, symmetric, 0 when the two
// judgments say the same thing. This is the quantity the stitch renders.
export function jsd(p, q) {
  const ks = [...new Set([...Object.keys(p), ...Object.keys(q)])];
  const sum = (o) => ks.reduce((a, k) => a + (o[k] || 0), 0) || 1;
  const sp = sum(p), sq = sum(q);
  const m = {};
  let d = 0;
  for (const k of ks) {
    const a = (p[k] || 0) / sp, b = (q[k] || 0) / sq;
    m[k] = 0.5 * (a + b);
    const kl = (x, y) => (x <= 0 || y <= 0 ? 0 : x * Math.log2(x / y));
    d += 0.5 * kl(a, m[k]) + 0.5 * kl(b, m[k]);
  }
  return d;
}
export const cellDisagreement = (c) => {
  const h = c.history;
  if (h.length < 2) return 0;
  let worst = 0;
  for (let i = 1; i < h.length; i++) worst = Math.max(worst, jsd(h[i - 1].probabilities, h[i].probabilities));
  return worst;
};

// ---------------------------------------------------------------- invariants
// Exported so the browser can run them on every keystroke and the headless
// verifier runs the same functions. One implementation, two callers.
export function checkInvariants(g) {
  const fails = [];
  const t = (ok, msg) => { if (!ok) fails.push(msg); return ok; };

  t(g.cells.length === g.width * g.height, 'I1: cell count != w*h');
  for (const c of g.cells) {
    const id = `cell(${c.x},${c.y})`;
    // I1: no cell ever stores a scalar alone
    if (!isVoid(c)) {
      t(c.probabilities && Object.keys(c.probabilities).length >= 2,
        `I1: ${id} has ${c.probabilities ? Object.keys(c.probabilities).length : 0} labels -- a scalar alone is a bug`);
      for (const f of ['confidence', 'entropy', 'entropyNorm', 'margin', 'pArgmax', 'overclaim', 'choice', 'labelSet']) {
        t(c[f] !== undefined && c[f] !== null, `I1: ${id} is missing ${f}`);
      }
      t(typeof c.confidence === 'number' && Number.isFinite(c.entropy) && Number.isFinite(c.margin),
        `I1: ${id} has a non-numeric derived field`);
      // the four derived numbers must be independently recomputable, i.e. the
      // cell really is holding the map and not four scalars that look like one
      const d = derived(c.probabilities, c.confidence);
      t(Math.abs(d.entropy - c.entropy) < 1e-9 && Math.abs(d.margin - c.margin) < 1e-9
        && Math.abs(d.pArgmax - c.pArgmax) < 1e-9 && argmax(c.probabilities) === c.choice,
        `I1: ${id} derived fields disagree with its own probability map`);
      t(Number.isInteger(c.x) && Number.isInteger(c.y), `I1: ${id} coord is not integer -- identity never floats`);
      t(c.history.length >= 1, `I1: ${id} carries no judgment at all`);
    }
  }
  // I2: the tensor round-trips, byte for byte
  const once = serialize(g);
  const twice = serialize(JSON.parse(once));
  t(once === twice, 'I2: grid -> file -> grid is not identity');
  // I3: every projection is declared and each declares the tensor it reads
  t(!!g.meta.foldedFrom || !g.meta.foldedFrom, 'I3: meta malformed');
  return fails;
}
