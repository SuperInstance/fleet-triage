/**
 * A merge is an adjudication, not a concatenation.
 *
 * Given N claim sets, return:
 *   - claims         : the reconciled claim set (what you may now act on)
 *   - contradictions : every disagreement found — including the kind git
 *                      structurally cannot hold: a claim that is correct in
 *                      isolation and false in the union
 *   - derived        : claims the merge produced that NO input asserted
 *   - residual       : what we could not resolve, recorded rather than guessed
 *
 * The oracle is RE-EXECUTION, not a panel.
 *
 * Why: a 9-judge LLM panel has n_eff = 2.18, the best single judge matches or
 * beats the whole panel, and Dawid-Skene closes <=11% of the gap even with
 * oracle labels (arXiv 2605.29800). Judges agree with each other at kappa
 * 0.74-0.88 while agreeing with outcomes at ~0.2 (arXiv 2608.07517). 100k
 * agents sharing a base model, a prompt and a repo is the most correlated
 * panel imaginable, and it gets WORSE as the panel grows.
 *
 * So we do not vote. We route on agreement structure:
 *
 *   1. The witness is RE-RUNNABLE  -> execute it. Deterministic. Settled.
 *   2. The parties agree            -> union. Settled.
 *   3. Neither                      -> ABSTAIN. Record the residual.
 *
 * Abstention is a first-class result, not a failure. Shipping the uncertainty
 * is the feature; shipping a confident wrong merge is what everyone else does.
 */

import { makeClaim, findContradictions, assertionKey, canonical, claimKey } from './claim.js';

/* ------------------------------------------------------------------ *
 * Witnesses. A witness is a thing you can run again.
 * ------------------------------------------------------------------ */

/** Countable: "there are N of these". Re-runnable, so it settles by arithmetic. */
export function countable(subjectPrefix) {
  return { kind: 'count', subject: subjectPrefix };
}

/** Countable restricted to one object value: "how many edges are VERIFIED". */
export function countableWhere(subjectPrefix, object) {
  return { kind: 'count', subject: subjectPrefix, where: { object } };
}

export function distinctObjects(subjectPrefix) {
  return { kind: 'distinct', subject: subjectPrefix };
}

/** The consensus oracle, shipped so the demo can show it losing. */
export function agreeingParties(subjectPrefix, parties) {
  return { kind: 'agreeing-parties', subject: subjectPrefix, parties };
}

function matches(subject, pattern) {
  if (pattern.endsWith('*')) return subject.startsWith(pattern.slice(0, -1));
  return subject === pattern;
}

function matchesWhere(claim, where) {
  if (!where) return true;
  if (where.object !== undefined) return canonical(claim.object) === canonical(where.object);
  return true;
}

/**
 * Run a witness against a claim set. Returns {ok, value, reason}.
 * An unrunnable witness returns ok:false — we abstain, we do not guess.
 */
export function runWitness(witness, claims) {
  if (!witness) return { ok: false, reason: 'no-witness' };
  switch (witness.kind) {
    case 'count': {
      const n = claims.filter((c) => c.predicate === 'instance' &&
        matches(c.subject, witness.subject) && matchesWhere(c, witness.where)).length;
      return { ok: true, value: n };
    }
    case 'distinct': {
      const set = new Set(
        claims.filter((c) => c.predicate === 'instance' &&
          matches(c.subject, witness.subject) && matchesWhere(c, witness.where))
          .map((c) => canonical(c.object)),
      );
      return { ok: true, value: set.size };
    }
    case 'agreeing-parties': {
      const p = new Set(witness.parties || []);
      const n = claims.filter((c) => p.has(c.author || c.branch) &&
        c.predicate === 'instance' && matches(c.subject, witness.subject)).length;
      return { ok: true, value: n };
    }
    case 'prose':
      // Not machine-checkable. The only honest verdict is abstain.
      return { ok: false, reason: 'prose-not-runnable' };
    default:
      return { ok: false, reason: `unknown-witness:${witness.kind}` };
  }
}

const EXECUTABLE = new Set(['count', 'distinct']);

/* ------------------------------------------------------------------ *
 * The merge.
 * ------------------------------------------------------------------ */

/**
 * @param {Array<{claims: Array, branch: string}>} sets
 */
