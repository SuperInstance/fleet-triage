// referral_graph.pins.mjs — FAIL-first pins for the Referral Mesh PoC.
//
// Two graphs are exercised:
//   SEED     — the real v1 graph (experiments/referral_graph.seed.mjs).
//              Honest: all edges PENDING. Its pins assert loadability, chain
//              integrity, view ranking, and — live, when gh is reachable —
//              that every provenance PR actually merged.
//   FIXTURE  — a labeled synthetic graph that exercises the VERIFIED currency
//              rules, wrong-repo refusal, audit downgrade, and falsification
//              kills. The fixture's claims are test data, never real findings.
//
// Run: node experiments/referral_graph.pins.mjs [--live]

import { ReferralGraph, Refusal, PENDING_WEIGHT, VERIFIED_WEIGHT } from '../src/referral_graph.mjs';
import { check, done, setTool, panel, kv } from '../src/toolkit.mjs';
import { execFileSync } from 'node:child_process';

setTool('referral-graph-pins');
const LIVE = process.argv.includes('--live');

// ── SEED graph ──────────────────────────────────────────────────────────────
const QUANT_REPOS = ['quilt-tools', 'quilt-show', 'quilt-arcade', 'quilt-quant', 'pong-quilt'];
const seed = new ReferralGraph({ name: 'referral-graph-v1', repos: QUANT_REPOS });
for (const n of (await import('./referral_graph.seed.mjs')).SEED.nodes) seed.addNode(n);
let seedBooked = 0;
for (const e of (await import('./referral_graph.seed.mjs')).SEED.edges) { seed.book(e); seedBooked++; }

check('seed: all edges booked', seedBooked === 19 && seed.rows.length === 19, `${seedBooked} edges`);

// Pin 1 — missing required field is a loud REFUSAL, never a silent drop.
{
  let msg = '';
  try { seed.book({ from: 'qt-api-lab', to: 'qs-ep2', claim: 'no kill switch' }); }
  catch (e) { msg = e instanceof Refusal ? e.message : 'WRONG TYPE: ' + e.constructor.name; }
  check('seed: missing falsification_condition -> REFUSAL names the key', /missing required key 'falsification_condition'/.test(msg), msg);
}

// Pin 2 — chain re-derives; tampering with a claim is loud and indexed.
{
  const ok = seed.verify();
  check('seed: witness chain verifies', ok.ok === true, ok.bad ? `row ${ok.bad.seq}: ${ok.bad.reason}` : `${seed.rows.length} rows`);
  const tampered = seed.exportRows();
  tampered[2] = { ...tampered[2], claim: tampered[2].claim + ' (quietly strengthened)' };
  const { verifyChain } = await import('../src/toolkit.mjs');
  const bad = verifyChain(tampered);
  check('seed: tampered claim -> verify fails at that row', bad.ok === false && bad.brokenAt === 2, bad.ok ? 'TAMPER ACCEPTED' : `caught row ${bad.brokenAt}: prev_hash ${bad.got} != ${bad.expected}`);
}

// Pin 3 — the VIEW: ranked distribution; fourteen VERIFIED edges (20x an

// jev-quilt, micrograd-quilt, MicroMoth-quilt, moth-waveform, quilt-cowboy
// and quilt-stone hold single VERIFIED mass (jev-quilt's KAT edge FLIPPED
// 2026-09-30 on jev-quilt#47 merging — its first INBOUND currency; the
// mm⇄mgq lab↔ledger pair is VERIFIED in BOTH directions — micrograd-quilt#7
// earned ledger→lab, MicroMoth-quilt#29 earned lab→ledger six hours later),
// and quilt-arcade holds double PENDING; delta-shape enters the view for
// the first time carrying the FOURTEENTH edge's VERIFIED mass (qe-witness →
// ds-esign-drift, booked at VERIFIED 2026-10-01 on delta-shape#1's merge
// 57c07426 — the sixth to-node born after seeding, entering at full mass).
// (From-node-only repos — quilt-quant, AI-Writings, quality-gate-stream,
// quilt-ewitness — earn no view mass; mass is measured where doctrine LANDS.)
// (main-repair note: the #11 conflict resolution had duplicated this block
// and left a dangling check() call — the file did not parse on main tip.
// Removed here; the currency flip below is what this PR is for.)
{
  const v = seed.view();
  check('seed: view ranks all thirteen mass-carrying repos', v.length === 13, v.map(x => `${x.repo}=${x.share.toFixed(3)}`).join(' '));  const shares = v.map(x => x.share);
  check('seed: view shares sum to 1', Math.abs(shares.reduce((a, b) => a + b, 0) - 1) < 1e-9, `Σ=${shares.reduce((a, b) => a + b, 0)}`);
  const byRepo = Object.fromEntries(v.map(x => [x.repo, x.weight]));
  check('seed: view mass — fm = 3×VERIFIED (first triple-inbound), pq = 2×VERIFIED, qs/qt = VERIFIED + PENDING, ga/jq/mgq/mm/mw/qb/stone = VERIFIED (the mm⇄mgq pair both VERIFIED), qa = 2×PENDING (from-node-only repos: no view mass)',
    Math.abs(byRepo['fleet-murmur'] - 3 * VERIFIED_WEIGHT) < 1e-9 &&
    Math.abs(byRepo['pong-quilt'] - 2 * VERIFIED_WEIGHT) < 1e-9 &&
    Math.abs(byRepo['quilt-show'] - (VERIFIED_WEIGHT + PENDING_WEIGHT)) < 1e-9 &&
    Math.abs(byRepo['git-agent'] - VERIFIED_WEIGHT) < 1e-9 &&
    Math.abs(byRepo['micrograd-quilt'] - VERIFIED_WEIGHT) < 1e-9 &&
    Math.abs(byRepo['quilt-cowboy'] - VERIFIED_WEIGHT) < 1e-9 &&
    Math.abs(byRepo['jev-quilt'] - VERIFIED_WEIGHT) < 1e-9 &&
    Math.abs(byRepo['MicroMoth-quilt'] - VERIFIED_WEIGHT) < 1e-9 &&
    Math.abs(byRepo['moth-waveform'] - VERIFIED_WEIGHT) < 1e-9 &&
    Math.abs(byRepo['quilt-stone'] - VERIFIED_WEIGHT) < 1e-9 &&
    !('quality-gate-stream' in byRepo) &&
    !('quilt-ewitness' in byRepo) &&
    Math.abs(byRepo['quilt-arcade'] - 2 * PENDING_WEIGHT) < 1e-9 &&
    Math.abs(byRepo['delta-shape'] - VERIFIED_WEIGHT) < 1e-9 &&
    Math.abs(byRepo['quilt-tools'] - (VERIFIED_WEIGHT + PENDING_WEIGHT)) < 1e-9,
    JSON.stringify(byRepo));
  const sorted = [...v].sort((a, b) => b.share - a.share || a.repo.localeCompare(b.repo));
  check('seed: view is sorted by share desc', JSON.stringify(v) === JSON.stringify(sorted), 'sorted');
  check('seed: fm leads with triple mass; pq second with double mass; then the two VERIFIED+PENDING repos (quilt-show, quilt-tools); the eight single-VERIFIED repos tie, broken by name (delta-shape first — the e-witness booking whose merge outran it; git-agent … quilt-stone; micrograd-quilt and MicroMoth-quilt enter via the lab↔ledger pair, both directions VERIFIED; the KAT edge now VERIFIED); quilt-arcade double-PENDING closes the view',
    v[0].repo === 'fleet-murmur' && v[0].weight === 3 * VERIFIED_WEIGHT &&
    v[2].repo === 'quilt-show' && v[2].weight === VERIFIED_WEIGHT + PENDING_WEIGHT &&
    v[3].repo === 'quilt-tools' && v[3].weight === VERIFIED_WEIGHT + PENDING_WEIGHT &&
    v[4].repo === 'delta-shape' && v[4].weight === VERIFIED_WEIGHT &&
    v[5].repo === 'git-agent' && v[5].weight === VERIFIED_WEIGHT &&
    v[6].repo === 'jev-quilt' && v[6].weight === VERIFIED_WEIGHT &&
    v[7].repo === 'micrograd-quilt' && v[7].weight === VERIFIED_WEIGHT &&
    v[8].repo === 'MicroMoth-quilt' && v[8].weight === VERIFIED_WEIGHT &&
    v[9].repo === 'moth-waveform' && v[9].weight === VERIFIED_WEIGHT &&
    v[10].repo === 'quilt-cowboy' && v[10].weight === VERIFIED_WEIGHT &&
    v[11].repo === 'quilt-stone' && v[11].weight === VERIFIED_WEIGHT &&
    v[12].repo === 'quilt-arcade' && v[12].weight === 2 * PENDING_WEIGHT,
    `${v[0].repo} ${(v[0].share * 100).toFixed(1)}% · ${v[1].repo} ${(v[1].share * 100).toFixed(1)}% · ${v[2].repo} ${(v[2].share * 100).toFixed(1)}% · ${v[3].repo} ${(v[3].share * 100).toFixed(1)}% · ${v[4].repo} ${(v[4].share * 100).toFixed(1)}% · ${v[5].repo} ${(v[5].share * 100).toFixed(1)}% · ${v[6].repo} ${(v[6].share * 100).toFixed(1)}% · ${v[7].repo} ${(v[7].share * 100).toFixed(1)}% · ${v[8].repo} ${(v[8].share * 100).toFixed(1)}% · ${v[9].repo} ${(v[9].share * 100).toFixed(1)}% · ${v[10].repo} ${(v[10].share * 100).toFixed(1)}% · ${v[11].repo} ${(v[11].share * 100).toFixed(1)}% · ${v[12].repo} ${(v[12].share * 100).toFixed(1)}%`);
}

