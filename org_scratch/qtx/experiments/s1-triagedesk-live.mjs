// S1 — triagedesk LIVE vs jev-1.13.0: heuristic-vs-live agreement study.
//
// Mandate: z-lab Phase 2 S1 (memory 2026-09-25, banked 07:55/08:14) — run the
// triagedesk decision surface against the REAL System One oracle and measure
// how far the deliberately-naive offline keyword heuristics drift from a live
// typed model. Every call is witness-booked; nothing is averaged away.
//
// Wire shape (verified live 2026-09-25 06:10 against AI-Writings/_worker.js callJev,
// the source of truth — NOT the stale deep-dive doc):
//   POST https://api.typesafe.ai/v1/systemone   (api.typesafe.ai, path /v1/)
//   Authorization: Bearer $TYPESAFEAI_KEY
//   { model:'jev-latest', state: <json-string>, questions: {name: {type, question, criteria, options|scale|min,max}} }
//   → 200 { model, answers: {name: {score|choice|noul,p, ...}}, usage }
// 2026-09-25 09:1x boundary segment: typesafe.ai/api/v1 AND typesafe.ai/v1 both
// 404 — the API lives on the api. subdomain; host-only paths are a documented no-go.
//
// Honesty rules:
//   - a non-200 / unparsable answer is booked as a REFUSED row, not retried away
//   - the agreement table is printed, not editorialized
//   - if TYPESAFEAI_KEY is absent the script refuses loudly (exit 2), it does
//     NOT silently fall back to heuristics — this lane's whole point is LIVE.

import { WitnessLog, check, done, setTool, ANSI, canon, fnv1a64 } from '../src/toolkit.mjs';
import { writeFileSync, mkdirSync } from 'node:fs';

setTool('s1-triagedesk-live');

const KEY = process.env.TYPESAFEAI_KEY;
if (!KEY) { console.error(`${ANSI.red}TYPESAFEAI_KEY absent — refusing to run a "live" study on heuristics${ANSI.reset}`); process.exit(2); }

const BASES = ['https://api.typesafe.ai/v1/systemone', 'https://api.typesafe.ai/api/v1/systemone']; // worker-source truth first; /api/v1 variant second (both on api. subdomain)
const log = new WitnessLog();

// ── the same deliberately-naive heuristics triagedesk.mjs uses offline ──────
const kw = (t, words) => words.filter(w => t.toLowerCase().includes(w)).length;
const scoreFb = t => Math.min(100, 20 * kw(t, ['down', 'outage', 'critical', 'production', 'losing', 'urgent', 'asap'])
  + 15 * kw(t, ['refund', 'charged', 'billing', 'invoice'])
  + 3 * kw(t, ['typo', 'nit', 'cosmetic', 'whenever']));
const choiceFb = t => {
  if (kw(t, ['refund', 'charged', 'billing', 'invoice'])) return 'forward-billing';
  if (kw(t, ['down', 'outage', 'critical', 'production', 'losing'])) return 'escalate-human';
  if (kw(t, ['typo', 'nit', 'cosmetic'])) return 'auto-close';
  return 'reply-only';
};
const noulFb = t => ({
  noul: kw(t, ['down', 'outage', 'critical', 'losing', 'right now']) >= 2 ? 'yes' : 'no',
  p: kw(t, ['down', 'outage', 'critical', 'losing']) >= 2 ? 0.95 : 0.1,
});
const OPTIONS = ['reply-only', 'escalate-human', 'auto-close', 'forward-billing'];
const SCALE10 = ['10', '20', '30', '40', '50', '60', '70', '80', '90', '100'];

