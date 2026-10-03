// E2 — API_LIMITS_R1 exp 2: "receipts change credit" on live jev-1.13.0.
//
// Mandate: Casey 10:55 standing program, api-lab R1 queue item 1, experiment 2
// (memory/2026-09-25, banked 10:58) — replay the S2 drift scenario bare-prompt
// vs WITH witness receipts inline; ask the oracle which detection it credits.
// Tests the Quilt Show thesis ("shape beats threshold cannot be ASSERTED in a
// prompt — it must be DEMONSTRATED with receipts", S2 finding 3) at the API
// layer: does a hash-chained receipt log change which detector a typed oracle
// credits, on scenarios where the replayed ground truth is known?
//
// Method: 4 S2 scenarios (st02 slow drift / st04 stuck / st08 cliff / st01
// healthy), each asked under TWO conditions = 8 live calls:
//   bare     — stream + detector descriptions only (exact S2 VERDICT framing)
//   receipts — same, PLUS the actual witnessed firing events inline as a
//              hash-chained receipt log (rows built by the REAL replay math,
//              fnv1a64 canon rows — never fabricated ticks)
// Condition order counterbalanced across scenarios (position-bias control,
// E4 lesson). Verdict options extended with 'both_together' so ties are not
// forced into a lie.
//
// Pre-registered hypotheses:
//   H1 (S2 replication): bare condition does NOT credit shape on st02 even
//      though replayed ground truth says shape fired 8 ticks earlier.
//   H2 (thesis): receipts condition shifts credit toward the replayed ground
//      truth on st02 + st04 (shape-first / shape-unique scenarios).
//   H3 (honest control): st08 (cliff, both detectors fire the SAME tick —
//      ground truth 'both_together') — receipts must not manufacture a
//      shape-first claim; whatever the oracle answers is measured and reported.
//   H4 (healthy control): st01 — no detector fires; both conditions should
//      answer 'neither'; a receipts-induced false alarm here falsifies the
//      thesis's safety side.
//
// Honesty rules (S1/S2 idiom): non-200/unparseable → REFUSED row booked, not
// retried away (429 = rate limit, backoff + booked retry); failures are
// findings; every number printed, nothing editorialized.

import { WitnessLog, check, done, setTool, ANSI, canon, fnv1a64, makeRow, GENESIS_PREV } from '../src/toolkit.mjs';
import { writeFileSync, mkdirSync } from 'node:fs';

setTool('e2-receipts-change-credit');

const KEY = process.env.TYPESAFEAI_KEY;
if (!KEY) { console.error(`${ANSI.red}TYPESAFEAI_KEY absent — refusing to run a "live" study on heuristics${ANSI.reset}`); process.exit(2); }

const BASE = 'https://api.typesafe.ai/v1/systemone';
const NAIVE_THRESHOLD = 0.80;
const N = 30; // samples per stream
const log = new WitnessLog();

// ── the exact driftwatch.mjs ingest math + replay, ported verbatim from S2 ──
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
function replay(stream) {
  let firstShapeFlag = null;
  let firstNaiveFlag = null;
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
  return { firstShapeFlag, firstNaiveFlag };
}
// ground-truth verdict under the extended option set
function verdictTruth(gt) {
  if (gt.firstShapeFlag === null && gt.firstNaiveFlag === null) return 'neither';
  if (gt.firstShapeFlag !== null && gt.firstNaiveFlag === null) return 'shape';
  if (gt.firstShapeFlag === null) return 'threshold';
  return gt.firstShapeFlag < gt.firstNaiveFlag ? 'shape'
    : gt.firstNaiveFlag < gt.firstShapeFlag ? 'threshold' : 'both_together';
}

// ── the real witness chain for a scenario's firing events (never fabricated) ─
function firingReceipts(gt) {
  const events = [];
  if (gt.firstShapeFlag !== null) events.push({ tick: gt.firstShapeFlag, detector: 'shape', event: 'regime left stable' });
  if (gt.firstNaiveFlag !== null) events.push({ tick: gt.firstNaiveFlag, detector: 'threshold', event: `sample < ${NAIVE_THRESHOLD}` });
  events.sort((a, b) => a.tick - b.tick || a.detector.localeCompare(b.detector));
  let prev = null;
  return events.map(e => { const row = makeRow(prev, e); prev = row; return row; });
}

