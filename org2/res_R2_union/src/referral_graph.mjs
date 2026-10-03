// referral_graph.mjs — the Referral Mesh substrate (Casey 12:03 mandate, PoC).
//
// "Not one thing but a distribution of intelligent referrals": ideas are
// nodes, referrals are weighted LINKs, and the answer to any question is a
// RANKED DISTRIBUTION over modules — every edge carrying the receipt that
// proves or the falsification condition that would kill it.
//
// Weight law (constitution):
//   PENDING  — speculation; weight ε. Cheap.
//   VERIFIED — a MERGED PR in the TARGET repo cites this technique; weight 1.
//              Cross-use is the only currency; speculation is not.
//   REFUTED  — its falsification_condition was met by observed evidence;
//              booked as a REFUSED row, kept in the graph as scar tissue.
//
// Every edge is booked as a row in an fnv1a-64 hash chain (the fleet receipt
// idiom, ported verbatim from quilt-cloudflare/src/ocean.ts via toolkit):
// tampering with a claim is loud, indexed, and re-derivable by a stranger.

import { fnv1a64, canon, makeRow, verifyChain } from './toolkit.mjs';

export const PENDING_WEIGHT = 0.05;
export const VERIFIED_WEIGHT = 1.0;
export const RECEIPT_RE = /^[\w.-]+\/[\w.-]+#\d+$/; // owner/repo#N

export class ReferralGraph {
  constructor({ name, repos = [] } = {}) {
    this.name = name ?? 'referral-graph';
    this.repos = repos;
    this.nodes = new Map(); // id -> {id, repo, kind, summary}
    this.rows = [];         // booked edge rows (the chain)
    this._prev = null;
  }

  addNode(node) {
    for (const k of ['id', 'repo', 'summary']) {
      if (!node?.[k]) throw new Refusal(`node missing required key '${k}'`);
    }
    if (this.nodes.has(node.id)) throw new Refusal(`duplicate node '${node.id}'`);
    this.nodes.set(node.id, { kind: 'idea', ...node });
    return this;
  }

  // Book an edge. Fields validated BEFORE booking — an invalid edge is a
  // REFUSAL (thrown), never a silent drop.
  //
  // Two distinct PR-shaped fields, do not conflate:
  //   provenance — where the FINDING lives (merged PR in the source repo).
  //                Shape-checked, never earns weight.
  //   receipt    — the CURRENCY (mandate 12:03): a merged PR in the TARGET
  //                repo that cites this technique. Only VERIFIED edges may
  //                carry one, and its target repo must match the to-node.
  book(edge) {
    const idx = this.rows.length;
    const refuse = why => { throw new Refusal(`edge ${idx}: ${why}`); };
    for (const k of ['from', 'to', 'claim', 'falsification_condition']) {
      if (!edge?.[k]) refuse(`missing required key '${k}'`);
    }
    if (!this.nodes.has(edge.from)) refuse(`unknown from-node '${edge.from}'`);
    if (!this.nodes.has(edge.to)) refuse(`unknown to-node '${edge.to}'`);
    if (edge.from === edge.to) refuse('self-referral is not a referral');
    if (edge.provenance !== undefined && edge.provenance !== null && !RECEIPT_RE.test(edge.provenance)) {
      refuse(`provenance '${edge.provenance}' is not owner/repo#N`);
    }
    if (edge.weight === 'VERIFIED') {
      if (!edge.receipt) refuse('VERIFIED without receipt — cross-use is the only currency');
      if (!RECEIPT_RE.test(edge.receipt)) refuse(`receipt '${edge.receipt}' is not owner/repo#N`);
      const [target] = edge.receipt.split('#');
      const toRepo = this.nodes.get(edge.to).repo;
      if (!target.endsWith('/' + toRepo) && target !== toRepo) {
        refuse(`receipt target '${target}' is not the to-node's repo (${toRepo}) — a merged PR in the WRONG repo does not verify`);
      }
    } else if (edge.weight === 'PENDING') {
      if (edge.receipt) refuse('PENDING edge cannot carry a receipt — weight must be earned');
    } else {
      refuse(`unknown weight '${edge.weight}' (PENDING|VERIFIED)`);
    }

    const row = makeRow(this._prev, {
      op: 'LINK',
      from: edge.from,
      to: edge.to,
      claim: edge.claim,
      weight: edge.weight,
      provenance: edge.provenance ?? null,
      receipt: edge.receipt ?? null,
      falsification_condition: edge.falsification_condition,
    });
    this._prev = row;
    this.rows.push(row);
    return row;
  }

