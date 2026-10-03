// Witness idiom — fnv-1a-64 hex — GAN-HARDENED elite #1
// bred by the quilt-loom Divergence Foundry (live leg)
// family: hilo32   hash: 3d237a99ef   voice: mech   gen: 1   novelty: 1
// contract: Given {text} (ASCII string), compute FNV-1a 64-bit: h=0xcbf29ce484222325; for each char code c in order: h ^= c; h *= 0x100000001b3 (mod 2^64). Return h as lowercase hex, zero-padded to 16 chars.
// provenance: outputs/elites/witness_fnv/ + outputs/fleet_live_results.json
export const solve = function solve(input) {
  const s = input.text;
  let hi = 0xcbf29ce4, lo = 0x84222325;
  for (let i = 0; i < s.length; i++) {
    const cc = s.charCodeAt(i);
    lo = (lo ^ cc) >>> 0;
    const T = hi * 435 + lo * 256;
    const m = lo * 435;
    const newLo = m % 4294967296;
    const c = (m - newLo) / 4294967296;
    const T0 = T % 4294967296;
    hi = (T0 + c) % 4294967296;
    lo = newLo;
  }
  const H = hi.toString(16).padStart(8, '0');
  const L = lo.toString(16).padStart(8, '0');
  return (H + L).toLowerCase();
};
export default solve;
