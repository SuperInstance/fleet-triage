// lattice-cell — the disagreement protocol's own suite.
//
// The test that matters is C3: it must FAIL if the panel ever starts resolving.

import { execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, mkdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { inspect, record, resolveWithPanel } from '../src/contest.js';

const git = (cwd, ...a) => execFileSync('git', a, { cwd, encoding: 'utf8', input: '' });
let pass = 0, fail = 0; const failed = [];
const ok = (id, c, d = '') => { if (c) { pass++; console.log(`PASS ${id}  ${d}`); } else { fail++; failed.push(id); console.log(`FAIL ${id}  ${d}`); } };

function twoCells() {
  const d = mkdtempSync(join(tmpdir(), 'lat-contest-'));
  execFileSync('git', ['init', '-q', '--bare', join(d, 'remote.git')]);
  execFileSync('git', ['init', '-q', join(d, 'a')]);
  const A = join(d, 'a');
  git(A, 'config', 'user.email', 'a@l'); git(A, 'config', 'user.name', 'alpha');
  git(A, 'remote', 'add', 'origin', join(d, 'remote.git'));
  mkdirSync(join(A, 'cells', 'shared', 'dials'), { recursive: true });
  writeFileSync(join(A, 'cells', 'shared', 'dials', '1'), '0.4\n');
  git(A, 'add', '-A'); git(A, 'commit', '-qm', 'seed'); git(A, 'branch', '-M', 'main'); git(A, 'push', '-q', 'origin', 'main');
  // two divergent commits, each with a frame, each asserting a different value
  const tip = [];
  for (const [v, id] of [['0.9', 'd-0-aaa'], ['0.1', 'd-0-bbb']]) {
    git(A, 'checkout', '-q', '-B', 'w' + v, 'main');
    writeFileSync(join(A, 'cells', 'shared', 'dials', '1'), v + '\n');
    git(A, 'add', '-A');
    git(A, 'commit', '-q', '-m', `quilt-cell(shared): set ${v}\n\nDispatch-Id: ${id}\nCell-Intent: set dial 1 to ${v}\nCell-Postcondition: dial:shared:1 == ${v}`);
    tip.push(git(A, 'rev-parse', 'HEAD').trim());
  }
  return { d, A, tip };
}

// ---------------------------------------------------------------- C1 declare
{
  const { d, A, tip } = twoCells();
  const v = inspect(A, tip[0], tip[1], 'shared', 1);
  ok('C1a divergent claims for one dial are a contest', v.contested === true, v.reason);
  ok('C1b the reason names the substrate, not a model', /divergent/.test(v.reason));
  // THE CONTROL THAT CANNOT PASS: ancestor tips are NOT a contest.
  const a0 = git(A, 'rev-list', '--max-parents=0', 'HEAD').trim();
  const anc = inspect(A, a0, tip[0], 'shared', 1);
  ok('C1c CONTROL: ancestor/descendant tips are NOT a contest', anc.contested === false, anc.reason);
  rmSync(d, { recursive: true, force: true });
}

// ---------------------------------------------------------------- C2 purity
{
  const { d, A, tip } = twoCells();
  const r1 = record(A, tip[0], tip[1], 'shared', 1);
  ok('C2a record is UNRESOLVED, never silently decided', r1.verdict === 'UNRESOLVED');
  ok('C2b both claims are kept verbatim', r1.candidates.length === 2 &&
     r1.candidates.every(c => c.claim !== null && c.frame.intent));
  // order independence: the two tips are sorted inside the record
  const r2 = record(A, tip[1], tip[0], 'shared', 1);
  ok('C2c the record is independent of argument order', r1.sig === r2.sig, r1.sig.slice(0, 16));
  ok('C2d the record is a pure function of the commits (deterministic hash)',
     r1.sig === record(A, tip[0], tip[1], 'shared', 1).sig);
  rmSync(d, { recursive: true, force: true });
}

// ------------------------------------- C3 more cells do NOT resolve it -----
{
  const { d, A, tip } = twoCells();
  const rec = record(A, tip[0], tip[1], 'shared', 1);
  const panel = [
    ...Array.from({ length: 3 }, () => ({ cell: 'fork1', agreesWith: 0 })),
    ...Array.from({ length: 3 }, () => ({ cell: 'fork2', agreesWith: 0 })),
  ];
  const one = resolveWithPanel(rec, [{ cell: 'lone', agreesWith: 0 }]);
  const many = resolveWithPanel(rec, panel);
  ok('C3a a single corroborating cell does NOT resolve', one.resolved === false);
  ok('C3b SIX unanimous cells STILL do not resolve', many.resolved === false);
  ok('C3c the majority it would have leaned on is recorded', many.majority === 0, `majority=${many.majority} margin=${many.margin}`);
  ok('C3d the margin grows while the conclusion does not (this IS the n_eff argument, executed)',
     many.margin > one.margin && many.resolved === one.resolved,
     `margin ${one.margin} -> ${many.margin}, resolved ${one.resolved} -> ${many.resolved}`);
  ok('C3e the record demands an out-of-band second opinion',
     /out-of-band/.test(many.admissible_evidence));
  // A tie must not be broken by argument order.
  const tie = resolveWithPanel(rec, [{ cell: 'x', agreesWith: 0 }, { cell: 'y', agreesWith: 1 }]);
  ok('C3f a 1-1 tie reports no majority', tie.majority === null && tie.margin === 0);
  rmSync(d, { recursive: true, force: true });
}

// ------------------------------------ C4 agreement is not a contest --------
{
  const { d, A, tip } = twoCells();
  const same = inspect(A, tip[0], tip[0], 'shared', 1);
  ok('C4a a tip compared with itself is not a contest', same.contested === false, same.reason);
  rmSync(d, { recursive: true, force: true });
}

console.log(`\nCONTEST: ${pass} pass, ${fail} fail`);
if (fail) { console.log('FAILED: ' + failed.join(' ')); process.exit(1); }