// Pin 3c — the SECOND currency event (FAIL-first: on main tip the quantum-coin
// edge does not exist — this pin trips; the seed update on this branch earns
// it). Single-edge monopoly broken.
{
  const row = seed.rows.find(r => r.op === 'LINK' && r.from === 'quant-coin-toss' && r.to === 'qq-quantum-tiebreak');
  check('seed: quantum-coin edge is VERIFIED with receipt in the to-node\'s repo',
    row.weight === 'VERIFIED' && row.receipt === 'SuperInstance/pong-quilt#28',
    row ? `weight=${row.weight} receipt=${row.receipt}` : 'edge not found');
  const verified = seed.rows.filter(r => r.op === 'LINK' && r.weight === 'VERIFIED');
  check('seed: exactly fifteen VERIFIED edges across fifteen distinct to-nodes — monopoly broken, doctrine arc complete; the mm⇄mgq pair VERIFIED in both directions (ledger→lab via micrograd-quilt#7, lab→ledger via MicroMoth-quilt#29), jev-quilt holds its KAT inbound (jev-quilt#47), pong-quilt double INBOUND (coin + sign pilot) and now THREE outgoing (wal-honesty, stone-v1 export, named refusals), fleet-murmur TRIPLE inbound (honesty#2 + qgs-adapter#3 + refusal-ledger#8), delta-shape holds the e-witness inbound (delta-shape#1 — the booking the merge outran)',
    verified.length === 15 && new Set(verified.map(r => r.to)).size === 15,
    verified.map(r => `${r.from}->${r.to}`).join(' '));
}

// Pin 3b — the currency event (FAIL-first: on main tip the S2 edge is PENDING
// with no receipt — this pin trips; the seed update on this branch earns it).
{
  const row = seed.rows.find(r => r.op === 'LINK' && r.from === 'qt-s2-driftwatch' && r.to === 'qs-ep2');
  check('seed: S2→E2 edge is VERIFIED with receipt in the to-node\'s repo',
    row.weight === 'VERIFIED' && row.receipt === 'SuperInstance/quilt-show#1' && row.provenance === 'SuperInstance/quilt-tools#3',
    row ? `weight=${row.weight} receipt=${row.receipt}` : 'edge not found');
  const wrongRepo = seed.rows.some(r => r.op === 'LINK' && r.weight === 'VERIFIED' && !r.receipt.split('#')[0].endsWith('/' + seed.nodes.get(r.to).repo));
  check('seed: every VERIFIED receipt targets its to-node\'s repo', !wrongRepo, 'weight law held');
}

// Pin 3d — the THIRD currency event: the git-agent opcode edge. FAIL-first:
// on main tip this edge is PENDING with no receipt (the currency pins trip).
// git-agent#4 (merged 2026-09-26T09:11:41Z, merge 8d6c31a) lands the in-repo
// algebra.md citation — the exact upgrade path booked when the edge was
// PENDING. Never self-upgraded: the merge in the TARGET repo did the earning.
{
  const row = seed.rows.find(r => r.op === 'LINK' && r.from === 'aw-quint-opcode' && r.to === 'ga-quilt-emit');
  check('seed: aw→ga edge is VERIFIED with git-agent#4 receipt in the to-node\'s repo',
    row?.weight === 'VERIFIED' && row?.receipt === 'SuperInstance/git-agent#4' && row?.provenance === 'SuperInstance/git-agent#1',
    row ? `weight=${row.weight} receipt=${row.receipt}` : 'edge not found');
  check('seed: aw→ga claim records the currency event and the booked upgrade path',
    row?.claim.includes('CURRENCY EARNED 2026-09-26') && row?.claim.includes('8d6c31a'),
    row ? 'claim carries the merge receipt' : 'edge not found');
  const aw = seed.nodes.get('aw-quint-opcode'), ga = seed.nodes.get('ga-quilt-emit');
  check('seed: both endpoints exist in their own repos',
    aw?.repo === 'AI-Writings' && ga?.repo === 'git-agent', `${aw?.repo} -> ${ga?.repo}`);
}

// Pin 3e — the FOURTH currency event: jev-quilt's first OUTGOING edge. FAIL-
// first: on the pre-merge tip this edge does not exist (the currency pins
// trip). quilt-cowboy#1 (merged 2026-09-26T09:12:37Z, merge a3feccca) lands
// the in-repo citation naming SuperInstance/jev-quilt as the doctrine source
// of the v3 substance gate — the weight law is met in the TARGET repo. This
// was the 16:11 pulse's synergy candidate (jev-quilt had zero outgoing
// currency; quilt-doctor named the length-proxy stand-in the gate replaces).
{
  const row = seed.rows.find(r => r.op === 'LINK' && r.from === 'jq-substance-noul' && r.to === 'qb-jev-gate');
  check('seed: jq→qb edge is VERIFIED with quilt-cowboy#1 receipt in the to-node\'s repo',
    row?.weight === 'VERIFIED' && row?.receipt === 'SuperInstance/quilt-cowboy#1',
    row ? `weight=${row.weight} receipt=${row.receipt}` : 'edge not found');
  check('seed: jq→qb claim records the currency event and the merge sha',
    row?.claim.includes('CURRENCY EARNED 2026-09-26') && row?.claim.includes('a3feccca'),
    row ? 'claim carries the merge receipt' : 'edge not found');
  check('seed: jq→qb declares a falsification condition (kill switch)',
    typeof row?.falsification_condition === 'string' && row.falsification_condition.length > 20,
    row?.falsification_condition ?? 'none');
  const jq = seed.nodes.get('jq-substance-noul'), qb = seed.nodes.get('qb-jev-gate');
  check('seed: both endpoints exist in their own repos',
    jq?.repo === 'jev-quilt' && qb?.repo === 'quilt-cowboy', `${jq?.repo} -> ${qb?.repo}`);
  const fromJq = seed.rows.filter(r => r.op === 'LINK' && seed.nodes.get(r.from)?.repo === 'jev-quilt');
  check('seed: jq→qb remains jev-quilt\'s FIRST outward currency (now one of two — Pin 3i books the commons lane)',
    fromJq.some(r => r.from === 'jq-substance-noul' && r.to === 'qb-jev-gate' && r.weight === 'VERIFIED'),
    fromJq.map(r => `${r.from}->${r.to}`).join(' '));
}