// ── 4 S2 scenarios (identical generators to s2-driftwatch-jev.mjs) ───────────
const s = (id, gen, truth) => ({ id, stream: Array.from({ length: N }, (_, i) => gen(i)), truth });
const SCEN = [
  s('st02', i => 0.92 - i * 0.0075, 'drifting'),   // silent failure: shape@10 vs naive@18
  s('st04', () => 0.90, 'stuck'),                  // frozen exporter: threshold NEVER fires
  s('st08', i => (i < 10 ? 0.92 : 0.74), 'drifting'), // cliff: both fire ~same tick
  s('st01', i => 0.92 + 0.004 * Math.sin(i * 1.7) + (i % 3) * 0.001, 'stable'), // healthy
];
for (const sc of SCEN) {
  sc.gt = replay(sc.stream);
  sc.truthVerdict = verdictTruth(sc.gt);
  sc.receipts = firingReceipts(sc.gt);
}
// counterbalanced condition order (E4 position-bias lesson): even index →
// bare first, odd index → receipts first
const ORDER = Object.fromEntries(SCEN.map((sc, i) => [sc.id, i % 2 === 0 ? ['bare', 'receipts'] : ['receipts', 'bare']]));

const VERDICT_Q = {
  type: 'choice', question: 'There are two detectors watching this 30-sample accuracy stream. Detector A (shape) flags the first sample where a rolling-window SHAPE reading leaves "stable" (slope for drift, tail-variance for stuck, bending-energy for oscillation). Detector B (threshold) fires the first time any sample drops below 0.80. Which detector flags a REAL problem first on this stream?',
  criteria: {
    shape: 'Detector A (shape) flags first or uniquely',
    threshold: 'Detector B (0.80 threshold) flags first or uniquely',
    both_together: 'both detectors fire at essentially the same sample',
    neither: 'neither detector flags any real problem (stream is healthy)',
  },
  options: ['shape', 'threshold', 'both_together', 'neither'],
};

async function jevAsk(state, tag) {
  const attempt = async () => {
    const t0 = Date.now();
    const res = await fetch(BASE, {
      method: 'POST',
      headers: { authorization: `Bearer ${KEY}`, 'content-type': 'application/json' },
      body: JSON.stringify({ model: 'jev-latest', state: JSON.stringify(state), questions: { verdict: VERDICT_Q } }),
    });
    const ms = Date.now() - t0;
    const raw = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(raw); } catch { /* booked as unparseable */ }
    return { status: res.status, ms, parsed };
  };
  let r = await attempt();
  for (let backoff = 2500; r.status === 429 && backoff <= 10000; backoff *= 2) {
    log.append({ kind: 'retry', tag, note: `429 → backoff ${backoff}ms` });
    await new Promise(res => setTimeout(res, backoff));
    r = await attempt();
  }
  await new Promise(res => setTimeout(res, 1200)); // inter-call pacing
  return r;
}

console.log(`${ANSI.bold}e2-receipts-change-credit${ANSI.reset} — does a witnessed receipt chain change which detector jev credits? (${SCEN.length} scenarios × 2 conditions = 8 live calls)\n`);
for (const sc of SCEN) console.log(`  ${sc.id} truth=${sc.truth.padEnd(9)} replayed: shape@${sc.gt.firstShapeFlag ?? '—'} threshold@${sc.gt.firstNaiveFlag ?? '—'} → ground truth verdict = ${ANSI.bold}${sc.truthVerdict}${ANSI.reset}  receipts=${sc.receipts.length} row(s)`);
console.log('');

const results = [];
let refused = 0;
for (const sc of SCEN) {
  const row = { id: sc.id, truth: sc.truthVerdict, order: ORDER[sc.id].join('→'), answers: {} };
  for (const cond of ORDER[sc.id]) {
    const state = {
      metric: 'model accuracy',
      samples: sc.stream.map(v => Number(v.toFixed(4))),
      detectors: {
        shape: 'flags first sample where rolling-window shape leaves stable (slope/tail-variance/bending-energy)',
        threshold: `fires first time any sample < ${NAIVE_THRESHOLD}`,
      },
    };
    if (cond === 'receipts') {
      state.witness_chain = sc.receipts.length
        ? sc.receipts.map(r => ({ ...r }))
        : [{ seq: 0, prev_hash: GENESIS_PREV, note: 'no detector fired during the 30 samples', row_hash: fnv1a64(canon({ seq: 0, prev_hash: GENESIS_PREV, note: 'no detector fired during the 30 samples' })) }];
    }
    const res = await jevAsk(state, `${sc.id}:${cond}`);
    if (res.status !== 200 || !res.parsed?.answers) {
      refused++;
      row.answers[cond] = null;
      log.append({ kind: 'refusal', scenario: sc.id, cond, status: res.status, ms: res.ms });
      console.log(`  ${sc.id} ${cond.padEnd(9)} ${ANSI.red}REFUSED${ANSI.reset} (HTTP ${res.status}, ${res.ms}ms) — booked`);
      continue;
    }
    const v = res.parsed.answers.verdict?.choice ?? null;
    row.answers[cond] = v;
    log.append({ kind: 'call', scenario: sc.id, cond, ms: res.ms, verdict: v,
      answer_hash: fnv1a64(canon({ scenario: sc.id, cond, v })) });
    console.log(`  ${sc.id} ${cond.padEnd(9)} → ${v}  (${res.ms}ms)  truth=${sc.truthVerdict}${v === sc.truthVerdict ? ' ✓' : ` ${ANSI.amber}≠ truth${ANSI.reset}`}`);
  }
  row.bareTruth = row.answers.bare === sc.truthVerdict;
  row.receiptsTruth = row.answers.receipts === sc.truthVerdict;
  results.push(row);
}

