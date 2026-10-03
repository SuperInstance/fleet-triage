/**
 * The real receipt, lifted from SuperInstance/quilt-tools.
 *
 * PR #32 (merge fb2e041) and PR #33 (merge 0101409) each independently
 * asserted the same counter. Both were CORRECT against the main each saw.
 * The merged truth is 19 edges / 15 VERIFIED / 4 PENDING.
 *
 * Neither is wrong. There is no loser. git's conflict model requires one.
 *
 * Verified against the live repo 2026-10-01:
 *   base  58e2a18  17 edges  13 VERIFIED  4 PENDING   (shared parent of both PRs)
 *   #32   a98a5c5  18 edges  14 VERIFIED  4 PENDING   asserts "18", "fourteen VERIFIED"
 *   #33   7caf5a3  18 edges  14 VERIFIED  4 PENDING   asserts "18", "fourteen VERIFIED"
 *   main  0101409  19 edges  15 VERIFIED  4 PENDING   asserts "19", "fifteen VERIFIED"
 */

import { makeClaim } from '../src/claim.js';
import { countable, countableWhere } from '../src/adjudicate.js';
import EDGES from './seed-edges-by-commit.json' with { type: 'json' };

const BASE = '58e2a18';
const PR32 = 'a98a5c5';
const PR33 = '7caf5a3';

const AUTHOR32 = 'agent/pr-32';
const AUTHOR33 = 'agent/pr-33';

/**
 * Turn one commit's edge list into claims.
 *
 * Each edge becomes two claims:
 *   (edge:<id>, instance, 1)                    -- the thing exists
 *   (repo-count, instance, <repo>)              -- per-repo cardinality
 * plus the aggregate counter claims the PR author actually wrote.
 */
function claimsFrom(commit, author) {
  const edges = EDGES[commit];
  const claims = [];

  for (const e of edges) {
    claims.push(makeClaim({
      subject: `edge:${e.from}->${e.to}`,
      predicate: 'instance',
      object: e.weight,
      witness: null,
      author,
      receipt: e.receipt,
      note: e.claim,
    }));
  }

  // The counter claims — the ones that actually conflicted.
  const verified = edges.filter((e) => e.weight === 'VERIFIED').length;
  const pending = edges.filter((e) => e.weight === 'PENDING').length;

  claims.push(makeClaim({
    subject: 'referral_graph.edges',
    predicate: 'count',
    object: edges.length,
    witness: countable('edge:*'),
    author,
    note: `pins.mjs: seedBooked === ${edges.length} && seed.rows.length === ${edges.length}`,
  }));
  claims.push(makeClaim({
    subject: 'referral_graph.edges',
    predicate: 'weight:VERIFIED',
    object: verified,
    witness: countableWhere('edge:*', 'VERIFIED'),
    author,
    note: `pins.mjs prose: "${numeral(verified)} VERIFIED"`,
  }));
  claims.push(makeClaim({
    subject: 'referral_graph.edges',
    predicate: 'weight:PENDING',
    object: pending,
    witness: countableWhere('edge:*', 'PENDING'),
    author,
    note: 'PENDING count',
  }));

  return claims;
}

function numeral(n) {
  return ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine',
    'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen',
    'eighteen', 'nineteen', 'twenty'][n] || String(n);
}

export const base = { branch: 'main@58e2a18', claims: claimsFrom(BASE, 'main') };
export const pr32 = { branch: 'edge14-verified-flip', claims: claimsFrom(PR32, AUTHOR32) };
export const pr33 = { branch: 'edge15-fm-refusal-ledger', claims: claimsFrom(PR33, AUTHOR33) };

/** The two PR branches as git saw them: true siblings off a shared parent. */
export const conflictingBranches = [pr32, pr33];

/** What actually landed on main (a98a5c5 and 7caf5a3 were re-merged). */
export const mergedTruth = { branch: 'main@0101409', claims: claimsFrom('0101409', 'main') };

export const provenance = { BASE, PR32, PR33, AUTHOR32, AUTHOR33 };
