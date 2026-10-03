// lattice-cell — the wake / execute / commit / dissolve loop.
//
// One invocation IS one cell lifetime. There is no daemon, no warm process,
// and nothing to shut down: the function returns and the process is free to
// vanish. The ONLY thing that outlives it is (a) the commit, on the remote, and
// (b) the ledger rows, which were flushed before the work started.
//
// CRASH POINTS. `LATTICE_CRASH_AT=<name>` calls process.exit(137) at a named
// point. That is a HARD exit: no finally, no atexit, no flush. It is the
// closest local analogue of "the Worker was evicted", and it is the only
// honest way to test the liveness question instead of asserting an answer to
// it. harness/crash-matrix.sh walks every one of them in a separate process.

import { execFileSync } from 'node:child_process';
import { Ledger, FileStore } from './ledger.js';

const CRASH = process.env.LATTICE_CRASH_AT || null;
const CP = {
  WAKE: 'wake',                 // repo cloned, nothing written anywhere yet
  DISPATCH: 'dispatch',         // ledger row durable, execute not yet started
  EXECUTE: 'execute',           // work done in the worktree, nothing committed
  COMMIT: 'commit',             // commit exists locally, NOT yet pushed
  PUSH: 'push',                 // commit is on the remote, outcome NOT yet written
  OUTCOME: 'outcome',           // outcome durable — the only clean exit
};
export { CP };

function die(at) {
  if (CRASH === at) {
    process.stderr.write(`lattice-cell: CRASH at ${at} (pid ${process.pid})\n`);
    process.exit(137);
  }
}

const git = (cwd, ...args) => {
  const opts = args.length && typeof args.at(-1) === 'object' && !Array.isArray(args.at(-1)) ? args.pop() : null;
  return execFileSync('git', args, {
    cwd, encoding: 'utf8',
    input: opts?.input ?? '',
    stdio: [opts?.input != null ? 'pipe' : 'ignore', 'pipe', 'pipe'],
  });
};

/** THE JOIN KEY. The dispatch id goes into the commit message so that Plane A
 *  (git) and Plane B (ledger) can be joined after either is lost. Without it
 *  the two planes are two logs and no way to reconcile them — see I6. */
function frame(dispatch) {
  return [
    `quilt-cell(${dispatch.cell}): ${dispatch.intent}`,
    '',
    `Dispatch-Id: ${dispatch.id}`,
    `Cell-Intent: ${dispatch.intent}`,
    dispatch.postcondition ? `Cell-Postcondition: ${dispatch.postcondition}` : null,
    dispatch.induced_by ? `Induced-By: ${dispatch.induced_by}` : null,
  ].filter(l => l !== null).join('\n');
}

function verifyPostcondition(cwd, dispatch) {
  // The postcondition is a RELATION over the committed tree, not a prose claim.
  // `dial:<cell>:<n> == <v>` is the one form implemented; it is deliberately
  // narrow, because a postcondition that cannot be evaluated is a comment.
  const m = /^dial:([a-z0-9_-]+):(\d+)\s*==\s*(-?[\d.]+)$/.exec(dispatch.postcondition || '');
  if (!m) return null;
  const got = parseFloat(git(cwd, 'show', `HEAD:cells/${m[1]}/dials/${m[2]}`).trim());
  return { holds: Math.abs(got - parseFloat(m[3])) < 1e-9, want: parseFloat(m[3]), got };
}

/** POSTCONDITION: a no-op run and a real run must produce the same OBSERVABLE
 *  set. If the harness mutates the worktree in the no-op case, this goes red —
 *  which is how we keep the no-op case from being a control that cannot fail. */
