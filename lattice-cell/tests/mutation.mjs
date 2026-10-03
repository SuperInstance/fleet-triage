// lattice-cell — the suite's own receipt.
//
// A green suite is not evidence. The question is what the suite CONSTRAINS.
// So: break the implementation five ways and require the invariant suite to go
// RED each time. A mutation that survives is a hole in the suite, and this file
// prints the holes rather than the score.
//
// This is the check `selectlib` earned the hard way ("a control that cannot
// fail is worse than no control") and the one the CRDT canary cannot pass.

import { execFileSync } from 'node:child_process';
import { cpSync, mkdtempSync, readFileSync, writeFileSync, rmSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';

const ROOT = join(new URL('.', import.meta.url).pathname, '..');

const MUTANTS = [
  {
    id: 'A', name: 'drop Dispatch-Id from the commit frame',
    file: 'src/cell.js',
    find: "`Dispatch-Id: ${dispatch.id}`,",
    repl: "`Dispatch-Id: `,",
    kills: 'I5a / I6a — the two planes can no longer be joined, so a lost outcome is unrecoverable',
  },
  {
    id: 'B', name: 'reconcile trusts the local object store instead of the remote',
    file: 'src/cell.js',
    find: 'let onRemote = remoteTips.has(sha) || (remoteLocal && sha === remoteLocal);',
    repl: 'let onRemote = true;',
    kills: 'I6a — an unpushed local commit gets certified as delivered (this is the pinned false-repair bug)',
  },
  {
    id: 'C', name: 'the dispatch row is written AFTER execute (the naive ordering)',
    file: 'src/cell.js',
    find: "  const d = await ledger.dispatch({ cell, intent, base, lease_ms, postcondition, induced_by });\n  die(CP.DISPATCH);",
    repl: "  const out0 = await apply?.(cwd);\n  const d = await ledger.dispatch({ cell, intent, base, lease_ms, postcondition, induced_by });\n  die(CP.DISPATCH);",
    kills: 'I2 — the ledger stops being a pre-registration and becomes a receipt, which is the hole the design exists to remove',
  },
  {
    id: 'D', name: 'a no-op run is recorded as COMMIT',
    file: 'src/cell.js',
    find: "const o = await ledger.outcome(d.id, 'REFUSED', { reason: 'no-op: worktree unchanged' });",
    repl: "git(cwd, 'commit', '-q', '--no-verify', '--allow-empty', '-m', 'no-op'); const o = await ledger.outcome(d.id, 'COMMIT', { tip: git(cwd, 'rev-parse', 'HEAD').trim() });",
    kills: 'I7a — a passing test and a failing test emit the same code, the fleet signature',
  },
  {
    id: 'E', name: 'the postcondition always holds',
    file: 'src/cell.js',
    find: 'return { holds: Math.abs(got - parseFloat(m[3])) < 1e-9, want: parseFloat(m[3]), got };',
    repl: 'return { holds: true, want: parseFloat(m[3]), got };',
    kills: 'I8a — the frame degrades into a comment, which is the fiction-lane failure',
  },
  {
    id: 'F', name: 'outcome accepted for an unknown dispatch id',
    file: 'src/ledger.js',
    find: "    if (!d) throw new Error(`I1 VIOLATION: outcome for unknown dispatch ${id}`);",
    repl: "    if (!d) { const s = await this.head(); await this.store.putBatch([[Ledger.key(s, 'O', id), { seq: s, kind: 'OUTCOME', id, cell: '??', status, at: Date.now(), ...detail }]]); await this.store.sync?.(); return { seq: s, kind: 'OUTCOME', id, status }; }",
    kills: 'I1b — a receipt with no work behind it',
  },
];

const results = [];
for (const m of MUTANTS) {
  const tmp = mkdtempSync(join(tmpdir(), `lat-mut-${m.id}-`));
  cpSync(ROOT, join(tmp, 'r'), { recursive: true, filter: (s) => !s.includes('/.git') && !s.includes('node_modules') });
  const target = join(tmp, 'r', m.file);
  const src = readFileSync(target, 'utf8');
  if (!src.includes(m.find)) { results.push({ ...m, verdict: 'MUTANT-DID-NOT-APPLY', killed: null }); rmSync(tmp, { recursive: true, force: true }); continue; }
  writeFileSync(target, src.replace(m.find, m.repl));
  let red = false, detail = '';
  try {
    execFileSync('node', [join(tmp, 'r', 'tests', 'invariants.mjs')], { stdio: ['ignore', 'pipe', 'pipe'], encoding: 'utf8' });
  } catch (e) {
    // A non-zero exit is NOT a kill. If the suite crashes on its own import,
    // every mutant "fails" and the score reads 100% — which is exactly what
    // happened the first time this file ran, and exactly the failure mode
    // ORIENTATION.md warns about. A kill requires a real FAIL line.
    detail = (e.stdout || '').split('\n').filter(l => l.startsWith('FAIL ')).map(l => l.split(' ')[1]).join(' ');
    if (!detail) {
      results.push({ ...m, verdict: 'HARNESS-BROKEN', killed: null,
        why: (e.stderr || '').split('\n').filter(Boolean).slice(0, 2).join(' | ') || `exit ${e.status}` });
      rmSync(tmp, { recursive: true, force: true });
      continue;
    }
    red = true;
  }
  results.push({ ...m, verdict: red ? 'KILLED' : 'SURVIVED', killed: detail || null });
  rmSync(tmp, { recursive: true, force: true });
}

console.log('\nlattice-cell MUTATION SCORE');
console.log('=====================================================================');
for (const r of results) {
  const tag = r.verdict === 'KILLED' ? 'KILLED  ' : r.verdict === 'SURVIVED' ? 'SURVIVED' : 'BROKEN  ';
  console.log(`${tag} ${r.id}  ${r.name}`);
  console.log(`              expected to kill: ${r.kills}`);
  if (r.verdict === 'KILLED') console.log(`              actually killed by: ${r.killed}`);
  if (r.verdict === 'HARNESS-BROKEN') console.log(`              !! the suite itself crashed: ${r.why}`);
}
const applied = results.filter(r => r.verdict !== 'MUTANT-DID-NOT-APPLY');
const killed = applied.filter(r => r.verdict === 'KILLED').length;
const surv = results.filter(r => r.verdict === 'SURVIVED');
console.log('---------------------------------------------------------------------');
console.log(`SCORE: ${killed}/${applied.length} killed (${(100 * killed / applied.length).toFixed(0)}%)`);
if (results.some(r => r.verdict === 'MUTANT-DID-NOT-APPLY')) { console.log('ERROR: a mutant did not apply — the pin is stale'); process.exit(2); }
const broken = results.filter(r => r.verdict === 'HARNESS-BROKEN');
if (broken.length) { console.log('SCORE UNTRUSTWORTHY: the suite crashed on ' + broken.map(b => b.id).join(' ') + '. A crash is not a kill.'); process.exit(2); }
if (surv.length) { console.log('SURVIVORS (suite holes): ' + surv.map(s => s.id).join(' ')); process.exit(1); }
console.log('No survivors. The suite constrains semantics, not just coverage.');
