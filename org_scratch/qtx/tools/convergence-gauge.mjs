// 11 — convergence-gauge: training-curve convergence certification.
//
// Realm: RL / NN training ops (quilt-rl / quilt-nn lanes).
// Engineer swap-in: point `push()` at your trainer's per-epoch metric callback;
// the sheet cells read like a training dashboard. The gauge never watches a
// threshold — it certifies the SHAPE of the curve.
//
// The design is deliberately single-question: "may I stop training?"
//   flat-tail latch — the last `window` samples stay inside `tolerance` of
//     each other (range, not std — a frozen plateau and a bounded-noise
//     plateau certify the same way);
//   change-point scan — two-sided CUSUM on the deltas (up-side on raw deltas,
//     down-side on SIGN-FLIPPED deltas — one pass, both regimes; Page 1954,
//     zero deps) so a CONVERGED verdict always says whether the path there
//     held a regime shift;
//   drift — per-sample slope over the last window, informational but checked;
//   hysteresis — borrowed from fleet-pager's paging bands (page at ≥70,
//     resolve only below 50): once the gauge LATCHES CONVERGED, a sample
//     straying past `tolerance` is booked as an excursion but does NOT flip
//     the verdict; only a stray beyond `tolerance × hysteresis` unlatches it.
//     Without that band, one noisy epoch after a certified plateau would
//     un-certify the whole run — page-flapping, but for the stop button.
//
// Lineage: delta-shape's shape predicates (slope/flatness read the curve, not
// thresholds) + fleet-pager's hysteresis band, adapted to this harness.
//
// Unlike its siblings this module also EXPORTS its core (`converge`,
// `makeGauge`) so RL/NN lanes can import it; the self-play below is guarded
// so importing is side-effect-free and `node tools/convergence-gauge.mjs`
// behaves exactly like every other tool here.
//
// Runs fully offline.

import { WitnessLog, check, done, setTool, panel, kv, ANSI, sheet } from '../src/toolkit.mjs';
import { pathToFileURL } from 'node:url';

setTool('convergence-gauge');

// ── the pure core: zero-dep series certification ────────────────────────────

export const DEFAULTS = Object.freeze({ window: 8, tolerance: 1e-3, minLen: 24, hysteresis: 2 });

const mean = a => a.reduce((s, x) => s + x, 0) / a.length;

function assertParams(p = {}) {
  const m = { ...DEFAULTS, ...p };
  for (const [k, v] of Object.entries(m)) {
    if (!Number.isFinite(v)) {
      throw new TypeError(`convergence-gauge: param ${k} must be a finite number, got ${String(v)}`);
    }
  }
  if (!Number.isInteger(m.window) || m.window < 2) {
    throw new TypeError(`convergence-gauge: window must be an integer >= 2, got ${String(m.window)}`);
  }
  if (m.tolerance <= 0) throw new TypeError(`convergence-gauge: tolerance must be > 0, got ${String(m.tolerance)}`);
  if (m.minLen < m.window) {
    throw new TypeError(`convergence-gauge: minLen (${m.minLen}) must be >= window (${m.window}) — cannot certify a tail shorter than the window`);
  }
  if (m.hysteresis < 1) {
    throw new TypeError(`convergence-gauge: hysteresis must be >= 1, got ${String(m.hysteresis)} — below 1 the gauge could unlatch on the very noise it certified`);
  }
  return m;
}

function assertSeries(series) {
  if (!Array.isArray(series)) {
    throw new TypeError(`convergence-gauge: series must be an array of numbers, got ${typeof series}`);
  }
  for (let i = 0; i < series.length; i++) {
    const v = series[i];
    if (typeof v !== 'number' || !Number.isFinite(v)) {
      throw new TypeError(`convergence-gauge: series[${i}] is not a finite number (${String(v)}) — refusing to certify a tampered curve`);
    }
  }
}