async function run({ repo, ledgerPath, cell, intent, base, postcondition, apply, induced_by, lease_ms = 30_000 }) {
  const store = await FileStore.open(ledgerPath);
  const ledger = new Ledger(store);
  const cwd = repo;

  git(cwd, 'fetch', '--all', '--prune', '--quiet');
  git(cwd, 'checkout', base);
  git(cwd, 'reset', '--hard', 'origin/' + base, '--quiet');
  die(CP.WAKE);

  // ---- the departure: durable intent BEFORE work exists -------------------
  const d = await ledger.dispatch({ cell, intent, base, lease_ms, postcondition, induced_by });
  die(CP.DISPATCH);

  // ---- execute ------------------------------------------------------------
  const out = await apply?.(cwd);
  die(CP.EXECUTE);

  // ---- commit: the frame is the only durable artifact --------------------
  git(cwd, 'add', '-A');
  const staged = git(cwd, 'diff', '--cached', '--name-only').trim();
  if (!staged) {
    // Nothing changed. This is a real and common outcome and it MUST NOT be
    // recorded as success — see I7 and the pin "no-op != commit".
    const o = await ledger.outcome(d.id, 'REFUSED', { reason: 'no-op: worktree unchanged' });
    die(CP.OUTCOME);
    return { dispatch: d, outcome: o, tip: null, post: null };
  }
  const msg = Buffer.from(frame(d));
  git(cwd, 'commit', '-q', '--no-verify', '-F', '-', { input: msg });
  const tip = git(cwd, 'rev-parse', 'HEAD').trim();
  const pc = verifyPostcondition(cwd, d);
  die(CP.COMMIT);

  // ---- push: the commit reaches the substrate, then we record it ----------
  git(cwd, 'push', '--quiet', 'origin', `HEAD:${base}`);
  die(CP.PUSH);

  const o = await ledger.outcome(d.id, 'COMMIT', { tip, postcondition_holds: pc?.holds ?? null });
  die(CP.OUTCOME);

  return { dispatch: d, outcome: o, tip, post: pc };
}

/** Recovery. After any crash, what does the lattice know?
 *
 *  REPAIR: any commit carrying `Dispatch-Id:` is evidence the work reached the
 *  remote even if the outcome row was lost. Receipts are a pure function of
 *  the commit (pinned, pins/purity.log), so a lost receipt is recomputable.
 *
 *  PAIRED WITH, AND THIS IS NOT OPTIONAL: the commit must be REACHABLE FROM A
 *  REMOTE REF. A local-worktree commit that never got pushed is not evidence of
 *  anything — it is the agent's own belief about itself. An earlier version of
 *  this function scanned `git log --all`, which includes unpushed local HEAD,
 *  and it cheerfully recorded COMMIT for a commit a fresh clone could not see.
 *  That is pinned in pins/bug-false-repair.log and it is the lattice's own
 *  version of the fleet's standing failure: a chain that agrees with itself.
 *  The check has to be made against a witness the reconciler does not control,
 *  and the remote is the only witness in this design that survives the Worker.
 */
async function reconcile({ repo, ledgerPath, remote = 'origin' }) {
  const store = await FileStore.open(ledgerPath);
  const ledger = new Ledger(store);
  const open = await ledger.unreconciled({});
  const settled = new Set();
  for (const r of await ledger.rows()) if (r.kind === 'OUTCOME') settled.add(r.id);

  // Reachability is the ONLY admissible evidence, and it is asked of the
  // remote, not of the working tree.
  const remoteTips = new Set(
    execFileSync('git', ['ls-remote', remote], { cwd: repo, encoding: 'utf8' })
      .split('\n').map(l => l.split('\t')[0]).filter(Boolean));

  let remoteLocal = null;
  try {
    remoteLocal = execFileSync('git', ['rev-parse', '--verify', '--quiet', `${remote}/HEAD`],
      { cwd: repo, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim() || null;
  } catch { remoteLocal = null; }

  const repaired = [], abandoned = [];
  for (const sha of execFileSync('git', ['rev-list', '--all'], { cwd: repo, encoding: 'utf8' })
    .split('\n').map(s => s.trim()).filter(Boolean)) {
    const body = execFileSync('git', ['log', '-1', '--format=%B', sha], { cwd: repo, encoding: 'utf8' });
    const m = /Dispatch-Id:\s*(\S+)/.exec(body);
    if (!m || settled.has(m[1]) || !open.some(o => o.dispatch.id === m[1])) continue;

    let onRemote = remoteTips.has(sha) || (remoteLocal && sha === remoteLocal);
    if (!onRemote) {
      // Independent probe: could a stranger fetch this object? Ask the remote
      // directly rather than asking the local object store, which already
      // believes it.
      try {
        execFileSync('git', ['fetch', remote, sha], { cwd: repo, stdio: 'ignore' });
        onRemote = remoteTips.has(sha);
      } catch { onRemote = false; }
    }
    if (onRemote) {
      await ledger.outcome(m[1], 'COMMIT', { tip: sha, repaired: true });
      repaired.push({ id: m[1], tip: sha });
    } else {
      // NEGATIVE RECEIPT. The work happened to a worker that no longer exists
      // and never reached the substrate. This row is the entire reason the
      // ledger exists: without it this is indistinguishable from a clean run.
      await ledger.outcome(m[1], 'LOST', { tip: sha, repaired: false, reason: 'commit never reached a remote ref' });
      abandoned.push({ id: m[1], tip: sha });
    }
  }
  return { openBefore: open.length, repaired, abandoned, stillOpen: (await ledger.unreconciled({})).length };
}

export { run, reconcile };
