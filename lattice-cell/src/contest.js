// lattice-cell — the disagreement protocol.
//
// THE VISION SAYS the lattice heals one another. It does not, and the reason
// is n_eff ≈ 2, measured six ways: a lattice of repositories from one account,
// one doctrine, one base model, and mostly one another as forks is the most
// correlated ensemble available. Differential testing across forks cannot
// catch a bug that was copied along with the code. So a lattice asked to
// adjudicate its own disagreement will agree loudly and be wrong together.
//
// THEREFORE THE LATTICE DOES NOT ADJUDICATE. It RECORDS.
//
// Three rules, each of which is a testable invariant rather than a principle:
//
//   C1  A contest is declared when two cells commit DIFFERENT values for the
//       same (cell-alias, dial) on divergent tips. Disagreement is a fact about
//       the substrate, detectable without a model and without a judge.
//   C2  The contest record is a PURE FUNCTION of the two commits — same
//       property as the receipt, pinned in pins/purity.log. Delete it and it
//       regenerates byte-identically from git alone. That is what makes a
//       cross-cell fact as durable as a per-repo one.
//   C3  MORE CELLS DO NOT RESOLVE A CONTEST. Agreement is counted, recorded,
//       and explicitly marked as NOT evidence. This is the one that has teeth
//       and it is a function with a measured output: see resolveWithPanel().
//
// The wire format is quilt-adjudication's, not a new one: the winner/loser/
// reason/`to_accept_the_loser` shape is already shipped and demoed there, and
// this lane has no business inventing a second dialect. What is added here is
// the part per-repo git cannot express — a fact that spans two repositories —
// and therefore the argument for a hub (see protocol/LATTICE.md §5).

import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const git = (cwd, ...a) => execFileSync('git', a, { cwd, encoding: 'utf8' });
const sha = (cwd, rev) => git(cwd, 'rev-parse', rev).trim();

function readClaim(cwd, rev, alias, dial) {
  try { return parseFloat(git(cwd, 'show', `${rev}:cells/${alias}/dials/${dial}`).trim()); }
  catch { return null; }
}
function frameOf(cwd, rev) {
  const b = git(cwd, 'log', '-1', '--format=%B', rev);
  const g = n => (new RegExp('^' + n + ':\\s*(.*)$', 'm').exec(b)?.[1] ?? null);
  return { dispatch_id: g('Dispatch-Id'), intent: g('Cell-Intent'), postcondition: g('Cell-Postcondition') };
}

/** C1. Is (tipA, tipB) a contest? Pure, and needs nothing but git. */
export function inspect(cwd, tipA, tipB, alias, dial) {
  const a = readClaim(cwd, tipA, alias, dial);
  const b = readClaim(cwd, tipB, alias, dial);
  const related = (() => {
    try { execFileSync('git', ['merge-base', '--is-ancestor', tipA, tipB], { cwd, stdio: 'ignore' }); return true; }
    catch { return false; }
  })();
  return {
    alias, dial, a, b,
    contested: a !== null && b !== null && a !== b && !related,
    reason: related ? 'tips are ancestor/descendant: fast-forward, not a contest'
      : a === null || b === null ? 'one tip does not carry this dial'
      : a === b ? 'cells agree'
      : 'divergent tips assert different values for one dial',
  };
}

/** C2. The record is a pure function of the two commits. No wall clock, no
 *  iteration order, no model output — the same shape as quilt-receipt, for
 *  the same reason: a witness you can regenerate is a witness you can audit. */
export function record(cwd, tipA, tipB, alias, dial) {
  const v = inspect(cwd, tipA, tipB, alias, dial);
  const body = {
    kind: 'contest',
    alias, dial,
    candidates: [tipA, tipB].sort().map(t => ({
      tip: t,
      claim: readClaim(cwd, t, alias, dial),
      frame: frameOf(cwd, t),
    })),
    verdict: v.contested ? 'UNRESOLVED' : 'NOT_A_CONTEST',
    reason: v.reason,
  };
  body.sig = createHash('sha256')
    .update(JSON.stringify({ ...body, sig: undefined }))
    .digest('hex');
  return body;
}

/** C3. The panel trap, as a function with a measured output.
 *
 *  extra: [{ tip, cell, agreesWith: 0|1 }]
 *  Returns what the lattice is allowed to conclude. `resolved` is FALSE for
 *  every input, and that is the design working, not a stub: the lattice has no
 *  admissible evidence for which of two divergent claims is true, because
 *  every member it could ask is drawn from the same correlated pool. Adding
 *  members changes `corroboration` and changes NOTHING else. */
export function resolveWithPanel(rec, extra = []) {
  const tally = [0, 0];
  for (const e of extra) tally[e.agreesWith]++;
  const best = Math.max(...tally), runnerUp = Math.min(...tally);
  return {
    resolved: false,
    corroborated_by: tally,
    // The number a majority rule would have leaned on, and the number that
    // actually carries information: the MARGIN. Three forks of one repo
    // produce a margin of 3 and an effective sample size of ~1.
    majority: tally[0] === tally[1] ? null : (tally[0] > tally[1] ? 0 : 1),
    margin: best - runnerUp,
    n_eff_ceiling: 2,
    admissible_evidence: 'none — requires an out-of-band second opinion, not more lattice members',
    record_sha256: rec.sig,
  };
}
