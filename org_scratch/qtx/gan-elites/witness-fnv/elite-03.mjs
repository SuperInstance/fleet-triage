// Witness idiom — fnv-1a-64 hex — GAN-HARDENED elite #3
// bred by the quilt-loom Divergence Foundry (offline leg)
// family: bigint_fold   hash: aa28e37705   voice: mech   gen: 1   novelty: 1
// contract: Given {text} (ASCII string), compute FNV-1a 64-bit: h=0xcbf29ce484222325; for each char code c in order: h ^= c; h *= 0x100000001b3 (mod 2^64). Return h as lowercase hex, zero-padded to 16 chars.
// provenance: outputs/elites/witness_fnv/ + outputs/fleet_live_results.json
export const solve = function solve(input) {
  const s = input.text;
  const P = 0x100000001b3n, M = 0xffffffffffffffffn;
  let acc = 0xcbf29ce484222325n;
  for (let i = 0; i < s.length; i++) {
    acc = (acc ^ BigInt(s.charCodeAt(i))) * P;
  }
  return (acc & M).toString(16).padStart(16, '0');
};
export default solve;
