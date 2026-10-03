#!/usr/bin/env python3
"""
panel_canary.py — CANARY x n_eff, the one that is not composition.

A bare canary pins a value.  A bare n_eff collapses M distributions to one number.
Neither can see the other.  The third thing this file computes is neither of those:

    n_witness  = (sum_i sigma_i)^2 / sum_i sigma_i^2     over the singular values
                 of the RESIDUAL matrix R, where r_m = P_m - consensus

the number of *effective independent witnesses* standing behind a green canary.

READ THIS LINE, IT IS THE WHOLE THING:
  a canary that all M members agree on is worth ONE witness, no matter how many
  members there were.  Passing the pin is not the claim.  The claim is that the
  passing was independent, and that is measurable.

Verdicts are THREE, not two, on purpose:
  CONFIRMED          canary green, n_witness >= K   -> the pin is corroborated
  REFUSED-CORRELATED canary green, n_witness <  K   -> the green is not evidence
  VIOLATED           canary red                      -> a HARD FAIL, and it is
                     NOT laundered by correlation. A panel that unanimously
                     agrees the pin is broken is the most unanimous panel there
                     is, and unanimity about a wrong value is the exact shape of
                     CANARY-FICTION.md.  Correlation may only ever DOWNGRADE
                     evidence of a PASS.  It can never suppress a FAIL.

THAT is why this makes things harder to get wrong rather than merely more
possible.  The one new failure mode a canary-n_eff tool could have introduced is
"the panel looked weak, so I'll ignore the red."  This design makes that
unrepresentable: the red path never reads n_witness at all.

JEV contract (JEV-CONTRACT.md) — three primitives, three shapes, never collapsed:
  choice  criteria:{label:null}   -> probabilities keyed by LABEL
  score   levels:[...]            -> probabilities keyed by LEVEL INDEX, "legend"
                                      maps index -> label.  Rebased, not summed.
  noul    (neither)               -> {"noul": 0.97}   REJECTED HERE.
  noul has no distribution, and a panel of scalars has no agreement structure.

OPTION IDENTITY IS BYTE-EXACT DECLARED INDEX.  NOT NFC.  This is the sharpest
thing in the file and I got it wrong first: an earlier version keyed the option
set on NFC, then refused to declare a canary whose options are {NFC, NFD}.  That
refusal was CORRECT and the design behind it was not.  NFC-normalising option
identity makes this canary STRUCTURALLY INCAPABLE of detecting the failure it
exists to detect, because NFC is the exact normalization the story is about.

  A canary is live only if its option identity is FINER than the normalization
  the pipeline actually runs.  `Canary.identity_floor()` reports that floor, and
  a canary the fleet's own normalizer can collapse is a DEAD canary that will
  pass forever.  Compare CANARY-FICTION.md: eleven ports agreed on a string the
  tool had normalized, and the pin was green the whole time.

KNOWN BOUND, stated rather than hidden:  the M residual rows sum to zero BY
CONSTRUCTION (they are deviations from their own mean), so rank(R) <= M-1, and
they live in a (K-1)-dimensional simplex, so

    n_witness <= min(M-1, K-1)        for M > 1

Five members can therefore certify at most FOUR independent witnesses, never five,
and a 3-option canary can never measure more than 2 whatever the panel is.  The
number is always reported with its ceiling, never bare.  (I first wrote this
bound as min(M, K-1), it was wrong, and the measured 4.00 for a 5-member panel
is what caught it -- the tool was right and the docstring was not.)
"""
import unicodedata

import numpy as np

K = 3  # independent witnesses required to promote a green canary to CONFIRMED


def _nfc(s):
    return unicodedata.normalize("NFC", s)


