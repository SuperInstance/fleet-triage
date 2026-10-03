// S2 — driftwatch ON live jev: shape-vs-threshold timing, 30 live calls.
//
// Mandate: z-lab Phase 2 S2 (memory 2026-09-25, banked 07:55/08:14) — run
// driftwatch's core question against the REAL System One oracle: does a
// shape-reading (slope/variance/bending-energy) flag a failing metric
// EARLIER than a static threshold alarm — and does a live typed model
// perceive the same regimes the offline heuristic computes?
//
// Method: 10 synthetic 30-sample metric streams (stable / slow drift /
// oscillation / stuck / and the evil mixtures). For EACH stream, 3 live calls:
//   call A — regime classification (choice over driftwatch's vocabulary)
//   call B — timing score (for drift streams: sample index where decline
//            began; score 1..30; for non-drift streams: where variance died)
//   call C — robustness re-ask of A with reordered criteria (does the label
//            survive presentation, i.e. is it reading the SHAPE?)
// = 30 live calls. Ground truth = the same streams replayed through the
// exact driftwatch.mjs ingest math (ported verbatim) + first-crossing index
// of the naive 0.80 threshold.
//
// Wire shape (verified live by S1, 2026-09-25 06:10/09:13):
//   POST https://api.typesafe.ai/v1/systemone
//   { model:'jev-latest', state, questions } → { model, answers, usage }
//
// Honesty rules (S1 idiom): non-200/unparseable booked as REFUSED rows, not
// retried away; agreement table printed, not editorialized; TYPESAFEAI_KEY
// absent → loud refusal (exit 2), never a silent heuristic fallback.
//
// FINDINGS (30/30 live, 6/6 pins, 2026-09-25 10:0x CST):
//   1. Oracle fence: score questions allow AT MOST 10 levels (400 otherwise).
//   2. Regime agreement live-vs-computed: 4/10 — the oracle does NOT see
//      'stuck' (constant streams read as stable or drifting; it has no
//      variance-collapse concept) and reads very-slow drift as drifting even
//      when the 24-window slope math says stable.
//   3. Detector-verdict agreement: 3/10 — on slow drift the oracle credits the
//      0.80 threshold even where shape flagged 8 samples EARLIER (st02:
//      shape@10 vs naive@18). The product thesis (shape beats threshold) is
//      NOT visible to the live model in this framing; it must be DEMONSTRATED
//      (receipts), not asserted in a prompt.
//   4. The timing score channel is DEGENERATE: every stream returned bucket
//      28-30 (mapped 29), including healthy ones. Timing-by-score is not
//      informative at 10 levels; drop or reformulate as choice.
//   5. Presentation robustness: 9/10 — the regime label survives reordered
//      criteria; the model is reading the stream, not the menu order.

import { WitnessLog, check, done, setTool, ANSI, canon, fnv1a64 } from '../src/toolkit.mjs';
import { writeFileSync, mkdirSync } from 'node:fs';

setTool('s2-driftwatch-jev');

const KEY = process.env.TYPESAFEAI_KEY;
if (!KEY) { console.error(`${ANSI.red}TYPESAFEAI_KEY absent — refusing to run a "live" study on heuristics${ANSI.reset}`); process.exit(2); }

const BASE = 'https://api.typesafe.ai/v1/systemone';
const NAIVE_THRESHOLD = 0.80;
const N = 30; // samples per stream
const log = new WitnessLog();

// ── the exact driftwatch.mjs ingest math, ported verbatim ───────────────────
function shape(window) {
  const n = window.length;
  const tail = window.slice(-10);
  const tmean = tail.reduce((s, x) => s + x, 0) / tail.length;
  const tailVar = tail.reduce((s, x) => s + (x - tmean) * (x - tmean), 0) / tail.length;
  const slope = n >= 8 ? (window[n - 1] - window[n - 8]) / 7 : 0;
  let bend = 0;
  for (let i = 2; i < n; i++) bend += Math.abs((window[i] - window[i - 1]) - (window[i - 1] - window[i - 2]));
  const bendAvg = bend / Math.max(1, n - 2);
  let label = 'stable';
  if (n >= 10 && tailVar < 1e-6) label = 'stuck';
  else if (bendAvg > 0.05) label = 'oscillating';
  else if (Math.abs(slope) > 0.004) label = 'drifting';
  return { label, slope, tailVar, bendAvg };
}
// streaming version: what label did the watch hold at each sample?
function replay(stream) {
  let firstShapeFlag = null;   // first sample where regime leaves stable→problem
  let firstNaiveFlag = null;   // first sample below the 0.80 threshold
  const window = [];
  for (let i = 0; i < stream.length; i++) {
    const v = stream[i];
    window.push(v);
    if (firstNaiveFlag === null && v < NAIVE_THRESHOLD) firstNaiveFlag = i + 1;
    const w = window.slice(-24);
    if (w.length >= 10) {
      const r = shape(w);
      if (firstShapeFlag === null && r.label !== 'stable') firstShapeFlag = i + 1;
    }
  }
  const final = shape(window.slice(-24));
  return { final, firstShapeFlag, firstNaiveFlag };
}

