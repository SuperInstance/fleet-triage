// lattice-cell — the invariant suite.
//
// Every check here is a RELATION, not a value. Per GIFT-ORACLE.md: when you
// cannot know the right answer, check that a relationship holds. Nothing below
// asserts "the answer is X"; each asserts a property that must survive a
// change to the answer.
//
// tests/mutation.mjs is the suite's own receipt: it breaks the implementation
// five ways and REQUIRES this file to go red each time. A suite that cannot be
// made to fail is not evidence of anything.

import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, mkdirSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Ledger, FileStore, OUTCOMES } from '../src/ledger.js';
import { run, reconcile } from '../src/cell.js';

const HERE = new URL('.', import.meta.url).pathname;
const CLI = join(HERE, '..', 'bin', 'lattice-cell');
let pass = 0, fail = 0; const failures = [];
const ok = (id, cond, detail = '') => {
  if (cond) { pass++; console.log(`PASS ${id}${detail ? '  ' + detail : ''}`); }
  else { fail++; failures.push(id); console.log(`FAIL ${id}  ${detail}`); }
};

const git = (cwd, ...a) => execFileSync('git', a, { cwd, encoding: 'utf8' });
function fixture(name) {
  const d = mkdtempSync(join(tmpdir(), `lat-${name}-`));
  execFileSync('git', ['init', '-q', '--bare', join(d, 'remote.git')]);
  execFileSync('git', ['init', '-q', join(d, 'cell')]);
  const c = join(d, 'cell');
  git(c, 'config', 'user.email', 'c@l'); git(c, 'config', 'user.name', 'cell');
  git(c, 'remote', 'add', 'origin', join(d, 'remote.git'));
  mkdirSync(join(c, 'cells', 'alpha', 'dials'), { recursive: true });
  writeFileSync(join(c, 'cells', 'alpha', 'dials', '1'), '0.4\n');
  writeFileSync(join(c, 'cells', 'alpha', 'dials', '15'), '0.0\n');
  git(c, 'add', '-A'); git(c, 'commit', '-qm', 'seed');
  git(c, 'branch', '-M', 'main'); git(c, 'push', '-q', 'origin', 'main');
  return { d, c, ledger: join(d, 'ledger.json') };
}
const touch = (c, v) => writeFileSync(join(c, 'cells', 'alpha', 'dials', '1'), `${v}\n`);
const rowsOf = async l => { const s = await FileStore.open(l); return new Ledger(s).rows(); };

// ---------------------------------------------------------------- I1 no orphans
{
  const { d, c, ledger } = fixture('i1');
  await run({ repo: c, ledgerPath: ledger, cell: 'alpha', intent: 'i1', base: 'main', apply: () => touch(c, 0.5) });
  const rows = await rowsOf(ledger);
  const ids = new Set(rows.filter(r => r.kind === 'DISPATCH').map(r => r.id));
  const orphans = rows.filter(r => r.kind === 'OUTCOME' && !ids.has(r.id));
  ok('I1a no outcome without a dispatch', orphans.length === 0, `orphans=${orphans.length}`);
  let threw = false;
  try { const s = await FileStore.open(ledger); await new Ledger(s).outcome('d-does-not-exist', 'COMMIT', {}); } catch { threw = true; }
  ok('I1b fabricated outcome is refused by the API', threw);
  rmSync(d, { recursive: true, force: true });
}

// ------------------------------------------------- I2/I3 settle every dispatch
{
  const { d, c, ledger } = fixture('i2');
  for (const v of [0.5, 0.6, 0.7])
    await run({ repo: c, ledgerPath: ledger, cell: 'alpha', intent: `set ${v}`, base: 'main', postcondition: `dial:alpha:1 == ${v}`, apply: () => touch(c, v) });
  const rows = await rowsOf(ledger);
  const disp = rows.filter(r => r.kind === 'DISPATCH'), out = rows.filter(r => r.kind === 'OUTCOME');
  ok('I2a every dispatch settled', disp.length === out.length && disp.length === 3, `${disp.length}/${out.length}`);
  const byId = new Map(disp.map(d2 => [d2.id, d2]));
  ok('I2b exactly one outcome per dispatch', out.every(o => out.filter(x => x.id === o.id).length === 1));
  ok('I3a outcome.at >= dispatch.at', out.every(o => byId.get(o.id).at <= o.at));
  ok('I3b log is monotonically sequenced', rows.every((r, i) => i === 0 || r.seq > rows[i - 1].seq));
  rmSync(d, { recursive: true, force: true });
}

