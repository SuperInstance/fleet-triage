// quilt-jev-web :: render.mjs   --- ALL OF THIS IS MINE.
// The source (`achimala/jev-paint`) could not be read: it is not present in this
// sandbox. So there is nothing to fork. What I *did* vendor is the source's
// doctrine (cell.py / q16.py / typesafe_client.py) into tensor.mjs + jev.mjs.
// The rendering below is written from scratch and is deliberately not a
// regression of the one it could not see.
//
// ARCHITECTURE: render() is a PURE function tensor -> display list of polys.
// Two executors consume the identical list: Canvas2D in the browser, a pure-JS
// scanline rasteriser in the verifier. So the PNG in the receipt is painted by
// the same op-list the browser paints -- "it renders" is not a hope.

import { isVoid, cellDisagreement, jsd } from './tensor.mjs';

export const PROJECTIONS = {
  'quilt.stitch': {
    id: 'quilt.stitch',
    title: 'QUILT / STITCH',
    blurb: 'geometry = the whole map. relief = margin. grain = entropy. seams = contest.',
    relief: 'margin', grain: 'entropy', hue: 'argmax', carriesHistory: true,
  },
  'entropy.relief': {
    id: 'entropy.relief',
    title: 'ENTROPY / RELIEF',
    blurb: "the source's idea, kept verbatim as a projection: relief = entropy, hue = argmax.",
    relief: 'entropy', grain: 'none', hue: 'argmax', carriesHistory: false,
  },
  'margin.relief': {
    id: 'margin.relief',
    title: 'MARGIN / RELIEF',
    blurb: 'the other dial: top1 - top2. how decided, independent of how loud.',
    relief: 'margin', grain: 'none', hue: 'argmax', carriesHistory: false,
  },
  'choice.flat': {
    id: 'choice.flat',
    title: 'CHOICE / FLAT  (degraded control)',
    blurb: 'one flat colour per argmax. this is what a scalar-only renderer looks like. shown so you can see what the others buy.',
    relief: 'none', grain: 'none', hue: 'argmax', carriesHistory: false,
  },
};
export const DEFAULT_PROJECTION = 'quilt.stitch';

// label -> hue. Derived from the GRID's vocabulary, not the cell's, so one
// legend governs the whole quilt and a shuffle of cells cannot reshuffle colour.
// Calm, ordered, tonally close. The alarm colour (SEAM / OVERCLAIM) is
// deliberately NOT in this list, so red on the surface can only mean danger.
// A categorical map that spends its most saturated hue on the most common
// label is a map whose danger signal nobody can read.
const HUES = ['#6b8fb5', '#8fb27a', '#c9a86a', '#a98bc4', '#6fb3b0', '#c28a9a', '#9a9faa', '#7d8fa8'];
export function palette(labels) {
  const m = {};
  labels.slice().sort().forEach((l, i) => { m[l] = HUES[i % HUES.length]; });
  return m;
}
// 4 channels ALWAYS. The rasteriser blends c[3]/255, so a 3-tuple silently
// becomes NaN and every such fill lands as opaque black. It is a one-character
// bug and it paints the entire field black, which looks like a data problem.
const rgb = (hex) => [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16), 255];
const mix = (a, b, t) => a.map((v, i) => (i === 3 ? v : Math.round(v + (b[i] - v) * t)));
const rgba = (c, a) => [c[0], c[1], c[2], Math.round(Math.max(0, Math.min(1, a)) * 255)];

const rect = (x, y, w, h) => [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];

// ---------------------------------------------------------------- the dials
// THE-LOOP.md: this is a loop with a dials object, not a pipeline. A dial
// changes what is *projected*; it never changes the tensor's address.
export const DEFAULT_DIALS = {
  projection: DEFAULT_PROJECTION,
  cell: 26,            // px
  gap: 1,              // px between patches
  relief: 0.34,        // max lift, in px
  grain: 0.85,         // stipple density multiplier
  stitch: true,        // draw the history thread
  showVoid: true,      // VOID cells are drawn, hatched, and counted
  scale: 1,            // px per unit of relief
};

