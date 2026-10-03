// lattice-cell — the Worker entry.
//
// Ephemeral execution armor, taken literally: this module holds no state, has
// no warm path, and keeps nothing between invocations. Everything it needs it
// either writes to the ledger (before work) or pushes to git (after work).
//
// UNTESTED IN DEPLOYMENT FROM THIS LANE. There is no CLOUDFLARE_TOKEN in the
// R&D sandbox and `wrangler whoami` reports "You are not authenticated", so
// this file has been executed under the local harness (which uses the SAME
// src/cell.js) and never on a real edge. Per ORIENTATION.md a failed fetch is
// UNVERIFIABLE, not false — and this is an honest gap, not a green check.
// Deploy command is in README.md and is the first thing to run with a token.

import { run, reconcile } from './cell.js';
import { Ledger, FileStore } from './ledger.js';

const DO = (env, cell) => env.CELL_LEDGER.get(env.CELL_LEDGER.idFromName(cell));

async function dispatchOn(env, req) {
  const job = await req.json();
  const { cell, intent, base, postcondition, induced_by, lease_ms } = job;
  const d = await (await DO(env, cell).fetch('https://do/cell/dispatch', {
    method: 'POST', body: JSON.stringify({ cell, intent, base, lease_ms, postcondition, induced_by }),
  })).json();
  return { dispatch: d, commit_url: `${new URL(req.url).origin}/commit/${d.id}` };
}

export default {
  // The cell is woken by a webhook (a push to the lattice hub), and returns
  // IMMEDIATELY with the dispatch id. The work is then done by a follow-up
  // call to /commit/<id>, so a slow or dead cell never holds the webhook open
  // and the caller is never left guessing whether the work was accepted.
  async fetch(req, env, ctx) {
    const u = new URL(req.url);
    const p = u.pathname;

    if (req.method === 'POST' && p === '/wake')      return Response.json(await dispatchOn(env, req));
    if (req.method === 'POST' && p === '/reap') {
      const cells = await env.CELLS.list();
      const out = [];
      for (const c of cells) out.push(await (await DO(env, c).fetch('https://do/cell/reap')).json());
      return Response.json({ cells: out });
    }
    if (p.startsWith('/commit/')) {
      const id = p.split('/').pop();
      const plan = await (await env.PLAN.get(id, 'json')).json();
      return Response.json(await run({ ...plan, env }));
    }
    if (p === '/reconcile') {
      // Reconstructs the ledger from Plane A. This is the operation that makes
      // a lost ledger a non-event, and it is the reason the DO can be treated
      // as a cache: nothing here depends on the DO having survived.
      return Response.json(await reconcile({ repo: u.searchParams.get('repo'), ledgerPath: u.searchParams.get('ledger') }));
    }
    if (p === '/rows') {
      const cell = u.searchParams.get('cell');
      return Response.json(await (await DO(env, cell).fetch('https://do/cell/rows')).json());
    }
    if (p === '/health') return Response.json({ ok: true, planeA: 'git', planeB: 'durable-object', durable: ['planeA'] });
    return new Response('lattice-cell', { status: 404 });
  },

  async queue(batch, env) {
    for (const msg of batch.messages) {
      const job = msg.body;
      const r = await run({ ...job, env });
      msg.ack();
      if (r.outcome.status === 'COMMIT') env.LATTICE.dispatchAsync({ kind: 'broadcast', cell: job.cell, tip: r.tip });
    }
  },
};

export { Ledger, FileStore };
