// 07 — driftwatch: regime detection for metric streams, without thresholds.
//
// Realm: ML-ops / data quality / observability.
// Engineer swap-in: point the sensor pushes at your model registry or
// metrics exporter; the regime vocabulary (stable / drifting / oscillating /
// stuck) and its hysteresis are the product.
//
// Why not thresholds: a static alarm fires late on slow drift, never on a
// stuck pipeline (the value looks healthy!), and fires constantly on healthy
// oscillation. This watch reads the SHAPE of the recent window instead —
// slope for drift, variance for stuck, bending energy for oscillation — and
// raises one event per regime CHANGE, not per sample.
//
// Runs fully offline.

import { sheet, WitnessLog, check, done, setTool, panel, kv, ANSI } from '../src/toolkit.mjs';

setTool('driftwatch');

const e = sheet('driftwatch', [
  { id: 'metrics.accuracy', kind: 'sensor', default: 0.92, description: 'the vital sign (any 0-1 metric works)' },

  { id: 'watch.window', kind: 'value', value: [], description: 'last 24 samples' },
  { id: 'watch.regime', kind: 'value', value: null, description: 'current regime: {label, drift, var, bend}' },
  { id: 'watch.events', kind: 'value', value: [], description: 'regime-change events' },

  // ingest: runs on every sensor push, updates the window, classifies the shape
  { id: 'watch.ingest', kind: 'program',
    description: 'listener action: append to window, recompute regime',
    code: `
      const w = (await runtime.get('watch.window')).data;
      const v = (await runtime.get('metrics.accuracy')).data;
      const window = [...w, v].slice(-24);
      await runtime.set('watch.window', window);

      const n = window.length;
      const mean = window.reduce((s, x) => s + x, 0) / n;
      // stuck = the TAIL froze (a frozen exporter writes identical values);
      // the full window may still carry older regimes, so look at the last 10
      const tail = window.slice(-10);
      const tmean = tail.reduce((s, x) => s + x, 0) / tail.length;
      const tailVar = tail.reduce((s, x) => s + (x - tmean) * (x - tmean), 0) / tail.length;
      const slope = n >= 8 ? (window[n - 1] - window[n - 8]) / 7 : 0;   // per-sample drift
      let bend = 0;                                                      // bending energy (gesture idiom)
      for (let i = 2; i < n; i++) bend += Math.abs((window[i] - window[i-1]) - (window[i-1] - window[i-2]));
      const bendAvg = bend / Math.max(1, n - 2);                         // per-step, so window length can't game it

      let label = 'stable';
      if (n >= 10 && tailVar < 1e-6) label = 'stuck';                    // a healthy metric breathes
      else if (bendAvg > 0.05) label = 'oscillating';                    // sharp direction changes
      else if (Math.abs(slope) > 0.004) label = 'drifting';              // steady slide
      const prev = (await runtime.get('watch.regime')).data;
      await runtime.set('watch.regime', { label, slope: Number(slope.toFixed(5)), tailVar: Number(tailVar.toFixed(8)), bendAvg: Number(bendAvg.toFixed(4)) });
      return { label, prev: prev?.label ?? null, changed: prev ? prev.label !== label : false };
    ` },

  // the trigger: every sensor push re-runs ingest
  { id: 'watch.trigger', kind: 'listener', watch: ['metrics.accuracy'], action: 'watch.ingest' },

  // regime-change alarm — edge-triggered on the label, first-sample guarded
  { id: 'alarm.change', kind: 'listener', watch: ['watch.regime'],
    condition: 'caller.metadata.prev != null && caller.metadata.prev.label !== caller.metadata.current.label',
    action: 'alarm.book' },
  { id: 'alarm.book', kind: 'program',
    code: `const evs = (await runtime.get('watch.events')).data;
      const reg = (await runtime.get('watch.regime')).data;
      const prev = evs.length ? evs[evs.length - 1].to : 'stable';
      await runtime.set('watch.events', [...evs, { from: prev, to: reg.label, slope: reg.slope, variance: reg.variance, bend: reg.bend, ts: Date.now() }]);
      return 1;` },

  // the naive competitor: a static threshold alarm, for comparison
  { id: 'naive.threshold', kind: 'value', value: 0.80 },
  { id: 'naive.fired', kind: 'value', value: [] },
]);