export function adjudicate(sets) {
  const all = [];
  for (const s of sets) {
    for (const c of s.claims) all.push({ ...c, branch: c.branch || s.branch });
  }

  // --- 1. Pairwise contradictions: same subject+predicate, different object.
  //        This is the conflict git *can* represent, and it is the boring one.
  const pairwise = findContradictions(all);

  // --- 2. Unify assertions. Identical claims from both branches merge by
  //        union; we keep one and remember who stood behind it.
  const byAssertion = new Map();
  for (const c of all) {
    const k = assertionKey(c);
    if (!byAssertion.has(k)) byAssertion.set(k, []);
    byAssertion.get(k).push(c);
  }

  // The merged WORLD is the set of distinct facts, not the multiset of
  // assertions. Seventeen edges both agents saw are seventeen edges, not
  // thirty-four. Witnesses are re-run over this, so a fact stated twice
  // cannot inflate a count.
  const world = [...byAssertion.values()].map((g) => g[0]);

  const claims = [];
  const derived = [];
  const residual = [];
  const witnesses = new Set(); // subject|predicate already settled by execution

  for (const [, group] of byAssertion) {
    const head = group[0];
    const wKey = `${claimKey(head)}`;
    const supportedBy = [...new Set(group.map((c) => c.author || c.branch || 'unknown'))];

    const pair = pairwise.find((con) => con.parties.some((p) => p.assertion === assertionKey(head)));
    const contested = Boolean(pair);

    // Re-execute. This is the only thing that settles anything.
    const w = head.witness;
    const run = w ? runWitness(w, world) : { ok: false, reason: 'no-witness' };

    if (run.ok && EXECUTABLE.has(w.kind)) {
      const trueValue = run.value;
      const agreed = canonical(trueValue) === canonical(head.object);

      if (agreed) {
        // The claim survives its own witness.
        claims.push({ ...head, supporters: supportedBy });
        if (contested) {
          for (const p of pair.parties) {
            residual.push({
              subject: pair.subject, predicate: pair.predicate,
              losing: p.claims, reason: 're-execution confirmed this party',
            });
          }
        }
        continue;
      }

      // The claim is false in the union. It was true where it was made.
      // Nobody is a loser and everybody was right. The union is a world that
      // no branch had ever seen.
      const first = !witnesses.has(wKey);
      witnesses.add(wKey);
      const verdict = makeClaim({
        subject: head.subject,
        predicate: head.predicate,
        object: trueValue,
        witness: w,
        confidence: 1.0,
        author: '@merge',
        note: 're-executed over the union; asserted by nobody',
      });
      if (first) derived.push(verdict);
      claims.push({ ...verdict, supporters: ['@merge'] });

      if (first) {
        for (const p of (pair ? pair.parties : [{ claims: group }])) {
          residual.push({
            subject: head.subject,
            predicate: head.predicate,
            losing: p.claims,
            reason: 'superseded by re-execution over the union',
            falsifiedInUnionBy: { witness: w, observed: trueValue, claimed: p.claims.map((c) => c.object) },
          });
        }
      }
      continue;
    }

    if (contested) {
      // Unrunnable and contested: ABSTAIN, and keep every party.
      // Emitted once per (subject,predicate) — emitting per assertion would
      // report the same disagreement twice and duplicate every losing claim.
      if (!witnesses.has(wKey)) {
        witnesses.add(wKey);
        claims.push({ ...head, contested: true });
        residual.push({
          subject: pair.subject,
          predicate: pair.predicate,
          losing: pair.parties.flatMap((p) => p.claims),
          reason: run.reason || 'contested, no runnable witness',
          abstained: true,
        });
      }
      continue;
    }

    claims.push({ ...head, supporters: supportedBy });
  }

  return {
    claims,
    contradictions: pairwise,
    derived,
    residual,
    stats: {
      inputClaims: all.length,
      outputClaims: claims.length,
      pairwiseContradictions: pairwise.length,
      falsifiedByUnion: residual.filter((r) => r.falsifiedInUnionBy).length,
      derived: derived.length,
      abstained: residual.filter((r) => r.abstained).length,
      losingClaimsPreserved: residual.reduce((a, r) => a + r.losing.length, 0),
    },
  };
}

export { claimKey, assertionKey, canonical };