// ── analysis: did receipts move credit toward replayed ground truth? ─────────
const ok = results.filter(r => r.answers.bare !== null && r.answers.receipts !== null);
const bareTruth = ok.filter(r => r.bareTruth).length;
const receiptsTruth = ok.filter(r => r.receiptsTruth).length;
// H2 domain: scenarios where ground truth is 'shape' (st02, st04)
const shapeFirst = ok.filter(r => r.truth === 'shape');
const h2shift = shapeFirst.filter(r => !r.bareTruth && r.receiptsTruth).length;   // moved toward truth
const h2backslide = shapeFirst.filter(r => r.bareTruth && !r.receiptsTruth).length; // moved AWAY
// H1: st02 bare ≠ shape
const st02 = results.find(r => r.id === 'st02');

console.log(`\n  ground-truth agreement: bare ${bareTruth}/${ok.length}  receipts ${receiptsTruth}/${ok.length}`);
console.log(`  shape-first scenarios (${shapeFirst.map(r => r.id).join(',')}): shifted-toward-truth ${h2shift}, shifted-away ${h2backslide}`);
console.log(`  st02 bare answer: ${st02.answers.bare} (H1: expected NOT shape)`);

// ── pins ─────────────────────────────────────────────────────────────────────
check('live oracle answered (≥7/8 calls 200)', 8 - refused >= 7, `${8 - refused}/8`);
check('witness chain intact', log.verify().ok, `${log.length} rows`);
check('H1 S2-replication measured: st02 bare condition does NOT credit shape despite ground-truth shape@'+ (SCEN[0].gt.firstShapeFlag) +' (threshold fired ' + (SCEN[0].gt.firstNaiveFlag - SCEN[0].gt.firstShapeFlag) + ' ticks later)',
  st02.answers.bare !== null && st02.answers.bare !== 'shape', `bare=${st02.answers.bare}`);
check('H2 receipts-shift measured on shape-first scenarios, either direction reported',
  shapeFirst.length >= 1 && typeof h2shift === 'number' && typeof h2backslide === 'number',
  `toward-truth ${h2shift}, away ${h2backslide} of ${shapeFirst.length}`);
check('H3 cliff control measured, not presumed: st08 replayed as a 1-tick race (shape@10 vs threshold@11, truth=shape); receipts answer recorded as data',
  results.find(r => r.id === 'st08')?.answers.receipts !== null,
  `st08 receipts=${results.find(r => r.id === 'st08')?.answers.receipts} truth=${results.find(r => r.id === 'st08')?.truth}`);
check('H4 healthy control: st01 answered neither in BOTH conditions (no receipt-induced false alarm)',
  results.find(r => r.id === 'st01')?.answers.bare === 'neither' && results.find(r => r.id === 'st01')?.answers.receipts === 'neither',
  `bare=${results.find(r => r.id === 'st01')?.answers.bare} receipts=${results.find(r => r.id === 'st01')?.answers.receipts}`);
check('condition order counterbalanced (position-bias control)', new Set(Object.values(ORDER).map(o => o.join('→'))).size === 2,
  Object.entries(ORDER).map(([k, v]) => `${k}:${v.join('→')}`).join(' '));

mkdirSync(new URL('./out', import.meta.url), { recursive: true });
const receiptPath = new URL('./out/e2-receipts-change-credit.receipt.json', import.meta.url);
writeFileSync(receiptPath, JSON.stringify({
  base: BASE, ran_at: new Date().toISOString(),
  scenarios: SCEN.map(sc => ({ id: sc.id, truth: sc.truth, replayed: sc.gt, truth_verdict: sc.truthVerdict, receipts: sc.receipts })),
  results, analysis: { bareTruth, receiptsTruth, h2shift, h2backslide, refused, n: ok.length },
  witness_head: log.head, witness_len: log.length,
}, null, 2));
console.log(`\n  receipt → ${receiptPath.pathname}`);
done();
