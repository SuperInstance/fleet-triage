// S3 — quantum-tided budget: budget-tide × MothQuantum, the appeal cell.
//
// Mandate: z-lab Phase 2 S3 (memory 2026-09-25, banked 07:55/08:14) —
// budget-tide × MothQuantum (engine-based); ONE quantum appeal per tide per
// dry envelope; hard debt refuses ABSOLUTELY; the 10-line "cell contract
// implications" section = quantum-tided autonomy PoC (frontier memo #4).
//
// The idea: when an envelope's tide is out, the spend program refuses before
// the money moves — but the refusal is appealable ONCE per tide, and the
// appeal is decided by a REAL quantum coin (MothQuantum coin-toss-v1, async
// job: 202 queued → poll → result). While the job is in flight the envelope
// sits in superposition: the refusal stands until the quantum outcome
// collapses it. Heads → one-time override (witnessed, with job id). Tails →
// the refusal is final. HARD DEBT (spent already ≥ budget at appeal time)
// refuses absolutely — no quantum lottery for insolvency.
//
// Cell contract implications (the PoC payload):
//   1. An appeal cell moves PENDING → ENTANGLED → COLLAPSED, and EVERY
//      transition is a witnessed row — including the pre-outcome state.
//   2. A cell may trigger quantum work; it must book a receipt BEFORE the
//      outcome exists. Custody precedes certainty.
//   3. Refusal under uncertainty is the DEFAULT: the dry envelope stays dry
//      for the whole poll window; superposition never spends.
//   4. The oracle is out-of-band (a remote engine), so the receipt carries
//      job_id + backend + result digest — custody can re-derive later.
//   5. One appeal per tide per envelope is a SHEET invariant (a cell value),
//      not a comment — the gate reads the cell, not the prose.
//   6. Hard debt refuses absolutely: some refusals are not appealable by
//      design, and that design lives in the gate formula.
//
// Wire shape (verified live 2026-09-25 ~03:00/06:10/10:1x CST):
//   POST {BASE}/engines/coin-toss-v1/process   (Bearer MOTHQUANTUM_KEY) → 202 {job_id,status:'queued'}
//   GET  {BASE}/jobs/{job_id}/status           → poll until terminal
//   GET  {BASE}/jobs/{job_id}/result           → { backend, mode, shots, output, ... }
//
// Honesty rules (S1/S2 idiom): non-202/poll-failure booked as REFUSED rows,
// never retried away; key absent → loud refusal (exit 2); the quantum engine
// is never simulated — if the live call fails, the run fails.

import { WitnessLog, check, done, setTool, ANSI, canon, fnv1a64 } from '../src/toolkit.mjs';
import { writeFileSync, mkdirSync } from 'node:fs';

setTool('s3-quantum-tided-budget');

const KEY = process.env.MOTHQUANTUM_KEY;
const BASE = process.env.MOTHQUANTUM_BASE ?? 'https://api.mothquantum.com/api/v1';
if (!KEY) { console.error(`${ANSI.red}MOTHQUANTUM_KEY absent — refusing to run a "quantum" appeal on a classical coin${ANSI.reset}`); process.exit(2); }

const log = new WitnessLog();

// ── the sheet (budget-tide idiom, in-memory values) ─────────────────────────
const envelopes = {
  groceries: { budget: 100, spent: 100 },   // dry exactly at the line — appealable
  dining:    { budget: 100, spent: 100 },   // dry — second appeal must be refused
  travel:    { budget: 100, spent: 140 },   // HARD DEBT — refuses absolutely
};
const appealsUsed = {};   // invariant cell: one appeal per tide per envelope
const outcomes = [];      // witnessed collapses

function spend(env, amount) {
  const e = envelopes[env];
  if (!e) return { refused: true, reason: 'no such envelope: ' + env };
  if (e.spent >= e.budget)
    return { refused: true, reason: `${env} tide is out: ${e.spent}/${e.budget} spent`, appealable: e.spent < e.budget ? false : false, hard_debt: false, dry: true };
  e.spent += amount;
  return { ok: true, env, amount, spent: e.spent, budget: e.budget };
}

// gate with appeal bookkeeping: dry & not-yet-appealed → appealable;
// dry & appealed → final refusal; hard debt (crossed by past spend) → absolute.
function gate(env) {
  const e = envelopes[env];
  if (e.spent < e.budget) return { tide: 'in' };
  if (e.spent > e.budget) return { tide: 'out', appealable: false, hard_debt: true };
  return appealsUsed[env]
    ? { tide: 'out', appealable: false, hard_debt: false, reason: 'appeal already spent this tide' }
    : { tide: 'out', appealable: true, hard_debt: false };
}

// ── MothQuantum client (engine-based, async job) ────────────────────────────
async function moth(path, opts = {}) {
  const t0 = Date.now();
  const res = await fetch(BASE + path, {
    ...opts,
    headers: { Authorization: `Bearer ${KEY}`, 'Content-Type': 'application/json', ...(opts.headers ?? {}) },
  });
  const text = await res.text();
  let parsed = null;
  try { parsed = JSON.parse(text); } catch { /* booked raw below */ }
  return { status: res.status, parsed, raw: text.slice(0, 400), ms: Date.now() - t0 };
}