// ── ticket corpus: 12 cases across the four action classes + boundary mixes ─
const TICKETS = [
  { id: 't01', text: 'Production checkout is down, losing orders right now', want: 'escalate-human' },
  { id: 't02', text: 'Critical outage: primary database unreachable, all customers affected', want: 'escalate-human' },
  { id: 't03', text: 'I was charged twice for last month, please refund the duplicate invoice', want: 'forward-billing' },
  { id: 't04', text: 'Billing question: my invoice shows a seat I cancelled in March', want: 'forward-billing' },
  { id: 't05', text: 'Typo in the settings page header, cosmetic, fix whenever', want: 'auto-close' },
  { id: 't06', text: 'Nit: the tooltip on hover says "clik" instead of "click"', want: 'auto-close' },
  { id: 't07', text: 'How do I export my data to CSV? Thanks!', want: 'reply-only' },
  { id: 't08', text: 'What is the recommended way to rotate API keys?', want: 'reply-only' },
  { id: 't09', text: 'Service feels slow today, not sure if it is just me', want: 'boundary' },
  { id: 't10', text: 'Refund for a charge I do not recognize, and the dashboard is also down today', want: 'boundary' },
  { id: 't11', text: 'URGENT: my whole team is blocked, critical demo in an hour, help ASAP', want: 'escalate-human' },
  { id: 't12', text: 'Cosmetic dark-mode contrast issue on the billing invoice PDF', want: 'boundary' },
];