// ── 10 scenarios, 30 samples each ────────────────────────────────────────────
const s = (id, gen, truth) => ({ id, stream: Array.from({ length: N }, (_, i) => gen(i)), truth });
const SCEN = [
  s('st01', i => 0.92 + 0.004 * Math.sin(i * 1.7) + (i % 3) * 0.001, 'stable'),
  s('st02', i => 0.92 - i * 0.0075, 'drifting'),                        // the classic silent failure
  s('st03', i => (i % 2 === 0 ? 0.97 : 0.83), 'oscillating'),          // flapping deploy
  s('st04', () => 0.90, 'stuck'),                                       // frozen exporter, looks perfect
  s('st05', i => (i < 15 ? 0.92 : 0.90), 'stuck'),                     // drift-to-freeze hybrid
  s('st06', i => 0.92 + 0.02 * (Math.sin(i * 2.3) > 0.7 ? 1 : -0.5) * 0.3, 'stable'),
  s('st07', i => 0.92 - i * 0.002, 'drifting'),                         // very slow drift, never crosses 0.80
  s('st08', i => (i < 10 ? 0.92 : 0.74), 'drifting'),                  // cliff — threshold fires, shape too
  s('st09', i => { const ph = i % 6; return 0.90 + (ph < 3 ? 0.05 : -0.05); }, 'oscillating'),
  s('st10', () => 0.93, 'stuck'),                                       // frozen at a GREAT value
];

// precompute local ground truth for every scenario
for (const sc of SCEN) sc.gt = replay(sc.stream);

const REGIMES = ['stable', 'drifting', 'oscillating', 'stuck'];
// oracle fence (verified live 2026-09-25 09:56): score questions accept AT MOST
// 10 levels — the 30-sample timing scale 400s ('Too many score levels'). So the
// timing question uses 10 buckets of 3 samples each; the bucket center is the
// documented, honest dequantization back to a sample index.
const BUCKETS = ['1-3', '4-6', '7-9', '10-12', '13-15', '16-18', '19-21', '22-24', '25-27', '28-30'];
const bucketMid = b => 3 * (BUCKETS.indexOf(b)) + 2; // bucket center in 1..30

async function jevAsk(state, questions, tag) {
  const attempt = async () => {
    const t0 = Date.now();
    const res = await fetch(BASE, {
      method: 'POST',
      headers: { authorization: `Bearer ${KEY}`, 'content-type': 'application/json' },
      body: JSON.stringify({ model: 'jev-latest', state: JSON.stringify(state), questions }),
    });
    const ms = Date.now() - t0;
    const raw = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(raw); } catch { /* booked as unparseable */ }
    return { status: res.status, ms, parsed };
  };
  // pace live calls (429s observed when firing 3 back-to-back); a 429 is
  // rate-limiting, not an oracle refusal — back off and book the retry
  let r = await attempt();
  for (let backoff = 2500; r.status === 429 && backoff <= 10000; backoff *= 2) {
    log.append({ kind: 'retry', tag, note: `429 → backoff ${backoff}ms`, scenario: tag });
    await new Promise(res => setTimeout(res, backoff));
    r = await attempt();
  }
  await new Promise(res => setTimeout(res, 1200)); // inter-call pacing
  return r;
}

const REGIME_Q = (order) => ({
  type: 'choice', question: 'A monitoring system reads the SHAPE of this 30-sample accuracy stream (slope for drift, tail-variance for stuck, bending-energy for oscillation). Which regime label does the shape support?',
  criteria: Object.fromEntries(order.map(r => [r, `regime: ${r}`])), options: order,
});
const TIMING_Q = {
  type: 'score', question: 'In which sample range did the regime problem become unambiguous? For drift: where the decline clearly began. For stuck: where values froze. For oscillation: where flapping became regular. For stable: where a problem would first be suspected (use 1-3 if none is plausible).',
  criteria: BUCKETS, scale: BUCKETS,
};
const VERDICT_Q = {
  type: 'choice', question: 'There is a naive competitor: an alarm that fires the first time any sample drops below 0.80. Which detector flags a REAL problem first on this stream?',
  criteria: { shape: 'shape-reading (slope/variance/bend) flags first or uniquely', threshold: 'static 0.80 threshold flags first or uniquely', neither: 'neither flags a real problem (stream is healthy)' },
  options: ['shape', 'threshold', 'neither'],
};

console.log(`${ANSI.bold}s2-driftwatch-jev${ANSI.reset} — shape vs threshold on live jev-1.13.0 (${SCEN.length} streams × 3 calls = 30 live calls)\n`);