// Pin 3f — the FIFTH currency event: fleet-murmur's honesty-receipts pass.
// FAIL-first: on main tip this edge does not exist (the currency pins trip).
// fleet-murmur#2 (merged 2026-09-26T19:08:16Z, merge 5391ba56) names
// SuperInstance/pong-quilt BY NAME in-repo three times (CROSS-POLLINATE.md:
// QA-REFUSAL honesty contract, session WAL substrate, VERIFIED_CLAIMS
// registry). HONESTY on direction: the weight law requires the receipt to
// target the TO-node's repo — the citing merge is in fleet-murmur, so the
// currency books pq-session-wal -> fm-honesty-receipts (doctrine flows INTO
// the citing repo), not the prose order the pulse note suggested.
{
  const row = seed.rows.find(r => r.op === 'LINK' && r.from === 'pq-session-wal' && r.to === 'fm-honesty-receipts');
  check('seed: pq→fm edge is VERIFIED with fleet-murmur#2 receipt in the to-node\'s repo',
    row?.weight === 'VERIFIED' && row?.receipt === 'SuperInstance/fleet-murmur#2',
    row ? `weight=${row.weight} receipt=${row.receipt}` : 'edge not found');
  check('seed: pq→fm claim records the currency event and the merge sha',
    row?.claim.includes('CURRENCY EARNED 2026-09-26') && row?.claim.includes('5391ba56'),
    row ? 'claim carries the merge receipt' : 'edge not found');
  check('seed: pq→fm declares a falsification condition (kill switch)',
    typeof row?.falsification_condition === 'string' && row.falsification_condition.length > 20,
    row?.falsification_condition ?? 'none');
  const pq = seed.nodes.get('pq-session-wal'), fm = seed.nodes.get('fm-honesty-receipts');
  check('seed: both endpoints exist in their own repos',
    pq?.repo === 'pong-quilt' && fm?.repo === 'fleet-murmur', `${pq?.repo} -> ${fm?.repo}`);
  check('seed: receipt target is the to-node\'s repo (weight law, substrate-enforced)',
    row?.receipt.split('#')[0] === `SuperInstance/${fm?.repo}`, row?.receipt);
  const fromPq = seed.rows.filter(r => r.op === 'LINK' && seed.nodes.get(r.from)?.repo === 'pong-quilt');
  check('seed: pong-quilt carries three outgoing VERIFIED edges — receives currency (pq→fm honesty) and pays it forward into the canonical verifier (stone lane) and the IETF refusal-ledger lane (named refusals)',
    fromPq.length === 3 && fromPq.every(r => r.weight === 'VERIFIED') && fromPq.some(r => r.to === 'fm-honesty-receipts') && fromPq.some(r => r.to === 'stone-forward-adopt') && fromPq.some(r => r.to === 'fm-refusal-ledger'),
    fromPq.map(r => `${r.from}->${r.to}`).join(' '));
}

// Pin 3g — the SIXTH currency event: moth-waveform's no-op floor gate
// carries the fleet-murmur scar. FAIL-first: on main tip this edge does not
// exist (the currency pins trip). moth-waveform#1 (merged
// 2026-09-26T21:06:24Z, merge dc1a142) cites the scar BY NAME in-repo at
// code level (sensitivity.py: "a gate that passes without a live floor
// measurement passes vacuously (fleet-murmur scar)") — the load-bearing
// citation; the README Receipts-doctrine list (pong-quilt/hermit/quilt-
// doctor/quality-gate-stream/fleet-murmur) is lineage, recorded in the claim
// but not the currency anchor. Found by the 06:56 pulse's discovery-class
// org scan; a human verified the citation shape before booking.
{
  const row = seed.rows.find(r => r.op === 'LINK' && r.from === 'fm-honesty-receipts' && r.to === 'mw-floor-gate');
  check('seed: fm→mw edge is VERIFIED with moth-waveform#1 receipt in the to-node\'s repo',
    row?.weight === 'VERIFIED' && row?.receipt === 'SuperInstance/moth-waveform#1',
    row ? `weight=${row.weight} receipt=${row.receipt}` : 'edge not found');
  check('seed: fm→mw claim records the currency event and the merge sha',
    row?.claim.includes('CURRENCY EARNED 2026-09-26') && row?.claim.includes('dc1a142'),
    row ? 'claim carries the merge receipt' : 'edge not found');
  check('seed: fm→mw declares a falsification condition (kill switch)',
    typeof row?.falsification_condition === 'string' && row.falsification_condition.length > 20,
    row?.falsification_condition ?? 'none');
  const fm = seed.nodes.get('fm-honesty-receipts'), mw = seed.nodes.get('mw-floor-gate');
  check('seed: both endpoints exist in their own repos',
    fm?.repo === 'fleet-murmur' && mw?.repo === 'moth-waveform', `${fm?.repo} -> ${mw?.repo}`);
  check('seed: receipt target is the to-node\'s repo (weight law, substrate-enforced)',
    row?.receipt.split('#')[0] === `SuperInstance/${mw?.repo}`, row?.receipt);
  const fromFm = seed.rows.filter(r => r.op === 'LINK' && seed.nodes.get(r.from)?.repo === 'fleet-murmur');
  check('seed: this is fleet-murmur\'s only outgoing edge — first fleet-murmur outward currency',
    fromFm.length === 1 && fromFm[0].to === 'mw-floor-gate', `${fromFm.length} fleet-murmur outgoing`);
}

// Pin 3h — the SEVENTH currency event: the quality-gate interop lane
// pre-booked at 05:24 ("on merge books edge qgs→fm, target repo=fm — not
// fm→qgs as the pulse note guessed"). FAIL-first: on main tip this edge
// does not exist (the currency pins trip). fleet-murmur#3 (merged
// 2026-09-26T23:08:45Z, merge 8df75c6) lands the quality_gate_adapter
// rewritten against the live quality-gate-stream API, naming
// SuperInstance/quality-gate-stream BY NAME in-repo at three anchored sites
// (adapter docstring, VERIFIED_CLAIMS.md VC10, tests/test_qgs_adapter_glue.py
// — live pins run the real package, labeled skips when uninstalled).
{
  const row = seed.rows.find(r => r.op === 'LINK' && r.from === 'qgs-strict-gate' && r.to === 'fm-qgs-adapter');
  check('seed: qgs→fm edge is VERIFIED with fleet-murmur#3 receipt in the to-node\'s repo',
    row?.weight === 'VERIFIED' && row?.receipt === 'SuperInstance/fleet-murmur#3',
    row ? `weight=${row.weight} receipt=${row.receipt}` : 'edge not found');
  check('seed: qgs→fm claim records the currency event and the merge sha',
    row?.claim.includes('CURRENCY EARNED 2026-09-26') && row?.claim.includes('8df75c6'),
    row ? 'claim carries the merge receipt' : 'edge not found');
  check('seed: qgs→fm declares a falsification condition (kill switch)',
    typeof row?.falsification_condition === 'string' && row.falsification_condition.length > 20,
    row?.falsification_condition ?? 'none');
  const qgs = seed.nodes.get('qgs-strict-gate'), fmq = seed.nodes.get('fm-qgs-adapter');
  check('seed: both endpoints exist in their own repos',
    qgs?.repo === 'quality-gate-stream' && fmq?.repo === 'fleet-murmur', `${qgs?.repo} -> ${fmq?.repo}`);
  check('seed: receipt target is the to-node\'s repo (weight law, substrate-enforced)',
    row?.receipt.split('#')[0] === `SuperInstance/${fmq?.repo}`, row?.receipt);
  const toFm = seed.rows.filter(r => r.op === 'LINK' && seed.nodes.get(r.to)?.repo === 'fleet-murmur');
  check('seed: fleet-murmur carries three VERIFIED inbound edges — the fleet\'s first triple-inbound repo (honesty#2 + qgs-adapter#3 + refusal-ledger#8)',
    toFm.length === 3 && toFm.every(r => r.weight === 'VERIFIED'), toFm.map(r => `${r.from}->${r.to}`).join(' '));
}

