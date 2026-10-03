// 10 — pipeline-guard: a data pipeline whose schema is a FENCE, not a hope.
//
// Realm: data engineering / ETL.
// Engineer swap-in: rows arrive from Kafka/CDC/file drops; the dead-letter
// cell is your retry topic; the schema cells are editable data — version
// them, diff them, relax them in a code review. That last part is the point:
// most pipelines hide their schema in code; here it is on the sheet.
//
// What it demonstrates:
//   - declarative validation: field → {type, required, min, max}; every
//     rejection carries a PRECISE reason (field, rule, got)
//   - the dead-letter queue is just a cell — inspect, fix, replay
//   - schema evolution as data: relaxing a bound lets previously-rejected
//     rows through on replay, without touching validation code
//   - every row (accepted or refused) lands in the witness chain
//
// Runs fully offline.

import { sheet, WitnessLog, check, done, setTool, panel, kv, ANSI } from '../src/toolkit.mjs';

setTool('pipeline-guard');

const SCHEMA_V1 = {
  order_id: { type: 'string', required: true },
  amount:   { type: 'number', required: true, min: 0, max: 10000 },
  currency: { type: 'string', required: true, oneOf: ['USD', 'EUR', 'GBP'] },
  qty:      { type: 'number', required: true, min: 1, max: 100 },
};

const e = sheet('pipeline-guard', [
  { id: 'schema.version', kind: 'value', value: { v: 1, fields: SCHEMA_V1 }, description: 'the fence, as editable data' },

  { id: 'pipe.accepted', kind: 'value', value: [] },
  { id: 'pipe.deadletter', kind: 'value', value: [], description: 'rejected rows + precise reasons' },

  // stats are pure
  { id: 'stats.accepted', kind: 'formula', expr: 'pipe.accepted.length' },
  { id: 'stats.rejected', kind: 'formula', expr: 'pipe.deadletter.length' },
  { id: 'stats.total_amount', kind: 'formula', expr: 'pipe.accepted.reduce((s, r) => s + r.row.amount, 0)' },

  // the gate
  { id: 'pipe.ingest', kind: 'program', deps: [],
    description: 'validate → accept or dead-letter, with reasons',
    code: `
      const schema = (await runtime.get('schema.version')).data;
      const { row, src } = input ?? {};
      if (!row || typeof row !== 'object') return { refused: true, reason: 'not an object' };

      const reasons = [];
      for (const [field, rule] of Object.entries(schema.fields)) {
        const v = row[field];
        if (rule.required && (v === undefined || v === null || v === ''))
          { reasons.push({ field, rule: 'required', got: 'missing' }); continue; }
        if (v === undefined || v === null) continue;
        if (rule.type === 'number' && typeof v !== 'number')
          { reasons.push({ field, rule: 'type:number', got: typeof v }); continue; }
        if (rule.type === 'string' && typeof v !== 'string')
          { reasons.push({ field, rule: 'type:string', got: typeof v }); continue; }
        if (rule.oneOf && !rule.oneOf.includes(v))
          { reasons.push({ field, rule: 'oneOf:' + rule.oneOf.join('|'), got: String(v) }); continue; }
        if (rule.type === 'number') {
          if (rule.min !== undefined && v < rule.min) reasons.push({ field, rule: 'min:' + rule.min, got: v });
          if (rule.max !== undefined && v > rule.max) reasons.push({ field, rule: 'max:' + rule.max, got: v });
        }
      }

      if (reasons.length) {
        const dl = (await runtime.get('pipe.deadletter')).data;
        await runtime.set('pipe.deadletter', [...dl, { row, src: src ?? null, reasons, at: Date.now() }]);
        return { accepted: false, reasons };
      }
      const acc = (await runtime.get('pipe.accepted')).data;
      await runtime.set('pipe.accepted', [...acc, { row, src: src ?? null, at: Date.now() }]);
      return { accepted: true };
    ` },

  // replay: re-run the dead-letter through the CURRENT schema (v2 relax, etc.)
  { id: 'pipe.replay', kind: 'program', deps: [],
    description: 'retry every dead-lettered row against the current schema',
    code: `
      const dl = (await runtime.get('pipe.deadletter')).data;
      await runtime.set('pipe.deadletter', []);
      return { replayed: dl.length, rows: dl.map(d => d.row) };
    ` },
]);

