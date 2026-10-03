import { ReferralGraph } from './src/referral_graph.mjs';
import { SEED } from './experiments/referral_graph.seed.mjs';
const g = new ReferralGraph({ name: 'recount' });
for (const n of SEED.nodes) g.addNode(n);
for (const e of SEED.edges) g.book(e);
const E = SEED.edges;
const V = E.filter(e => e.weight === 'VERIFIED');
const P = E.filter(e => e.weight === 'PENDING');
const repos = new Set(SEED.nodes.map(n => n.repo));
console.log('nodes        :', SEED.nodes.length);
console.log('repos        :', repos.size);
console.log('TOTAL EDGES  :', E.length);
console.log('VERIFIED     :', V.length);
console.log('PENDING      :', P.length);
// inbound mass per repo
const inbound = {};
for (const e of E) {
  const r = SEED.nodes.find(n => n.id === e.to).repo;
  inbound[r] = (inbound[r] || 0) + 1;
}
console.log('\n--- INBOUND MASS (all edges) ---');
Object.entries(inbound).sort((a,b)=>b[1]-a[1]).forEach(([r,c])=>console.log(String(c).padStart(2), r));
const vin = {};
for (const e of V) { const r = SEED.nodes.find(n=>n.id===e.to).repo; vin[r]=(vin[r]||0)+1; }
console.log('\n--- INBOUND MASS (VERIFIED only) ---');
Object.entries(vin).sort((a,b)=>b[1]-a[1]).forEach(([r,c])=>console.log(String(c).padStart(2), r));
console.log('\n--- fleet-murmur inbound edge detail ---');
E.filter(e => SEED.nodes.find(n=>n.id===e.to).repo === 'fleet-murmur')
 .forEach(e => console.log(' ', e.weight.padEnd(8), e.from, '->', e.to, '| receipt:', e.receipt ?? 'none'));
console.log('\nfleet-murmur inbound total =', inbound['fleet-murmur'] ?? 0,
            '| VERIFIED-only =', vin['fleet-murmur'] ?? 0);