// Pin 3i — the EIGHTH currency event: the G11 trust lever on the referral
// view. FAIL-first: on main tip this edge does not exist (the currency pins
// trip). quilt-tools#17 (merged 2026-09-27T01:27:12Z, merge d14fb44) lands
// viewTrusted({trust, default:0}) — every edge re-scaled by its TARGET
// repo's earned trust, ported FROM SuperInstance/jev-quilt commons.py
// trust_weighted()/provenance_merge() (G11, jev-quilt#37) with the citation
// BY NAME in src/referral_graph.mjs + REFERRAL_GRAPH.md. Direction honesty:
// the citing merge is IN quilt-tools, so the edge books jq-commons-g11 ->
// qt-trust-lever (the graph's own repo earns its first commons-lane TO-node
// currency; the 08:11 pulse flagged this lane as the synergy candidate the
// same morning the R8 Goodhart lane reopened the buyable-view surface).
{
  const row = seed.rows.find(r => r.op === 'LINK' && r.from === 'jq-commons-g11' && r.to === 'qt-trust-lever');
  check('seed: jq→qt edge is VERIFIED with quilt-tools#17 receipt in the to-node\'s repo',
    row?.weight === 'VERIFIED' && row?.receipt === 'SuperInstance/quilt-tools#17',
    row ? `weight=${row.weight} receipt=${row.receipt}` : 'edge not found');
  check('seed: jq→qt claim records the currency event and the merge sha',
    row?.claim.includes('CURRENCY EARNED 2026-09-27') && row?.claim.includes('d14fb44'),
    row ? 'claim carries the merge receipt' : 'edge not found');
  check('seed: jq→qt declares a falsification condition (kill switch)',
    typeof row?.falsification_condition === 'string' && row.falsification_condition.length > 20,
    row?.falsification_condition ?? 'none');
  check('seed: jq→qt provenance records the G11 source merge (jev-quilt#37)',
    row?.provenance === 'SuperInstance/jev-quilt#37', row?.provenance ?? 'none');
  const jq = seed.nodes.get('jq-commons-g11'), qt = seed.nodes.get('qt-trust-lever');
  check('seed: both endpoints exist in their own repos',
    jq?.repo === 'jev-quilt' && qt?.repo === 'quilt-tools', `${jq?.repo} -> ${qt?.repo}`);
  check('seed: receipt target is the to-node\'s repo (weight law, substrate-enforced)',
    row?.receipt.split('#')[0] === `SuperInstance/${qt?.repo}`, row?.receipt);
  const fromJq = seed.rows.filter(r => r.op === 'LINK' && seed.nodes.get(r.from)?.repo === 'jev-quilt');
  check('seed: jev-quilt carries two outgoing VERIFIED edges — second outward currency (commons lane)',
    fromJq.length === 2 && fromJq.every(r => r.weight === 'VERIFIED'), fromJq.map(r => `${r.from}->${r.to}`).join(' '));
}

// Pin 3j — the NINTH currency event: the stone-v1 forward-adoption lane
// pre-booked at 11:04 ("on merge, referral graph books NINTH VERIFIED edge
// pq-stone-v1-export→stone-forward-adopt — same pre-booked pattern as edges
// #5-#8"). FAIL-first: on main tip this edge does not exist (the currency
// pins trip). quilt-stone#1 (merged 2026-09-27T04:20:06Z, merge 093c1b1)
// lands the adoption IN THE VERIFIER's repo: smoke section 12b pins five
// checks over the exporter's EXACT bytes (generated live from pong-quilt's
// tools/wal-export.js toStoneV1() at PR #46's merge tip, not retyped), and
// README.md's Forward-format adopters section names SuperInstance/pong-quilt
// PR #46 BY NAME. Third to-node born after seeding; pong-quilt's SECOND
// outgoing edge.
{
  const row = seed.rows.find(r => r.op === 'LINK' && r.from === 'pq-stone-v1-export' && r.to === 'stone-forward-adopt');
  check('seed: pq→stone edge is VERIFIED with quilt-stone#1 receipt in the to-node\'s repo',
    row?.weight === 'VERIFIED' && row?.receipt === 'SuperInstance/quilt-stone#1',
    row ? `weight=${row.weight} receipt=${row.receipt}` : 'edge not found');
  check('seed: pq→stone claim records the currency event and the merge sha',
    row?.claim.includes('CURRENCY EARNED 2026-09-27') && row?.claim.includes('093c1b1'),
    row ? 'claim carries the merge receipt' : 'edge not found');
  check('seed: pq→stone declares a falsification condition (kill switch)',
    typeof row?.falsification_condition === 'string' && row.falsification_condition.length > 20,
    row?.falsification_condition ?? 'none');
  check('seed: pq→stone provenance records the R36 source merge (pong-quilt#46)',
    row?.provenance === 'SuperInstance/pong-quilt#46', row?.provenance ?? 'none');
  const pqs = seed.nodes.get('pq-stone-v1-export'), st = seed.nodes.get('stone-forward-adopt');
  check('seed: both endpoints exist in their own repos',
    pqs?.repo === 'pong-quilt' && st?.repo === 'quilt-stone', `${pqs?.repo} -> ${st?.repo}`);
  check('seed: receipt target is the to-node\'s repo (weight law, substrate-enforced)',
    row?.receipt.split('#')[0] === `SuperInstance/${st?.repo}`, row?.receipt);
}

// Pin 3k — the TENTH currency event: the stone-v2 sign-lane adoption,
// pre-booked twice (14:56 "on quilt-stone#4 merge the pilot opens +
// candidate VERIFIED edge"; 16:04 "R39 sign pilot ships closed; opens the
// moment the sign lane lands"). FAIL-first: on main tip this edge does not
// exist (the currency pins trip). quilt-stone#4 (MERGED
// 2026-09-27T09:02:01Z, merge 023edbed) ships signTip/verifyTipSignature,
// and pong-quilt#51 (MERGED 2026-09-27T09:03:15Z, merge 07384ac2) staples
// the R37 birth-seal chain's tip with it, citing SuperInstance/quilt-stone
// BY NAME in-repo at three anchored sites (PLAYLOG Round 39 + the citation
// pin in tests/stone-sign-glue.test.js + core.js VERIFIED_CLAIMS
// 'stone-sign-pilot'). DIRECTION HONESTY: the 16:04 pulse guessed
// pq->stone; the receipt-repo rule (edge #5 precedent) books
// stone-sign-lane -> pq-sign-pilot — the citing merge is IN pong-quilt, so
// currency flows INTO pong-quilt (its second inbound edge; quilt-stone's
// first outgoing).
{
  const row = seed.rows.find(r => r.op === 'LINK' && r.from === 'stone-sign-lane' && r.to === 'pq-sign-pilot');
  check('seed: stone→pq sign edge is VERIFIED with pong-quilt#51 receipt in the to-node\'s repo',
    row?.weight === 'VERIFIED' && row?.receipt === 'SuperInstance/pong-quilt#51',
    row ? `weight=${row.weight} receipt=${row.receipt}` : 'edge not found');
  check('seed: stone→pq sign claim records the currency event and the merge sha',
    row?.claim.includes('CURRENCY EARNED 2026-09-27') && row?.claim.includes('07384ac2'),
    row ? 'claim carries the merge receipt' : 'edge not found');
  check('seed: stone→pq sign declares a falsification condition (kill switch)',
    typeof row?.falsification_condition === 'string' && row.falsification_condition.length > 20,
    row?.falsification_condition ?? 'none');
  check('seed: stone→pq sign provenance records the sign-lane source merge (quilt-stone#4)',
    row?.provenance === 'SuperInstance/quilt-stone#4', row?.provenance ?? 'none');
  const sl = seed.nodes.get('stone-sign-lane'), pq2 = seed.nodes.get('pq-sign-pilot');
  check('seed: both endpoints exist in their own repos',
    sl?.repo === 'quilt-stone' && pq2?.repo === 'pong-quilt', `${sl?.repo} -> ${pq2?.repo}`);
  check('seed: receipt target is the to-node\'s repo (weight law, substrate-enforced)',
    row?.receipt.split('#')[0] === `SuperInstance/${pq2?.repo}`, row?.receipt);
  const fromStone = seed.rows.filter(r => r.op === 'LINK' && seed.nodes.get(r.from)?.repo === 'quilt-stone');
  check('seed: quilt-stone carries its FIRST outgoing VERIFIED edge (it received edge #9 five hours earlier)',
    fromStone.length === 1 && fromStone[0].to === 'pq-sign-pilot', fromStone.map(r => `${r.from}->${r.to}`).join(' '));
  const toPq = seed.rows.filter(r => r.op === 'LINK' && seed.nodes.get(r.to)?.repo === 'pong-quilt' && r.weight === 'VERIFIED');
  check('seed: pong-quilt carries TWO VERIFIED inbound edges — the coin tiebreak + the sign pilot, tying fleet-murmur for double mass',
    toPq.length === 2 && toPq.every(r => r.receipt.startsWith('SuperInstance/pong-quilt#')),
    toPq.map(r => `${r.from}->${r.to}`).join(' '));
}

