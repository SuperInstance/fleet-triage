// Ocean recall — sparse integer cosine — GAN-HARDENED elite #2
// bred by the quilt-loom Divergence Foundry (offline leg)
// family: sorted_two_pointer   hash: d3e5fd7d58   voice: mech   gen: 1   novelty: 1
// contract: Given {a, b} (objects mapping term->positive integer count), return their cosine similarity as a number rounded to 4 decimals (Math.round(x*10000)/10000). Convention: if either bag has zero total norm, return 0.
// provenance: outputs/elites/cosine_sparse/ + outputs/fleet_live_results.json
export const solve = function solve(input) {
  const a = input.a, b = input.b;
  const ka = Object.keys(a).sort();
  const kb = Object.keys(b).sort();
  let i = 0, j = 0, dot = 0;
  while (i < ka.length && j < kb.length) {
    if (ka[i] === kb[j]) { dot += a[ka[i]] * b[kb[j]]; i++; j++; }
    else if (ka[i] < kb[j]) { i++; }
    else { j++; }
  }
  let na = 0;
  for (const k of ka) { na += a[k] * a[k]; }
  let nb = 0;
  for (const k of kb) { nb += b[k] * b[k]; }
  if (na === 0 || nb === 0) return 0;
  return Math.round((dot / (Math.sqrt(na) * Math.sqrt(nb))) * 10000) / 10000;
};
export default solve;
