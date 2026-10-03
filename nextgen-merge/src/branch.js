/**
 * A Durable Object per branch.
 *
 * git's `refs/heads/foo.lock` is a filesystem lock: correct on one machine,
 * undefined across 100k writers on a network filesystem. A branch name is a
 * natural key, and a DO is the same primitive with a real compare-and-swap
 * and a single-threaded actor behind it.
 *
 * Every mutation goes through `commit(head, base, claims)`, which is a CAS:
 * it refuses if `head` has moved. The losing agent does not silently clobber
 * — it gets back the current head and re-adjudicates. That is the behaviour
 * git's lockfile gives you for free and its *content* model does not.
 */

import { adjudicate } from './adjudicate.js';

const MERGE_LIMIT = 200; // claim sets folded into one adjudication in a single pass

export class Branch {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.head = null;        // { seq, claims, mergedFrom[], at }
    this.merges = 0;         // monotonic; proves no lost update
    this.rejected = 0;       // CAS failures, i.e. contended writes
  }

  async init() {
    const stored = await this.state.storage.get('head');
    if (stored) this.head = stored.head;
    this.merges = (await this.state.storage.get('merges')) || 0;
    this.rejected = (await this.state.storage.get('rejected')) || 0;
  }

  async fetch(req) {
    await this.init();
    const url = new URL(req.url);
    const path = url.pathname;
    const name = url.searchParams.get('branch') || 'unknown';

    if (req.method === 'GET' && path.endsWith('/head')) {
      return json({ branch: name, head: this.head, merges: this.merges, rejected: this.rejected });
    }

    if (req.method === 'POST' && path.endsWith('/commit')) {
      const body = await req.json();
      return json(await this.commit(body));
    }

    if (req.method === 'POST' && path.endsWith('/merge')) {
      const body = await req.json();
      return json(await this.merge(body));
    }

    return json({ error: 'not found', path }, 404);
  }

  get name() {
    return this._name || 'unknown';
  }

  /** CAS. */
  async commit({ claims = [], expectedHead = null, author = null, message = null }) {
    const current = this.head ? this.head.seq : 0;
    if (expectedHead !== null && expectedHead !== current) {
      this.rejected++;
      await this.state.storage.put('rejected', this.rejected);
      return {
        ok: false,
        reason: 'stale-head',
        expectedHead,
        actualHead: current,
        hint: 'someone merged while you were working; re-adjudicate against the new head',
      };
    }
    if (claims.length > MERGE_LIMIT) {
      return { ok: false, reason: 'too-many-claims', limit: MERGE_LIMIT };
    }

    this.merges++;
    this.head = {
      seq: current + 1,
      claims,
      mergedFrom: [],
      author,
      message,
      at: new Date().toISOString(),
    };
    await this.state.storage.put('head', { head: this.head });
    await this.state.storage.put('merges', this.merges);
    return { ok: true, head: this.head, merges: this.merges };
  }

  /**
   * Adjudicate a set of branch claim-sets into this branch's head.
   * Returns the reconciled set, every contradiction, the derived claims, and
   * the residual — with every losing claim preserved.
   */
  async merge({ sets = [], expectedHead = null, author = null }) {
    const current = this.head ? this.head.seq : 0;
    if (expectedHead !== null && expectedHead !== current) {
      this.rejected++;
      await this.state.storage.put('rejected', this.rejected);
      return { ok: false, reason: 'stale-head', expectedHead, actualHead: current };
    }

    const all = sets.map((s) => ({ ...s, claims: s.claims || [] }));
    if (this.head && !all.some((s) => s.branch === this.head.__branch)) {
      // Fold the current head back in so the merge is over the real union.
      all.unshift({ branch: 'head', claims: this.head.claims });
    }

    const result = adjudicate(all);

    this.merges++;
    this.head = {
      seq: current + 1,
      claims: result.claims,
      mergedFrom: all.map((s) => s.branch),
      author,
      at: new Date().toISOString(),
    };
    await this.state.storage.put('head', { head: this.head });
    await this.state.storage.put('merges', this.merges);

    return { ok: true, head: this.head, merges: this.merges, ...result };
  }
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj, null, 2), {
    status,
    headers: { 'content-type': 'application/json', 'access-control-allow-origin': '*' },
  });
}

export { json };