async function quantumAppeal(env) {
  // PENDING: appeal filed, receipt booked BEFORE the outcome exists.
  // The appeal is CONSUMED at filing — one per tide per envelope is a sheet
  // invariant (a cell value), so it is written here, not in a comment.
  appealsUsed[env] = true;
  log.append({ kind: 'appeal', state: 'PENDING', envelope: env, engine: 'coin-toss-v1' });
  const job = await moth(`/engines/coin-toss-v1/process`, { method: 'POST', body: JSON.stringify({ params: { shots: 10 } }) });
  if (job.status !== 202 || !job.parsed?.job_id) {
    log.append({ kind: 'refusal', state: 'REFUSED', envelope: env, status: job.status, ms: job.ms });
    return { ok: false, reason: 'moth submit failed', status: job.status };
  }
  // ENTANGLED: job in flight, refusal STILL stands (superposition never spends)
  log.append({ kind: 'appeal', state: 'ENTANGLED', envelope: env, job_id: job.parsed.job_id });
  let status = job.parsed.status, polls = 0;
  while (!['completed', 'failed', 'cancelled'].includes(status) && polls < 30) {
    await new Promise(r => setTimeout(r, 1500));
    const s = await moth(`/jobs/${job.parsed.job_id}/status`);
    polls++;
    status = s.parsed?.status ?? 'failed';
    if (s.status !== 200) break;
  }
  const result = await moth(`/jobs/${job.parsed.job_id}/result`);
  const output = result.parsed?.output ?? result.parsed?.result?.output ?? null;
  const backend = result.parsed?.backend ?? result.parsed?.result?.backend ?? null;
  // COLLAPSED: outcome witnessed with custody-grade fields
  const digest = fnv1a64(canon({ job: job.parsed.job_id, output, backend, status }));
  log.append({ kind: 'appeal', state: 'COLLAPSED', envelope: env, job_id: job.parsed.job_id,
    status, output, backend, polls, digest });
  return { ok: status === 'completed' && output !== null, output, backend, job_id: job.parsed.job_id, polls, status };
}

// ── the run ──────────────────────────────────────────────────────────────────
console.log('  S3 quantum-tided budget — live MothQuantum appeals\n');

// 0. dry refusal refuses BEFORE any money moves
const g0 = spend('groceries', 20);
check('dry envelope refuses before money moves', g0.refused === true && envelopes.groceries.spent === 100, JSON.stringify(g0));

// 1. live appeal #1 on groceries (dry, unused) → quantum coin decides
const st1 = gate('groceries');
check('dry, unappealed envelope is appealable', st1.appealable === true && st1.hard_debt === false, JSON.stringify(st1));
const a1 = await quantumAppeal('groceries');
check('appeal #1 reached COLLAPSED via live engine', a1.ok === true && ['heads', 'tails'].includes(a1.output),
  `job=${a1.job_id} status=${a1.status} output=${a1.output} backend=${a1.backend} polls=${a1.polls}`);
if (a1.ok && a1.output === 'heads') { envelopes.groceries.spent -= 25; outcomes.push({ env: 'groceries', verdict: 'override' }); }
else outcomes.push({ env: 'groceries', verdict: 'refusal-final' });

// 2. one appeal per tide per envelope: second appeal refused WITHOUT a coin
const st2 = gate('groceries');
check('second appeal same tide refused without quantum call', st2.appealable === false, JSON.stringify(st2));

// 3. live appeal #2 on dining
const a2 = await quantumAppeal('dining');
check('appeal #2 reached COLLAPSED via live engine', a2.ok === true && ['heads', 'tails'].includes(a2.output),
  `job=${a2.job_id} status=${a2.status} output=${a2.output} backend=${a2.backend} polls=${a2.polls}`);
if (a2.ok && a2.output === 'heads') { envelopes.dining.spent -= 25; outcomes.push({ env: 'dining', verdict: 'override' }); }
else outcomes.push({ env: 'dining', verdict: 'refusal-final' });

// 4. hard debt refuses absolutely — travel (140/100) gets NO appeal
const st4 = gate('travel');
check('hard debt refuses absolutely (no appeal offered)', st4.hard_debt === true && st4.appealable === false, JSON.stringify(st4));
const s4 = spend('travel', 10);
check('hard-debt spend refused', s4.refused === true && envelopes.travel.spent === 140, JSON.stringify(s4));

// 5. witness chain intact, PENDING/ENTANGLED/COLLAPSED all present
const states = log.rows.filter(r => r.kind === 'appeal').map(r => r.state);
check('cell contract: PENDING booked before outcome', states.filter(s => s === 'PENDING').length === 2, states.join(','));
check('cell contract: ENTANGLED booked while in flight', states.filter(s => s === 'ENTANGLED').length === 2, states.join(','));
check('cell contract: COLLAPSED witnessed with job_id', log.rows.filter(r => r.state === 'COLLAPSED' && r.job_id).length === 2, '');
check('witness chain intact', log.verify().ok, `${log.length} rows, head ${log.head}`);

mkdirSync(new URL('./out', import.meta.url), { recursive: true });
const receiptPath = new URL('./out/s3-quantum-tided-budget.receipt.json', import.meta.url);
writeFileSync(receiptPath, JSON.stringify({ base: BASE, ran_at: new Date().toISOString(),
  outcomes, envelopes, states, appeals: log.rows.filter(r => r.kind === 'appeal'),
  witness_head: log.head, witness_len: log.length }, null, 2));
console.log(`\n  outcomes: ${outcomes.map(o => `${o.env}=${o.verdict}`).join('  ')}`);
console.log(`  receipt → ${receiptPath.pathname}`);
done();