// ---------------------------------------- I4/I5 tip is reachable ON THE REMOTE
{
  const { d, c, ledger } = fixture('i4');
  const r = await run({ repo: c, ledgerPath: ledger, cell: 'alpha', intent: 'i4', base: 'main', apply: () => touch(c, 0.5) });
  const tips = new Set(execFileSync('git', ['ls-remote', 'origin'], { cwd: c, encoding: 'utf8' })
    .split('\n').map(l => l.split('\t')[0]).filter(Boolean));
  ok('I4a recorded tip exists on a remote ref', tips.has(r.tip), `tip=${r.tip?.slice(0, 7)}`);
  // METAMORPHIC M1: a fresh clone of the remote must contain the tip. The
  // local repo already believes in it, so it is asked nothing.
  const cold = join(d, 'cold');
  execFileSync('git', ['clone', '-q', join(d, 'remote.git'), cold]);
  let visible = true; try { execFileSync('git', ['cat-file', '-e', r.tip], { cwd: cold }); } catch { visible = false; }
  ok('I4b a STRANGER can see the tip (cold clone)', visible);
  rmSync(d, { recursive: true, force: true });
}

// -------------------------------------------- I5 the frame is on the commit
{
  const { d, c, ledger } = fixture('i5');
  const r = await run({ repo: c, ledgerPath: ledger, cell: 'alpha', intent: 'raise to 0.9', base: 'main', postcondition: 'dial:alpha:1 == 0.9', apply: () => touch(c, 0.9) });
  const body = git(c, 'log', '-1', '--format=%B', r.tip);
  ok('I5a commit carries Dispatch-Id', body.includes(`Dispatch-Id: ${r.dispatch.id}`));
  ok('I5b commit carries the pre-registered intent', body.includes('Cell-Intent: raise to 0.9'));
  ok('I5c commit carries a postcondition RELATION', body.includes('Cell-Postcondition: dial:alpha:1 == 0.9'));
  ok('I5d postcondition actually held', r.post?.holds === true, JSON.stringify(r.post));
  rmSync(d, { recursive: true, force: true });
}

// --------------------------------------- I6 the ledger is reconstructible (M2)
{
  const { d, c, ledger } = fixture('i6');
  // Simulate the push-crash: work done, commit pushed, outcome never written.
  const s = await FileStore.open(ledger); const L = new Ledger(s);
  const disp = await L.dispatch({ cell: 'alpha', intent: 'reconcile me', base: 'main', lease_ms: 30000 });
  const L2 = new Ledger(await FileStore.open(ledger));
  const d2 = (await L2.rows()).find(r => r.kind === 'DISPATCH');
  execFileSync('git', ['-C', c, 'checkout', '-q', '-B', 'main']);
  touch(c, 0.8);
  execFileSync('git', ['add', '-A'], { cwd: c });
  execFileSync('git', ['commit', '-q', '--no-verify', '-m', `frame\n\nDispatch-Id: ${d2.id}`], { cwd: c, input: '' });
  execFileSync('git', ['push', '-q', 'origin', 'main'], { cwd: c });
  const rec = await reconcile({ repo: c, ledgerPath: ledger });
  ok('I6a reconcile repaired the lost outcome', rec.repaired.length === 1 && rec.stillOpen === 0, JSON.stringify(rec.repaired));
  // METAMORPHIC M2: repair is a FIXPOINT. Running it again must change nothing.
  const rec2 = await reconcile({ repo: c, ledgerPath: ledger });
  ok('I6b reconcile is idempotent (M2 fixpoint)', rec2.repaired.length === 0 && rec2.stillOpen === 0);
  rmSync(d, { recursive: true, force: true });
}