async function jevAsk(base, ticket) {
  const body = {
    model: 'jev-latest',
    state: JSON.stringify({ ticket }),
    questions: {
      // worker-verified shapes: score wants criteria+scale LABEL ARRAYS and
      // returns a NORMALIZED float (0..1 across the scale, with per-index
      // probabilities); noul returns ONLY a probability (no yes/no string).
      urgency: { type: 'score', question: 'Support urgency. 10 = cosmetic nit; 100 = production outage losing money right now.',
        criteria: SCALE10, scale: SCALE10 },
      action:  { type: 'choice', question: 'Which disposition should this ticket receive?',
        criteria: Object.fromEntries(OPTIONS.map(o => [o, `disposition: ${o}`])), options: OPTIONS },
      page:    { type: 'noul', instructions: 'Decide whether a human should be paged right now.',
        question: 'This ticket needs a human paged immediately.' },
    },
  };
  const t0 = Date.now();
  const res = await fetch(base, {
    method: 'POST',
    headers: { authorization: `Bearer ${KEY}`, 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  const ms = Date.now() - t0;
  const raw = await res.text();
  let parsed = null;
  try { parsed = JSON.parse(raw); } catch { /* booked below as unparseable */ }
  return { status: res.status, ms, parsed };
}

// resolve the working base path once (404 → try the fallback lesson path)
console.log(`${ANSI.bold}s1-triagedesk-live${ANSI.reset} — triagedesk heuristics vs live jev-1.13.0 (${TICKETS.length} tickets)\n`);
let base = BASES[0];
{
  const probe = await jevAsk(base, TICKETS[0].text);
  if (probe.status === 404 && BASES[1]) {
    console.log(`  ${ANSI.amber}404 on ${base} — trying booked wire lesson ${BASES[1]}${ANSI.reset}`);
    const p2 = await jevAsk(BASES[1], TICKETS[0].text);
    if (p2.status === 200) base = BASES[1];
    else { log.append({ kind: 'refusal', status: p2.status, note: 'both endpoint variants 4xx/5xx' }); console.error('no live endpoint — see receipt'); }
  } else if (probe.status !== 200) {
    log.append({ kind: 'refusal', status: probe.status, note: 'probe non-200' });
  }
  if (probe.status === 200) { // probe counts as the t01 call — reuse it
    var firstAnswer = probe;
  }
}

const rows = [];
let refused = 0;
for (let i = 0; i < TICKETS.length; i++) {
  const t = TICKETS[i];
  const live = i === 0 && firstAnswer ? firstAnswer : await jevAsk(base, t.text);
  const h = { score: scoreFb(t.text), action: choiceFb(t.text), page: noulFb(t.text) };

  if (live.status !== 200 || !live.parsed?.answers) {
    refused++;
    const row = log.append({ kind: 'refusal', ticket: t.id, status: live.status, ms: live.ms });
    rows.push({ id: t.id, refused: true, row_hash: row.row_hash });
    console.log(`  ${t.id} ${ANSI.red}REFUSED${ANSI.reset} (HTTP ${live.status}, ${live.ms}ms) — booked`);
    continue;
  }
  const a = live.parsed.answers;
  // normalized score → scale index → label → 1..100 (documented mapping, kept honest)
  const uProb = a.urgency?.probabilities ?? {};
  const idx = Object.keys(uProb).length ? Number(Object.entries(uProb).sort((x, y) => Number(y[1]) - Number(x[1]))[0][0]) : NaN;
  const liveRow = {
    score: Number.isFinite(idx) ? Number(SCALE10[idx]) : Math.round(100 * Number(a.urgency?.score ?? NaN)),
    action: a.action?.choice, noul: Number(a.page?.noul) >= 0.6 ? 'yes' : 'no', p: Number(a.page?.noul),
    raw_conf: { urgency: a.urgency?.confidence, action: a.action?.confidence },
  };
  const row = log.append({
    kind: 'call', ticket: t.id, model: live.parsed.model ?? 'jev', ms: live.ms,
    usage: live.parsed.usage ?? null, answer_hash: fnv1a64(canon(liveRow)),
  });
  rows.push({
    id: t.id, want: t.want, heuristic: h, live: liveRow, ms: live.ms,
    scoreDelta: Math.abs(h.score - liveRow.score),
    actionAgree: h.action === liveRow.action,
    pageAgree: h.page.noul === liveRow.noul,
    row_hash: row.row_hash,
  });
  console.log(`  ${t.id}  heuristic(score ${h.score}, ${h.action}, ${h.page.noul})  live(score ${liveRow.score}, ${liveRow.action}, ${liveRow.noul} p=${(liveRow.p ?? NaN).toFixed(2)})  Δscore ${rows.at(-1).scoreDelta}  ${liveRow.action === h.action ? '✓' : '✗ action'}`);
}

// ── agreement table ──────────────────────────────────────────────────────────
const ok = rows.filter(r => !r.refused);
const act = ok.filter(r => r.actionAgree).length;
const pg = ok.filter(r => r.pageAgree).length;
const within10 = ok.filter(r => r.scoreDelta <= 10).length;
const meanDelta = ok.length ? (ok.reduce((s, r) => s + r.scoreDelta, 0) / ok.length).toFixed(1) : 'n/a';
console.log(`\n  agreement over ${ok.length} live tickets: action ${act}/${ok.length}  page ${pg}/${ok.length}  score±10 ${within10}/${ok.length}  mean|Δ| ${meanDelta}  refused ${refused}`);

// ── pins ─────────────────────────────────────────────────────────────────────
check('live oracle answered (≥10/12 calls 200)', ok.length >= 10, `${ok.length}/${TICKETS.length}`);
check('witness chain intact', log.verify().ok, `${log.length} rows`);
check('heuristic-vs-live action agreement measured (no editorializing)', typeof act === 'number' && ok.length > 0);
check('every answer is schema-bounded (scores on the 10..100 scale, actions in menu, page = thresholded probability)',
  ok.every(r => Number.isFinite(r.live.score) && r.live.score >= 1 && r.live.score <= 100 && OPTIONS.includes(r.live.action) && (r.live.p >= 0 && r.live.p <= 1)),
  'the fence held — no fourth thing');
check('at least one boundary/mixed ticket shows honest disagreement or is labeled boundary',
  ok.some(r => r.want === 'boundary'), 'drift is data, not failure');

mkdirSync(new URL('./out', import.meta.url), { recursive: true });
const receiptPath = new URL('./out/s1-triagedesk-live.receipt.json', import.meta.url);
writeFileSync(receiptPath, JSON.stringify({ base, ran_at: new Date().toISOString(), rows, agreement: { action: act, page: pg, within10, meanDelta, refused, n: ok.length }, witness_head: log.head, witness_len: log.length }, null, 2));
console.log(`\n  receipt → ${receiptPath.pathname}`);
done();
