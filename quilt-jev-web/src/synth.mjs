// quilt-jev-web :: synth.mjs
// THE NO-KEY PATH. This module is the reason a blank canvas can never be
// mistaken for a canvas of zeros: when there is no key we do NOT fill cells
// with 0, we load a *named, finite, hand-built* tensor and label it
// `source: 'synthetic'` in the header, in the file, and in the PNG's caption.
// And a handful of cells are VOID -- genuinely never judged -- so the void
// surface is on screen from the first paint and the distinction is structural
// rather than a banner you can scroll past.

import { cell, grid } from './tensor.mjs';

const VERDICTS = ['holds', 'refuted', 'underdetermined', 'partial', 'not-tested'];

// deterministic LCG -- the no-key tensor is a *fixture*, so it is byte-stable
// across sessions and machines. No Math.random anywhere in the data path.
function lcg(seed) { let s = seed >>> 0; return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296); }
const norm = (a) => { const s = a.reduce((x, y) => x + y, 0) || 1; return a.map((v) => v / s); };
const zip = (probs, labels) => Object.fromEntries(labels.map((l, i) => [l, Math.round(probs[i] * 1e6) / 1e6]));
const renorm = (m) => { const s = Object.values(m).reduce((a, b) => a + b, 0); return Object.fromEntries(Object.entries(m).map(([k, v]) => [k, Math.round((v / s) * 1e6) / 1e6])); };

export function synthGrid({ width = 12, height = 8, seed = 0x5eed1e7 } = {}) {
  const rnd = lcg(seed);
  const cells = [];
  // Cells that carry the four states the surface must be able to show. Named so
  // a reader can point at the grid and say "that one, there".
  const PLANTED = {
    '(3,2)': { kind: 'contested', note: 'high entropy, high margin: decided AND contested' },
    '(7,4)': { kind: 'contested', note: 'same failure, different labels' },
    '(2,6)': { kind: 'overclaim', note: 'confidence exceeds p(argmax)' },
    '(9,1)': { kind: 'overclaim', note: 'overclaim on a 3-label cell' },
    '(1,3)': { kind: 'overclaim', note: 'the judge is certain and its own map says otherwise' },
    '(5,3)': { kind: 'void',    note: 'never judged' },
    '(10,5)': { kind: 'void',   note: 'never judged' },
    '(0,7)': { kind: 'void',    note: 'never judged' },
    '(6,1)': { kind: 'quilt',   note: 'judged 3x, all three disagree' },
    '(4,5)': { kind: 'quilt',   note: 'judged 2x, agree then reverse' },
    '(11,2)': { kind: 'quilt',   note: 'judged 3x, two agree one dissents' },
  };
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const p = PLANTED[`(${x},${y})`];
    if (p && p.kind === 'void') { cells.push({ x, y, origin: 'void', history: [] }); continue; }

    let probs, confidence;
    if (p && p.kind === 'contested') {
      // decided-but-contested: two labels far apart, the tail flat. This is the
      // cell the source's relief-by-entropy renders as MAXIMUM RELIEF.
      probs = norm([0.52, 0.30, 0.08, 0.06, 0.04]);
      confidence = 0.81;
    } else if (p && p.kind === 'overclaim') {
      probs = norm([0.44, 0.26, 0.14, 0.10, 0.06]);
      confidence = 0.93;                      // claims more than p(argmax)=0.44
    } else if (p && p.kind === 'quilt') {
      const n = (x + y) % 2 ? 3 : 2;
      const history = [];
      for (let i = 0; i < n; i++) {
        const base = rnd();
        const hp = norm([
          0.30 + base * 0.45, 0.25 + rnd() * 0.35, rnd() * 0.2, rnd() * 0.15, rnd() * 0.1,
        ]);
        history.push({
          judge: ['kestrel', 'marginalia', 'quill'][i % 3],
          at: `2026-10-0${1 + i}T0${i}:00:00Z`,
          confidence: Math.round(Math.max(0.05, Math.max(...hp) * (0.6 + rnd() * 0.35)) * 1000) / 1000,
          probabilities: zip(hp, VERDICTS),
        });
      }
      // current head = most recent judgment; keep all of them, none averaged
      const head = history[history.length - 1];
      cells.push(cell({ x, y, confidence: head.confidence, probabilities: renorm(head.probabilities), history }));
      continue;
    } else {
      // ordinary background field: a mix of settled and open
      // three regimes, so the quilt has settled ground AND fog AND the seam
      // between them. rnd() decides which: <.34 peaked, <.72 middling, else flat.
      const r = rnd();
      const sharp = r < 0.34 ? 0.94 : r < 0.72 ? 0.45 : 0.05;
      const raw = [
        0.06 + sharp * 0.86, 0.06 + rnd() * (1 - sharp) * 0.7, rnd() * (1 - sharp) * 0.5,
        rnd() * (1 - sharp) * 0.4, rnd() * (1 - sharp) * 0.3,
      ];
      // rotate which label wins by POSITION. without this the whole field's
      // argmax is 'holds' and the quilt is one flat hue -- a wall, not a quilt.
      const rot = (x * 2 + y * 3) % VERDICTS.length;
      probs = norm(raw.map((_, i) => raw[(i + rot) % raw.length]));
      // calibrate to the source: JEV's stated confidence tracks the top
      // probability from BELOW (contract's live case: conf .61 vs p .74), and
      // the further down the distribution sits the wider the gap. a uniform
      // conf would manufacture 60+ phantom overclaims out of ordinary cells.
      const top = Math.max(...probs);
      confidence = Math.round(Math.max(0.05, top * (0.62 + rnd() * 0.30)) * 1000) / 1000;
    }
    cells.push(cell({ x, y, confidence, probabilities: zip(probs, VERDICTS) }));
  }
  return grid({
    width, height, cells,
    meta: {
      source: 'synthetic',
      model: null,
      api_key: false,
      created: '2026-10-02T08:00:00Z',
      note: 'FIXTURE. no API key was present. these are not measurements and not zeros.',
      planted: Object.fromEntries(Object.entries(PLANTED).map(([k, v]) => [k, v.note])),
    },
  });
}
export { VERDICTS };
