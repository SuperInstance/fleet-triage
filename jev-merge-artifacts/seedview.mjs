import { ReferralGraph } from './src/referral_graph.mjs';
import { SEED } from './experiments/referral_graph.seed.mjs';
const g=new ReferralGraph({name:'v'}); for(const n of SEED.nodes) g.addNode(n); for(const e of SEED.edges) g.book(e);
const E=SEED.edges;
let o=`REFERRAL GRAPH — seed.mjs as it stands on quilt-tools main (post-merge of PR #32 and PR #33)\n`;
o+=`TOTAL EDGES: ${E.length}\nVERIFIED: ${E.filter(e=>e.weight==='VERIFIED').length}\nPENDING: ${E.filter(e=>e.weight==='PENDING').length}\nNODES: ${SEED.nodes.length}\nREPOS: ${new Set(SEED.nodes.map(n=>n.repo)).size}\n\n`;
E.forEach((e,i)=>{o+=`edge ${i+1}: ${e.from} -> ${e.to} [${e.weight}] receipt=${e.receipt??'none'}\n`});
console.log(o);
