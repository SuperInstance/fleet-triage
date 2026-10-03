#!/usr/bin/env python3
"""
adversarial_split.py — a split generator that cannot accidentally leak.

THE DEFECT
----------
A random 80/20 split of a table whose rows are near-duplicates puts a row's twin on
the other side of the boundary. A high-capacity model then fits the twin and inherits
its label. The reported score measures the dataset's duplication rate, not its
signal. The tell is a score that is *implausibly* high, or a memoriser that beats the
real observation.

WHAT THIS TOOL DOES
-------------------
It evaluates the same dataset under two splits and prints both:

  naive        random over rows              -- what everyone does
  group-aware  whole groups held out         -- what you have to do

and it prints the LEAK, so the two numbers are interpretable:

  twin_rate        fraction of test rows whose EXACT feature-twin is in train
  group_overlap    fraction of test rows whose GROUP appears in train

A group-aware split is not automatically honest either. It is honest about the
grouping you chose. If your grouping is the wrong axis, you have built a very
confident number about nothing, so the tool reports the leak rather than assuming
it is zero.

THE MEMOIRER
------------
`FNV1aMemory` is the brief's adversary, built literally: a 64-bit irreversible hash of
the feature string, scored by 1-nearest-neighbour exact match. It carries **zero**
information about the label. Anything it scores, it stole from a duplicate. That is
the whole point -- it is the null hypothesis wearing a model.

Nothing here depends on sklearn, which is absent in this environment. numpy only.
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from pathlib import Path

import numpy as np

# ───────────────────────────────────────────────────────────── FNV-1a 64-bit

_FNV64_OFFSET = 0xCBF29CE484222325
_FNV64_PRIME = 0x100000001B3
_M64 = 0xFFFFFFFFFFFFFFFF


def fnv1a64(s: str) -> int:
    """64-bit FNV-1a. Irreversible in the sense that matters here: you cannot
    invert it to recover the string, and it carries no label information."""
    h = _FNV64_OFFSET
    for b in s.encode("utf-8", "replace"):
        h ^= b
        h = (h * _FNV64_PRIME) & _M64
    return h


class FNV1aMemory:
    """1-NN on an exact 64-bit hash. Zero information. Pure memorisation."""

    name = "FNV1a-64 1-NN (memoriser, 0 bits of signal)"

    def fit(self, keys, y):
        self.tab = {}
        for k, lab in zip(keys, y):
            # majority label per exact twin
            self.tab.setdefault(k, []).append(lab)
        self.prior = float(np.mean(y)) if len(y) else 0.5
        self.maj = collections.Counter(y).most_common(1)[0][0] if len(y) else 0
        return self

    def predict(self, keys):
        out = []
        for k in keys:
            v = self.tab.get(k)
            if v is None:
                out.append(self.maj)          # unseen twin -> majority class
            else:
                out.append(1 if np.mean(v) >= 0.5 else 0)
        return np.array(out)


# ───────────────────────────────────────────────────── honest feature model

class LogReg:
    """Plain multinomial-free binary logistic regression, full-batch GD.

    Deliberately low-capacity. It can only use what the feature vector contains; it
    cannot invent a partition of the input space to isolate one string.
    """

    def __init__(self, l2=1.0, iters=400, lr=0.5, seed=0):
        self.l2, self.iters, self.lr, self.seed = l2, iters, lr, seed

    def fit(self, X, y):
        rng = np.random.default_rng(self.seed)
        self.w = rng.normal(0, 1e-3, X.shape[1])
        self.b = 0.0
        n = len(y)
        for _ in range(self.iters):
            z = X @ self.w + self.b
            p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
            g = X.T @ (p - y) / n + self.l2 * self.w / n
            gb = float(np.mean(p - y))
            self.w -= self.lr * g
            self.b -= self.lr * gb
        return self

    def predict(self, X):
        z = X @ self.w + self.b
        return (1.0 / (1.0 + np.exp(-np.clip(z, -30, 30))) >= 0.5).astype(int)


EXTS = [".ts", ".js", ".py", ".md", ".json", ".yml", ".yaml", ".rs", ".go", ".sh"]


def featurise(rec: dict) -> list[float]:
    """The COMPLETE OBSERVATION: every field the resolver actually recorded,
    turned into a fixed vector. This is the thing the hash is supposed to beat."""
    raw = rec.get("raw") or ""
    tgt = rec.get("target") or ""
    low = raw.lower()
    f = [
        float(len(raw)),
        float(len(tgt)),
        float("`" in raw),
        float("/" in raw),
        float(tgt.startswith("http")),
        float(rec.get("stage") == "citation"),
        float(rec.get("stage") == "external"),
        float(rec.get("outcome") is not None and rec["outcome"].startswith("URL_")),
        float(bool(rec.get("check"))),
        min(len(rec.get("check") or ""), 120) / 120.0,
        min(rec.get("docline") or 0, 400) / 400.0,
        float("__" in raw),
        float("(" in raw),
        float(any(e in low for e in EXTS)),
    ]
    f += [float(low.endswith(e)) for e in EXTS]
    d = rec.get("detail") or ""
    for k in ("in citing repo", "in index", "symbol", "line", "path"):
        f.append(float(k in d.lower()))
    return f


# ───────────────────────────────────────────────────────────────── splits

def split_naive(n, frac=0.2, seed=0):
    idx = list(range(n))
    random.Random(seed).shuffle(idx)
    k = int(n * frac)
    return idx[k:], idx[:k]


def split_group_aware(groups, frac=0.2, seed=0):
    """Hold out whole groups. Greedy largest-first with a size target, so the test
    set has a similar number of rows to the naive one."""
    by = collections.defaultdict(list)
    for i, g in enumerate(groups):
        by[g].append(i)
    items = sorted(by.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))
    rng = random.Random(seed)
    total = sum(len(v) for _, v in items)
    target = total * frac
    test, acc = [], 0
    for g, rows in items:
        if acc >= target:
            break
        test.extend(rows)
        acc += len(rows)
    testset = set(test)
    train = [i for i in range(total) if i not in testset]
    return train, test


def leak(keys, groups, tr, te):
    trk = set(keys[i] for i in tr)
    trg = set(groups[i] for i in tr)
    twin = sum(1 for i in te if keys[i] in trk) / max(len(te), 1)
    ovl = sum(1 for i in te if groups[i] in trg) / max(len(te), 1)
    return twin, ovl


# ───────────────────────────────────────────────────── the synthetic control

def synthetic_control(seed=0, n_pairs=300):
    """The orchestrator's confirmation, rebuilt so the instrument itself is tested.

    Features are PURE NOISE. Duplicates share a label. Nothing in X predicts y.
    Any score above chance is memorisation, full stop.

    This control must show: naive >> 0.5, group-aware ~= chance.
    If it does not, the tool is broken and the real-dataset numbers mean nothing.
    """
    rng = random.Random(seed)
    keys, y, groups = [], [], []
    for i in range(n_pairs):
        k = fnv1a64(f"noise-{rng.random()}")
        lab = rng.randint(0, 1)
        g = f"g{i}"
        for _ in range(2):                    # exactly one duplicate per group
            keys.append(k)
            y.append(lab)
            groups.append(g)
    out = {}
    for name, (tr, te) in (("naive", split_naive(len(y), seed=seed)),
                           ("group-aware", split_group_aware(groups, seed=seed))):
        m = FNV1aMemory().fit([keys[i] for i in tr], np.array([y[i] for i in tr]))
        p = m.predict([keys[i] for i in te])
        yt = np.array([y[i] for i in te])
        out[name] = bal_acc(p, yt)
    return out


# ─────────────────────────────────────────────────────────────── metrics

def bal_acc(pred, y):
    """Balanced accuracy: the mean of per-class recall. Chance = 0.5 exactly,
    regardless of class imbalance, which raw accuracy is not."""
    pred, y = np.asarray(pred), np.asarray(y)
    recalls = []
    for c in (0, 1):
        m = y == c
        if m.sum():
            recalls.append(float((pred[m] == c).mean()))
    return float(np.mean(recalls)) if recalls else float("nan")


def auc_score(pred, y):
    """AUC via MIDRANKS. Chance = 0.5.

    CALIBRATION HISTORY
    v1  used plain ordinal ranks with no tie correction. The memoriser emits binary
        predictions, so under a group-aware split ~91% of test rows are TIED on the
        majority class. Ordinal ranks break those ties arbitrarily and in index order,
        which reported AUC 0.88 on a model whose balanced accuracy was 0.52 -- a
        number that is arithmetically impossible and would have been quoted as
        "the hash still has signal". It had none. The instrument was lying in the
        direction that flatters the leak, which is the worst direction available.
        Fixed with proper midranks: tied values share the mean of their ranks.
