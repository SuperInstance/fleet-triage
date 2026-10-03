// 03 — ocean-recall: a team memory that makes answers cheaper, as a sheet.
//
// Realm: knowledge management / personal AI memory.
// Engineer swap-in: replace localEmbed with a real embedding endpoint (the
// adapter contract is one function: text → vector); replace the memory cell
// with your store. The recall policy — threshold, receipts, stats — is the
// sheet, visible and editable.
//
// The discipline it implements is the fleet's tidepool/Ocean idiom:
//   remember at task end, recall at task start, absence is information,
//   forgetting is an event too — and every remember/recall/forget lands in
//   a hash-chained witness log, so the memory's own history is auditable.
//
// Runs fully offline (deterministic embedder, one geometry). No model, no
// network, no excuses — this is the whole product in ~90 lines of sheet.

import { sheet, WitnessLog, localEmbed, cosine, check, done, setTool, panel, kv, ANSI } from '../src/toolkit.mjs';

setTool('ocean-recall');

const e = sheet('ocean-recall', [
  { id: 'config.threshold', kind: 'value', value: 0.35, description: 'recall hit threshold — tuned to this geometry (a BGE deployment would sit near 0.92)' },

  { id: 'ocean.memory', kind: 'value', value: [], description: 'the memory: [{id, text, vec, meta, ts}]' },

  { id: 'ocean.remember', kind: 'program', deps: [],
    description: 'store a note + its vector (refuses duplicates by id)',
    code: `
      const { id, text, meta, vec } = input ?? {};
      if (!id || !text || !vec) return { refused: true, reason: 'remember requires id+text+vec' };
      const memory = (await runtime.get('ocean.memory')).data;
      if (memory.some(m => m.id === id)) return { refused: true, reason: 'id already remembered: ' + JSON.stringify(id) };
      await runtime.set('ocean.memory', [...memory, { id, text, vec, meta: meta ?? null, ts: Date.now() }]);
      return { remembered: id, size: memory.length + 1 };
    ` },

  { id: 'ocean.recall', kind: 'program', deps: [],
    description: 'the only read path: embed → cosine scan → best above threshold, or honest miss',
    code: `
      const cosine = (a, b) => a.reduce((s, x, i) => s + x * b[i], 0);
      const { query, vec } = input ?? {};
      if (!query || !vec) return { refused: true, reason: 'recall requires query+vec' };
      const threshold = (await runtime.get('config.threshold')).data;
      const memory = (await runtime.get('ocean.memory')).data;
      let best = { sim: 0, idx: -1 };
      memory.forEach((m, idx) => { const sim = cosine(m.vec, vec); if (sim > best.sim) best = { sim, idx }; });
      if (best.idx < 0 || best.sim < threshold)
        return { hit: false, query, sim: Number(best.sim.toFixed(4)), note: 'absence is information' };
      const m = memory[best.idx];
      return { hit: true, query, sim: Number(best.sim.toFixed(4)), id: m.id, text: m.text, meta: m.meta };
    ` },

  { id: 'ocean.forget', kind: 'program', deps: [],
    description: 'forget by id — a witnessed event, not a silent delete',
    code: `
      const { id } = input ?? {};
      const memory = (await runtime.get('ocean.memory')).data;
      const next = memory.filter(m => m.id !== id);
      if (next.length === memory.length) return { refused: true, reason: 'nothing remembered as ' + JSON.stringify(id) };
      await runtime.set('ocean.memory', next);
      return { forgot: id, size: next.length };
    ` },

  // live counters
  { id: 'ocean.size', kind: 'formula', expr: 'ocean.memory.length' },
]);

console.log(`${ANSI.bold}ocean-recall${ANSI.reset} — remember / recall / forget, with an auditable memory\n`);

const log = new WitnessLog();
let eid = 0;   // ops carry event ids: reads are pure and cacheable, ops are not
const remember = async (id, text, meta) => {
  const r = (await e.call('ocean.remember', { id, text, meta, vec: localEmbed(text), eid: ++eid })).data;
  log.append({ op: 'remember', id, size: r?.size ?? null, refused: !!r?.refused });
  return r;
};
const recall = async query => {
  const vec = localEmbed(query);
  const r = (await e.call('ocean.recall', { query, vec, eid: ++eid })).data;
  log.append({ op: 'recall', query, hit: !!r?.hit, sim: r?.sim ?? null, id: r?.id ?? null });
  return r;
};
const forget = async id => {
  const r = (await e.call('ocean.forget', { id, eid: ++eid })).data;
  log.append({ op: 'forget', id, refused: !!r?.refused });
  return r;
};

// ── a team remembers what it learned ──
await remember('arch-001', 'we chose postgres over mongo because the access pattern is strongly relational', { tag: 'adr' });
await remember('arch-002', 'the billing worker must be idempotent: stripe webhooks retry for 72 hours', { tag: 'lesson' });
await remember('ops-001', 'the eu region deploy freezes during the sunday maintenance window', { tag: 'ops' });

panel('memory', [
  kv('size', `${(await e.get('ocean.size')).data} notes`),
  kv('geometry', 'local deterministic embed (64-d), one geometry'),
]);

// ── recall: exact, paraphrase, unrelated ──
const r1 = await recall('why did we pick postgres instead of mongo?');
check('exact-substance recall hits', r1.hit === true && r1.id === 'arch-001', `sim=${r1.sim}`);

const r2 = await recall('is the billing worker safe when stripe retries?');
check('paraphrase recall hits', r2.hit === true && r2.id === 'arch-002', `sim=${r2.sim}`);

const r3 = await recall('what wine pairs with salmon?');
check('unrelated query honestly misses', r3.hit === false, `sim=${r3.sim} < threshold — absence is information`);

// ── forgetting is a witnessed event ──
const f1 = await forget('arch-001');
check('forget removes the note', f1.forgot === 'arch-001' && (await e.get('ocean.size')).data === 2);
const f2 = await forget('arch-001');
check('double forget refuses honestly', f2.refused === true, f2.reason);

const r4 = await recall('why did we pick postgres instead of mongo?');
check('forgotten note is gone from recall', r4.hit === false, `sim=${r4.sim}`);

// ── the memory's own history is sealed ──
const v = log.verify();
panel('witness ledger', [
  kv('entries', log.length),
  kv('ops', log.rows.map(r => r.op[0]).join('')),   // r/r/f fingerprint
  kv('head', v.head),
]);
check('witness chain sealed', v.ok, `${log.length} memory operations, head ${v.head.slice(0, 12)}…`);

done();