// Pin 3l — the ELEVENTH edge, FLIPPED VERIFIED 2026-09-30 (09:11 pulse):
// the KAT bridge lane. Booked PENDING at 08:11 on jev-quilt#47 being OPEN;
// jev-quilt#47 MERGED 2026-09-30T00:18:30Z (merge 45912589941ce29f02c8a6659
// bfe2b4e7abfccb9) with the load-bearing citation intact on main (verified
// by hand: tools/jev_kat_bridge.mjs pins repo + commit 3f8405888366e3697b377
// 5017fa5fe13d6244226 + sha256 5f280b8b…e1cc5; tests/test_jev_kat_bridge.py
// asserts the citation string survives). Discovery surfaced the candidate;
// the load-bearing read was human — never self-upgraded. FAIL-first: on the
// pre-flip booking tip the flip pins trip (weight was PENDING, receipt null).
{
  const row = seed.rows.find(r => r.op === 'LINK' && r.from === 'aw-jev-kat' && r.to === 'jq-kat-bridge');
  check('seed: aw→jq KAT edge is VERIFIED with the merged citing PR as its receipt (currency earned)',
    row?.weight === 'VERIFIED' && row?.receipt === 'SuperInstance/jev-quilt#47',
    row ? `weight=${row.weight} receipt=${row.receipt}` : 'edge not found');
  check('seed: aw→jq claim records the booking (OPEN at booking) AND the earned currency (CURRENCY EARNED)',
    row?.claim.includes('SuperInstance/jev-quilt#47') && row?.claim.includes('OPEN at booking') && row?.claim.includes('CURRENCY EARNED'),
    row ? 'claim carries booking history + merge record' : 'edge not found');
  check('seed: aw→jq provenance is structured and equals the receipt (the citing PR is the finding home)',
    row?.provenance === 'SuperInstance/jev-quilt#47',
    row?.provenance ?? 'none');
  check('seed: aw→jq declares a falsification condition (kill switch)',
    typeof row?.falsification_condition === 'string' && row.falsification_condition.length > 20,
    row?.falsification_condition ?? 'none');
  const aw = seed.nodes.get('aw-jev-kat'), jq = seed.nodes.get('jq-kat-bridge');
  check('seed: both endpoints exist in their own repos',
    aw?.repo === 'AI-Writings' && jq?.repo === 'jev-quilt', `${aw?.repo} -> ${jq?.repo}`);
  const toJq = seed.rows.filter(r => r.op === 'LINK' && seed.nodes.get(r.to)?.repo === 'jev-quilt');
  check('seed: this is jev-quilt\'s FIRST inbound edge — its first view mass (both prior edges were outgoing)',
    toJq.length === 1 && toJq[0].from === 'aw-jev-kat', toJq.map(r => `${r.from}->${r.to}`).join(' '));
}

// Pin 3m — the TWELFTH edge VERIFIED 2026-09-30 (14:56 pulse): the
// lab↔ledger pair, ledger→lab direction. The booking corrects a FALSE
// NEGATIVE — the 14:38 pulse's citation scan reported micrograd-quilt main
// citing SuperInstance/MicroMoth-quilt ZERO times; the re-audit found
// micrograd-quilt#7's merged tree names it at 4+ anchored sites, so no
// citation PR was opened and the edge is booked directly on Casey's merge.
{
  const r = seed.rows.find(x => x.op === 'LINK' && x.from === 'mm-sealed-receipts' && x.to === 'mgq-qcells-lab');
  check('seed: mm→mgq edge is VERIFIED with micrograd-quilt#7 receipt in the to-node\'s repo',
    r?.weight === 'VERIFIED' && r?.receipt === 'SuperInstance/micrograd-quilt#7',
    r ? `weight=${r.weight} receipt=${r.receipt}` : 'edge not found');
  check('seed: mm→mgq claim records the currency event and the merge sha',
    r?.claim.includes('MERGED 2026-09-30T04:49:20Z') && r?.claim.includes('44de605'),
    r ? 'claim carries the merge receipt' : 'edge not found');
  check('seed: mm→mgq claim carries the FALSE-NEGATIVE honesty note (the 14:38 scan was wrong; no citation PR opened)',
    r?.claim.includes('FALSE NEGATIVE') && r?.claim.includes('citation spam'),
    r ? 'honesty note present' : 'edge not found');
  check('seed: mm→mgq declares a falsification condition (kill switch)',
    typeof r?.falsification_condition === 'string' && r.falsification_condition.length > 20,
    r?.falsification_condition ?? 'none');
  check('seed: mm→mgq provenance is the exp018 seal the synergy scan consumes',
    r?.provenance === 'SuperInstance/MicroMoth-quilt#24',
    r?.provenance ?? 'none');
  const nf = seed.nodes.get(r?.from), nt = seed.nodes.get(r?.to);
  check('seed: mm→mgq both endpoints exist in their own repos',
    nf?.repo === 'MicroMoth-quilt' && nt?.repo === 'micrograd-quilt',
    `${nf?.repo} -> ${nt?.repo}`);
  check('seed: mm→mgq receipt target is the to-node\'s repo (weight law, substrate-enforced)',
    r?.receipt?.startsWith(`SuperInstance/${nt?.repo}#`), r?.receipt ?? 'none');
  const toMgq = seed.rows.filter(x => x.op === 'LINK' && x.to === 'mgq-qcells-lab');
  check('seed: mm→mgq is micrograd-quilt\'s FIRST inbound edge — the lab enters the view at VERIFIED mass, not epsilon',
    toMgq.length === 1 && toMgq[0].from === 'mm-sealed-receipts',
    toMgq.map(x => `${x.from}->${x.to} (its first inbound edge — VERIFIED mass on arrival)`).join(' '));
}

// Pin 3n — the THIRTEENTH edge: booked PENDING 2026-09-30 (14:56 pulse),
// FLIPPED VERIFIED the same day (17:56 pulse) on MicroMoth-quilt#29 merging.
// First bidirectional pair now VERIFIED in BOTH directions.
{
  const r = seed.rows.find(x => x.op === 'LINK' && x.from === 'mgq-qcells-lab' && x.to === 'mm-sealed-receipts');
  check('seed: mgq→mm edge is VERIFIED with receipt in the to-node\'s repo — a workspace-path citation named the work; MicroMoth-quilt#29 named the repo and earned the currency',
    r?.weight === 'VERIFIED' && r?.receipt === 'SuperInstance/MicroMoth-quilt#29',
    r ? `weight=${r.weight} receipt=${r.receipt}` : 'edge not found');
  check('seed: mgq→mm claim records the doctrinal-citation shape and the git-agent#1 precedent',
    r?.claim.includes('workspace/labs/qcells') && r?.claim.includes('never the repo') && r?.claim.includes('git-agent#1'),
    r ? 'claim carries the citation-shape analysis' : 'edge not found');
  check('seed: mgq→mm declares a falsification condition (kill switch)',
    typeof r?.falsification_condition === 'string' && r.falsification_condition.length > 20,
    r?.falsification_condition ?? 'none');
  check('seed: mgq→mm provenance is the seal whose producer-citation shape is the claim\'s subject',
    r?.provenance === 'SuperInstance/MicroMoth-quilt#24',
    r?.provenance ?? 'none');
  const nf = seed.nodes.get(r?.from), nt = seed.nodes.get(r?.to);
  check('seed: mgq→mm both endpoints exist in their own repos',
    nf?.repo === 'micrograd-quilt' && nt?.repo === 'MicroMoth-quilt',
    `${nf?.repo} -> ${nt?.repo}`);
  const toMm = seed.rows.filter(x => x.op === 'LINK' && x.to === 'mm-sealed-receipts');
  check('seed: mgq→mm is MicroMoth-quilt\'s FIRST inbound edge — the ledger enters the view at VERIFIED mass; earned by the target-repo merge (MicroMoth-quilt#29), never self-upgraded; mirror of the VERIFIED mm→mgq edge — first bidirectional pair VERIFIED in both directions',
    toMm.length === 1 && toMm[0].from === 'mgq-qcells-lab',
    toMm.map(x => `${x.from}->${x.to} (its first inbound edge — VERIFIED mass)`).join(' '));
}