// ---------------------------------------------------------------- render
export function render(g, dials = {}) {
  const d = { ...DEFAULT_DIALS, ...dials };
  const P = PROJECTIONS[d.projection];
  if (!P) throw new Error(`unknown projection ${d.projection}`);
  const pal = palette(g.labels);
  const ops = [];
  const stats = {
    projection: P.id, relief: P.relief, grain: P.grain,
    total: g.cells.length,
    void: 0, settled: 0, open: 0, contested: 0, overclaim: 0, history: 0,
    contestedCells: [], overclaimCells: [],
  };
  const W = g.width * (d.cell + d.gap) + d.gap;
  const H = g.height * (d.cell + d.gap) + d.gap;
  ops.push({ op: 'clear', c: [14, 15, 18, 255] });

  for (const c of g.cells) {
    const x = d.gap + c.x * (d.cell + d.gap);
    const y = d.gap + c.y * (d.cell + d.gap);
    const s = d.cell;

    if (isVoid(c)) {
      // ---- VOID. The project's central failure mode gets its own surface.
      // Desaturated, hatched, *no* cast shadow, *no* grain, counted on its own
      // axis. A run of zeros would have a hue, a bar, and relief. This has
      // none of those, so no amount of squinting turns "nothing" into "zero".
      stats.void++;
      if (!d.showVoid) continue;
      ops.push({ op: 'poly', pts: rect(x, y, s, s), c: [34, 35, 40, 255] });
      for (let i = -s; i < s; i += 4) {
        ops.push({ op: 'poly', pts: rect(x + i, y, 1.2, s), c: [58, 60, 68, 255] });
      }
      continue;
    }

    const rank = c.history.length;
    if (rank > 1) stats.history++;
    // ---- the four states, decided ONCE and drawn everywhere consistently
    const state = classify(c);
    stats[state]++;
    if (state === 'contested') stats.contestedCells.push([c.x, c.y]);
    if (state === 'overclaim') stats.overclaimCells.push([c.x, c.y]);

    // ---- geometry: the distribution, all of it, always. Bands are sorted by
    // descending probability (ties by label) inside the painters below, so the
    // order is a function of the distribution and not of dict iteration order.

    if (P.carriesHistory && rank > 1) {
      // THE QUILT. One sub-row per prior judgment, top = most recent. A cell
      // judged three times is a three-layer patch, so "how many times" and
      // "did they agree" are one glance, not a memory task.
      const rh = (s - (rank - 1) * 0.5) / rank;
      c.history.forEach((h, i) => {
        const ry = y + i * (rh + 0.5);
        paintBar(ops, h, pal, x, ry, s, rh, d, P, state, false);
      });
      if (d.stitch) stitch(ops, c, pal, x, y, s, rank);
    } else {
      paintBar(ops, c, pal, x, y, s, s, d, P, state, true);
    }

    // ---- the seam: high entropy AND high margin == confidently contested.
    // The judge is *decided*; the field is *contested*. Nothing in the source's
    // relief-by-entropy can show this -- it reads as "very uncertain", which is
    // the safe-sounding half of a much more dangerous truth.
    if (state === 'contested') {
      ops.push({ op: 'poly', pts: rect(x, y + s / 2 - 1.5, s, 3), c: [232, 62, 44, 245] });
      ops.push({ op: 'poly', pts: [[x, y], [x + s, y + s]], c: [232, 62, 44, 170] });
      ops.push({ op: 'poly', pts: [[x + s, y], [x, y + s]], c: [232, 62, 44, 110] });
    }
    if (c.block && c.block.contestedInside > 0) {
      stats.swallowed = (stats.swallowed || 0) + c.block.contestedInside;
      for (let i = 0; i < Math.min(4, c.block.contestedInside); i++) {
        ops.push({ op: 'poly', pts: rect(x + 2 + i * 5, y + 1, 3, 2), c: [232, 62, 44, 220] });
      }
    }
    if (state === 'overclaim') {
      // confidence > p(argmax): the judge claims more than its own map allows
      for (let i = 0; i < s; i += 3) ops.push({ op: 'poly', pts: rect(x + i, y + s - 4, 1.2, 4), c: [255, 214, 64, 240] });
    }
  }
  return { ops, width: W, height: H, dials: d, projection: P, stats, pal, size: [W, H] };
}

// ---------------------------------------------------------------- cell state
export function classify(c) {
  // Thresholds are on NORMALISED entropy, so a 3-label cell and a 7-label cell
  // are comparable. Overclaim dominates: it is a contradiction in the record.
  if (c.overclaim > 0.02) return 'overclaim';
  if (c.entropyNorm > 0.55 && c.margin > 0.20) return 'contested';
  if (c.entropyNorm > 0.55) return 'open';
  return 'settled';
}

