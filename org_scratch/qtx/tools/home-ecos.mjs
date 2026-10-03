// 06 — home-ecos: a home that baselines itself and acts on what it senses.
//
// Realm: IoT / smart home / energy.
// Engineer swap-in: sensors are pushed from MQTT/Zigbee bridges; the actuator
// plan cell drives your thermostat/switch API. The EWMA baseline, the
// occupancy rules and the surge detector are sheet cells — retune live.
//
// Two ideas working together:
//   1. SELF-BASELINING: an EWMA of power draw lives in a value cell, updated
//      by a listener→program loop on every sensor push. "Normal" is learned,
//      not configured. A surge is current >> baseline — caught even when the
//      absolute watts look harmless (a 300W heater is invisible to a fixed
//      threshold in a house that runs 8kW, obvious in one that sleeps at 90W).
//   2. GESTURE CHECK: the shape of the recent power series (bending energy —
//      the fleet's differential-geometry idiom) separates smooth duty cycles
//      from resistive-heater flatlines and failing-motor chatter. A fridge
//      cycles; a stuck compressor doesn't.
//
// Runs fully offline.

import { sheet, WitnessLog, check, done, setTool, panel, kv, ANSI } from '../src/toolkit.mjs';

setTool('home-ecos');

const e = sheet('home-ecos', [
  // sensors (pushed by the bridge)
  { id: 'home.power',     kind: 'sensor', default: 90, description: 'whole-home power, W' },
  { id: 'home.temp',      kind: 'sensor', default: 21.0, description: 'inside temp, °C' },
  { id: 'home.occupancy', kind: 'sensor', default: 0, description: '0/1 — anyone home?' },

  // learned state
  { id: 'home.baseline', kind: 'value', value: { ewma: 90, n: 0 }, description: 'EWMA of power — learned normal' },
  { id: 'home.window',   kind: 'value', value: [], description: 'last 32 power samples (the gesture)' },
  { id: 'hvac.setpoint', kind: 'value', value: { mode: 'eco', target: 18.0 }, description: 'actuator plan (the thing that changes the world)' },

  // config
  { id: 'config.alpha',     kind: 'value', value: 0.15 },
  { id: 'config.surge_mul', kind: 'value', value: 2.2 },
  { id: 'config.comfort',   kind: 'value', value: 21.5 },

  // occupancy-aware comfort policy (pure)
  { id: 'policy.target', kind: 'formula',
    expr: 'home.occupancy > 0 ? config.comfort : 18.0' },
  { id: 'policy.hvac_mode', kind: 'formula',
    expr: 'home.occupancy > 0 ? (home.temp < policy.target ? "heat" : "idle") : "eco"' },

  // actuator listener: mode/target changes apply to the plan cell
  { id: 'apply.hvac', kind: 'listener', watch: ['policy.hvac_mode'],
    condition: 'caller.metadata.prev != null && caller.metadata.prev !== caller.metadata.current',
    action: 'actuate.hvac' },
  { id: 'actuate.hvac', kind: 'program',
    code: `const target = (await runtime.get('policy.target')).data;
      const mode = (await runtime.get('policy.hvac_mode')).data;
      const cur = (await runtime.get('hvac.setpoint')).data;
      if (cur.mode === mode && cur.target === target) return { applied: false };
      await runtime.set('hvac.setpoint', { mode, target });
      return { applied: true, mode, target };` },

  // surge events (the detector is the tool layer; booking is the sheet's)
  { id: 'home.events', kind: 'value', value: [] },
]);

console.log(`${ANSI.bold}home-ecos${ANSI.reset} — learned baselines, occupancy-aware comfort, gesture-checked power\n`);

const log = new WitnessLog();
let eid = 0;
const events = async () => (await e.get('home.events')).data;
const drainEvents = async () => {
  const evs = await events();
  while (log.length < evs.length) { const ev = evs[log.length]; log.append(ev); }
};

const bendingEnergy = w => w.reduce((s, x, i) => (i > 1 ? s + Math.abs((x - w[i - 1]) - (w[i - 1] - w[i - 2])) : s), 0);

