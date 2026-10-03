// 01 — fleet-pager: golden-signal incident paging as a quilt sheet.
//
// Realm: DevOps / SRE.
// Engineer swap-in: point `notify()` at PagerDuty/Opsgenie/Slack; replace the
// synthetic sensor feeds with your metrics scraper. The sheet IS the paging
// policy — change formulas, not code.
//
// The design is deliberately classic SRE:
//   golden signals (latency, errors, saturation) → burn-rate ratios → one
//   severity score → edge-triggered listeners with hysteresis (page on rise
//   through a band, resolve only when back under the lower band) → every
//   page/resolve booked into a hash-chained witness log.
//
// Why quilt: paging policies are usually scattered across alert configs and
// dashboard thresholds. Here the whole policy is 8 visible cells, reactive by
// construction, and every decision it makes is receipted.

import { sheet, WitnessLog, check, done, setTool, panel, kv, ANSI } from '../src/toolkit.mjs';

setTool('fleet-pager');

// ── the sheet: the entire paging policy, visible ─────────────────────────────
const e = sheet('fleet-pager', [
  // golden-signal sensors (swap for your scraper)
  { id: 'svc.latency',    kind: 'sensor', default: 120,  description: 'p95 latency, ms (SLO 300)' },
  { id: 'svc.error_rate', kind: 'sensor', default: 0.2,  description: 'error rate, % (SLO 0.5)' },
  { id: 'svc.saturation', kind: 'sensor', default: 0.40, description: 'resource saturation, 0-1 (warn 0.6)' },

  // burn-rate ratios — pure formulas
  { id: 'burn.errors',   kind: 'formula', expr: 'svc.error_rate / 0.5',  description: 'error budget burn, ×' },
  { id: 'burn.latency',  kind: 'formula', expr: 'svc.latency / 300',    description: 'latency budget burn, ×' },

  // one severity score to rule the paging bands (0-100)
  { id: 'severity', kind: 'formula',
    expr: 'Math.round(40 * Math.min(1, burn.errors) + 35 * Math.min(1, burn.latency) + 25 * Math.min(1, Math.max(0, svc.saturation - 0.6) / 0.4))',
    description: 'composite severity: errors 40 / latency 35 / saturation 25' },

  // paging bands — edge-triggered with hysteresis. First-sample guard:
  // prev == null means "no previous sample" → no transition → no page.
  // (Without this, a freshly-loaded quiet sheet announces its own recovery.)
  { id: 'page.sev2', kind: 'listener', watch: ['severity'],
    condition: 'caller.metadata.prev != null && caller.metadata.current >= 70 && caller.metadata.prev < 70',
    action: 'pager.notify_sev2' },
  { id: 'page.sev3', kind: 'listener', watch: ['severity'],
    condition: 'caller.metadata.prev != null && caller.metadata.current >= 40 && caller.metadata.current < 70 && caller.metadata.prev < 40',
    action: 'pager.notify_sev3' },
  { id: 'page.resolve', kind: 'listener', watch: ['severity'],
    condition: 'caller.metadata.prev != null && caller.metadata.current < 50 && caller.metadata.prev >= 50',
    action: 'pager.notify_resolve' },

  // the integrations: programs that decide who gets woken up, then book the
  // event into pager.events (the tool drains this cell → integrations)
  { id: 'pager.events', kind: 'value', value: [], description: 'engine-decided paging events (tool drains → PagerDuty/Slack)' },
  { id: 'pager.notify_sev2', kind: 'program',
    code: `const ev = { event: "PAGE_SEV2", severity: (await runtime.get("severity")).data, oncall: "platform-primary", channel: "#inc-bot" };\n        const log = (await runtime.get("pager.events")).data;\n        await runtime.set("pager.events", [...log, { ...ev, ts: Date.now() }]);\n        return ev;` },
  { id: 'pager.notify_sev3', kind: 'program',
    code: `const ev = { event: "TICKET_SEV3", severity: (await runtime.get("severity")).data, oncall: "next-business-day", channel: "#sre-tickets" };\n        const log = (await runtime.get("pager.events")).data;\n        await runtime.set("pager.events", [...log, { ...ev, ts: Date.now() }]);\n        return ev;` },
  { id: 'pager.notify_resolve', kind: 'program',
    code: `const ev = { event: "RESOLVED", severity: (await runtime.get("severity")).data, channel: "#inc-bot" };\n        const log = (await runtime.get("pager.events")).data;\n        await runtime.set("pager.events", [...log, { ...ev, ts: Date.now() }]);\n        return ev;` },
]);

// drain engine-decided events → witness ledger (→ your integrations)
const fired = [];
const log = new WitnessLog();
const drain = async () => {
  const events = (await e.get('pager.events')).data;
  while (fired.length < events.length) {
    const ev = events[fired.length];
    fired.push(ev);
    log.append({ kind: 'pager', event: ev.event, severity: ev.severity, oncall: ev.oncall ?? null, ts: ev.ts });
  }
};

const sev = async () => (await e.get('severity')).data;
const show = async label => panel(label, [
  kv('latency', `${(await e.get('svc.latency')).data} ms   error_rate: ${(await e.get('svc.error_rate')).data}%   saturation: ${(await e.get('svc.saturation')).data}`),
  kv('burn', `errors ×${(await e.get('burn.errors')).data.toFixed(1)}   latency ×${(await e.get('burn.latency')).data.toFixed(1)}`),
  kv('severity', `${await sev()} / 100`),
]);

console.log(`${ANSI.bold}fleet-pager${ANSI.reset} — golden signals → burn rates → severity → edge-triggered pages\n`);

await show('t=0  steady state');
await drain();
check('quiet system pages nobody', fired.length === 0, `baseline severity ${await sev()} — below the sev3 band`);

// ── scenario: latency degrades (sev3 band) ──
await e.set('svc.latency', 480);
await drain();
await show('t+5m latency degrades (480ms)');
const t3 = fired.find(f => f.event === 'TICKET_SEV3');
check('sev3 ticket fired on first crossing', !!t3, `severity=${t3?.severity}`);
check('no sev2 page yet (band discipline)', !fired.some(f => f.event === 'PAGE_SEV2'));

// ── errors spike too (sev2 band) ──
await e.set('svc.error_rate', 4.0);
await drain();
await show('t+9m errors spike (4.0%)');
const p2 = fired.find(f => f.event === 'PAGE_SEV2');
check('sev2 page fired once', fired.filter(f => f.event === 'PAGE_SEV2').length === 1, `severity=${p2?.severity} → ${p2?.oncall}`);

// staying inside the band must NOT re-page (edge-triggered, not level)
await e.set('svc.saturation', 0.95);
await drain();
const sev2CountAfterInBand = fired.filter(f => f.event === 'PAGE_SEV2').length;
check('no duplicate page while in-band', sev2CountAfterInBand === 1, `saturation 0.95 keeps severity in sev2 band`);

// ── recovery: resolve only under the lower hysteresis band ──
await e.set('svc.error_rate', 0.1);
await e.set('svc.latency', 140);
await e.set('svc.saturation', 0.45);
await drain();
await show('t+40m recovered');
check('resolve fired below hysteresis band', fired.some(f => f.event === 'RESOLVED'), `severity=${await sev()}`);

// ── every decision receipted, chain sealed ──
panel('witness ledger', [
  kv('entries', log.length),
  kv('head', log.head),
  kv('verify', JSON.stringify(log.verify())),
]);
check('witness chain sealed', log.verify().ok, `${log.length} receipts, head ${log.head}`);

done();