// ------------------------------------------- I7 a no-op is not a success (P6)
{
  const { d, c, ledger } = fixture('i7');
  const r = await run({ repo: c, ledgerPath: ledger, cell: 'alpha', intent: 'noop', base: 'main', apply: undefined });
  ok('I7a no-op run is REFUSED, not COMMIT', r.outcome.status === 'REFUSED', r.outcome.status);
  ok('I7b no-op run creates no commit', r.tip === null);
  // THE CONTROL THAT MUST BE ABLE TO FAIL: the same cell, with work, commits.
  const { d: d2, c: c2, ledger: l2 } = fixture('i7b');
  const r2 = await run({ repo: c2, ledgerPath: l2, cell: 'alpha', intent: 'work', base: 'main', apply: () => touch(c2, 0.5) });
  ok('I7c CONTROL: the same code with work DOES commit', r2.outcome.status === 'COMMIT' && r2.tip !== null);
  ok('I7d I7a and I7c are distinguishable (the check has teeth)', r.outcome.status !== r2.outcome.status);
  rmSync(d, { recursive: true, force: true }); rmSync(d2, { recursive: true, force: true });
}

// ------------------------------------------- I8 postcondition is falsifiable
{
  const { d, c, ledger } = fixture('i8');
  // Intent asks for 0.9; the work writes 0.5. The frame must NOT be a comment.
  const r = await run({ repo: c, ledgerPath: ledger, cell: 'alpha', intent: 'claim 0.9', base: 'main', postcondition: 'dial:alpha:1 == 0.9', apply: () => touch(c, 0.5) });
  ok('I8a a false postcondition is recorded as not holding', r.post?.holds === false, JSON.stringify(r.post));
  ok('I8b the outcome is still COMMIT (the work happened) but carries the verdict',
     r.outcome.status === 'COMMIT' && r.outcome.postcondition_holds === false);
  rmSync(d, { recursive: true, force: true });
}

// ------------------------------- I9 permutation invariance (M1) + no reuse
{
  const { d, c, ledger } = fixture('i9');
  const a = await run({ repo: c, ledgerPath: ledger, cell: 'alpha', intent: 'first', base: 'main', apply: () => touch(c, 0.5) });
  const b = await run({ repo: c, ledgerPath: ledger, cell: 'alpha', intent: 'first', base: 'main', apply: () => touch(c, 0.6) });
  ok('I9a the same intent twice yields two distinct dispatches', a.dispatch.id !== b.dispatch.id);
  ok('I9b the second dispatch does not inherit the first outcome', b.outcome.id === b.dispatch.id && b.tip !== a.tip);
  const rows = await rowsOf(ledger);
  const outs = rows.filter(r => r.kind === 'OUTCOME');
  // METAMORPHIC M3: filtering the log by cell must be a projection — the same
  // rows, never more. A lattice that can settle a dispatch for a cell it was
  // not dispatched to is a lattice writing to the wrong door.
  const alpha = rows.filter(r => r.cell === 'alpha');
  ok('I9c per-cell projection is a subset of the whole log (M3)', alpha.length === rows.length && outs.every(o => o.cell === 'alpha'));
  rmSync(d, { recursive: true, force: true });
}


// ============ ADDED AFTER THE MUTATION SCORE CAME BACK 4/6 ================
// Both survivors were the two load-bearing properties, and both were visible
// in harness/crash-matrix.sh the whole time as ROWS nobody had promoted to
// ASSERTIONS. A crash matrix is not a test suite.

