// 09 — habit-atlas: a habit tracker that models momentum like a physical system.
//
// Realm: health / personal analytics / coaching apps.
// Engineer swap-in: check-ins arrive from your app's UI; the digest program
// is the seam to notifications. The momentum math and streak policy are
// cells — a coach can retune them live.
//
// The design choice that matters: habits are modeled as PHYSICS, not badges.
// Each habit carries momentum (an EWMA of adherence that decays when you
// slip and recovers gradually when you return), so "how am I doing" is a
// number with hysteresis — not a guilt flag that resets on one bad day.
// Streaks stay for motivation; momentum tells the truth.
//
// Runs fully offline.

import { sheet, WitnessLog, check, done, setTool, panel, kv, ANSI } from '../src/toolkit.mjs';

setTool('habit-atlas');

const DAY = 86400000;
const t0 = Date.now();

const e = sheet('habit-atlas', [
  // one habit: morning run. (Duplicate this cell set per habit — or generate.)
  { id: 'habit.run', kind: 'value', value: { streak: 0, best: 0, momentum: 0.5, lastDone: null, target: 5 } },
  { id: 'config.decay', kind: 'value', value: 0.25, description: 'momentum lost per missed day' },
  { id: 'config.gain', kind: 'value', value: 0.15, description: 'momentum gained per done day' },
  { id: 'config.rest_day', kind: 'value', value: 1, description: 'rest days per week that never break momentum' },

  // weekly state
  { id: 'week.done', kind: 'value', value: 0 },
  { id: 'week.rest_used', kind: 'value', value: 0 },

  // derived: where the habit actually is
  { id: 'status.zone', kind: 'formula',
    expr: 'habit.run.momentum >= 0.75 ? "cruising" : habit.run.momentum >= 0.45 ? "building" : "rebuilding"',
    description: 'momentum zones with hysteresis — no cliff edges' },

  // check-in: the fence lives here (no double-checkins, no retroactive edits)
  { id: 'habit.checkin', kind: 'program', deps: [],
    description: 'checkin(done|rest|miss) — updates streak + momentum',
    code: `
      const { day, did } = input ?? {};
      if (typeof day !== 'number' || typeof did !== 'boolean') return { refused: true, reason: 'checkin needs day + did' };
      const h = (await runtime.get('habit.run')).data;
      if (h.lastDone !== null && day <= h.lastDone) return { refused: true, reason: 'day already checked in (or out of order)' };

      let streak = h.streak, momentum = h.momentum;
      if (did) { streak = h.streak + 1; momentum = Math.min(1, momentum + (await runtime.get('config.gain')).data); }
      else {
        streak = 0;
        const restUsed = (await runtime.get('week.rest_used')).data;
        const restQuota = (await runtime.get('config.rest_day')).data;
        momentum = Math.max(0, momentum - (restUsed < restQuota ? 0 : (await runtime.get('config.decay')).data));
      }
      const best = Math.max(h.best, streak);
      await runtime.set('habit.run', { ...h, streak, best, momentum, lastDone: day });
      if (did) await runtime.set('week.done', ((await runtime.get('week.done')).data) + 1);
      return { day, did, streak, momentum: Number(momentum.toFixed(3)), best };
    ` },
]);

console.log(`${ANSI.bold}habit-atlas${ANSI.reset} — momentum as physics: gains are slow, slips decay, rest is free\n`);

const log = new WitnessLog();
let eid = 0;
const day = n => t0 + n * DAY;
const checkin = async (n, did) => {
  const r = (await e.call('habit.checkin', { day: day(n), did, eid: ++eid })).data;
  log.append({ op: did ? 'done' : 'miss', day: n, streak: r?.streak ?? null, momentum: r?.momentum ?? null, refused: !!r?.refused });
  return r;
};
const momentum = async () => (await e.get('habit.run')).data.momentum;
const zone = async () => (await e.get('status.zone')).data;

// ── two weeks of real life ──
const schedule = [1,1,1,0,1,1,1, 1,0,0,1,1,1,1];   // week 1 strong, week 2 wobbly
const results = [];
for (let d = 0; d < schedule.length; d++) results.push(await checkin(d, schedule[d] === 1));

panel('week 1', [
  kv('days 0-6', '6 of 7 done'),
  kv('streak', `${results[6].streak}`),
  kv('momentum', `${results[6].momentum}`),
  kv('zone', `${ANSI.green}${await zone()}${ANSI.reset}`),
]);
check('streak counts the run days', results[6].streak === 3, 'run run run (rest) run run run → 3-run streak');
check('momentum rose through week 1', results[6].momentum > 0.75, `${results[6].momentum} — cruising`);
check('rest day did not break the streak', results[3].streak === 0 && results[4].streak === 1,
  'miss resets streak (motivation) but momentum barely moved');

const trough = Math.min(...results.map(r => r.momentum));
check('misses decay momentum but gently', trough < results[6].momentum && trough > 0.3, `trough ${trough}`);

panel('week 2', [
  kv('days 7-13', '5 of 7 done (two slips)'),
  kv('momentum', `${results[13].momentum}`),
  kv('zone', results[13].momentum >= 0.75 ? `${ANSI.green}cruising${ANSI.reset}` : `${ANSI.amber}building${ANSI.reset}`),
  kv('best streak', `${results[13].best}`),
]);
check('momentum recovered after the wobble', results[13].momentum >= results[6].momentum - 0.2,
  `${results[13].momentum} — the system forgives, gradually`);

// ── the fences ──
const dbl = await checkin(13, true);
check('double check-in refused', dbl.refused === true, dbl.reason);
const back = await checkin(5, true);
check('retroactive check-in refused', back.refused === true, 'days are append-only, like everything else here');

const v = log.verify();
const dones = log.rows.filter(r => r.op === 'done').length;
panel('the fortnight', [
  kv('check-ins', `${log.length} (fenced: ${log.rows.filter(r => r.refused).length} refused)`),
  kv('runs', `${dones} of 14`),
  kv('final momentum', `${await momentum()} (${await zone()})`),
  kv('head', v.head),
]);
check('witness chain sealed', v.ok, `${log.length} days, head ${v.head.slice(0, 12)}…`);

done();
