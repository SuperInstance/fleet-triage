// 08 — approvals: one sheet, many tenants, policies that know who's asking.
//
// Realm: SaaS workflow / multi-tenant backends.
// Engineer swap-in: identity comes from your auth (JWT claims → identity
// tags); the approval programs are the seam to your notification system.
// The policy cells are the product — edit thresholds without a deploy.
//
// What it demonstrates (all verified in play-testing):
//   - caller-context routing: the SAME sheet serves every tenant with
//     different policy answers, memoized per (tenant, input)
//   - tenant isolation: approver programs check caller.identity — cross-
//     tenant approvals are refused at the cell, not the UI
//   - policy per tier: premium self-approves small spends; standard needs
//     a human far earlier — same cells, different caller
//   - every decision lands in one hash-chained audit trail
//
// Runs fully offline.

import { sheet, WitnessLog, check, done, setTool, panel, kv, ANSI } from '../src/toolkit.mjs';

setTool('approvals');

const TENANTS = {
  acme:   { id: 'acme',   tags: ['tenant:acme',   'tier:premium'] },
  globex: { id: 'globex', tags: ['tenant:globex', 'tier:standard'] },
  initech: { id: 'initech', tags: ['tenant:initech', 'tier:standard'] },
};

const e = sheet('approvals', [
  // shared state
  { id: 'req.queue', kind: 'value', value: [], description: 'pending approval requests' },
  { id: 'req.decided', kind: 'value', value: [], description: 'decided requests' },
  { id: 'config.premium_self', kind: 'value', value: 5000, description: 'premium auto-approve ceiling, USD' },
  { id: 'config.standard_self', kind: 'value', value: 500, description: 'standard auto-approve ceiling, USD' },

  // policy: evaluated PER CALLER — same cells, different answers per tenant.
  // Caller-dependent policy must live in PROGRAMS: formulas are functions of
  // cells only, and `caller` is not in a formula's scope. (Patch 11 threads
  // the asking tenant's context into nested runtime.get/call — so these
  // programs see the caller, not a blank context.)
  { id: 'policy.ceiling', kind: 'program', deps: [],
    description: 'auto-approve ceiling for the asking tenant',
    code: 'const premium = (await runtime.get("config.premium_self")).data; const standard = (await runtime.get("config.standard_self")).data; return caller.identity.tags.includes("tier:premium") ? premium : standard;' },
  { id: 'policy.check', kind: 'program', deps: [],
    description: 'does this amount auto-approve for the asking tenant?',
    code: 'const amount = input?.amount; const ceiling = (await runtime.call("policy.ceiling")).data; return { auto: amount <= ceiling, ceiling };' },

  // submit: any tenant may file
  { id: 'flow.submit', kind: 'program', deps: [],
    description: 'file a spend request; policy auto-decides small ones per tier',
    code: `
      const { rid, amount, purpose } = input ?? {};
      if (!rid || !(amount > 0)) return { refused: true, reason: 'requests need rid + positive amount' };
      const verdict = (await runtime.call('policy.check', { amount })).data;   // ctx threads (patch 11)
      const auto = verdict?.auto;
      const ceiling = verdict?.ceiling;
      const req = { rid, amount, purpose: purpose ?? '', tenant: caller.identity.id, auto, ceiling };
      if (auto) {
        const d = (await runtime.get('req.decided')).data;
        await runtime.set('req.decided', [...d, { ...req, decision: 'auto-approved', by: 'policy' }]);
        return { rid, decision: 'auto-approved', ceiling };
      }
      const q = (await runtime.get('req.queue')).data;
      await runtime.set('req.queue', [...q, req]);
      return { rid, decision: 'human-review', ceiling };
    ` },

  // approve: only the request's own tenant may act — the fence
  { id: 'flow.approve', kind: 'program', deps: [],
    description: 'approve a queued request; identity must match the request tenant',
    code: `
      const { rid } = input ?? {};
      const q = (await runtime.get('req.queue')).data;
      const req = q.find(r => r.rid === rid);
      if (!req) return { refused: true, reason: 'no such pending request: ' + rid };
      if (req.tenant !== caller.identity.id)
        return { refused: true, reason: 'cross-tenant approval: ' + caller.identity.id + ' cannot approve ' + req.tenant + ' requests' };
      await runtime.set('req.queue', q.filter(r => r.rid !== rid));
      const d = (await runtime.get('req.decided')).data;
      await runtime.set('req.decided', [...d, { ...req, decision: 'approved', by: caller.identity.id }]);
      return { rid, decision: 'approved', by: caller.identity.id };
    ` },
]);

