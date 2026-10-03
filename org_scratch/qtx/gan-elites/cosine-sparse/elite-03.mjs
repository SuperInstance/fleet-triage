// Ocean recall — sparse integer cosine — GAN-HARDENED elite #3
// bred by the quilt-loom Divergence Foundry (offline leg)
// family: a_key_scan   hash: b5ad63c6e9   voice: mech   gen: 5   novelty: 0.84192
// contract: Given {a, b} (objects mapping term->positive integer count), return their cosine similarity as a number rounded to 4 decimals (Math.round(x*10000)/10000). Convention: if either bag has zero total norm, return 0.
// provenance: outputs/elites/cosine_sparse/ + outputs/fleet_live_results.json
export const solve = function solve(input) {
  const a = input.a, b = input.b;
  let dot = 0, na = 0, nb = 0;
  for (const k in a) { na += a[k] * a[k]; }
  for (const k in b) { nb += b[k] * b[k]; }
  if (na === 0 || nb === 0) return 0;
  for (const k in a) { dot += a[k] * (b[k] || 0); }
  const cos = dot / (Math.sqrt(na) * Math.sqrt(nb));
  return Math.round(cos * 10000) / 10000;
};
export default solve;
