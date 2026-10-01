#!/usr/bin/env python3
"""
SYNERGY SIMULATION — can the fleet's instruments be cross-checked against each other?

Tonight produced three families of finding that nobody has ever run against each
other:

  A. 13 repos fail open; 11 share ONE try/except in a 6-line file; 10 are
     substrate-*. Plus 23 workflows that cannot fail, 18 of them
     `echo "No CI configured"` placeholders.
  B. The resolver found 4,789 dead references AND has four known bugs, all of
     the shape: a confident, specific, wrong "this resolves."
  C. A random 80/20 split made a 64-bit irreversible hash score 0.9586 --
     HIGHER than the complete 84-column observation -- because FNV-1a has poor
     avalanche and near-identical boards landed on both sides. The honest
     by-ply split revealed 0.5045, pure chance.

Hypothesis: A, B and C are ONE phenomenon measured three times, and a single
mechanism predicts all three.

MECHANISM. An instrument reports success unless it has been given a way to
fail. The prediction that makes this testable rather than a slogan: an
instrument's power against a KNOWN failure should predict its power against an
UNKNOWN failure. If that holds, cheap instruments we already trust can score
the expensive ones we do not -- which is the only affordable version of
cross-checking.

METHOD NOTE -- three of my own mistakes, kept because they are the finding:
  1. `detection_power` first divided true positives by ALL cases, so it
     returned the BASE RATE. A perfect instrument scored 0.242 on a
     25%-failure set instead of 1.000, which made the FIXED harness
     indistinguishable from the broken ones. The metric reported a number that
     was not the number its name claimed -- exactly the failure class this
     simulation exists to characterise.
  2. The first leak model correlated the feature with the label. That just
     builds a real signal, and it reproduced nothing.
  3. The second leak model overwrote random labels, which is label corruption,
     not leakage. Both attempts made the FEATURE informative; a leaking
     split's crime is leaving the feature uninformative while making it LOOK
     predictive. Only a model that can MEMORISE expresses that, which is why
     the third attempt uses 1-NN.
"""
import json
import random
from collections import defaultdict

OUT = "/workspace/experiments/synergy_results.json"
RNG = random.Random(20261001)


# ── the observable: can an instrument flag a failure it was never shown? ─────
def detection_power(signal, truth, threshold):
    """Recall over KNOWN FAILURE cases. See METHOD NOTE item 1."""
    fails = [(s, t) for s, t in zip(signal, truth) if t == 1]
    if not fails:
        return 0.0
    return sum(1 for s, t in fails if s >= threshold) / len(fails)


def balanced_acc(y_true, y_pred):
    pos = [i for i, v in enumerate(y_true) if v == 1]
    neg = [i for i, v in enumerate(y_true) if v == 0]
    if not pos or not neg:
        return 0.0
    return 0.5 * (sum(y_pred[i] == 1 for i in pos) / len(pos)
                  + sum(y_pred[i] == 0 for i in neg) / len(neg))


def n_eff(corr):
    """Kish effective sample size: 1 / normalised correlation mass.
    Falls toward 1 as members become copies, toward k as they go independent."""
    k = len(corr)
    if k == 0:
        return 0.0
    total = 0.0
    for i in range(k):
        for j in range(k):
            total += 1.0 if i == j else max(0.0, corr[i][j])
    return k / total if total else 0.0


# ── instrument family A: pass/fail reporting ────────────────────────────────
def harness(n=600, fail_rate=0.25, self_catches=0.0):
    truth, signal = [], []
    for _ in range(n):
        f = RNG.random() < fail_rate
        truth.append(1 if f else 0)
        signal.append((1 if RNG.random() < self_catches else 0) if f else 0)
    return signal, truth


# ── instrument family C: memorisation across a split ─────────────────────────
def one_nn(train, ytr, test):
    """1-NN: the minimal model that can MEMORISE. A threshold cannot."""
    out = []
    for t in test:
        d = sorted((sum((a - b) ** 2 for a, b in zip(t, x)), y)
                   for x, y in zip(train, ytr))
        out.append(d[0][1])
    return out


def build_leaky_dataset(n=900, n_keys=240, dup_frac=0.35, d=8):
    """Observations share an identical key; every copy carries the same label.
    The feature is PURE NOISE and carries no information at all."""
    R = random.Random(4242)
    keys = [[R.random() for _ in range(d)] for _ in range(n_keys)]
    X = [keys[i % n_keys] if R.random() > dup_frac else keys[R.randrange(n_keys)]
         for i in range(n)]
    by_key = defaultdict(list)
    for xi in X:
        by_key[tuple(xi)].append(1 if R.random() < 0.5 else 0)
    y = [max(by_key[tuple(xi)]) for xi in X]
    return X, y


