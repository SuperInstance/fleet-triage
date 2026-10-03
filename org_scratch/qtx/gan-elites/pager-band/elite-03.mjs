// Fleet-pager — hysteresis banding — GAN-HARDENED elite #3
// bred by the quilt-loom Divergence Foundry (offline leg)
// family: boolean_index   hash: 6f73333f95   voice: mech   gen: 1   novelty: 1
// contract: Given severity cur (integer 0-100) and prev (previous severity, integer or null): band = "sev2" if cur>=70, "sev3" if cur>=40, else "quiet". page_sev2 fires iff prev!=null and cur>=70 and prev<70; page_sev3 iff prev!=null and cur>=40 and cur<70 and prev<40; resolve iff prev!=null and cur<50 and prev>=50. Return {band, page_sev2, page_sev3, resolve}.
// provenance: outputs/elites/pager_band/ + outputs/fleet_live_results.json
export const solve = function solve(input) {
  const cur = input.cur, prev = input.prev;
  const band = ['quiet', 'sev3', 'sev2'][(cur >= 40) + (cur >= 70)];
  const has = !(prev == null);
  return {
    band,
    page_sev2: has && (prev < 70) && (cur >= 70),
    page_sev3: has && (cur < 70) && (prev < 40) && (cur >= 40),
    resolve: has && (prev >= 50) && (cur < 50),
  };
};
export default solve;