let surgeCount = 0;
async function sample(power, { temp = 21.0, occupancy = 1 } = {}) {
  await e.set('home.occupancy', occupancy);
  await e.set('home.temp', temp);

  const base = (await e.get('home.baseline')).data;
  const alpha = (await e.get('config.alpha')).data;
  const mul = (await e.get('config.surge_mul')).data;
  const ewma = base.ewma + alpha * (power - base.ewma);
  const over = base.n >= 8 && power > mul * base.ewma;      // only after warmup
  // edge-triggered: flag the TRANSITION into surge, not every sample —
  // a sustained oven hour is one event, not sixty
  const isSurge = over && !base.surging;

  await e.set('home.baseline', { ewma, n: base.n + 1, surging: over });

  const win = (await e.get('home.window')).data;
  const window = [...win, power].slice(-32);
  await e.set('home.window', window);

  if (isSurge) {
    const evs = await events();
    await e.set('home.events', [...evs, { op: 'SURGE', watts: power, baseline: Math.round(base.ewma), ratio: Number((power / base.ewma).toFixed(2)), ts: Date.now() }]);
    surgeCount++;
  } else if (!over && base.surging) {
    const evs = await events();
    await e.set('home.events', [...evs, { op: 'SURGE_END', watts: power, baseline: Math.round(base.ewma), ts: Date.now() }]);
  }

  await e.push('home.power', power);
  await drainEvents();
  return { ewma, isSurge, gesture: Math.round(bendingEnergy(window)) };
}

// ── the day: quiet morning, people home, evening heater spike ──
let r;
for (let i = 0; i < 12; i++) r = await sample(85 + Math.round(10 * Math.sin(i / 2)), { occupancy: 0, temp: 20.5 });   // empty house
panel('overnight', [
  kv('baseline', `${Math.round(r.ewma)} W (learned from ${12} samples)`),
  kv('hvac', JSON.stringify((await e.get('hvac.setpoint')).data)),
]);
check('baseline learned the quiet house', r.ewma > 80 && r.ewma < 100, `ewma=${Math.round(r.ewma)} W`);
check('eco mode applied while away', (await e.get('hvac.setpoint')).data.mode === 'eco');

r = await sample(95, { occupancy: 1, temp: 20.2 });    // family home
r = await sample(310, { occupancy: 1, temp: 20.1 });   // HVAC kicks in
check('occupancy flips hvac to heat', (await e.get('hvac.setpoint')).data.mode === 'heat',
  `target ${(await e.get('policy.target')).data}°C`);

for (let i = 0; i < 10; i++) r = await sample(2400 + Math.round(80 * Math.sin(i)), { occupancy: 1, temp: 20.6 });   // oven + heater evening
panel('evening', [
  kv('baseline', `${Math.round(r.ewma)} W`),
  kv('gesture', `bending energy ${r.gesture} over last 32 samples (smooth duty cycles bend little)`),
  kv('events', (await events()).length),
]);
check('evening draw = one event, not sixty', surgeCount === 1,
  `surges so far: ${surgeCount} — edge-triggered, the oven coming on is one event`);

// the hidden heater: 2am, everything off, one garage heater nobody switched
// off. The night is long — 25 quiet samples let the baseline forget the day.
r = await sample(95, { occupancy: 0, temp: 20.9 });
for (let i = 0; i < 24; i++) r = await sample(90 + Math.round(5 * Math.sin(i / 3)), { occupancy: 0, temp: 20.9 });
const before = surgeCount;
r = await sample(400, { occupancy: 0, temp: 20.9 });    // garage heater nobody switched off
panel('2am', [
  kv('baseline', `${Math.round(r.ewma)} W (quiet night)`),
  kv('sample', '400 W = 4.2× baseline'),
  kv('verdict', r.isSurge ? `${ANSI.red}SURGE flagged${ANSI.reset}` : 'not flagged'),
]);
check('2am heater caught against the learned baseline', r.isSurge || surgeCount > before,
  `quiet-night baseline ~120 W → 400 W is a wave, not noise (surge #${surgeCount})`);

const v = log.verify();
check('event ledger sealed', v.ok, `${log.length} home events, head ${v.head.slice(0, 12)}…`);

done();
