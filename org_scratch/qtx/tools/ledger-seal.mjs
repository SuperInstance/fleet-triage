// 02 — ledger-seal: a tamper-evident audit ledger that lives in a sheet.
//
// Realm: security / compliance / bookkeeping.
// Engineer swap-in: replace the append/verify program cells with your storage
// (SQLite, S3 object-lock, blockchain-lite); keep the cell model — the audit
// QUERY surface and the tamper alarm are the part worth keeping.
//
// The claim it demonstrates: an append-only log where every row carries
// fnv1a64(prev_hash + canonical row) makes silent edits *detectable* — and
// the verifier pins the exact row where the chain breaks. That is the whole
// product: WORM semantics without special hardware, ~60 lines.
//
// The clever bit vs. a hand-rolled chain: the ledger IS sheet state, so
// queries, redaction policies and retention rules are formulas/programs
// watching the same dependency graph — no separate audit framework.

import { sheet, WitnessLog, verifyChain, fnv1a64, canon, check, done, setTool, panel, kv, ANSI } from '../src/toolkit.mjs';

setTool('ledger-seal');

// ── the sheet: append + query, with the ledger as reactive state ────────────
const e = sheet('ledger-seal', [
  { id: 'ledger.rows', kind: 'value', value: [], description: 'the append-only witness chain' },

  // retention policy as a formula: everything older than 90d may archive
  { id: 'policy.archive_cutoff', kind: 'value', value: 90 * 24 * 3600 * 1000 },

  { id: 'ledger.append', kind: 'program', deps: [],
    description: 'appends a hash-sealed row; refuses rows without actor+action',
    code: `
      const fnv1a64 = (input) => {
        let h = 0xcbf29ce484222325n;
        const prime = 0x100000001b3n, mask = 0xffffffffffffffffn;
        for (let i = 0; i < input.length; i++) { h ^= BigInt(input.charCodeAt(i)); h = (h * prime) & mask; }
        return h.toString(16).padStart(16, '0');
      };
      const canon = (row) => { const s = {}; for (const k of Object.keys(row).sort()) s[k] = row[k]; return JSON.stringify(s); };

      const { actor, action, payload } = input ?? {};
      if (!actor || !action) return { refused: true, reason: 'rows require actor+action' };  // the fence
      const rows = (await runtime.get('ledger.rows')).data;
      const prev = rows[rows.length - 1] ?? null;
      const seq = prev ? prev.seq + 1 : 0;
      const prev_hash = prev ? prev.row_hash : '0'.repeat(16);
      const fields = { action, actor, payload: payload ?? null, prev_hash, seq, ts: Date.now() };
      const row = { ...fields, row_hash: fnv1a64(canon(fields)) };
      await runtime.set('ledger.rows', [...rows, row]);
      return { seq, row_hash: row.row_hash };
    ` },

  { id: 'ledger.query', kind: 'program', deps: [],
    description: 'audit query: filter by actor/action, verify while reading',
    code: `
      const { actor, action } = input ?? {};
      const rows = (await runtime.get('ledger.rows')).data;
      return rows.filter(r =>
        (!actor || r.actor === actor) && (!action || r.action === action));
    ` },

  { id: 'ledger.verify', kind: 'program', deps: [],
    description: 're-derive every row_hash; pin the first broken link',
    code: `
      const fnv1a64 = (input) => {
        let h = 0xcbf29ce484222325n;
        const prime = 0x100000001b3n, mask = 0xffffffffffffffffn;
        for (let i = 0; i < input.length; i++) { h ^= BigInt(input.charCodeAt(i)); h = (h * prime) & mask; }
        return h.toString(16).padStart(16, '0');
      };
      const canon = (row) => { const s = {}; for (const k of Object.keys(row).sort()) s[k] = row[k]; return JSON.stringify(s); };
      const rows = (await runtime.get('ledger.rows')).data;
      let prevHash = '0'.repeat(16);
      for (let i = 0; i < rows.length; i++) {
        const { row_hash, ...rest } = rows[i];
        if (rows[i].seq !== i || rows[i].prev_hash !== prevHash || fnv1a64(canon(rest)) !== row_hash)
          return { ok: false, brokenAt: i, detail: 'chain re-derivation mismatch' };
        prevHash = rows[i].row_hash;
      }
      return { ok: true, count: rows.length, head: prevHash };
    ` },
]);

console.log(`${ANSI.bold}ledger-seal${ANSI.reset} — append-only witness ledger + tamper alarm + audit queries\n`);

// Every append carries a unique event id (eid): audit best practice, and
// it makes each call's memo key distinct — the engine serves identical
// (context, input) pairs from cache, which is exactly what you want for
// reads and exactly what an append must avoid.
let eid = 0;
const callAppend = payload => e.call('ledger.append', { ...payload, eid: ++eid });

// ── a short, realistic audit story ──
await callAppend({ actor: 'alice',   action: 'grant.role',   payload: { role: 'admin', to: 'bob' } });
await callAppend({ actor: 'bob',     action: 'read.secret',  payload: { key: 'prod/db/password' } });
await callAppend({ actor: 'mallory', action: 'login.failed', payload: { attempts: 5 } });
await callAppend({ actor: 'alice',   action: 'revoke.role',  payload: { role: 'admin', from: 'mallory' } });
await callAppend({ actor: 'bob',     action: 'read.secret',  payload: { key: 'prod/db/password' } });

const rows = (await e.get('ledger.rows')).data;
check('append fence: 5 clean rows accepted', rows.length === 5);
const refused = await callAppend({ actor: '', action: 'nope' });  // eid++ keeps it out of append's memo too
check('append fence rejects actorless rows', refused.data?.refused === true, refused.data?.reason);

// audit queries are just programs over the same reactive state
const bobReads = (await e.call('ledger.query', { actor: 'bob', action: 'read.secret' })).data;
check('audit query: bob read the secret twice', bobReads.length === 2, `seqs ${bobReads.map(r => r.seq).join(',')}`);

const v0 = (await e.call('ledger.verify', { phase: 'clean' })).data;
check('chain verifies clean', v0.ok === true, `${v0.count} rows, head ${v0.head.slice(0, 12)}…`);
panel('clean ledger', [
  kv('rows', v0.count),
  kv('head', v0.head),
  kv('verdict', `${ANSI.green}SEALED${ANSI.reset}`),
]);

// ── the tamper: a storage-level silent edit (what an attacker hopes is invisible) ──
const tampered = JSON.parse(JSON.stringify(rows));
tampered[2].payload.attempts = 1;              // "he only tried once, your honor"
tampered[2].ts -= 86400000;                    // and yesterday, not today
await e.set('ledger.rows', tampered);

const v1 = (await e.call('ledger.verify', { phase: 'after-tamper' })).data;
panel('tamper alarm', [
  kv('edit', 'row seq=2: attempts 5→1, ts −1d (silent)'),
  kv('verdict', v1.ok ? `${ANSI.green}SEALED (?!)` : `${ANSI.red}TAMPER DETECTED${ANSI.reset}`),
  kv('broken at', v1.ok ? '—' : `seq=${v1.brokenAt}`),
]);
check('tamper detected at exactly the edited row', v1.ok === false && v1.brokenAt === 2,
  `verifier pinned seq=${v1.brokenAt}`);

// restoration heals the chain — nothing to reconcile by hand
await e.set('ledger.rows', rows);
const v2 = (await e.call('ledger.verify', { phase: 'restored' })).data;
check('restore heals the chain', v2.ok === true, `head ${v2.head.slice(0, 12)}…`);

done();
