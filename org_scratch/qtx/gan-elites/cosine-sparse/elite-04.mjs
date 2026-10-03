// Ocean recall — sparse integer cosine — GAN-HARDENED elite #4
// bred by the quilt-loom Divergence Foundry (offline leg)
// family: union_set   hash: d952b7a8da   voice: mech   gen: 4   novelty: 0.82935
// contract: Given {a, b} (objects mapping term->positive integer count), return their cosine similarity as a number rounded to 4 decimals (Math.round(x*10000)/10000). Convention: if either bag has zero total norm, return 0.
// provenance: outputs/elites/cosine_sparse/ + outputs/fleet_live_results.json
export const solve = function solve(input) {
  const a = input.a, b = input.b;
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  let dot = 0, na = 0, nb = 0;
  for (const k of keys) {
    const x = a[k] || 0, y = b[k] || 0;
    dot += x * y;
  }
  for (const k of Object.keys(a)) { na += a[k] * a[k]; }
  for (const k of Object.keys(b)) { nb += b[k] * b[k]; }
  if (na === 0 || nb === 0) return 0;
  return Math.round((dot / (Math.sqrt(na) * Math.sqrt(nb))) * 10000) / 10000;
};
export default solve;