// ------------------- I10 pre-registration is durable BEFORE execute -------
// Run a real child process, kill it HARD at the dispatch checkpoint, and read
// the ledger afterwards. If the intent row is not already on disk at that
// instant, the crash has eaten the request and there is nothing left to lease.
{
  const { d, c, ledger } = fixture('i10');
  let killed = false;
  try {
    execFileSync('node', [CLI, 'run', '--repo', c, '--ledger', ledger, '--cell', 'alpha',
      '--intent', 'pre-registration', '--base', 'main', '--obstruction', '0.5'],
      { env: { ...process.env, LATTICE_CRASH_AT: 'dispatch' }, stdio: 'ignore' });
  } catch (e) { killed = e.status === 137; }
  ok('I10a the child really died at the dispatch checkpoint (exit 137)', killed);
  const rows = await rowsOf(ledger);
  const disp = rows.filter(r => r.kind === 'DISPATCH'), out = rows.filter(r => r.kind === 'OUTCOME');
  ok('I10b the DISPATCH row is durable BEFORE execute begins', disp.length === 1, `dispatches=${disp.length}`);
  ok('I10c and no outcome exists yet (the open lease is representable)', out.length === 0);
  // The ROW existing is not the property — a ledger that writes its dispatch
  // row after execute() also has a row. The property is ORDER, and the only
  // witness to it is the worktree: at the dispatch checkpoint the cell must
  // not have started working. (Mutation C writes the row one step later and
  // survived I10b; this is the check that kills it.)
  const onDisk = readFileSync(join(c, 'cells', 'alpha', 'dials', '1'), 'utf8').trim();
  ok('I10e ORDER: execute has NOT begun at the dispatch checkpoint', onDisk === '0.4', `dials/1=${onDisk} (pre-dispatch value is 0.4)`);
  // THE CONTROL: the same run with no crash must settle it. Without this row
  // I10b could pass on a ledger that never settles anything.
  const { d: d2, c: c2, ledger: l2 } = fixture('i10b');
  await run({ repo: c2, ledgerPath: l2, cell: 'alpha', intent: 'control', base: 'main', apply: () => touch(c2, 0.5) });
  const r2 = await rowsOf(l2);
  ok('I10d CONTROL: the uncrashed run does settle (I10b has teeth)',
     r2.filter(x => x.kind === 'OUTCOME').length === 1);
  rmSync(d, { recursive: true, force: true }); rmSync(d2, { recursive: true, force: true });
}

// ------------------- I11 reconcile must NOT certify an unpushed commit -----
// The pinned false-repair bug (pins/bug-false-repair.log). An earlier version
// of reconcile() scanned the local object store, found a commit the Worker had
// made and never pushed, and recorded COMMIT. A cold clone of the remote could
// not see that object. The reconciler was agreeing with itself.
{
  const { d, c, ledger } = fixture('i11');
  const L0 = new Ledger(await FileStore.open(ledger));
  const d0 = await L0.dispatch({ cell: 'alpha', intent: 'never pushed', base: 'main', lease_ms: 30000 });
  const id = d0.id;
  execFileSync('git', ['checkout', '-q', '-B', 'main'], { cwd: c });
  touch(c, 0.8);
  execFileSync('git', ['add', '-A'], { cwd: c });
  execFileSync('git', ['commit', '-q', '--no-verify', '-m', `frame\n\nDispatch-Id: ${id}`], { cwd: c, input: '' });
  const sha = execFileSync('git', ['rev-parse', 'HEAD'], { cwd: c, encoding: 'utf8' }).trim();
  // NOT pushed. A cold clone is the independent witness.
  const cold = join(d, 'cold');
  execFileSync('git', ['clone', '-q', join(d, 'remote.git'), cold]);
  let strangerSees = true; try { execFileSync('git', ['cat-file', '-e', sha], { cwd: cold }); } catch { strangerSees = false; }
  ok('I11a the cold clone cannot see the unpushed commit', strangerSees === false);
  const rec = await reconcile({ repo: c, ledgerPath: ledger });
  const row = (await rowsOf(ledger)).find(r => r.kind === 'OUTCOME' && r.id === id);
  ok('I11b reconcile does NOT claim COMMIT for an unpushed commit', row?.status !== 'COMMIT', `status=${row?.status}`);
  ok('I11c reconcile records a NEGATIVE receipt instead (LOST)', row?.status === 'LOST', `status=${row?.status}`);
  ok('I11d and the negative receipt leaves nothing open', rec.stillOpen === 0);
  rmSync(d, { recursive: true, force: true });
}

console.log(`\nINVARIANTS: ${pass} pass, ${fail} fail`);
if (fail) { console.log('FAILED: ' + failures.join(' ')); process.exit(1); }