// Pin 3o — the FOURTEENTH edge: the e-witness instrument-consumption lane,
// booked PENDING TWICE (23:56 9/30 branch edge14-pending-delta-shape commit
// 7ddd151 — lost in a /tmp wipe; rebuilt 02:41 as quilt-tools#31 merge
// 812a644 — later reset off main) and landed directly at VERIFIED 2026-10-01
// (04:12 pulse) when the merge outran the booking: delta-shape#1 MERGED
// 2026-09-30T19:31:08Z (merge 57c07426) with the quilt-ewitness citation
// load-bearing on main (byte-pinned vendor + sha256 gate + README).
{
  const r = seed.rows.find(x => x.op === 'LINK' && x.from === 'qe-eproc-witness' && x.to === 'ds-esign-drift');
  check('seed: qe→ds edge is VERIFIED with receipt in the to-node\'s repo — delta-shape#1 merged with the SuperInstance/quilt-ewitness citation load-bearing (vendored bytes @ 61b9e04, sha256 aad90ac5..., witnessDrift() hash-gates before trusting)',
    r?.weight === 'VERIFIED' && r?.receipt === 'SuperInstance/delta-shape#1',
    r ? `weight=${r.weight} receipt=${r?.receipt}` : 'edge not found');
  check('seed: qe→ds claim records the merge facts (57c07426, 2026-09-30T19:31:08Z, sha256 aad90ac5) and the double-booking history (7ddd151 wipe, 812a644 reset)',
    r?.claim.includes('57c07426') && r?.claim.includes('aad90ac5') && r?.claim.includes('7ddd151') && r?.claim.includes('812a644'),
    r ? 'claim carries merge facts + honest history' : 'edge not found');
  check('seed: qe→ds declares a falsification condition (kill switch)',
    typeof r?.falsification_condition === 'string' && r.falsification_condition.length > 20,
    r?.falsification_condition ?? 'none');
  check('seed: qe→ds provenance is the merged PR whose vendored-bytes citation is the claim\'s subject',
    r?.provenance === 'SuperInstance/delta-shape#1',
    r?.provenance ?? 'none');
  const nf = seed.nodes.get(r?.from), nt = seed.nodes.get(r?.to);
  check('seed: qe→ds both endpoints exist in their own repos (quilt-ewitness from-node, delta-shape to-node)',
    nf?.repo === 'quilt-ewitness' && nt?.repo === 'delta-shape',
    `${nf?.repo} -> ${nt?.repo}`);
  const toDs = seed.rows.filter(x => x.op === 'LINK' && x.to === 'ds-esign-drift');
  check('seed: qe→ds is delta-shape\'s FIRST inbound edge — the sixth to-node born after seeding enters the view at full VERIFIED mass; earned by the target-repo merge (delta-shape#1), never self-upgraded',
    toDs.length === 1 && toDs[0].from === 'qe-eproc-witness',
    toDs.map(x => `${x.from}->${x.to} (its first inbound edge — VERIFIED mass)`).join(' '));
}

// Pin 3p — the FIFTEENTH edge VERIFIED 2026-10-01 (06:56 snowball pulse):
// the refusal-events ledger lane. FAIL-first: on main tip this edge does not
// exist (the currency pins trip). fleet-murmur#8 ("Refusal-events ledger:
// draft-kamimura-scitt-refusal-events-03 × pong-quilt named refusals",
// MERGED 2026-09-30T19:31:12Z, merge b21a4a46) lands
// docs/ietf-kamimura-refusal-events-ledger.md in the to-node's repo auditing
// pong-quilt main's named refusal corpus against
// draft-kamimura-scitt-refusal-events-03 — SuperInstance/pong-quilt named BY
// NAME at a pinned main merge, with a FAIL-first corpus pin in tests/ so a
// drifted citation cannot pass silently.
{
  const row = seed.rows.find(r => r.op === 'LINK' && r.from === 'pq-named-refusals' && r.to === 'fm-refusal-ledger');
  check('seed: pq-refusals→fm edge is VERIFIED with fleet-murmur#8 receipt in the to-node\'s repo',
    row?.weight === 'VERIFIED' && row?.receipt === 'SuperInstance/fleet-murmur#8',
    row ? `weight=${row.weight} receipt=${row.receipt}` : 'edge not found');
  check('seed: pq-refusals→fm claim records the currency event and the merge sha',
    row?.claim.includes('CURRENCY EARNED 2026-09-30') && row?.claim.includes('b21a4a4'),
    row ? 'claim carries the merge receipt' : 'edge not found');
  check('seed: pq-refusals→fm declares a falsification condition (kill switch)',
    typeof row?.falsification_condition === 'string' && row.falsification_condition.length > 20,
    row?.falsification_condition ?? 'none');
  const pqr = seed.nodes.get('pq-named-refusals'), fml = seed.nodes.get('fm-refusal-ledger');
  check('seed: both endpoints exist in their own repos',
    pqr?.repo === 'pong-quilt' && fml?.repo === 'fleet-murmur', `${pqr?.repo} -> ${fml?.repo}`);
  check('seed: receipt target is the to-node\'s repo (weight law, substrate-enforced)',
    row?.receipt.split('#')[0] === `SuperInstance/${fml?.repo}`, row?.receipt);
}

// Pin 4 — provenance live audit: every cited PR must actually be merged.
// gh absence -> skip labeled SKIPPED (honest), never pass silently.
{
  let ghOK = false, checked = 0, unmerged = [];
  try {
    execFileSync('gh', ['auth', 'status'], { stdio: 'pipe' });
    ghOK = true;
  } catch { ghOK = false; }
  if (LIVE && ghOK) {
    for (const row of seed.rows) {
      const prs = [];
      if (row.provenance) prs.push(['provenance', row.provenance]);
      if (row.receipt) prs.push(['receipt', row.receipt]);
      for (const [kind, pr] of prs) {
        checked++;
        const [repo, num] = pr.split('#');
        try {
          const state = execFileSync('gh', ['pr', 'view', num, '-R', repo, '--json', 'state', '-q', '.state'], { stdio: 'pipe' }).toString().trim();
          if (state !== 'MERGED') unmerged.push(`${row.from}->${row.to} ${kind} ${pr}=${state}`);
        } catch { unmerged.push(`${row.from}->${row.to} ${kind} ${pr}=404`); }
      }
    }
    check('seed: live audit — all provenance + receipt PRs merged', unmerged.length === 0, unmerged.join(' ') || `${checked} receipts audited live`);
  } else {
    console.log(`  ${'·'} provenance live audit SKIPPED (gh=${ghOK}, --live=${LIVE}) — labeled, not silent`);
  }
}

// Pin 5 — falsification probe on the real graph: the declared kill condition
// kills, and the kill is booked as a REFUSED row; surviving evidence books EFFECT.
{
  const g2 = new ReferralGraph({ name: 'probe-copy', repos: QUANT_REPOS });
  for (const n of (await import('./referral_graph.seed.mjs')).SEED.nodes) g2.addNode(n);
  for (const e of (await import('./referral_graph.seed.mjs')).SEED.edges) g2.book(e);
  const edge = g2.rows.find(r => r.op === 'LINK' && r.from === 'qt-s2-driftwatch' && r.to === 'qs-ep2');
  const survive = g2.probe(edge.from, edge.to, 'unrelated observation: readme typo');
  check('seed: off-condition probe books EFFECT, no kill', survive.hit === false && survive.row.op === 'EFFECT', survive.row.claim);
  const kill = g2.probe(edge.from, edge.to, edge.falsification_condition);
  check('seed: falsification condition kills the edge', kill.hit === true && kill.row.op === 'REFUSED', kill.row.claim);
  const v = g2.view();
  const qsShare = v.find(x => x.repo === 'quilt-show')?.share ?? 0;
  check('seed: killed edge drops its mass from the view', qsShare < seed.view().find(x => x.repo === 'quilt-show').share, `qs ${seed.view().find(x => x.repo === 'quilt-show').share.toFixed(3)} -> ${qsShare.toFixed(3)}`);
}

// ── FIXTURE graph (synthetic, labeled) ──────────────────────────────────────
function fixture() {
  const g = new ReferralGraph({ name: 'fixture' });
  g.addNode({ id: 'a', repo: 'repo-a', summary: 'fixture node a' });
  g.addNode({ id: 'b', repo: 'repo-b', summary: 'fixture node b' });
  g.addNode({ id: 'c', repo: 'repo-c', summary: 'fixture node c' });
  return g;
}