class Canary:
    """A canary as a TYPED CELL: a closed option set with stable keys, one pinned.

    `labels` is the full option set.  `pin` is the index that must hold.  Nothing
    outside the set can be asserted about this canary — not by a panel member,
    not by the pin itself.
    """

    def __init__(self, key, labels, pin):
        if not 0 <= pin < len(labels):
            raise ValueError("pin outside the option set")
        if len(set(labels)) != len(labels):   # byte-exact: NFC and NFD ARE different
            raise ValueError("option set is not closed: duplicate exact label")
        self.key, self.labels, self.pin = key, list(labels), pin
        self._index = {l: i for i, l in enumerate(labels)}   # byte-exact identity

    def identity_floor(self):
        """The coarsest normalization under which this canary's options COLLAPSE.

        If the fleet's own normalizer reaches this floor, the canary is dead:
        every option it distinguishes is the same option to the pipeline, so the
        pin passes forever and no panel can tell.  Returns None if no collapse.
        """
        for name, fn in (("NFC", _nfc),
                         ("NFD", lambda s: unicodedata.normalize("NFD", s)),
                         ("casefold", str.casefold),
                         ("strip-space", lambda s: s.replace(" ", "")),
                         ("strip-accent", lambda s: "".join(
                             c for c in unicodedata.normalize("NFD", s)
                             if not unicodedata.combining(c)))):
            if len({fn(l) for l in self.labels}) < len(self.labels):
                return name
        return None

    def parse(self, assertion):
        """JEV response -> probability vector over DECLARED option indices.

        Returns None — a refusal, in every case — when the assertion is a noul
        (already collapsed), when it names an option outside the closed set, or
        when a `score` legend maps two level indices onto the same label (two
        levels silently merged into one, which is real: it happens when a level
        list has the same string pasted into it twice, and it loses data with no
        error at all).
        """
        if not isinstance(assertion, dict):
            return None
        probs = assertion.get("probabilities")
        if not probs:
            return None                                    # noul, or no distribution
        if "legend" in assertion:                         # `score`: keys are indices
            legend = assertion["legend"]
            targets = [legend.get(k, k) for k in probs]
            if len(set(targets)) != len(targets):          # legend collapsed levels
                return None
            probs = dict(zip(targets, probs.values()))
        vec = [0.0] * len(self.labels)
        seen = set()
        for label, value in probs.items():
            idx = self._index.get(label)                  # byte-exact
            if idx is None:                               # option outside the set
                return None
            if idx in seen:                               # silent collision
                return None
            seen.add(idx)
            vec[idx] = float(value)
        total = sum(vec)
        if total <= 0:
            return None
        return [v / total for v in vec]                    # never a scalar, always a vector


def n_witness(vectors):
    """Effective independent witnesses behind an agreed-on value.

    Residuals around the consensus, then the participation ratio of the residual
    spectrum.  M identical members -> rank 0 -> 1 witness.  M members each
    carrying information the others lack -> M witnesses.
    """
    stack = np.asarray(vectors, dtype=float)               # M x K
    residual = stack - stack.mean(axis=0, keepdims=True)
    sv = np.linalg.svd(residual, compute_uv=False)
    m, n_opts = stack.shape
    ceiling = min(max(m - 1, 1), n_opts - 1)   # rows sum to zero -> rank <= M-1
    if sv.sum() <= 1e-12:
        return 1.0, np.array([]), ceiling                  # rank 0: unanimous
    return float(sv.sum() ** 2 / (sv ** 2).sum()), sv, ceiling


def panel_green(vectors, pin):
    """Does any member assert the pinned option?  A max over members, not a mean:
    the canary fires on one honest witness, which is what a canary is for."""
    return any(pin == max(range(len(v)), key=lambda i: v[i]) for v in vectors)


def verdict(canary, assertions, k=K):
    """The only place n_witness is consulted.  Note where it is NOT: the red path."""
    vectors = [v for v in (canary.parse(a) for a in assertions) if v is not None]
    if not vectors:
        return "EMPTY", "no usable distribution (noul-shaped, out-of-set, or colliding)"
    if not panel_green(vectors, canary.pin):
        # n_witness deliberately unread here.  Correlation cannot launder a red.
        return "VIOLATED", "no member names the pinned option; hard fail, unanimity or not"
    n, _sv, ceiling = n_witness(vectors)
    if n >= k:
        return "CONFIRMED", f"n_witness={n:.2f} >= k={k} (ceiling {ceiling})"
    return "REFUSED-CORRELATED", f"n_witness={n:.2f} < k={k} (ceiling {ceiling})"


def ci_exit(v):
    """How this verdict may be wired into CI.

    REFUSED is NOT green.  A canary that measured its own panel and declined to
    confirm is a BLOCKING state, and if a tool can be wired so that the scary
    outcome is the passing exit code, the tool has added a failure mode instead
    of removing one.  There is no configuration here in which any non-CONFIRMED
    verdict returns 0.
    """
    return {"CONFIRMED": 0, "REFUSED-CORRELATED": 1, "EMPTY": 1, "VIOLATED": 2}[v]


def show(title, canary, assertions, k=K):
    v, why = verdict(canary, assertions, k)
    print(f"\n{title}")
    print(f"  verdict : {v}")
    print(f"  why     : {why}")
    vectors = [x for x in (canary.parse(a) for a in assertions) if x is not None]
    if vectors:
        n, sv, ceiling = n_witness(vectors)
        consensus = np.mean(np.asarray(vectors, dtype=float), axis=0)
        print("  per-member distributions (declared option keys, no scalar collapse):")
        for i, vec in enumerate(vectors):
            dist = " ".join(f"[{j}]{nm_!r}={x:.2f}"
                            for j, (nm_, x) in enumerate(zip(canary.labels, vec)) if x)
            print(f"    m{i}: {dist}")
        print("  consensus         : " + " ".join(
            f"[{j}]{nm_!r}={x:.2f}" for j, (nm_, x) in enumerate(zip(canary.labels, consensus)) if x))
        print(f"  residual spectrum : "
              f"{np.array2string(sv, precision=3) if sv.size else '[] (rank 0)'}"
              f"   ceiling={ceiling}  n_witness={n:.2f}")
    return v
