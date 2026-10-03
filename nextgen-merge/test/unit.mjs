/**
 * Unit tests for the claim model and the adjudicator.
 * No framework. `node test/unit.mjs` must exit 0 or non-zero, and you should
 * believe the exit code.
 */

import { makeClaim, findContradictions, assertionKey } from '../src/claim.js';
import { adjudicate, runWitness, countable, countableWhere } from '../src/adjudicate.js';
import { conflictingBranches, mergedTruth } from '../fixture/quilt-tools.mjs';

let pass = 0, fail = 0;
function t(name, fn) {
  try { fn(); console.log(`  ok   ${name}`); pass++; }
  catch (e) { console.log(`  FAIL ${name}\n       ${e.message}`); fail++; }
}
function eq(a, b, msg) {
  const A = JSON.stringify(a), B = JSON.stringify(b);
  if (A !== B) throw new Error(`${msg || ''} expected ${B}, got ${A}`);
}
function ok(c, msg) { if (!c) throw new Error(msg || 'expected truthy'); }

console.log('\n  nextgen-merge — unit\n');

/* ---- the claim model ---- */

t('contradiction is structural, not linguistic', () => {
  const a = makeClaim({ subject: 'repo:x', predicate: 'count', object: 18 });
  const b = makeClaim({ subject: 'repo:x', predicate: 'count', object: 19 });
  // different words, different numbers, unrelated wording
  eq(findContradictions([a, b]).length, 1, 'one contradiction:');
});

t('same assertion from two agents is not a contradiction', () => {
  const a = makeClaim({ subject: 'repo:x', predicate: 'count', object: 18, author: 'p32' });
  const b = makeClaim({ subject: 'repo:x', predicate: 'count', object: 18, author: 'p33' });
  eq(findContradictions([a, b]).length, 0);
});

t('different subject is not a contradiction', () => {
  const a = makeClaim({ subject: 'repo:x', predicate: 'count', object: 18 });
  const b = makeClaim({ subject: 'repo:y', predicate: 'count', object: 19 });
  eq(findContradictions([a, b]).length, 0);
});

t('object equality is type-aware via canonical()', () => {
  const a = makeClaim({ subject: 's', predicate: 'p', object: { x: 1, y: 2 } });
  const b = makeClaim({ subject: 's', predicate: 'p', object: { y: 2, x: 1 } });
  eq(assertionKey(a), assertionKey(b), 'key order must not matter:');
  eq(findContradictions([a, b]).length, 0);
});

/* ---- witnesses ---- */

t('count witness re-runs over the merged world', () => {
  const claims = [
    makeClaim({ subject: 'edge:1', predicate: 'instance', object: 'V' }),
    makeClaim({ subject: 'edge:2', predicate: 'instance', object: 'V' }),
  ];
  eq(runWitness(countable('edge:*'), claims).value, 2);
});

t('countWhere filters by object value', () => {
  const claims = [
    makeClaim({ subject: 'edge:1', predicate: 'instance', object: 'VERIFIED' }),
    makeClaim({ subject: 'edge:2', predicate: 'instance', object: 'PENDING' }),
  ];
  eq(runWitness(countableWhere('edge:*', 'VERIFIED'), claims).value, 1);
});

t('prose witness is unrunnable — we abstain, we do not guess', () => {
  const r = runWitness({ kind: 'prose', text: 'the graph looks right' }, []);
  ok(!r.ok && r.reason === 'prose-not-runnable');
});

/* ---- adjudication ---- */

t('two agents agreeing on a false count: merge derives the truth', () => {
  const mk = (n, author) => [
    ...Array.from({ length: n }, (_, i) => makeClaim({ subject: `edge:${author}${i}`, predicate: 'instance', object: 'V', author })),
    makeClaim({ subject: 'g', predicate: 'count', object: 1, witness: countable('edge:*'), author }),
  ];
  const r = adjudicate([
    { branch: 'a', claims: mk(3, 'a1') },
    { branch: 'b', claims: mk(4, 'b1') },
  ]);
  eq(r.derived.length, 1, 'one derived claim:');
  eq(r.derived[0].object, 7, 'union size:');
  eq(r.stats.losingClaimsPreserved, 2, 'both losing claims kept:');
});

t('abstention preserves every party and invents nothing', () => {
  const r = adjudicate([{
    branch: 'a',
    claims: [
      makeClaim({ subject: 'g', predicate: 'count', object: 18, witness: { kind: 'prose' }, author: 'p32' }),
      makeClaim({ subject: 'g', predicate: 'count', object: 19, witness: { kind: 'prose' }, author: 'p33' }),
    ],
  }]);
  eq(r.stats.abstained, 1, 'abstained once:');
  eq(r.derived.length, 0, 'no derived claim:');
  eq(r.residual[0].losing.length, 2, 'both parties preserved:');
});

/* ---- the real receipt ---- */

t('quilt-tools PR32+PR33 -> 19 edges / 15 VERIFIED, matching GitHub main', () => {
  const r = adjudicate(conflictingBranches);
  const count = r.claims.find((c) => c.subject === 'referral_graph.edges' && c.predicate === 'count');
  const ver = r.claims.find((c) => c.predicate === 'weight:VERIFIED');
  eq(count.object, 19, 'edges:');
  eq(ver.object, 15, 'VERIFIED:');
  ok(count.author === '@merge', 'the value was asserted by the merge, not by either agent:');
  eq(r.derived.length, 2);
});

t('the adjudicated result equals what actually landed on main', () => {
  const a = adjudicate(conflictingBranches);
  const truth = mergedTruth.claims;
  const fromMerge = (s, p) => a.claims.find((c) => c.subject === s && c.predicate === p)?.object;
  const fromMain = (s, p) => truth.find((c) => c.subject === s && c.predicate === p)?.object;
  for (const p of ['count', 'weight:VERIFIED', 'weight:PENDING']) {
    eq(fromMerge('referral_graph.edges', p), fromMain('referral_graph.edges', p), `${p}:`);
  }
});

t('merge is commutative and idempotent', () => {
  const A = adjudicate([conflictingBranches[0], conflictingBranches[1]]);
  const B = adjudicate([conflictingBranches[1], conflictingBranches[0]]);
  const key = (r) => r.claims.map((c) => assertionKey(c)).sort().join('|');
  eq(key(A), key(B), 'order must not change the outcome:');
  const C = adjudicate([...conflictingBranches, conflictingBranches[0]]);
  eq(key(C), key(A), 're-merging a branch already merged must be a no-op:');
});

console.log(`\n  ${pass} passed, ${fail} failed\n`);
process.exit(fail ? 1 : 0);