console.log(`${ANSI.bold}approvals${ANSI.reset} — one sheet, three tenants, policies that know who's asking\n`);

const log = new WitnessLog();
let eid = 0;
const ctxOf = t => ({ identity: TENANTS[t], ts: Date.now() });   // CallerContext shape: { identity: {id, tags} }
const submit = async (tenant, req) => {
  const r = (await e.call('flow.submit', { ...req, eid: ++eid }, ctxOf(tenant))).data;
  log.append({ op: 'submit', tenant, rid: req.rid, decision: r?.decision ?? 'refused' });
  return r;
};
const approve = async (tenant, rid) => {
  const r = (await e.call('flow.approve', { rid, eid: ++eid }, ctxOf(tenant))).data;
  log.append({ op: 'approve', tenant, rid, decision: r?.decision ?? 'refused' });
  return r;
};
const queue = async () => (await e.get('req.queue')).data;
const decided = async () => (await e.get('req.decided')).data;

// ── the same request, three tenants, three answers ──
const verdictFor = async (tenant, amount) => (await e.call('policy.check', { amount }, ctxOf(tenant))).data;
const va = await verdictFor('acme', 2400), vg = await verdictFor('globex', 2400);
panel('policy: $2,400 spend, same sheet', [
  kv('acme (premium)', `ceiling $${va.ceiling} — auto: ${va.auto}`),
  kv('globex (standard)', `ceiling $${vg.ceiling} — auto: ${vg.auto}`),
]);
check('premium tier self-approves $2,400', va.auto === true && va.ceiling === 5000, `ceiling $${va.ceiling}`);
check('standard tier routes $2,400 to a human', vg.auto === false && vg.ceiling === 500, `ceiling $${vg.ceiling}`);

// ── the flow ──
const r1 = await submit('acme', { rid: 'A-1', amount: 2400, purpose: 'sponsor booth' });
check('acme files $2,400 → auto-approved', r1.decision === 'auto-approved', `ceiling $${r1.ceiling}`);
const r2 = await submit('globex', { rid: 'G-1', amount: 2400, purpose: 'sponsor booth' });
check('globex files $2,400 → human review', r2.decision === 'human-review', 'same sheet, same request, different policy');
const r3 = await submit('globex', { rid: 'G-2', amount: 120, purpose: 'team lunch' });
check('globex small spend still self-approves', r3.decision === 'auto-approved', `ceiling $${r3.ceiling}`);

// ── the fence: cross-tenant approval refused at the cell ──
const sneaky = await approve('initech', 'G-1');
check('cross-tenant approval REFUSED', sneaky.refused === true, sneaky.reason);
const legit = await approve('globex', 'G-1');
check('own-tenant approval works', legit.decision === 'approved', `by ${legit.by}`);
check('approved request left the queue', (await queue()).find(r => r.rid === 'G-1') === undefined);

// ── audit trail ──
const d = await decided();
panel('decided ledger', [
  ...d.map(x => kv(x.rid, `${x.tenant} $${x.amount} → ${x.decision}${x.by === 'policy' ? '' : ' by ' + x.by}`)),
]);
const v = log.verify();
check('witness chain sealed', v.ok, `${log.length} flow events, head ${v.head.slice(0, 12)}…`);

done();
