// Pin: vendor/quilt-core/README.md tool-count + self-check-count claims
// stay in lockstep with the live tool set (witness_rng seed_from_book
// bug class: a docs count that silently drifts from behavior).
// FAIL-first: on main tip pre-fix this trips RED ("ten tools", "75/75").
import { readFileSync, readdirSync } from 'node:fs';

const readme = readFileSync('vendor/quilt-core/README.md', 'utf8');
const tools = readdirSync('tools').filter(f => f.endsWith('.mjs')).sort();
const n = tools.length;
const num = ['zero','one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve'];

let failures = 0;
const check = (ok, label) => { console.log(`${ok ? 'PASS' : 'FAIL'} ${label}`); if (!ok) failures++; };

check(new RegExp(`The ${num[n]} tools in this repo`).test(readme),
  `readme claims "${num[n]} tools" (live: ${n})`);
check(!/The (?:nine|ten|twelve) tools in this repo/.test(readme),
  'readme carries no stale tool-count');

// self-check totals: run each tool's harness line is too slow for a pin;
// instead the per-tool counts are pinned in main README — cross-check the
// vendor claim against that table's sum.
const main = readFileSync('README.md', 'utf8');
const counts = [...main.matchAll(/\| \d+\/(\d+) \|/g)].map(m => Number(m[1]));
const total = counts.reduce((a, b) => a + b, 0);
check(counts.length === n, `main README table lists ${counts.length} tools (live: ${n})`);
check(readme.includes(`${total}/${total} checks`),
  `readme claims "${total}/${total} checks" (main-README table sum: ${total})`);

console.log(failures ? `\n${failures} pin(s) RED` : `\nall vendor-readme-count pins green (${n} tools, ${total} checks)`);
process.exit(failures ? 1 : 0);