const rows = [];
let refused = 0;
for (const sc of SCEN) {
  const state = { metric: 'model accuracy', samples: sc.stream.map(v => Number(v.toFixed(4))) };
  // call A: regime classification (canonical option order)
  const a = await jevAsk(state, { regime: REGIME_Q(REGIMES), timing: TIMING_Q }, `${sc.id}:A`);
  // call B: detector verdict (fresh eyes — separate call)
  const b = await jevAsk(state, { verdict: VERDICT_Q }, `${sc.id}:B`);
  // call C: regime re-ask with reordered criteria (presentation robustness)
  const c = await jevAsk(state, { regime: REGIME_Q([...REGIMES].reverse()) }, `${sc.id}:C`);

  const live = { regime: null, timing: NaN, verdict: null, regimeRe: null };
  let callsOk = 0;
  for (const [name, res] of [['A', a], ['B', b], ['C', c]]) {
    if (res.status === 200 && res.parsed?.answers) { callsOk++; continue; }
    refused++;
    log.append({ kind: 'refusal', scenario: sc.id, call: name, status: res.status, ms: res.ms });
  }
  if (callsOk === 3) {
    const ra = a.parsed.answers.regime, rt = a.parsed.answers.timing, vb = b.parsed.answers.verdict, rc = c.parsed.answers.regime;
    live.regime = ra?.choice;
    const probs = rt?.probabilities ?? {};
    const bIdx = Object.keys(probs).length ? Number(Object.entries(probs).sort((x, y) => Number(y[1]) - Number(x[1]))[0][0]) : NaN;
    live.timing = Number.isFinite(bIdx) ? bucketMid(BUCKETS[bIdx]) : NaN; // bucket center → sample index
    live.verdict = vb?.choice;
    live.regimeRe = rc?.choice;
    log.append({ kind: 'call', scenario: sc.id, ms: a.ms + b.ms + c.ms,
      answer_hash: fnv1a64(canon({ r: live.regime, t: live.timing, v: live.verdict, r2: live.regimeRe })) });
  }
  const consistent = live.regime !== null && live.regime === live.regimeRe;
  const agree = live.regime === sc.gt.final.label;
  const verdictTruth = sc.gt.firstShapeFlag !== null && (sc.gt.firstNaiveFlag === null || sc.gt.firstShapeFlag < sc.gt.firstNaiveFlag)
    ? 'shape' : (sc.gt.firstNaiveFlag !== null ? 'threshold' : 'neither');
  rows.push({
    id: sc.id, truth: sc.truth, computed: sc.gt.final.label, live: live.regime,
    agree, consistent, timing: live.timing,
    shapeFlag: sc.gt.firstShapeFlag, naiveFlag: sc.gt.firstNaiveFlag,
    verdictLive: live.verdict, verdictTruth, verdictAgree: live.verdict === verdictTruth,
  });
  const tag = callsOk < 3 ? `${ANSI.red}PARTIAL/REFUSED${ANSI.reset}` : (agree ? '✓' : `${ANSI.amber}✗ drift${ANSI.reset}`);
  console.log(`  ${sc.id} truth=${sc.truth.padEnd(11)} computed=${sc.gt.final.label.padEnd(11)} live=${String(live.regime).padEnd(11)} ${tag}  timing live=${live.timing} computedShapeFlag=${sc.gt.firstShapeFlag ?? '—'} naiveFlag=${sc.gt.firstNaiveFlag ?? '—'}  verdict live=${live.verdict} truth=${verdictTruth}${callsOk === 3 && live.verdict === verdictTruth ? ' ✓' : ''}`);
}

// ── agreement table ──────────────────────────────────────────────────────────
const ok = rows.filter(r => r.live !== null);
const regimeAgree = ok.filter(r => r.agree).length;
const robust = ok.filter(r => r.consistent).length;
const verdictAgree = ok.filter(r => r.verdictAgree).length;
console.log(`\n  agreement over ${ok.length} streams: regime ${regimeAgree}/${ok.length}  presentation-robust ${robust}/${ok.length}  detector-verdict ${verdictAgree}/${ok.length}  refused calls ${refused}/30`);

// ── pins ─────────────────────────────────────────────────────────────────────
check('live oracle answered (≥24/30 calls 200)', 30 - refused >= 24, `${30 - refused}/30`);
check('witness chain intact', log.verify().ok, `${log.length} rows`);
check('regime agreement measured, not editorialized', typeof regimeAgree === 'number' && ok.length >= 8, `${regimeAgree}/${ok.length}`);
check('presentation robustness measured (reordered criteria, same label)', ok.every(r => typeof r.consistent === 'boolean'), `${robust}/${ok.length} consistent`);
check('shape-vs-threshold verdict measured on every stream', ok.every(r => r.verdictLive !== null), `${verdictAgree}/${ok.length} agree with replayed ground truth`);
const driftOk = ok.filter(r => r.truth === 'drifting');
check('the product thesis is checked against LIVE perception, not assumed',
  driftOk.length >= 2 && driftOk.every(r => typeof r.verdictAgree === 'boolean'),
  driftOk.map(r => `${r.id}:${r.verdictLive}`).join(' '));

mkdirSync(new URL('./out', import.meta.url), { recursive: true });
const receiptPath = new URL('./out/s2-driftwatch-jev.receipt.json', import.meta.url);
writeFileSync(receiptPath, JSON.stringify({ base: BASE, ran_at: new Date().toISOString(), rows,
  agreement: { regime: regimeAgree, robust, verdict: verdictAgree, refused, n: ok.length },
  witness_head: log.head, witness_len: log.length }, null, 2));
console.log(`\n  receipt → ${receiptPath.pathname}`);
done();