// flat tail: the maximal suffix whose values stay pairwise inside tolerance
// (measured as range = max − min, so "flat" means every pair, not every step).
function flatTail(series, tol) {
  const n = series.length;
  if (n === 0) return 0;
  let lo = series[n - 1], hi = series[n - 1], tail = 1;
  for (let i = n - 2; i >= 0; i--) {
    const lo2 = Math.min(lo, series[i]), hi2 = Math.max(hi, series[i]);
    if (hi2 - lo2 > tol) break;
    lo = lo2; hi = hi2; tail++;
  }
  return tail;
}

// change-point scan: two-sided CUSUM on the deltas. The up-side accumulator
// rides the raw deltas (d − k); the down-side rides the SIGN-FLIPPED deltas
// (−d − k) — one pass certifies both rise- and fall-regime shifts. Slack k
// and threshold h derive from `tolerance` so the scan and the latch speak the
// same units: bounded noise (range <= tolerance) can never accumulate, a real
// regime shift trips within a step or two. Zero deps, deterministic.
function changePoints(series, p) {
  const k = p.tolerance, h = 4 * p.tolerance;
  const cps = [];
  let up = 0, down = 0;
  for (let i = 1; i < series.length; i++) {
    const d = series[i] - series[i - 1];
    up = Math.max(0, up + d - k);
    down = Math.max(0, down - d - k);   // ← CUSUM of the sign-flipped deltas
    if (up > h || down > h) { cps.push(i); up = 0; down = 0; }
  }
  return cps;
}

// stateful gauge: push() one sample at a time (a trainer callback), snapshot()
// any time. The latch/hysteresis state machine lives here and in the sheet
// program below — the double-entry cross-check keeps both honest.
export function makeGauge(params = {}) {
  const p = assertParams(params);
  const hist = [];
  let latched = false, anchor = null, latchedAt = null, excursions = 0, flips = 0;

  const g = {
    params: p,
    get series() { return hist.slice(); },
    push(x) {
      if (typeof x !== 'number' || !Number.isFinite(x)) {
        throw new TypeError(`convergence-gauge: push(${String(x)}) refused — not a finite number`);
      }
      hist.push(x);
      const n = hist.length;
      const tail = flatTail(hist, p.tolerance);
      if (!latched && n >= p.minLen && tail >= p.window) {
        anchor = mean(hist.slice(-p.window));       // the certified level
        latched = true; latchedAt = n - 1;
      } else if (latched) {
        const exc = Math.abs(x - anchor);
        if (exc > p.tolerance * p.hysteresis) { latched = false; flips++; }  // left the band
        else if (exc > p.tolerance) excursions++;                            // booked, not fatal
      }
      return g.snapshot();
    },
    snapshot() {
      const n = hist.length;
      const verdict = n === 0 || n < p.minLen ? 'INSUFFICIENT'
        : latched ? 'CONVERGED' : 'NOT_CONVERGED';
      const back = Math.min(p.window, n - 1);
      return {
        verdict,
        flat_tail_len: n ? flatTail(hist, p.tolerance) : 0,
        change_points: changePoints(hist, p),
        mean_last_window: n ? mean(hist.slice(-p.window)) : null,
        drift: n >= 2 ? (hist[n - 1] - hist[n - 1 - back]) / back : null,
        n, latched_at: latchedAt, excursions, flips,
        anchor,   // the certified level (mean of the window that latched)
      };
    },
  };
  return g;
}

// one-shot: fold the whole series through a fresh gauge. The verdict is the
// hysteresis state AFTER the last sample — a curve that converged and then
// hard-excursed reports NOT_CONVERGED, not its prettier past.
export function converge(series, params = {}) {
  assertSeries(series);
  const p = assertParams(params);
  const g = makeGauge(p);
  let snap = null;
  for (const x of series) snap = g.push(x);
  if (!snap) {
    return { verdict: 'INSUFFICIENT', flat_tail_len: 0, change_points: [],
             mean_last_window: null, drift: null, n: 0, latched_at: null,
             excursions: 0, flips: 0 };
  }
  return snap;
}

