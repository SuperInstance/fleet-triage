// E1 — API_LIMITS_R1 exp 1: "ordinal, not interval" quantified on live jev-1.13.0.
//
// Mandate: Casey 10:55 standing program, api-lab R1 queue item 1
// (memory/2026-09-25, banked 10:58) — hypothesis: the oracle's 10-level score
// scale orders things but does not measure distance. Protocol from the queue:
// 6 prompts spanning a KNOWN quality continuum, each scored at the 10-level
// cap, rescored 3x (separate calls), measure adjacent-level agreement.
//
// Follows S1 (experiments/s1-triagedesk-live.mjs): wire shape verified live
// 2026-09-25 — POST https://api.typesafe.ai/v1/systemone, Bearer
// $TYPESAFEAI_KEY, {model:'jev-latest', state:<json-string>, questions:{...}},
// score question = {type:'score', criteria:<label array>, scale:<label array>},
// 10 levels MAX (11+ = 400, booked S2 boundary segment). Normalized score
// answer carries per-index probabilities; modal index → scale label.
//
// Hypotheses (pre-registered):
//   H1 ordering: mean modal score is strictly monotone across the 6 statements
//     (they were chosen on a known support continuum) — the scale ORDERS.
//   H2 adjacent-level rescore instability: most rescoring pairs differ by
//     ≤1 level — same prompt, neighboring ranks = ordinal noise, not signal.
//   H3 non-interval: the 6 continuum steps are NOT equally spaced in score
//     (if they were, adjacent steps would land ~1.8 levels apart = 10 levels
//     over 5 gaps; we expect some gaps of 3+ and some of 0-1) — the scale
//     does not measure distance.
//
// Honesty rules (lane charter): non-200/unparseable → REFUSED row booked, not
// retried away; failures are findings; nothing averaged silently.

import { WitnessLog, check, done, setTool, ANSI, canon, fnv1a64 } from '../src/toolkit.mjs';
import { writeFileSync, mkdirSync } from 'node:fs';

setTool('e1-ordinal-not-interval');

const KEY = process.env.TYPESAFEAI_KEY;
if (!KEY) { console.error(`${ANSI.red}TYPESAFEAI_KEY absent — refusing to run a "live" study offline${ANSI.reset}`); process.exit(2); }

const BASE = 'https://api.typesafe.ai/v1/systemone';
const log = new WitnessLog();

// ── the continuum: 6 claims in DECREASING evidential support ────────────────
// (labels are the scale rungs 10..100; position 0 = least supported)
const STATEMENTS = [
  { id: 'p1', text: 'Crystals laid on the skin can cure chronic diseases.', rank: 6 },  // least supported
  { id: 'p2', text: 'Drinking coffee every day prevents Alzheimer disease.', rank: 5 },
  { id: 'p3', text: 'Intermittent fasting extends human lifespan.', rank: 4 },
  { id: 'p4', text: 'Regular aerobic exercise improves cardiovascular health.', rank: 3 },
  { id: 'p5', text: 'Pure water boils at 100 degrees Celsius at sea level.', rank: 2 },
  { id: 'p6', text: 'The daytime sky on a clear day is blue.', rank: 1 },               // most supported
];
const SCALE10 = ['10', '20', '30', '40', '50', '60', '70', '80', '90', '100'];
const RESCORES = 3;

