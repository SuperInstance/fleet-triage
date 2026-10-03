// referral_graph.discovery.mjs — the mesh hunts its own currency (Casey
// 12:03 mandate; REFERRAL_GRAPH.md "Next rungs": auditReceipts against the
// live org PR stream).
//
// auditReceipts (src/referral_graph.mjs) *guards* existing VERIFIED edges —
// it decays them when a cited PR un-merges. But it cannot *mint* currency:
// a PENDING edge earns weight only when a merged PR in the TARGET repo cites
// its technique, and nobody was watching the org's merged-PR stream for
// that. This tool watches.
//
// For every PENDING edge, a small set of citation HINTS names the technique
// in the words a citing PR would plausibly use (kept next to the seed so a
// technique rename is a one-place edit). Live mode searches GitHub merged
// PRs in the edge's TARGET repo for each hint. A hit is a CANDIDATE upgrade:
// printed with its PR for a human to verify the citation is load-bearing,
// then the edge flips in referral_graph.seed.mjs (the seed is the ledger;
// this tool never books — weight must still be earned by an explicit edit
// the pins can FAIL-first).
//
// Honesty rules, same as the pins: gh absent / not --live -> every edge is
// reported SKIPPED, labeled, never passed silently. A hit in the WRONG repo
// is reported as invalid currency (a merged PR in the wrong repo does not
// verify — the weight law's whole point).

import { execFileSync } from 'node:child_process';

// Citation hints per PENDING edge, keyed `${from}->${to}`. The to-repo is
// derived from the seed, not restated — a typo here cannot move the target.
export const HINTS = {
  'qt-api-lab->qs-ep2':      ['receipts flip credit', 'receipts-over-scores', 'E2 receipts'],
  'qt-s3-tide->qa-plugins':  ['quantum-tided', 'PENDING/ENTANGLED/COLLAPSED', 'S3 witness'],
  'qa-negspace->qt-api-lab': ['NEGATIVE_SPACE', 'declined patch 12', 'declined-patch-12'],
  'qs-ep3->qa-plugins':      ['drag-to-reshape', 'episode-3 watcher', 'episode 3 watcher'],
  'aw-jev-kat->jq-kat-bridge': ['jev_kat', 'known-answer control', 'AI-Writings'],
  'mgq-qcells-lab->mm-sealed-receipts': ['micrograd-quilt', 'qcells lab', 'SuperInstance/micrograd-quilt'],
};

// Anti-Goodhart guard (first live discovery run, 2026-09-26): the graph's
// own PRs mention every technique it books — if a REFERRAL_GRAPH artifact
// could mint its edges' currency, the mesh would pay itself. A candidate
// whose title matches this pattern is reported EXCLUDED, never a candidate.
export const SELF_REFERENTIAL = /referral[ _-]?graph/i;

// Fuzzy-match guard (live run 2026-09-28): `gh search prs` ranks rather than
// filters — it returned quilt-arcade#3 for 'episode-3 watcher' when that PR
// never mentions watchers or episode 3 anywhere. So every search hit is
// citation-verified BEFORE it may present as a candidate: the hint text must
// appear literally (case-insensitive) in the PR's title, body, or diff. A
// hit that fails is surfaced as fuzzy-rejected — printed, never booked,
// never dropped silently. A gh error during verify is verify-unknown,
// surfaced the same way (an unverifiable hit is not a pass).

// searchFn(hint, repoFull) -> [{number,title,url,mergedAt}] — injectable for
// pins. Default: live GitHub merged-PR search scoped to the org + repo.
function ghSearch(hint, repoFull) {
  const out = execFileSync('gh', ['search', 'prs', `${hint} repo:${repoFull}`, '--merged', '--json', 'number,title,url', '--limit', '20'], { stdio: 'pipe' }).toString();
  return JSON.parse(out);
}

// verifyFn(hint, prNumber, repoFull) -> true | false | null — injectable for
// pins. Default: literal case-insensitive hint text in title, body, or diff;
// null = gh error (unknown, never a pass).
function ghVerify(hint, number, repoFull) {
  const needle = hint.toLowerCase();
  try {
    const view = JSON.parse(execFileSync('gh', ['pr', 'view', String(number), '--repo', repoFull, '--json', 'title,body'], { stdio: 'pipe' }).toString());
    if (((view.title ?? '') + '\n' + (view.body ?? '')).toLowerCase().includes(needle)) return true;
    const diff = execFileSync('gh', ['pr', 'diff', String(number), '--repo', repoFull], { stdio: 'pipe' }).toString();
    return diff.toLowerCase().includes(needle);
  } catch { return null; }
}