console.log(`${ANSI.bold}pipeline-guard${ANSI.reset} — validation as visible data, dead-letters as recoverable cells\n`);

const log = new WitnessLog();
let eid = 0;
const ingest = async (row, src) => {
  const r = (await e.call('pipe.ingest', { row, src, eid: ++eid })).data;
  log.append({ op: r?.accepted ? 'accept' : 'reject', src: src ?? null, reasons: r?.reasons?.map(x => `${x.field}:${x.rule}`).join(',') ?? null });
  return r;
};

// ── the stream: 5 good rows, 4 bad in instructive ways ──
const rows = [
  { order_id: 'o-1001', amount: 129.9,  currency: 'USD', qty: 3 },
  { order_id: 'o-1002', amount: 54.2,   currency: 'EUR', qty: 1 },
  { order_id: 'o-1003', amount: '89.9', currency: 'USD', qty: 2 },    // amount as string
  { order_id: 'o-1004', amount: 14999,  currency: 'USD', qty: 1 },    // over max
  { order_id: 'o-1005', amount: 12,     currency: 'YEN', qty: 1 },     // currency not in oneOf
  { order_id: 'o-1006', amount: 7.5,    currency: 'GBP' },             // qty missing
  { order_id: 'o-1007', amount: 22,     currency: 'USD', qty: 40 },
  { order_id: 'o-1008', amount: 33.33,  currency: 'EUR', qty: 9 },
  { amount: 5, currency: 'USD', qty: 1 },                              // id missing entirely
];
for (const [i, row] of rows.entries()) await ingest(row, `kafka:orders:p${i}`);

panel('run 1 (schema v1)', [
  kv('accepted', `${(await e.get('stats.accepted')).data} rows, total $${(await e.get('stats.total_amount')).data.toFixed(2)}`),
  kv('dead-letter', `${(await e.get('stats.rejected')).data} rows`),
]);
check('4 clean rows accepted', (await e.get('stats.accepted')).data === 4);
check('5 bad rows dead-lettered', (await e.get('stats.rejected')).data === 5);

const dl = (await e.get('pipe.deadletter')).data;
check('rejections carry precise reasons', dl.every(d => d.reasons.length > 0 && d.reasons[0].field && d.reasons[0].rule),
  dl.map(d => `${d.src}: ${d.reasons.map(r => r.field + '/' + r.rule).join(', ')}`).join(' | '));
check('type error named the field and rule',
  dl.some(d => d.reasons.some(r => r.field === 'amount' && r.rule === 'type:number')));
check('range error named the bound',
  dl.some(d => d.reasons.some(r => r.field === 'amount' && r.rule === 'max:10000')));
check('oneOf error named the enum',
  dl.some(d => d.reasons.some(r => r.field === 'currency' && r.rule.startsWith('oneOf'))));

// ── schema evolution: v2 raises the amount ceiling (prices went up) ──
await e.set('schema.version', { v: 2, fields: { ...SCHEMA_V1, amount: { ...SCHEMA_V1.amount, max: 20000 } } });
const replay = (await e.call('pipe.replay', { eid: ++eid })).data;
for (const row of replay.rows) await ingest(row, 'replay');
panel('run 2 (schema v2 + replay)', [
  kv('accepted', `${(await e.get('stats.accepted')).data} rows, total $${(await e.get('stats.total_amount')).data.toFixed(2)}`),
  kv('dead-letter', `${(await e.get('stats.rejected')).data} rows`),
]);
check('replay recovered the over-ceiling row', (await e.get('stats.accepted')).data === 5,
  'the 14,999 order passes under v2 — schema changed as data, no deploy');
check('genuinely bad rows stayed dead', (await e.get('stats.rejected')).data === 4,
  'a schema relax is not an amnesty');

const v = log.verify();
check('witness chain sealed', v.ok, `${log.length} row events, head ${v.head.slice(0, 12)}…`);

done();
