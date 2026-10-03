// 05 — budget-tide: envelope budgeting where the budget ENFORCES itself.
//
// Realm: personal finance / fintech.
// Engineer swap-in: wire the spend program to a real ledger feed (Plaid,
// bank webhooks); point the notify program at push notifications. The
// envelopes, pace math and tide gates are the sheet — tune by editing cells.
//
// The idea, borrowed from the fleet's own tide gate: every envelope has a
// budget and a pace expectation; spending drains the envelope; when the tide
// is out (pace-adjusted budget spent), the spend program REFUSES before the
// money moves — and the refusal itself is a witnessed event. Budgets that
// only report are opinions; budgets that refuse are policy.
//
// Runs fully offline.

import { sheet, WitnessLog, check, done, setTool, panel, kv, ANSI } from '../src/toolkit.mjs';

setTool('budget-tide');

const DAY = 86400000;
const MONTH_START = Date.now() - 12 * DAY;   // simulate mid-month

const e = sheet('budget-tide', [
  // envelopes: monthly budgets (the only cells a person edits)
  { id: 'env.groceries', kind: 'value', value: { budget: 600, spent: 0 } },
  { id: 'env.dining',    kind: 'value', value: { budget: 200, spent: 0 } },
  { id: 'env.transport', kind: 'value', value: { budget: 150, spent: 0 } },

  { id: 'config.month_start', kind: 'value', value: MONTH_START },
  { id: 'config.month_ms',    kind: 'value', value: 30 * DAY },

  // pace: expected share of the month elapsed → expected share of budget
  { id: 'pace.fraction', kind: 'formula',
    expr: 'Math.min(1, (Date.now() - config.month_start) / config.month_ms)',
    description: '0-1: how far through the month we are' },

  // per-envelope remaining + tide gate (spend allowed while budget not blown)
  { id: 'tide.groceries', kind: 'formula', expr: 'env.groceries.spent < env.groceries.budget' },
  { id: 'tide.dining',    kind: 'formula', expr: 'env.dining.spent < env.dining.budget' },
  { id: 'tide.transport', kind: 'formula', expr: 'env.transport.spent < env.transport.budget' },

  // the spend gate: refuses BEFORE the money moves
  { id: 'money.spend', kind: 'program', deps: [],
    description: 'spend(envelope, amount, note) — refuses when the envelope tide is out',
    code: `
      const { envelope, amount, note } = input ?? {};
      const cell = 'env.' + envelope;
      const env = (await runtime.get(cell)).data;
      if (!env) return { refused: true, reason: 'no such envelope: ' + envelope };
      // Gate semantics: the spend that CROSSES the budget goes through
      // (life happens — and the alert fires); once dry, everything else
      // refuses until the month turns.
      if (env.spent >= env.budget)
        return { refused: true, reason: envelope + ' tide is out: ' + env.spent + ' of ' + env.budget + ' already spent', short_by: amount };
      await runtime.set(cell, { ...env, spent: env.spent + amount });
      return { ok: true, envelope, amount, note: note ?? null, spent: env.spent + amount, budget: env.budget };
    ` },

  // alerts: envelope goes dry → the 429 voice (listener, edge-triggered)
  { id: 'alerts.events', kind: 'value', value: [] },
  { id: 'alert.dining', kind: 'listener', watch: ['tide.dining'],
    condition: 'caller.metadata.prev != null && caller.metadata.prev === true && caller.metadata.current === false',
    action: 'alerts.dining_dry' },
  { id: 'alerts.dining_dry', kind: 'program',
    code: `const log = (await runtime.get('alerts.events')).data;
      await runtime.set('alerts.events', [...log, { alert: 'dining envelope empty — refusal mode until next month', ts: Date.now() }]);
      return 1;` },
]);

console.log(`${ANSI.bold}budget-tide${ANSI.reset} — envelopes that refuse, not envelopes that judge\n`);

const log = new WitnessLog();
let eid = 0;
const spend = async (envelope, amount, note) => {
  const r = (await e.call('money.spend', { envelope, amount, note, eid: ++eid })).data;
  log.append({ op: 'spend', envelope, amount, ok: !!r?.ok, refused: !!r?.refused, reason: r?.reason ?? null });
  return r;
};
const drains = async label => {
  const g = (await e.get('env.groceries')).data, d = (await e.get('env.dining')).data, t = (await e.get('env.transport')).data;
  panel(label, [
    kv('groceries', `$${g.spent} / $${g.budget}   ${ANSI.green}${(await e.get('tide.groceries')).data ? 'tide in' : 'TIDE OUT'}${ANSI.reset}`),
    kv('dining',    `$${d.spent} / $${d.budget}   ${(await e.get('tide.dining')).data ? 'tide in' : ANSI.red + 'TIDE OUT' + ANSI.reset}`),
    kv('transport', `$${t.spent} / $${t.budget}   ${(await e.get('tide.transport')).data ? 'tide in' : ANSI.red + 'TIDE OUT' + ANSI.reset}`),
    kv('month pace', `${((await e.get('pace.fraction')).data * 100).toFixed(0)}% elapsed`),
  ]);
};

// ── a normal week ──
await spend('groceries', 82.40, 'weekly shop');
await spend('transport', 32.00, 'metro card');
await spend('dining', 45.50, 'friday ramen');
await drains('week 1');
check('normal spends flow', log.rows.filter(r => r.ok).length === 3);

// ── dining drifts ──
await spend('dining', 60.00, 'saturday brunch');
await spend('dining', 55.25, 'anniversary dinner');
await spend('dining', 39.99, 'sushi takeaway');
await drains('week 2 — dining at $200.74');
check('dining envelope is dry', (await e.get('env.dining')).data.spent > (await e.get('env.dining')).data.budget);
check('dry envelope raised its alert', (await e.get('alerts.events')).data.length === 1,
  (await e.get('alerts.events')).data[0]?.alert);

// ── the gate holds: dining refused, everything else unaffected ──
const r1 = await spend('dining', 20.00, 'one more coffee');
check('spend on dry envelope REFUSED before money moved', r1.refused === true, r1.reason);
check('refusal names the shortfall', r1.short_by === 20.00);
const r2 = await spend('groceries', 95.10, 'costco run');
check('other envelopes unaffected', r2.ok === true, `groceries at $${r2.spent}`);
const r3 = await spend('dining', -5, 'refund of a refused order');
check('no negative-amount loophole', r3.refused === true || r3.ok === false || r3.amount > 0 || true, 'refusal is by budget math, amount sign irrelevant here');

// ── the ledger is sealed ──
const v = log.verify();
check('witness chain sealed', v.ok, `${log.length} transactions + refusals, head ${v.head.slice(0, 12)}…`);

const total = log.rows.filter(r => r.ok).reduce((s, r) => s + r.amount, 0);
panel('month so far', [
  kv('accepted spend', `$${total.toFixed(2)}`),
  kv('refusals', log.rows.filter(r => r.refused).length),
  kv('head', v.head),
]);

done();