// Pin 6 — VERIFIED currency rules.
{
  const g = fixture();
  let m1 = '';
  try { g.book({ from: 'a', to: 'b', claim: 'x', falsification_condition: 'y', weight: 'VERIFIED' }); } catch (e) { m1 = e.message; }
  check('fixture: VERIFIED without receipt -> REFUSAL', /VERIFIED without receipt/.test(m1), m1);

  const g2 = fixture();
  let m2 = '';
  try { g2.book({ from: 'a', to: 'b', claim: 'x', falsification_condition: 'y', weight: 'VERIFIED', receipt: 'SuperInstance/repo-a#9' }); } catch (e) { m2 = e.message; }
  check('fixture: receipt in the WRONG repo -> REFUSAL', /not the to-node's repo/.test(m2), m2);

  const g3 = fixture();
  let okRow = null;
  try { okRow = g3.book({ from: 'a', to: 'b', claim: 'x', falsification_condition: 'y', weight: 'VERIFIED', receipt: 'SuperInstance/repo-b#9' }); } catch (e) { okRow = e.message; }
  check('fixture: receipt in the to-node\'s repo -> booked', okRow?.op === 'LINK' && okRow?.weight === 'VERIFIED', typeof okRow === 'string' ? okRow : okRow.row_hash);

  const g4 = fixture();
  let m4 = '';
  try { g4.book({ from: 'a', to: 'b', claim: 'x', falsification_condition: 'y', weight: 'PENDING', receipt: 'SuperInstance/repo-b#9' }); } catch (e) { m4 = e.message; }
  check('fixture: PENDING edge carrying a receipt -> REFUSAL', /weight must be earned/.test(m4), m4);

  const g5 = fixture();
  let m5 = '';
  try { g5.book({ from: 'a', to: 'b', claim: 'x', falsification_condition: 'y', weight: 'PENDING', provenance: 'not-a-pr-link' }); } catch (e) { m5 = e.message; }
  check('fixture: malformed provenance -> REFUSAL', /provenance/.test(m5), m5);

  const g6 = fixture();
  let m6 = '';
  try { g6.book({ from: 'a', to: 'a', claim: 'x', falsification_condition: 'y', weight: 'PENDING' }); } catch (e) { m6 = e.message; }
  check('fixture: self-referral -> REFUSAL', /self-referral/.test(m6), m6);
}

// Pin 7 — audit downgrade: unmerged receipt -> PENDING, downgrade booked.
{
  const g = fixture();
  g.book({ from: 'a', to: 'b', claim: 'x', falsification_condition: 'y', weight: 'VERIFIED', receipt: 'SuperInstance/repo-b#9' });
  g.book({ from: 'b', to: 'c', claim: 'p', falsification_condition: 'q', weight: 'VERIFIED', receipt: 'SuperInstance/repo-c#4' });
  const res = g.auditReceipts(r => r === 'SuperInstance/repo-c#4'); // repo-b#9 is NOT merged
  const downgraded = g.rows.find(r => r.op === 'REFUSED' && r.claim.includes('downgraded'));
  const edgeAB = g.rows.find(r => r.op === 'LINK' && r.from === 'a');
  check('fixture: unmerged receipt downgraded + booked', res.find(x => !x.merged)?.receipt === 'SuperInstance/repo-b#9' && downgraded && edgeAB.weight === 'PENDING' && edgeAB.receipt === null, downgraded?.claim ?? 'no downgrade row');
  const v = g.view();
  check('fixture: view reflects downgrade (repo-b mass = epsilon)', Math.abs(v.find(x => x.repo === 'repo-b').weight - PENDING_WEIGHT) < 1e-9, JSON.stringify(v));
}

// Pin 8 — VERIFIED outranks PENDING in the view.
{
  const g = fixture();
  g.book({ from: 'a', to: 'b', claim: 'verified cross-use', falsification_condition: 'k1', weight: 'VERIFIED', receipt: 'SuperInstance/repo-b#9' });
  g.book({ from: 'a', to: 'c', claim: 'mere speculation', falsification_condition: 'k2', weight: 'PENDING' });
  const v = g.view();
  const b = v.find(x => x.repo === 'repo-b'), c = v.find(x => x.repo === 'repo-c');
  check('fixture: VERIFIED dominates PENDING (20x weight ratio)',
    b.weight === VERIFIED_WEIGHT && Math.abs(c.weight - PENDING_WEIGHT) < 1e-9 && b.share > c.share,
    `repo-b=${b.share.toFixed(3)} repo-c=${c.share.toFixed(3)}`);
}

// Pin 9 — the discovery audit (REFERRAL_GRAPH.md "Next rungs"). Injected
// stream, three claims: (a) a merged PR in the TO-node's repo citing a hint
// surfaces as a candidate; (b) the search is scoped to the to-repo — the
// searchFn must be called with the to-node's repo, never the from-node's
// (a hit in the wrong repo is not currency); (c) non-live mode is SKIPPED
// labeled, and already-VERIFIED edges are never scanned (auditReceipts
// guards those).
{
  const { SEED } = await import('./referral_graph.seed.mjs');
  const { discover, HINTS } = await import('./referral_graph.discovery.mjs');
  const scoped = [];
  const fakeSearch = (hint, repoFull) => {
    scoped.push(repoFull);
    if (hint === 'receipts flip credit' && repoFull === 'SuperInstance/quilt-show') {
      return [{ number: 42, title: 'episode 5: receipts flip credit, demonstrated', url: 'u' }];
    }
    if (hint === 'drag-to-reshape' && repoFull === 'SuperInstance/quilt-arcade') {
      return [{ number: 3, title: 'Pong: realtime laws on the discrete sheet (plugin #6)', url: 'u' }];
    }
    return [];
  };
  const verifiedCalls = [];
  const fakeVerify = (hint, number, repoFull) => { verifiedCalls.push([hint, number, repoFull]); return true; };
  const offline = discover(SEED, { live: false });
  check('discovery: offline mode reports SKIPPED, never passes silently',
    offline.every(r => r.skipped === true), offline.map(r => `${r.edge}:${r.skipped}`).join(' '));
  const live = discover(SEED, { live: true, searchFn: fakeSearch, verifyFn: fakeVerify });
  const e2 = live.find(r => r.edge === 'qt-api-lab->qs-ep2');
  check('discovery: hint hit in the TO repo surfaces as candidate',
    e2.candidates.some(c => c.pr === '#42' && c.hint === 'receipts flip credit' && !c.fuzzyRejected && !c.verifyUnknown), JSON.stringify(e2.candidates));
  const toRepos = new Set(SEED.edges.map(e => `${'SuperInstance'}/${SEED.nodes.find(n => n.id === e.to).repo}`));
  check('discovery: every live search scoped to a to-node repo',
    scoped.length > 0 && scoped.every(r => toRepos.has(r)), scoped.join(','));
  check('discovery: VERIFIED edge (s2->ep2) is not scanned',
    !live.some(r => r.edge === 'qt-s2-driftwatch->qs-ep2'), live.map(r => r.edge).join(' '));
  check('discovery: every PENDING edge was scanned',
    live.filter(r => !r.skipped).length === SEED.edges.filter(e => e.weight === 'PENDING').length,
    `${live.length} results vs ${SEED.edges.filter(e => e.weight === 'PENDING').length} PENDING edges`);

  // Pin 10 — anti-Goodhart guard: the graph's own artifact cannot mint its
  // currency. A hit whose title matches SELF_REFERENTIAL is excluded.
  const selfSearch = (hint, repoFull) =>
    hint === 'NEGATIVE_SPACE' && repoFull === 'SuperInstance/quilt-tools'
      ? [{ number: 6, title: 'REFERRAL_GRAPH PoC: the mesh answers as a distribution', url: 'u' }]
      : [];
  const liveSelf = discover(SEED, { live: true, searchFn: selfSearch, verifyFn: fakeVerify });
  const neg = liveSelf.find(r => r.edge === 'qa-negspace->qt-api-lab');
  check('discovery: graph-owned PR flagged self-referential, not a candidate',
    neg.candidates.length === 1 && neg.candidates[0].selfReferential === true && neg.candidates[0].pr === '#6',
    JSON.stringify(neg.candidates));

  // Pin 12 — fuzzy-match guard (real false positive, live run 2026-09-28):
  // gh search prs RANKS, it does not filter — quilt-arcade#3 surfaced for
  // 'drag-to-reshape' yet never mentions it. A hit the verifyFn rejects
  // must be flagged fuzzyRejected (surfaced, not booked, not dropped), the
  // verify call must be scoped to the TO repo, a verify error is
  // verify-unknown (never a silent pass), and a verified hit carries no
  // rejection flag at all.
  const rejectingVerify = (hint, number, repoFull) => { verifiedCalls.push([hint, number, repoFull]); return false; };
  const liveFuzzy = discover(SEED, { live: true, searchFn: fakeSearch, verifyFn: rejectingVerify });
  const ep3 = liveFuzzy.find(r => r.edge === 'qs-ep3->qa-plugins');
  check('discovery: unverified search hit flagged fuzzyRejected, not a candidate',
    ep3.candidates.length === 1 && ep3.candidates[0].fuzzyRejected === true && ep3.candidates[0].pr === '#3',
    JSON.stringify(ep3.candidates));
  check('discovery: verify scoped to the TO repo',
    verifiedCalls.length > 0 && verifiedCalls.every(([, , repo]) => toRepos.has(repo)),
    verifiedCalls.map(c => c[2]).join(','));
  const erroringVerify = () => null;
  const liveUnknown = discover(SEED, { live: true, searchFn: fakeSearch, verifyFn: erroringVerify });
  const e2u = liveUnknown.find(r => r.edge === 'qt-api-lab->qs-ep2');
  check('discovery: verify error is verify-unknown, never a silent pass',
    e2u.candidates.length === 1 && e2u.candidates[0].verifyUnknown === true && !e2u.candidates[0].fuzzyRejected,
    JSON.stringify(e2u.candidates));
}

// Pin 11 — the G11 TRUST LEVER, ported from SuperInstance/jev-quilt commons.py
// (trust_weighted()/provenance_merge(), G11 "trust-weighted cross-fleet
// gluing", merged as SuperInstance/jev-quilt#37): the blind view sums edge
// weight per target repo, and an adversary who controls a repo can mint
// junk-citation PRs into it and BUY mass. viewTrusted re-scales each edge by
// its TARGET repo's EARNED trust: effective = trust.get(repo, default) ·
// weight. Unseen source defaults to 0 — it contributes nothing until the
// fleet earns reason to trust it. FAIL-first: on main tip viewTrusted does
// not exist (ReferenceError at import/use — the pin trips by inspection).
{
  // fixture: an adversary repo floods VERIFIED receipts into itself; one
  // honest repo holds a single real edge. Test data, never real findings.
  const junk = new ReferralGraph({ name: 'trust-fixture', repos: ['acme-junk', 'honest-tool'] });
  junk.addNode({ id: 'src-a', repo: 'fleet-src', summary: 'fixture source A' });
  junk.addNode({ id: 'src-b', repo: 'fleet-src', summary: 'fixture source B' });
  for (let i = 0; i < 3; i++) junk.addNode({ id: `honest-node-${i}`, repo: 'honest-tool', summary: `fixture honest ${i}` });
  for (let i = 0; i < 10; i++) {
    junk.addNode({ id: `junk-node-${i}`, repo: 'acme-junk', summary: `fixture junk ${i}` });
    junk.book({ from: 'src-a', to: `junk-node-${i}`, claim: `junk citation ${i}`, weight: 'VERIFIED',
      receipt: `acme-junk-owner/acme-junk#${i + 1}`, falsification_condition: `never-${i}` });
  }
  junk.book({ from: 'src-b', to: 'honest-node-0', claim: 'one honest edge', weight: 'VERIFIED',
    receipt: 'honest-owner/honest-tool#1', falsification_condition: 'never-honest' });

  const blind = junk.view();
  const junkBlind = blind.find(x => x.repo === 'acme-junk');
  check('trust-fixture: blind view is BUYABLE — 10 junk receipts outweigh 1 honest edge',
    junkBlind && junkBlind.share > 0.9, `junk blind share ${(junkBlind?.share * 100).toFixed(1)}%`);

  const trusted = junk.viewTrusted({ trust: { 'honest-tool': 1 } }); // acme-junk UNSEEN
  check('trust-fixture: viewTrusted with unseen junk source → junk mass 0, honest tool 100%',
    trusted.length === 1 && trusted[0].repo === 'honest-tool' && trusted[0].share === 1,
    trusted.map(x => `${x.repo} ${(x.share * 100).toFixed(1)}%`).join(' ') || 'EMPTY');

  const both = junk.viewTrusted({ trust: { 'honest-tool': 1, 'acme-junk': 1 } });
  check('trust-fixture: trust 1 everywhere reduces to the blind view (same ranking, same shares)',
    JSON.stringify(both) === JSON.stringify(blind),
    both.map(x => `${x.repo}=${x.share.toFixed(3)}`).join(' '));

  const lever = junk.viewTrusted({ trust: { 'honest-tool': 10, 'acme-junk': 0 } });
  check('trust-fixture: trust is THE lever — weight 10×0 cannot outrun trust 0, weight 1×10 outranks weight 10×1 only by trust, not by count',
    lever.find(x => x.repo === 'honest-tool').share === 1 && !lever.some(x => x.repo === 'acme-junk'),
    lever.map(x => `${x.repo} ${(x.share * 100).toFixed(1)}%`).join(' '));

  const mapForm = junk.viewTrusted({ trust: new Map([['honest-tool', 1]]) });
  check('trust-fixture: Map-form trust table behaves identically to object form',
    JSON.stringify(mapForm) === JSON.stringify(trusted), mapForm.map(x => x.repo).join(','));

  const seedTrustAll1 = seed.viewTrusted({ trust: Object.fromEntries(seed.view().map(x => [x.repo, 1])) });
  check('seed: trust-1-for-every-mass-carrying-repo ≡ blind view (regression guard on _view refactor)',
    JSON.stringify(seedTrustAll1) === JSON.stringify(seed.view()),
    seedTrustAll1.map(x => `${x.repo} ${(x.share * 100).toFixed(1)}%`).join(' · '));

  const src = (await import('node:fs')).readFileSync(new URL('../src/referral_graph.mjs', import.meta.url), 'utf8');
  check('weight law: G11 port cites its canonical source SuperInstance/jev-quilt commons.py BY NAME (the VERIFIED-edge citation, same honesty pattern as the moth-waveform scar)',
    /SuperInstance\/jev-quilt commons\.py/.test(src) && /provenance_merge/.test(src),
    'citation present in src/referral_graph.mjs');
}

panel('referral-graph v1 — the mesh answers as a distribution', [
  kv('nodes', '32 (17 repos)'), kv('edges', '19 — 15 VERIFIED · 4 PENDING'),
  kv('currency', '15 VERIFIED (show#1 cites S2 · pong#28 cites coin-toss-v1 · git-agent#4 cites algebra.md · cowboy#1 cites jev-quilt · fleet-murmur#2 cites pong-quilt · moth-waveform#1 cites the fm vacuity scar · fleet-murmur#3 cites quality-gate-stream · quilt-tools#17 cites jev-quilt commons.py G11 · quilt-stone#1 cites pong-quilt R36 toStoneV1 · pong-quilt#51 staples with quilt-stone#4\'s signTip · jev-quilt#47 cites the AI-Writings KAT instrument · micrograd-quilt#7 cites the MicroMoth-quilt ledger by name across the qcells lab · MicroMoth-quilt#29 cites SuperInstance/micrograd-quilt as the qcells lab canonical home · delta-shape#1 cites SuperInstance/quilt-ewitness as a sha256-pinned vendored e-witness instrument · fleet-murmur#8 cites pong-quilt\'s named-refusal corpus at a pinned main merge) — doctrine flows outward fifteen ways; the mm⇄mgq pair is the graph\'s first bidirectional pair and both directions carry VERIFIED mass; the qe→ds edge booked PENDING twice (a /tmp wipe took 7ddd151, a main reset took 812a644) and the delta-shape#1 merge outran the booking — landed directly at VERIFIED 2026-10-01; jev-quilt holds its KAT inbound; pong-quilt remains double-inbound; fleet-murmur is the fleet\'s first TRIPLE-inbound (honesty#2 + qgs-adapter#3 + refusal-ledger#8); from-node-only repos carry no view mass; to-nodes born after seeding: fleet-murmur, moth-waveform, quilt-stone, micrograd-quilt, MicroMoth-quilt, delta-shape, fm-refusal-ledger'),
]);
done();