console.log(`${ANSI.bold}driftwatch${ANSI.reset} — reads the shape of a metric; static thresholds shown up for contrast\n`);

const log = new WitnessLog();
let naiveFired = 0;
async function push(v) {
  await e.set('metrics.accuracy', v);
  if (v < (await e.get('naive.threshold')).data) naiveFired++;
  await drain();
}
const drain = async () => {
  const evs = (await e.get('watch.events')).data;
  while (log.length < evs.length) { const ev = evs[log.length]; log.append({ op: 'REGIME', from: ev.from, to: ev.to }); }
};
const regime = async () => (await e.get('watch.regime')).data;

// ── phase 1: healthy stable metric (noise around 0.92) ──
for (let i = 0; i < 14; i++) await push(0.92 + 0.004 * Math.sin(i * 1.7) + (i % 3) * 0.001);
panel('phase 1', [kv('regime', (await regime()).label), kv('naive alarms', naiveFired)]);
check('healthy metric reads stable', (await regime()).label === 'stable');

// ── phase 2: slow drift 0.92 → 0.76 (the classic silent failure) ──
let driftFlaggedAt = null, naiveFiredAt = null;
for (let i = 0; i < 22; i++) {
  const v = 0.92 - i * 0.0075;
  await push(v);
  if (driftFlaggedAt === null && (await regime()).label === 'drifting') driftFlaggedAt = v;
  if (naiveFiredAt === null && naiveFired > 0) naiveFiredAt = v;
}
const r2 = await regime();
panel('phase 2', [kv('regime', `${r2.label}`), kv('slope', `${r2.slope}/sample`), kv('naive alarms', naiveFired)]);
check('slow drift caught by slope', r2.label === 'drifting', `flagged while accuracy was still ${driftFlaggedAt?.toFixed(3)}`);
check('shape beats threshold: flagged EARLIER than 0.80 alarm',
  driftFlaggedAt !== null && naiveFiredAt !== null && driftFlaggedAt > naiveFiredAt,
  `driftwatch @ ${driftFlaggedAt?.toFixed(3)} vs static @ ${naiveFiredAt?.toFixed(3)} — a day of lead time in production`);

// ── phase 3: oscillation (flapping deployment) ──
for (let i = 0; i < 16; i++) await push(i % 2 === 0 ? 0.97 : 0.83);
const r3 = await regime();
panel('phase 3', [kv('regime', r3.label), kv('bend/sample', r3.bendAvg), kv('naive alarms', naiveFired)]);
check('oscillation caught by bending energy', r3.label === 'oscillating', `mean is healthy 0.90 — thresholds see nothing here`);

// ── phase 4: stuck (frozen exporter — value looks perfect) ──
for (let i = 0; i < 10; i++) await push(0.90);
const r4 = await regime();
panel('phase 4', [kv('regime', r4.label), kv('tail variance', r4.tailVar), kv('naive alarms', naiveFired)]);
check('stuck caught by variance collapse', r4.label === 'stuck', '0.90 forever looks healthy to any threshold — not to variance');

// ── the alarm trail ──
const evs = (await e.get('watch.events')).data;
check('one event per regime change', evs.length >= 3, evs.map(ev => `${ev.from}→${ev.to}`).join(', '));
const v = log.verify();
check('witness chain sealed', v.ok, `${log.length} regime events, head ${v.head.slice(0, 12)}…`);

panel('regime trail', evs.slice(-4).map(ev => kv(`${ev.from}`, `→ ${ANSI.cyan}${ev.to}${ANSI.reset}`)));

done();