export function discover(seed, { live = false, searchFn = ghSearch, verifyFn = ghVerify, org = 'SuperInstance' } = {}) {
  const byId = new Map(seed.nodes.map(n => [n.id, n]));
  const results = [];
  for (const edge of seed.edges) {
    const key = `${edge.from}->${edge.to}`;
    if (edge.weight !== 'PENDING') continue; // VERIFIED guarded by auditReceipts; REFUTED scars skipped
    const hints = HINTS[key] ?? [];
    const entry = { edge: key, toRepo: byId.get(edge.to).repo, hints: hints.length, candidates: [], skipped: !live };
    if (live) {
      for (const hint of hints) {
        let hits = [];
        try { hits = searchFn(hint, `${org}/${byId.get(edge.to).repo}`); }
        catch { entry.candidates.push({ hint, error: 'search failed' }); continue; }
        for (const h of hits) {
          const selfReferential = SELF_REFERENTIAL.test(h.title ?? '');
          const verified = selfReferential ? undefined : verifyFn(hint, h.number, `${org}/${byId.get(edge.to).repo}`);
          entry.candidates.push({ hint, pr: `#${h.number}`, title: h.title, url: h.url, ...(selfReferential ? { selfReferential: true } : verified === false ? { fuzzyRejected: true } : verified === null ? { verifyUnknown: true } : {}) });
        }
      }
    }
    results.push(entry);
  }
  return results;
}

// CLI: node experiments/referral_graph.discovery.mjs [--live]
if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/'))) {
  const LIVE = process.argv.includes('--live');
  const { SEED } = await import('./referral_graph.seed.mjs');
  let ghOK = false;
  try { execFileSync('gh', ['auth', 'status'], { stdio: 'pipe' }); ghOK = true; } catch { ghOK = false; }
  const results = discover(SEED, { live: LIVE && ghOK });
  for (const r of results) {
    if (r.skipped) {
      console.log(`${r.edge} -> ${r.toRepo}: SKIPPED (gh=${ghOK}, --live=${LIVE}) — labeled, not silent`);
    } else {
      const real = r.candidates.filter(c => !c.selfReferential && !c.fuzzyRejected && !c.verifyUnknown);
      const fuzzy = r.candidates.filter(c => c.fuzzyRejected);
      const unknown = r.candidates.filter(c => c.verifyUnknown);
      const self = r.candidates.filter(c => c.selfReferential);
      if (real.length === 0 && self.length === 0 && fuzzy.length === 0 && unknown.length === 0) {
        console.log(`${r.edge} -> ${r.toRepo}: 0 candidates across ${r.hints} hints`);
      } else {
        if (real.length) {
          console.log(`${r.edge} -> ${r.toRepo}: ${real.length} CANDIDATE(S) — hint text verified in PR; still confirm load-bearing, then flip the seed:`);
          for (const c of real) console.log(`    [${c.hint}] ${c.pr} ${c.title}\n      ${c.url ?? c.error ?? ''}`);
        }
        if (fuzzy.length) {
          console.log(`${r.edge} -> ${r.toRepo}: ${fuzzy.length} FUZZY-REJECTED (gh search ranked it, but the hint text is absent from PR title/body/diff — surfaced, not booked):`);
          for (const c of fuzzy) console.log(`    [${c.hint}] ${c.pr} ${c.title}\n      ${c.url ?? ''}`);
        }
        if (unknown.length) {
          console.log(`${r.edge} -> ${r.toRepo}: ${unknown.length} VERIFY-UNKNOWN (gh error during citation check — surfaced, not booked):`);
          for (const c of unknown) console.log(`    [${c.hint}] ${c.pr} ${c.title}`);
        }
        if (self.length) {
          console.log(`${r.edge} -> ${r.toRepo}: ${self.length} EXCLUDED (self-referential — the graph's own artifact cannot mint its currency):`);
          for (const c of self) console.log(`    [${c.hint}] ${c.pr} ${c.title}`);
        }
      }
    }
  }
}