  // Falsification probe: evidence observed → does it meet an edge's stated
  // kill condition? Meeting it flips the edge to REFUTED and books the kill
  // as a REFUSED row — dying honestly is promotable, hiding it is not.
  probe(from, to, evidence) {
    const row = this.rows.find(r => r.from === from && r.to === to);
    if (!row) throw new Refusal(`no edge ${from} -> ${to} to probe`);
    const hit = evidence === row.falsification_condition;
    const kill = makeRow(this._prev, {
      op: hit ? 'REFUSED' : 'EFFECT',
      from, to,
      claim: hit ? `falsified: ${evidence}` : `survived probe: ${evidence}`,
      weight: row.weight,
      provenance: row.provenance,
      receipt: row.receipt,
      falsification_condition: row.falsification_condition,
    });
    this._prev = kill;
    this.rows.push(kill);
    return { hit, row: kill };
  }

  // Receipt audit: the graph claims certain PRs merged. An auditor (live gh,
  // or any injected checker) decides; unmerged/404 → edge downgraded to
  // PENDING with the downgrade booked, not silently rewritten.
  auditReceipts(isMerged) {
    const results = [];
    for (const row of this.rows) {
      if (row.op !== 'LINK' || row.weight !== 'VERIFIED') continue;
      const merged = isMerged(row.receipt);
      results.push({ receipt: row.receipt, merged });
      if (!merged) {
        const downgrade = makeRow(this._prev, {
          op: 'REFUSED', from: row.from, to: row.to,
          claim: `receipt ${row.receipt} not merged — downgraded to PENDING`,
          weight: 'PENDING', provenance: row.provenance, receipt: null,
          falsification_condition: row.falsification_condition,
        });
        this._prev = downgrade;
        this.rows.push(downgrade);
        row.weight = 'PENDING'; row.receipt = null; // history preserves the lie
      }
    }
    return results;
  }

  // The VIEW: the answer as a ranked distribution over modules. Verified
  // referrals dominate; pending speculation keeps a whisper; refuted scars
  // keep zero mass but stay visible.
  view() { return this._view(() => 1); }

  // The G11 TRUST LEVER — ported from SuperInstance/jev-quilt commons.py
  // (trust_weighted() / provenance_merge(), G11 "trust-weighted cross-fleet
  // gluing", merged as SuperInstance/jev-quilt#37). The blind view sums edge
  // weight per target repo, and weight is cheap to inflate: a source the
  // fleet has not earned to trust can merge N junk-citation PRs into its own
  // repo and buy itself mass. viewTrusted re-scales every edge by its
  // TARGET repo's EARNED trust:
  //
  //     effective(edge) = trust.get(toRepo, default) · weight(edge)
  //
  // An unseen source defaults to 0: it contributes NOTHING until the fleet
  // earns reason to trust it — a lie minted at weight 1.0 ×10 by a stranger
  // is scaled to 0 and cannot outvote one small trusted truth. Trust is the
  // lever; weight alone is not. Ranking shape, refuted-scar exclusion, and
  // share arithmetic are identical to view() (trust 1 for every repo reduces
  // exactly to the blind view — pinned).
  viewTrusted({ trust = {}, default: dflt = 0 } = {}) {
    const t = trust instanceof Map ? (k) => trust.get(k) ?? dflt
                                   : (k) => Object.hasOwn(trust, k) ? trust[k] : dflt;
    return this._view(t);
  }

  _view(trustOf) {
    const mass = new Map(); // repo -> weight
    let total = 0;
    const refuted = new Set();
    for (const r of this.rows) {
      if (r.op === 'REFUSED' && r.claim.startsWith('falsified:')) refuted.add(`${r.from}->${r.to}`);
    }
    for (const r of this.rows) {
      if (r.op !== 'LINK' || refuted.has(`${r.from}->${r.to}`)) continue;
      const w = r.weight === 'VERIFIED' ? VERIFIED_WEIGHT : PENDING_WEIGHT;
      const repo = this.nodes.get(r.to).repo;
      const tw = trustOf(repo) * w;
      if (tw <= 0) continue; // an untrusted source contributes nothing (G11)
      mass.set(repo, (mass.get(repo) ?? 0) + tw);
      total += tw;
    }
    return [...mass.entries()]
      .map(([repo, w]) => ({ repo, weight: w, share: total ? w / total : 0 }))
      .sort((a, b) => b.share - a.share || a.repo.localeCompare(b.repo));
  }

  verify() { return verifyChain(this.rows); }
  exportRows() { return this.rows.map(r => ({ ...r })); }
}

export class Refusal extends Error {
  constructor(msg) { super(msg); this.name = 'REFUSAL'; }
}
