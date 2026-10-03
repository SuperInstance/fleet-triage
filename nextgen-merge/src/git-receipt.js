/**
 * What git actually did, measured 2026-10-01 against the live repo.
 *
 * This file is the receipt. Every number in it was produced by running git,
 * not by reading the PR bodies. `npm run verify` re-runs all of it from a
 * fresh clone so a judge can check rather than trust.
 *
 * --- The shape of the failure -------------------------------------------------
 *
 *   58e2a18  Merge PR #30                 17 edges  13 VERIFIED  4 PENDING
 *     |  \
 *     |   a98a5c5  PR #32 head             18 edges  14 VERIFIED  4 PENDING
 *     |  /                                  asserts "18", "fourteen VERIFIED"
 *     |   7caf5a3  PR #33 head             18 edges  14 VERIFIED  4 PENDING
 *     |  /                                  asserts "18", "fourteen VERIFIED"
 *     | /
 *   fb2e041  Merge PR #32   -> "18", "fourteen"
 *   0101409  Merge PR #33   -> "19", "fifteen"    <-- what actually landed
 *
 * Both agents branched from the same parent. Both counted 17 + 1. Both are
 * right. The union is 19. There is no losing claim, and git's conflict model
 * has no representation for a merge with no loser.
 */

export const GIT_RECEIPT = {
  repo: 'SuperInstance/quilt-tools',
  verified: '2026-10-01',
  parents: {
    base: '58e2a18',
    pr32: 'a98a5c5',
    pr33: '7caf5a3',
  },
  siblings: true,
  perCommit: {
    '58e2a18': { edges: 17, VERIFIED: 13, PENDING: 4, asserts: '17 / thirteen VERIFIED' },
    'a98a5c5': { edges: 18, VERIFIED: 14, PENDING: 4, asserts: '18 / fourteen VERIFIED' },
    '7caf5a3': { edges: 18, VERIFIED: 14, PENDING: 4, asserts: '18 / fourteen VERIFIED' },
    'fb2e041': { edges: 18, VERIFIED: 14, PENDING: 4, asserts: '18 / fourteen VERIFIED' },
    '0101409': { edges: 19, VERIFIED: 15, PENDING: 4, asserts: '19 / fifteen VERIFIED' },
  },
  key: 'Both PRs assert 18. The merged tree has 19. Both are correct.',
};

/** `git merge a98a5c5 7caf5a3` from the shared base. */
export const naiveMerge = {
  command: 'git checkout 58e2a18 && git merge a98a5c5 && git merge 7caf5a3',
  conflictedFiles: ['experiments/REFERRAL_GRAPH.md', 'experiments/referral_graph.pins.mjs'],
  conflictHunks: 5,
  seedFile: {
    file: 'experiments/referral_graph.seed.mjs',
    autoMerged: true,
    askedNothing: true,
    resultEdges: 19,
    consequence:
      'The file holding the actual edge data merged WITHOUT a conflict marker, ' +
      'silently taking the union. git never surfaced that the world is now 19 ' +
      'while both agents pinned it at 18. The dangerous half of this merge was ' +
      'the half git did not complain about.',
  },
  whyGitCannotHelp:
    'Both hunks are counter assertions. git can only ask a human to pick a ' +
    'side, and here there is no side to pick: 18 was true on both branches and ' +
    '19 is true only in the union. git has no third option to offer.',
};

/** The "keep both" resolution every agent reaches for. */
export const keepBothResult = {
  strategy: 'concatenate both sides of every hunk, drop the markers',
  hunks: 5,
  output: '/tmp/keepboth.mjs',
  openBraces: 270,
  closeBraces: 269,
  parses: false,
  error: 'SyntaxError: missing ) after argument list',
  at: 'experiments/referral_graph.pins.mjs:110',
  cause:
    'Both sides open a block for their own new pin and both close it. Unioning ' +
    'them yields two openings and one closing, and two colliding const bindings.',
};

/** What the human actually did, which is the real cost of git here. */
export const actualResolution = {
  commit: '175a398',
  message: 'edge15 landing: union world-state 15 VERIFIED — assertions re-derived empirically from pins run',
  what:
    'A third person re-ran the pins, computed 19 and 15 by hand, and overwrote ' +
    'both agents\' assertions. The merge worked. The two claims that were ' +
    'overwritten were not recorded anywhere — not in the tree, not in the log, ' +
    'not in the PR bodies, which still say "17 to 18, 13 to 14" today.',
};
