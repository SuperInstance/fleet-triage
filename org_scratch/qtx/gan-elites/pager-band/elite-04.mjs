// Fleet-pager — hysteresis banding — GAN-HARDENED elite #4
// bred by the quilt-loom Divergence Foundry (offline leg)
// family: rules_table   hash: dac5cc639a   voice: mech   gen: 8   novelty: 0.86615
// contract: Given severity cur (integer 0-100) and prev (previous severity, integer or null): band = "sev2" if cur>=70, "sev3" if cur>=40, else "quiet". page_sev2 fires iff prev!=null and cur>=70 and prev<70; page_sev3 iff prev!=null and cur>=40 and cur<70 and prev<40; resolve iff prev!=null and cur<50 and prev>=50. Return {band, page_sev2, page_sev3, resolve}.
// provenance: outputs/elites/pager_band/ + outputs/fleet_live_results.json
export const solve = function solve(input) {
  const cur = input.cur, prev = input.prev;
  const rows = [[70, 'sev2'], [40, 'sev3']];
  let band = 'quiet';
  for (const row of rows) {
    if (cur >= row[0]) { band = row[1]; break; }
  }
  const has = (prev !== null && prev !== undefined);
  const flags = [
    ['page_sev2', [cur >= 70, prev < 70]],
    ['page_sev3', [cur >= 40, cur < 70, prev < 40]],
    ['resolve', [cur < 50, prev >= 50]],
  ];
  const out = { band, page_sev2: false, page_sev3: false, resolve: false };
  if (has) {
    for (const f of flags) {
      if (f[1].every(Boolean)) out[f[0]] = true;
    }
  }
  return out;
};
export default solve;
