// lattice-cell — one Durable Object per (lattice, cell).
//
// Why a DO and not a filesystem lock: a branch name is a natural key and the
// contention is per-branch, so the serializable unit is the branch. A DO gives
// input-gate serialization for free — no two events for the same cell are ever
// in flight, which is exactly the property a lockfile has to buy and exactly
// the property git cannot give you across 477 repos.
//
// The DO is NOT the record. It is a lease table. It is allowed to be lost —
// see I6, which reconstructs it from commits carrying `Dispatch-Id:`. The
// design does not depend on the DO surviving, and that is the point: a
// substrate you cannot lose is a substrate you cannot use for anything new.

import { Ledger, MemStore, OUTCOMES } from './ledger.js';

export class CellLedger {
  constructor(state, env) { this.state = state; this.env = env; }

  async fetch(req) {
    const url = new URL(req.url);
    const op = url.pathname.replace(/^\/cell\//, '').replace(/\/$/, '');

    if (op === 'reap') {
      // The only thing in the lattice that produces a NEGATIVE receipt.
      // Sweeping expired leases turns "silence" from an unobservable into a
      // recorded LEASE_EXPIRED. A quorum cannot do this: a cell that did not
      // wake is not correlated with one that did, so presence is a liveness
      // fact and needs no independence argument at all.
      const now = Date.now();
      const rows = await new Ledger(new MemStoreProxy(this.state)).rows();
      const settled = new Set(rows.filter(r => r.kind === 'OUTCOME').map(r => r.id));
      const expired = [];
      for (const d of rows.filter(r => r.kind === 'DISPATCH' && !settled.has(r.id))) {
        if (now - d.at > d.lease_ms) {
          await new Ledger(new MemStoreProxy(this.state)).outcome(d.id, 'LEASE_EXPIRED', { at: now });
          expired.push(d.id);
        }
      }
      return Response.json({ expired, swept: now });
    }

    const ledger = new Ledger(new MemStoreProxy(this.state));
    if (op === 'dispatch') {
      const body = await req.json();
      return Response.json(await ledger.dispatch(body));
    }
    if (op === 'outcome') {
      const { id, status, ...detail } = await req.json();
      if (!OUTCOMES.includes(status)) return new Response('bad status', { status: 400 });
      return Response.json(await ledger.outcome(id, status, detail));
    }
    if (op === 'rows') return Response.json(await ledger.rows());
    return new Response('not found', { status: 404 });
  }
}

// Durable Object storage already gives atomic put + the durability point.
// MemStore.sync() is a no-op here for exactly that reason.
class MemStoreProxy {
  constructor(state) { this.state = state; }
  #cache = new Map();
  async get(k) {
    if (this.#cache.has(k)) return this.#cache.get(k);
    const v = await this.state.storage.get(k);
    if (v) this.#cache.set(k, v);
    return v ?? null;
  }
  async put(k, v) { this.#cache.set(k, v); await this.state.storage.put(k, v); }
  async putBatch(e) { for (const [k, v] of e) await this.put(k, v); }
  async list(p) {
    const all = await this.state.storage.list({ prefix: p });
    return Object.values(all).map(v => JSON.parse(v)).sort((a, b) => a.seq - b.seq);
  }
  async sync() { /* storage.put is already durable on return */ }
}