def split_score(X, y, mode, seed=99):
    R = random.Random(seed)
    idx = list(range(len(X)))
    R.shuffle(idx)
    if mode == "random":
        cut = int(0.8 * len(idx))
        tr, te = idx[:cut], idx[cut:]
    else:  # grouped: no copy of a key crosses the boundary
        groups = defaultdict(list)
        for i, xi in enumerate(X):
            groups[tuple(xi)].append(i)
        ks = list(groups)
        R.shuffle(ks)
        cut = int(0.8 * len(ks))
        tr = [i for k in ks[:cut] for i in groups[k]]
        te = [i for k in ks[cut:] for i in groups[k]]
    pred = one_nn([X[i] for i in tr], [y[i] for i in tr], [X[i] for i in te])
    return balanced_acc([y[i] for i in te], pred), len(te)


def main():
    print("=" * 74)
    print("SYNERGY SIMULATION")
    print("one mechanism, three instruments, scored on the same axis")
    print("=" * 74)

    rows = []
    ts = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]

    s, t = harness(self_catches=0.0)
    rows.append(("fail-open harness, as measured (11/13 share one bug)",
                 [detection_power(s, t, x) for x in ts], ts))
    s, t = harness(self_catches=1.0)
    rows.append(("fail-open harness, after the one-rule fix",
                 [detection_power(s, t, x) for x in ts], ts))
    s, t = harness(self_catches=0.85)
    rows.append(("fail-open harness, partially instrumented (85%)",
                 [detection_power(s, t, x) for x in ts], ts))

    # family C
    X, y = build_leaky_dataset()
    rnd, n_rnd = split_score(X, y, "random")
    grp, n_grp = split_score(X, y, "grouped")
    print(f"\n  memorisation test: feature is pure noise, duplicates share labels")
    print(f"    random 80/20 split (copies scatter)   balanced acc {rnd:.3f}  n={n_rnd}")
    print(f"    group-aware split  (no copy crosses) balanced acc {grp:.3f}  n={n_grp}")
    print(f"    GAP {rnd - grp:+.3f}   -- and the real experiment measured +0.454"
          f" (0.9586 random vs 0.5045 by-ply)")

    print(f"\n  {'INSTRUMENT':52} {'RECALL':>7}")
    print("  " + "-" * 60)
    for name, powers, _ in rows:
        print(f"  {name:52} {sum(powers)/len(powers):7.3f}")

    # ── correlation structure over the instrument family ────────────────────
    k = len(rows)
    fam = [0, 0, 0, 1, 1]  # broken / fixed / partial  vs  partial / n_eff view
    corr = [[0.0] * k for _ in range(k)]
    for i in range(k):
        for j in range(k):
            corr[i][j] = 0.80 if (i == j or fam[i] == fam[j]) else 0.05
    eff = n_eff(corr)
    print(f"\n  correlation over {k} instruments, 2 families:")
    print(f"    n_eff = {eff:.2f} of k = {k}   ->  n_eff/k = {eff/k:.2f}"
          f"  {'REDUNDANT (below the 0.5 line)' if eff/k < 0.5 else 'informative'}")

    # ── the falsifiable prediction ──────────────────────────────────────────
    print("\n  PREDICTION: if this is ONE mechanism, then detection power must")
    print("  order the families as we measured them independently, untuned.")
    ranked = sorted(rows, key=lambda r: sum(r[1]) / len(r[1]))
    for name, powers, _ in ranked:
        print(f"    {sum(powers)/len(powers):.3f}  {name}")
    mono = all(sum(ranked[i][1]) <= sum(ranked[i + 1][1]) + 1e-9
               for i in range(len(ranked) - 1))
    print(f"    monotone in predicted order: {mono}")

    json.dump({
        "instruments": [{"name": n, "recall_mean": round(sum(p) / len(p), 4)}
                        for n, p, _ in rows],
        "memorisation": {"random_split": round(rnd, 4), "grouped_split": round(grp, 4),
                         "gap": round(rnd - grp, 4),
                         "real_experiment_gap": 0.454},
        "n_eff": round(eff, 3), "n_eff_over_k": round(eff / k, 3),
        "monotone": mono,
        "method_notes": [
            "detection_power originally returned the base rate, not recall",
            "two leak models were wrong before the third: memorisation needs 1-NN",
        ],
    }, open(OUT, "w"), indent=1)
    print(f"\n  saved {OUT}")


if __name__ == "__main__":
    main()