// ── self-play: the tool grades its own homework ──────────────────────────────

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) await selfPlay();

async function selfPlay() {
  console.log(`${ANSI.bold}convergence-gauge${ANSI.reset} — certifies training-curve convergence: flat-tail latch + CUSUM scan + hysteresis\n`);

  // ── phase 1: the pure core on honest curves ──
  const flat = Array.from({ length: 30 }, (_, i) => 0.12 + 0.0002 * Math.sin(i * 0.9));
  const r1 = converge(flat);
  panel('curve A — flat plateau', [
    kv('verdict', r1.verdict), kv('flat tail', `${r1.flat_tail_len} samples`),
    kv('change points', String(r1.change_points.length)),
    kv('drift', `${r1.drift.toExponential(2)}/sample`),
  ]);
  check('flat series certifies', r1.verdict === 'CONVERGED' && r1.flat_tail_len >= 8,
    `flat_tail_len=${r1.flat_tail_len} >= window 8`);

  const trend = Array.from({ length: 40 }, (_, i) => 1.0 - 0.0125 * i);
  const r2 = converge(trend);
  panel('curve B — still descending', [
    kv('verdict', r2.verdict), kv('drift', `${r2.drift.toFixed(5)}/sample`),
    kv('cusum', `${r2.change_points.length} change points — the ramp trips it too`),
  ]);
  check('trending series refuses', r2.verdict === 'NOT_CONVERGED' && Math.abs(r2.drift) > 0.01,
    `drift ${r2.drift.toFixed(5)}/sample — the stop button stays locked`);

  const bounded = Array.from({ length: 40 }, (_, i) => 0.5 + 0.0004 * Math.sin(i * 0.7));
  const r3 = converge(bounded);
  check('noisy-but-bounded series certifies', r3.verdict === 'CONVERGED',
    `amp 4e-4 <= tolerance 1e-3, flat_tail_len=${r3.flat_tail_len}`);

  const short = converge(flat.slice(0, 23));
  const empty = converge([]);
  check('short curve is INSUFFICIENT', short.verdict === 'INSUFFICIENT',
    '23 samples < minLen 24 — even a perfect tail cannot certify what is too short');
  check('empty curve is INSUFFICIENT', empty.verdict === 'INSUFFICIENT' && empty.flat_tail_len === 0);

  // regime shift: 15 samples at ~0.50, then a restart-level jump to ~0.90
  const restart = [
    ...Array.from({ length: 15 }, (_, i) => (i % 2 ? 0.5002 : 0.5)),
    ...Array.from({ length: 15 }, (_, i) => (i % 2 ? 0.9002 : 0.9)),
  ];
  const r4 = converge(restart);
  panel('curve C — converged, but the path had a jump', [
    kv('verdict', r4.verdict), kv('change points', `[${r4.change_points.join(', ')}]`),
    kv('latched at', `sample ${r4.latched_at}`),
  ]);
  check('change-point scan flags a genuine regime shift',
    r4.change_points.length === 1 && r4.change_points[0] >= 14 && r4.change_points[0] <= 16,
    'two-sided CUSUM on the deltas — down-side rides sign-flipped deltas');
  check('flat series books zero change points', r1.change_points.length === 0,
    'bounded noise never accumulates: slack k = tolerance');

  // ── phase 2: hysteresis (fleet-pager's band discipline, on the stop button) ──
  const g = makeGauge({ window: 4, tolerance: 1, minLen: 8, hysteresis: 2 });
  for (let i = 0; i < 10; i++) g.push(10 + 0.3 * Math.sin(i));
  const anchor = g.snapshot().anchor;
  const midExcursion = g.push(anchor + 1.6);   // > tolerance, inside tolerance×hysteresis
  panel('hysteresis probe', [
    kv('anchor', anchor.toFixed(3)), kv('excursion', '+1.6 (unlatch band is ±2.0)'),
    kv('verdict', midExcursion.verdict), kv('flat tail', `${midExcursion.flat_tail_len}`),
  ]);
  check('hysteresis holds under a small re-excursion',
    midExcursion.verdict === 'CONVERGED' && midExcursion.flat_tail_len < 4 && midExcursion.excursions === 1,
    `flat_tail_len=${midExcursion.flat_tail_len} < window — latched anyway, excursion booked`);
  const backInside = g.push(anchor + 0.1);
  check('returning inside the band keeps the certification', backInside.verdict === 'CONVERGED');

  const flipped = g.push(anchor + 5);          // beyond tolerance×hysteresis
  check('hard excursion beyond the band flips the verdict',
    flipped.verdict === 'NOT_CONVERGED' && flipped.flips === 1,
    'the band is not a blind latch — a real departure un-certifies');
  let re = null;
  for (let i = 0; i < 8; i++) re = g.push(anchor + 5 + 0.3 * Math.sin(i));
  check('gauge re-certifies at the new level', re.verdict === 'CONVERGED' && re.latched_at >= flipped.n,
    `re-latched at sample ${re.latched_at}`);

  // ── phase 3: tamper discipline — loud refusals are receipts too ──
  let err = null; try { converge([0.12, NaN, 0.13]); } catch (ex) { err = ex; }
  check('NaN tamper fails loudly', !!err, err?.message);
  err = null; try { converge([0.12, '0.13', 0.14]); } catch (ex) { err = ex; }
  check('non-numeric element fails loudly', !!err, err?.message);
  err = null; try { converge(flat, { minLen: 4 }); } catch (ex) { err = ex; }
  check('bad config (minLen < window) fails loudly', !!err, err?.message);

  // ── phase 4: the sheet runs the same policy — push a real-ish curve ──
  const e = sheet('convergence-gauge', [
    { id: 'curve.loss', kind: 'sensor', default: 1.0, description: 'the training curve (per-step loss or any metric) — push per epoch' },
    { id: 'gauge.params', kind: 'value', value: { ...DEFAULTS },
      description: 'certification bands: latch inside tolerance, unlatch beyond tolerance×hysteresis' },
    { id: 'gauge.window', kind: 'value', value: [], description: 'the curve so far' },
    { id: 'gauge.state', kind: 'value',
      value: { verdict: 'INSUFFICIENT', latched: false, flatTail: 0, excursions: 0, flips: 0, n: 0, anchor: null },
      description: 'gauge state (fleet-pager hysteresis idiom)' },
    { id: 'gauge.events', kind: 'value', value: [], description: 'verdict transitions (tool drains → witness ledger)' },
    { id: 'gauge.ingest', kind: 'program',
      description: 'the policy: flat-tail latch + hysteresis band (mirrors the exported makeGauge)',
      code: `const p = (await runtime.get('gauge.params')).data;
        const hist = [...(await runtime.get('gauge.window')).data, (await runtime.get('curve.loss')).data];
        await runtime.set('gauge.window', hist);
        const n = hist.length;
        // flat tail: maximal suffix whose range stays inside tolerance
        let tail = 1, lo = hist[n-1], hi = hist[n-1];
        for (let i = n - 2; i >= 0; i--) {
          const lo2 = Math.min(lo, hist[i]), hi2 = Math.max(hi, hist[i]);
          if (hi2 - lo2 > p.tolerance) break;
          lo = lo2; hi = hi2; tail++;
        }
        const st = (await runtime.get('gauge.state')).data;
        const next = { ...st, n, flatTail: tail };
        if (!next.latched && n >= p.minLen && tail >= p.window) {
          const win = hist.slice(-p.window);
          next.anchor = win.reduce((s, x) => s + x, 0) / p.window;
          next.latched = true; next.latchedAt = n - 1;
        } else if (next.latched) {
          const exc = Math.abs(hist[n-1] - next.anchor);
          if (exc > p.tolerance * p.hysteresis) { next.latched = false; next.flips = (next.flips ?? 0) + 1; }
          else if (exc > p.tolerance) next.excursions = (next.excursions ?? 0) + 1;
        }
        next.verdict = n < p.minLen ? 'INSUFFICIENT' : next.latched ? 'CONVERGED' : 'NOT_CONVERGED';
        await runtime.set('gauge.state', next);
        // book only transitions that matter — hysteresis-accepted noise books state, not events
        if (st.verdict !== next.verdict && (next.verdict === 'CONVERGED' || st.verdict === 'CONVERGED')) {
          const evs = (await runtime.get('gauge.events')).data;
          const relatch = evs.some(ev => ev.op === 'LATCH' || ev.op === 'RE-LATCH');
          await runtime.set('gauge.events', [...evs, {
            op: next.verdict === 'CONVERGED' ? (relatch ? 'RE-LATCH' : 'LATCH') : 'FLIP',
            from: st.verdict, to: next.verdict, at: n,
            anchor: next.anchor == null ? null : Number(next.anchor.toFixed(6)), ts: Date.now(),
          }]);
        }
        return next;` },
    { id: 'gauge.trigger', kind: 'listener', watch: ['curve.loss'], action: 'gauge.ingest' },
  ]);

  const log = new WitnessLog();
  const drain = async () => {
    const evs = (await e.get('gauge.events')).data;
    while (log.length < evs.length) {
      const ev = evs[log.length];
      log.append({ op: 'gauge', event: ev.op, from: ev.from, to: ev.to, at: ev.at });
    }
  };
  const state = async () => (await e.get('gauge.state')).data;

  // decay phase (still descending), then a bounded-noise plateau at 0.12
  const curve = [
    ...Array.from({ length: 24 }, (_, i) => 0.98 - 0.035 * i + 0.004 * Math.sin(i * 1.1)),
    ...Array.from({ length: 16 }, (_, i) => 0.12 + 0.0004 * Math.sin(i * 1.3)),
  ];
  for (let i = 0; i < 12; i++) await e.set('curve.loss', curve[i]);
  await drain();
  check('sheet gauge is INSUFFICIENT during warmup', (await state()).verdict === 'INSUFFICIENT',
    `n=${(await state()).n} < minLen 24`);

  for (let i = 12; i < curve.length; i++) await e.set('curve.loss', curve[i]);
  await drain();
  const st = await state();
  panel('sheet after the plateau', [
    kv('verdict', st.verdict), kv('flat tail', `${st.flatTail}`),
    kv('anchor', st.anchor?.toFixed(6)), kv('events', String(log.length)),
  ]);
  check('sheet gauge latches CONVERGED on the curve', st.verdict === 'CONVERGED' && st.latched);

  const rCore = converge(curve);
  check('sheet verdict matches the exported core (double-entry)',
    rCore.verdict === st.verdict,
    `core=${rCore.verdict} sheet=${st.verdict} — two implementations, one answer`);

  await e.set('curve.loss', 0.13);   // 10× tolerance — outside the hysteresis band
  await drain();
  const st2 = await state();
  const ops = (await e.get('gauge.events')).data.map(ev => ev.op);
  check('hard excursion flips the sheet too — booked as a FLIP receipt',
    st2.verdict === 'NOT_CONVERGED' && ops.includes('FLIP'),
    `${ops.join(' → ') || 'no events'}`);

  panel('witness ledger', [
    kv('entries', log.length), kv('head', log.head),
    kv('verify', JSON.stringify(log.verify())),
  ]);
  check('witness chain sealed', log.verify().ok, `${log.length} verdict receipts, head ${log.head.slice(0, 12)}…`);

  done();
}
