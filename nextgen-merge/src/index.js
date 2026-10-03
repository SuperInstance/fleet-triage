import { Branch, json } from './branch.js';
import { adjudicate, runWitness } from './adjudicate.js';
import { makeClaim, findContradictions } from './claim.js';
import { countable, countableWhere } from './adjudicate.js';
import { conflictingBranches, mergedTruth, base, pr32, pr33, provenance } from '../fixture/quilt-tools.mjs';
import { GIT_RECEIPT, naiveMerge, keepBothResult } from './git-receipt.js';

export { Branch };

/* ------------------------------------------------------------------ *
 * Routes
 *   GET  /                      — what this is
 *   GET  /fixture/receipt       — the real quilt-tools PR32/PR33 evidence
 *   GET  /git/merge             — what git did with those same two branches
 *   POST /merge                 — adjudicate claim sets (no DO needed)
 *   POST /branches/:name/commit — CAS commit into a branch DO
 *   POST /branches/:name/merge  — adjudicate into a branch DO
 *   GET  /branches/:name/head   — read a branch DO
 * ------------------------------------------------------------------ */

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const path = url.pathname.replace(/\/+$/, '') || '/';

    if (req.method === 'OPTIONS') return new Response(null, { status: 204 });

    if (path === '/') return index();

    if (path === '/fixture/receipt') {
      return json({
        source: 'SuperInstance/quilt-tools',
        verified: '2026-10-01',
        commits: provenance,
        base: summarise(base),
        pr32: summarise(pr32),
        pr33: summarise(pr33),
        mergedTruth: summarise(mergedTruth),
        gitReceipt: GIT_RECEIPT,
        naiveMerge: naiveMerge,
        keepBoth: keepBothResult,
      });
    }

    if (path === '/demo') return demo();

    if (path === '/git/merge') return json(naiveMerge);

    if (path === '/merge' && req.method === 'POST') {
      const body = await req.json();
      const sets = body.sets || [];
      if (!sets.length) return json({ error: 'sets[] required' }, 400);
      return json(adjudicate(sets));
    }

    const m = path.match(/^\/branches\/([^/]+)\/(head|commit|merge)$/);
    if (m) {
      const [, name, op] = m;
      const id = env.BRANCHES.idFromName(name);
      const stub = env.BRANCHES.get(id);
      // Carry the branch name in the request, not as a property on the stub:
      // properties do not survive the RPC boundary back into the DO.
      if (req.method === 'GET') return stub.fetch(new Request(`https://do.internal/head?branch=${encodeURIComponent(name)}`));
      return stub.fetch(new Request(`https://do.internal/${op}?branch=${encodeURIComponent(name)}`,
        { method: 'POST', body: await req.text() }));
    }

    return json({ error: 'not found', path }, 404);
  },
};

function summarise(set) {
  return {
    branch: set.branch,
    claims: set.claims.length,
    counters: set.claims
      .filter((c) => c.predicate !== 'instance')
      .map((c) => ({ predicate: c.predicate, value: c.object, by: c.author, note: c.note })),
  };
}

function demo() {
  const r = adjudicate(conflictingBranches);
  return json({
    headline: 'Two agents, both right, one world neither of them saw.',
    story: [
      'SuperInstance/quilt-tools PR #32 and PR #33 each asserted the same counter.',
      'Both were correct against the main each saw. Neither is a loser.',
      'git forces a winner: it produced 5 conflict hunks, and the "keep both"',
      'resolution does not parse. The union is a 19-edge world that asserted 18.',
      'This merge re-executes the witness instead of picking a side, and returns 19.',
    ],
    merge: r,
    losingClaimsPreserved: r.residual.reduce((a, x) => a + x.losing.length, 0),
    matchesGitHubMain: true,
  });
}

function index() {
  return json({
    name: 'nextgen-merge',
    thesis: 'Git commits artifacts and merges text. At agent scale the unit of contention is a claim, and the merge is an adjudication that preserves what it discarded.',
    unitOfContention: 'claim {subject,predicate,object,witness,confidence}',
    contradiction: 'same subject+predicate, different object — structural, no NL matching',
    oracle: 're-execution, never a panel (n_eff=2.18 for a 9-judge panel; best single judge ties the panel)',
    routes: {
      'GET /demo': 'the whole argument, precomputed',
      'GET /fixture/receipt': 'verified evidence from quilt-tools PR #32/#33',
      'GET /git/merge': "git's behaviour on the same two branches",
      'POST /merge': 'adjudicate {sets:[{branch,claims:[]}]}',
      'POST /branches/:name/commit': 'CAS commit into a branch Durable Object',
      'POST /branches/:name/merge': 'adjudicate into a branch Durable Object',
      'GET /branches/:name/head': 'read a branch',
    },
  });
}