"""
    pred, y = np.asarray(pred, float), np.asarray(y)
    npos, nneg = int((y == 1).sum()), int((y == 0).sum())
    if npos == 0 or nneg == 0:
        return float("nan")
    order = np.argsort(pred, kind="mergesort")
    sp = pred[order]
    ranks = np.empty(len(pred), float)
    i = 0
    while i < len(sp):
        j = i
        while j + 1 < len(sp) and sp[j + 1] == sp[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0     # midrank, 1-based
        i = j + 1
    rpos = ranks[y == 1].sum()
    return float((rpos - npos * (npos + 1) / 2.0) / (npos * nneg))


# ─────────────────────────────────────────────────────────────── loaders

def load_resolver(path):
    """THE REAL DATASET. 25,379 findings produced by a previous lane's resolver run
    over 199 real repos. Not constructed by this tool, not constructed by me."""
    data = json.loads(Path(path).read_text())["findings"]
    keys, y, groups, X = [], [], [], []
    for r in data:
        raw = r.get("raw") or ""
        keys.append(fnv1a64(raw))
        y.append(1 if r.get("outcome") == "RESOLVES" else 0)
        doc = r.get("doc") or ""
        for pre in ("/workspace/projects/fleet-triage/repos/", "/workspace/repos/",
                    "/workspace/projects/"):
            if doc.startswith(pre):
                doc = doc[len(pre):]
                break
        groups.append(doc.split("/")[0])
        X.append(featurise(r))
    return np.array(keys), np.array(y), groups, np.array(X)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=None, help="resolver_report.json")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    print("=" * 92)
    print("SYNTHETIC CONTROL — features are PURE NOISE, duplicates share a label.")
    print("Anything above 0.5 here is memorisation. This validates the instrument.")
    print("=" * 92)
    sc = synthetic_control(a.seed)
    print(f"  naive split        balanced-acc = {sc['naive']:.4f}")
    print(f"  group-aware split  balanced-acc = {sc['group-aware']:.4f}")
    gap = sc["naive"] - sc["group-aware"]
    print(f"  GAP                {gap:+.4f}   "
          f"{'instrument OK' if sc['naive'] > 0.75 and sc['group-aware'] < 0.75 else 'INSTRUMENT SUSPECT'}")

    if not a.dataset:
        return 0

    print("\n" + "=" * 92)
    print("REAL DATASET — resolver_report.json. 25,379 citation findings, 199 repos.")
    print("Produced by a previous lane's resolver run. NOT constructed by this tool.")
    print("=" * 92)
    keys, y, groups, X = load_resolver(a.dataset)
    n = len(y)
    print(f"rows={n}  features={X.shape[1]}  positives={y.mean():.3f}  groups={len(set(groups))}")

    c = collections.Counter(keys)
    dup = sum(v for v in c.values() if v > 1)
    print(f"distinct feature-strings={len(c)}  rows sharing a twin={dup} ({dup/n:.1%})")

    results = {}
    for name in ("naive", "group-aware"):
        if name == "naive":
            tr, te = split_naive(n, seed=a.seed)
        else:
            tr, te = split_group_aware(groups, seed=a.seed)
        twin, ovl = leak(keys.tolist(), groups, tr, te)
        ytr, yte = y[tr], y[te]
        Xtr, Xte = X[tr], X[te]

        mem = FNV1aMemory().fit([keys[i] for i in tr], ytr)
        pm = mem.predict([keys[i] for i in te])
        lr = LogReg(seed=a.seed).fit(Xtr, ytr.astype(float))
        pl = lr.predict(Xte)

        results[name] = {
            "twin_rate": twin, "group_overlap": ovl,
            "fnv1a_bal_acc": bal_acc(pm, yte), "fnv1a_auc": auc_score(pm, yte),
            "obs_bal_acc": bal_acc(pl, yte), "obs_auc": auc_score(pl, yte),
            "n_train": len(tr), "n_test": len(te),
        }
        print(f"\n--- {name} split  (train {len(tr)} / test {len(te)}) ---")
        print(f"  LEAK  twin_rate(test row has its exact twin in train) = {twin:.4f}")
        print(f"        group_overlap(test row's repo also in train)      = {ovl:.4f}")
        print(f"  FNV1a-64 1-NN memoriser   balanced-acc {bal_acc(pm, yte):.4f}   AUC {auc_score(pm, yte):.4f}")
        print(f"  COMPLETE OBSERVATION      balanced-acc {bal_acc(pl, yte):.4f}   AUC {auc_score(pl, yte):.4f}")
        verdict = "MEMORISER WINS" if bal_acc(pm, yte) > bal_acc(pl, yte) else "observation wins"
        print(f"  -> {verdict}  (delta {bal_acc(pm, yte) - bal_acc(pl, yte):+.4f})")

    d = results["naive"]; g = results["group-aware"]
    print("\n" + "=" * 92)
    print("THE GAP — same dataset, same models, only the split changed")
    print("=" * 92)
    for k, lbl in (("fnv1a_bal_acc", "FNV1a memoriser"), ("obs_bal_acc", "complete observation")):
        print(f"  {lbl:<24} naive {d[k]:.4f}  ->  group-aware {g[k]:.4f}   "
              f"drop {d[k]-g[k]:+.4f}  ({(d[k]-g[k])/max(d[k],1e-9):.1%} of the score)")
    print(f"\n  twin_rate      naive {d['twin_rate']:.4f}  ->  group-aware {g['twin_rate']:.4f}")
    print(f"  group_overlap  naive {d['group_overlap']:.4f}  ->  group-aware {g['group_overlap']:.4f}")

    if a.json:
        Path(a.json).write_text(json.dumps(
            {"synthetic_control": sc, "real": results,
             "n_rows": n, "n_features": int(X.shape[1]), "n_groups": len(set(groups)),
             "twin_rows": int(dup)}, indent=1))
        print(f"\njson -> {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