function paintBar(ops, h, pal, x, y, w, hgt, d, P, state, withRelief) {
  const bands = Object.keys(h.probabilities).sort()
    .map((l) => [l, h.probabilities[l]])
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));

  // THE DIAL, made structural. `t` in [0,1] is the dial's reading of this
  // judgment. It sets the bar's THICKNESS: the map is always full width and
  // always complete, so a dial can change how loud a cell is without ever
  // changing what the cell says. A shadow would have done the same job badly
  // and invisibly.
  const dialValue = P.relief === 'entropy' ? (h.entropyNorm || 0)
    : P.relief === 'margin' ? (h.margin || 0)
    : 1;
  const inset = hgt * 0.5 * (1 - Math.max(0.38, dialValue));   // floor keeps the map readable
  const by = y + inset;
  const bh = Math.max(1, hgt - inset * 2);

  if (P.hue === 'argmax' && P.id === 'choice.flat') {
    // the degraded control, drawn honestly: one flat block, no map at all.
    ops.push({ op: 'poly', pts: rect(x, y, w, hgt), c: rgb(pal[h.labelSet ? argmaxLabel(h) : bands[0][0]] || '#8a8f98') });
    return;
  }

  let cx = x;
  bands.forEach(([l, p], i) => {
    const bw = w * p;
    ops.push({ op: 'poly', pts: rect(cx, by, Math.max(0.4, bw), bh), c: rgb(pal[l] || '#8a8f98') });
    if (i > 0) ops.push({ op: 'poly', pts: rect(cx - 0.5, by, 1, bh), c: [12, 13, 16, 255] });   // seam between bands
    cx += bw;
  });
  // the dial gets ONE more channel, a cast shadow whose length is proportional
  // to the same reading, so relief is redundant rather than sole-carrier
  if (withRelief && P.relief !== 'none') {
    const lift = bh * dialValue * 0.55;
    if (lift > 0.4) ops.push({ op: 'poly', pts: rect(x, by + bh, w, lift), c: [0, 0, 0, 110] });
  }

  // grain: texture, never geometry. stipple density = entropy. Contested cells
  // are *textured*; the bar underneath is untouched and still fully readable.
  if (P.grain === 'entropy' && d.grain > 0) {
    // between-cell spread rides the same channel: a fold that averaged away the
    // disagreement gets it back as texture, which is where it belongs
    const amp = Math.max(h.entropyNorm, (h.block && h.block.spread) || 0);
    const n = Math.round(amp * 30 * d.grain);
    for (let i = 0; i < n; i++) {
      const gx = x + ((i * 7919) % 1000) / 1000 * w;
      const gy = y + ((i * 6271) % 1000) / 1000 * hgt;
      ops.push({ op: 'poly', pts: rect(gx, gy, 1, 1), c: [255, 255, 255, 70] });
    }
  }
}
const argmaxLabel = (h) => {
  let best = Object.keys(h.probabilities).sort()[0], bv = -Infinity;
  for (const l of Object.keys(h.probabilities).sort()) if (h.probabilities[l] > bv) { bv = h.probabilities[l]; best = l; }
  return best;
};

function stitch(ops, c, pal, x, y, s, rank) {
  // THE THREAD. One line through the patch whose kinks ARE the disagreement.
  // Every judgment of a cell shares the cell's label vocabulary, so boundary k
  // of row i lines up with boundary k of row i+1 and can be joined directly.
  // Where two judgments agree the thread runs straight; where they do not it
  // jumps sideways, and the colour of the jump is their Jensen-Shannon
  // divergence. You do not read a number; you read a shape.
  const rh = (s - (rank - 1) * 0.5) / rank;
  const rows = [];
  for (let i = 0; i < rank; i++) {
    const h = c.history[i];
    const bands = Object.keys(h.probabilities).sort()
      .map((l) => [l, h.probabilities[l]])
      .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1));
    const by = y + i * (rh + 0.5) + rh;
    const bounds = [];
    let cx = x;
    for (const [, p] of bands) { cx += s * p; bounds.push(cx); }   // cumulative edges
    rows.push(bounds.map((bx) => [bx, by]));
  }
  for (let i = 1; i < rank; i++) {
    const dj = jsd(c.history[i - 1].probabilities, c.history[i].probabilities);
    const col = rgba(mix(rgb('#5fb87a'), rgb('#e0574a'), Math.min(1, dj * 2.2)), 235);
    const up = rows[i - 1], dn = rows[i];
    const n = Math.min(up.length, dn.length);   // min: never invent a boundary
    for (let k = 0; k < n; k++) {
      const [ux, uy] = up[k], [dx2, dy2] = dn[k];
      const t = 1.4;                                   // thread half-thickness
      ops.push({
        op: 'poly',
        pts: [
          [Math.min(ux, dx2) - t, Math.min(uy, dy2)],
          [Math.max(ux, dx2) + t, Math.min(uy, dy2)],
          [Math.max(ux, dx2) + t, Math.max(uy, dy2)],
          [Math.min(ux, dx2) - t, Math.max(uy, dy2)],
        ],
        c: col,
      });
    }
  }
}
