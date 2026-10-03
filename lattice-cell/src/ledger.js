// lattice-cell — the dispatch ledger.
//
// THE ONE DEPARTURE FROM "THE COMMIT IS THE ONLY DURABLE ARTIFACT":
// a DISPATCH row is written and durably flushed BEFORE the cell executes.
//
// Rationale (lattice-RD.md §2): a commit is a POSITIVE artifact. A hash chain
// is total over the commits that exist and silent about the ones that do not,
// so "cell woke and disagreed" and "cell was dispatched and died" are the same
// observation: nothing. The ledger exists solely to make silence representable.
//
// It is an INTENT log, not a content log. It holds no diff, no file contents,
// and no claim about correctness — only that a unit of work was requested, and
// later, how it ended (or that it did not). Everything that describes *what
// was done* still lives in the commit, as the vision requires.
//
// The join key between the two planes is `dispatch_id`, which is written into
// the commit message. That is what makes reconciliation possible after total
// loss of this file: see protocol/LATTICE.md, invariant I6.

import { randomUUID } from 'node:crypto';

/** Statuses an outcome may take. REFUSED is a SUCCESS — the cell ran and said no. */
export const OUTCOMES = Object.freeze(['COMMIT', 'REFUSED', 'LOST', 'LEASE_EXPIRED']);
export const TERMINAL = Object.freeze(new Set(OUTCOMES));

/** Backends must be crash-honest: put() must not return until the bytes are
 *  recoverable by a process that dies immediately afterwards. */
export class MemStore {
  #m = new Map();
  async get(k) { return this.#m.has(k) ? this.#m.get(k) : null; }
  async put(k, v) { this.#m.set(k, JSON.stringify(v)); }   // DO storage: atomic
  async list(p) {
    const out = [];
    for (const [k, raw] of this.#m) if (k.startsWith(p)) out.push(JSON.parse(raw));
    return out.sort((a, b) => a.seq - b.seq);
  }
  async putBatch(entries) { for (const [k, v] of entries) this.#m.set(k, JSON.stringify(v)); }
}

export class FileStore {
  constructor(path) { this.path = path; this.#buf = new Map(); this.#dirty = false; }
  #buf; #dirty;
  async get(k) { return this.#buf.has(k) ? this.#buf.get(k) : null; }
  async put(k, v) { this.#buf.set(k, JSON.stringify(v)); this.#dirty = true; }
  async putBatch(entries) { for (const [k, v] of entries) { this.#buf.set(k, JSON.stringify(v)); this.#dirty = true; } }
  async list(p) {
    const out = [];
    for (const [k, raw] of this.#buf) if (k.startsWith(p)) out.push(JSON.parse(raw));
    return out.sort((a, b) => a.seq - b.seq);
  }
  /** Flush + fsync. This is the durability point that makes the ledger
   *  worth its cost: without it, a crash between dispatch and execute is
   *  exactly the hole the ledger exists to remove. */
  async sync() {
    if (!this.#dirty) return;
    const { writeFileSync, renameSync, openSync, fsyncSync, closeSync } = await import('node:fs');
    const tmp = this.path + '.tmp';
    writeFileSync(tmp, JSON.stringify(Object.fromEntries(this.#buf)));
    const fd = openSync(tmp, 'r'); fsyncSync(fd); closeSync(fd);
    renameSync(tmp, this.path);
    this.#dirty = false;
  }
  static async open(path) {
    const { existsSync, readFileSync, mkdirSync } = await import('node:fs');
    const { dirname } = await import('node:path');
    mkdirSync(dirname(path), { recursive: true });
    const s = new FileStore(path);
    if (existsSync(path)) for (const [k, v] of Object.entries(JSON.parse(readFileSync(path, 'utf8')))) s.#buf.set(k, v);
    return s;
  }
}

export class Ledger {
  constructor(store) { this.store = store; }

  static key(seq, kind, id) { return `${String(seq).padStart(12, '0')}:${kind}:${id}`; }

  async head() {
    const all = await this.store.list('0000000000');
    return all.length ? all[all.length - 1].seq + 1 : 0;
  }

  /** Pre-registered intent. MUST be synced before execute() is called. */
  async dispatch({ cell, intent, base, lease_ms, postcondition, induced_by = null }) {
    const seq = await this.head();
    const id = `d-${seq}-${randomUUID().slice(0, 8)}`;
    const row = {
      seq, kind: 'DISPATCH', id, cell, intent, base, lease_ms,
      postcondition: postcondition ?? null,   // a RELATION, not a prose claim — see LATTICE.md §4
      induced_by,                             // the id of the dispatch that provoked this one
      at: Date.now(),
    };
    await this.store.putBatch([[Ledger.key(seq, 'D', id), row]]);
    await this.store.sync?.();
    return row;
  }

  async outcome(id, status, detail = {}) {
    if (!TERMINAL.has(status)) throw new Error(`unknown outcome status: ${status}`);
    const dispatches = (await this.store.list('0000000000')).filter(r => r.kind === 'DISPATCH');
    const d = dispatches.find(r => r.id === id);
    if (!d) throw new Error(`I1 VIOLATION: outcome for unknown dispatch ${id}`);
    const seq = await this.head();
    const row = { seq, kind: 'OUTCOME', id, cell: d.cell, status, at: Date.now(), ...detail };
    await this.store.putBatch([[Ledger.key(seq, 'O', `${id}#${row.at}#${seq}`), row]]);
    await this.store.sync?.();
    return row;
  }

  async rows() { return this.store.list('0000000000'); }

  /** Reconciliation: rebuild what the ledger believes from what the repos
   *  actually contain. Returns outcomes the ledger did NOT record. */
  async unreconciled(tipsByCell) {
    const rows = await this.rows();
    const settled = new Set(rows.filter(r => r.kind === 'OUTCOME').map(r => r.id));
    const out = [];
    for (const r of rows.filter(r => r.kind === 'DISPATCH' && !settled.has(r.id))) {
      out.push({ dispatch: r, tip: tipsByCell[r.cell] ?? null });
    }
    return out;
  }
}