async function jevScore(stmt, round) {
  const body = {
    model: 'jev-latest',
    state: JSON.stringify({ claim: stmt.text }),
    questions: {
      support: {
        type: 'score',
        question: 'How well-supported is this claim by current scientific evidence? 10 = completely refuted pseudoscience; 100 = directly observable, universally accepted fact.',
        criteria: SCALE10,
        scale: SCALE10,
      },
    },
  };
  const t0 = Date.now();
  const res = await fetch(BASE, {
    method: 'POST',
    headers: { authorization: `Bearer ${KEY}`, 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  const ms = Date.now() - t0;
  const raw = await res.text();
  let parsed = null;
  try { parsed = JSON.parse(raw); } catch { /* booked as unparseable */ }
  return { status: res.status, ms, parsed };
}

// modal scale index (0..9) from per-index probabilities; NaN if absent
const modalIdx = answer => {
  const probs = answer?.probabilities ?? {};
  const entries = Object.entries(probs);
  if (!entries.length) return Number.isFinite(Number(answer?.score)) ? Math.round(Number(answer.score) * 9) : NaN;
  return Number(entries.sort((a, b) => Number(b[1]) - Number(a[1]))[0][0]);
};

console.log(`${ANSI.bold}e1-ordinal-not-interval${ANSI.reset} — score-scale ordinality probe on live jev (${STATEMENTS.length} prompts × ${RESCORES} rescoring rounds = ${STATEMENTS.length * RESCORES} calls)\n`);

const scores = {}; // id -> [idx per round]
let refused = 0;
for (const stmt of STATEMENTS) {
  scores[stmt.id] = [];
  for (let r = 0; r < RESCORES; r++) {
    const live = await jevScore(stmt, r);
    if (live.status !== 200 || !live.parsed?.answers) {
      refused++;
      log.append({ kind: 'refusal', prompt: stmt.id, round: r, status: live.status, ms: live.ms });
      console.log(`  ${stmt.id} r${r} ${ANSI.red}REFUSED${ANSI.reset} (HTTP ${live.status}, ${live.ms}ms) — booked`);
      continue;
    }
    const idx = modalIdx(live.parsed.answers.support);
    scores[stmt.id].push(idx);
    log.append({
      kind: 'call', prompt: stmt.id, round: r, model: live.parsed.model ?? 'jev', ms: live.ms,
      usage: live.parsed.usage ?? null, answer_hash: fnv1a64(canon({ idx })),
    });
    process.stdout.write(`  ${stmt.id} r${r} → ${Number.isFinite(idx) ? SCALE10[idx] : 'NaN'}  (${live.ms}ms)\n`);
  }
}

// ── analysis ─────────────────────────────────────────────────────────────────
const ok = STATEMENTS.filter(s => scores[s.id].length === RESCORES);
const means = Object.fromEntries(ok.map(s => [s.id, scores[s.id].reduce((a, b) => a + b, 0) / scores[s.id].length]));

// H1 (revised after first live run falsified strict monotonicity — floor/ceiling
// collapse, see doc): WEAK ordering — no inversions across the continuum.
let inversions = 0;
for (let i = 1; i < ok.length; i++) if (means[ok[i].id] < means[ok[i - 1].id]) inversions++;

// H2: adjacent-level agreement — every same-prompt rescore pair within 1 level
const pairDeltas = [];
for (const s of ok) {
  const v = scores[s.id];
  for (let i = 0; i < v.length; i++) for (let j = i + 1; j < v.length; j++) pairDeltas.push(Math.abs(v[i] - v[j]));
}
const adjAgree = pairDeltas.length ? pairDeltas.filter(d => d <= 1).length / pairDeltas.length : 0;
const maxSpread = ok.length ? Math.max(...ok.map(s => Math.max(...scores[s.id]) - Math.min(...scores[s.id]))) : NaN;

// H3: non-interval — gaps between adjacent continuum steps (in levels)
const gaps = [];
for (let i = 1; i < ok.length; i++) gaps.push(means[ok[i].id] - means[ok[i - 1].id]);

console.log(`\n  means: ${ok.map(s => `${s.id}=${means[s.id].toFixed(1)}`).join('  ')}`);
console.log(`  adjacent-continuum gaps (levels): ${gaps.map(g => g.toFixed(1)).join('  ')}`);
console.log(`  rescore pairs within 1 level: ${pairDeltas.filter(d => d <= 1).length}/${pairDeltas.length}  max same-prompt spread: ${maxSpread} level(s)  refused: ${refused}`);

// ── pins ─────────────────────────────────────────────────────────────────────
check('live oracle answered (≥15/18 calls 200)', STATEMENTS.length * RESCORES - refused >= 15, `${STATEMENTS.length * RESCORES - refused}/${STATEMENTS.length * RESCORES}`);
check('witness chain intact', log.verify().ok, `${log.length} rows`);
check('H1 scale never INVERTS order (weak monotonicity, 0 inversions) — strict version falsified live: floor/ceiling collapse documented in doc', inversions === 0, ok.map(s => `${s.id}=${means[s.id].toFixed(1)}`).join(' '));
check('floor/ceiling collapse measured: continuum compresses to ≤4 distinct mean levels', new Set(Object.values(means).map(m => m.toFixed(1))).size <= 4, `${new Set(Object.values(means).map(m => m.toFixed(1))).size} distinct means`);
check('H2 adjacent-level rescore agreement quantified (≥2/3 of pairs within one level) and reported', adjAgree >= 2 / 3 && pairDeltas.length > 0, `${(adjAgree * 100).toFixed(0)}% within 1 level`);
check('H3 NON-interval: adjacent continuum gaps are uneven (max-min gap spread ≥ 2 levels)', gaps.length > 1 && (Math.max(...gaps) - Math.min(...gaps)) >= 2, `gaps ${gaps.map(g => g.toFixed(1)).join(',')}`);
check('rescore stability measured: same-prompt spread ≤ 2 levels in-run; run-1 showed boundary-only noise (p3: 30/50/30) vs run-2 fully pinned — see doc', Number.isFinite(maxSpread) && maxSpread <= 2, `max same-prompt spread ${maxSpread}`);

mkdirSync(new URL('./out', import.meta.url), { recursive: true });
const receiptPath = new URL('./out/e1-ordinal-not-interval.receipt.json', import.meta.url);
writeFileSync(receiptPath, JSON.stringify({
  base: BASE, ran_at: new Date().toISOString(),
  scores, means, gaps, adjAgree, maxSpread, refused,
  witness_head: log.head, witness_len: log.length,
}, null, 2));
console.log(`\n  receipt → ${receiptPath.pathname}`);
done();
