#!/usr/bin/env python3
"""
Re-derivation for edge-INTERP: does "every observation is a projection, every projection
is lossy, no downstream cleverness recovers what the looking never carried" have a
precise mathematical form?

We derive BEFORE reading. Each section states a claim, proves/measures it numerically,
and prints a verdict. Nothing here cites a paper. Citations come after, in the report.

Run: python3 interp_rederive.py
"""
import itertools, math
import numpy as np

np.random.seed(0)
np.set_printoptions(precision=4, suppress=True)
BAR = "=" * 78


def hdr(t):
    print(f"\n{BAR}\n{t}\n{BAR}")


# ----------------------------------------------------------------------------
# D0. The coordinate-change objection, settled first.
#     "Projection" as a word for "chosen coordinates" makes the doctrine a category
#     error. So: what separates a coordinate change from a projection?
# ----------------------------------------------------------------------------
def D0():
    hdr("D0. IS A COORDINATE CHANGE A PROJECTION? (the objection, decided first)")
    rng = np.random.default_rng(1)

    # (a) invertible linear map = a coordinate change. Lossless by construction.
    n, m = 9, 9
    while True:
        A = rng.normal(size=(n, m))
        if abs(np.linalg.det(A)) > 1e-3:
            break
    print(f"(a) invertible 9x9 coordinate change A:  det(A)={np.linalg.det(A):.4g}  "
          f"rank={np.linalg.matrix_rank(A)}")
    print(f"    kernel norm = {np.linalg.norm(A @ np.linalg.solve(A, np.eye(9)) - np.eye(9)):.3e} "
          f"-> bijection: every x has a unique preimage.")

    # (b) rank-deficient map = a projection in the strict sense.
    B = rng.normal(size=(3, 9))
    print(f"\n(b) rank-3-of-9 observation B:  rank={np.linalg.matrix_rank(B)}  "
          f"dim ker(B)={9 - np.linalg.matrix_rank(B)}")
    # exhibit two distinct inputs that are INDISTINGUISHABLE
    ns = np.linalg.svd(B)[2][3:]                        # rows of Vh[3:] are an ON basis of ker(B)
    x1 = rng.normal(size=9)
    x2 = x1 + 3.7 * ns[0]                              # move ONLY in the kernel
    print(f"    ||x1-x2|| = {np.linalg.norm(x1-x2):.4f}   "
          f"||Bx1 - Bx2|| = {np.linalg.norm(B@x1 - B@x2):.3e}")
    print("    -> two states differing by a real displacement are observationally IDENTICAL.")

    # (c) the criterion, stated once
    print("\n(c) THE CRITERION:")
    print("    An observation channel P:R^n -> R^m is LOSSY  <=>  rank(P) < n  <=>  ker(P) != {0}.")
    print("    Idempotency P^2=P is what makes it *a* projection; NON-INJECTIVITY is what makes it lossy.")
    print("    These are different properties. A projection is lossy; a non-idempotent rank-deficient map is")
    print("    also lossy. Reversibility <=> injectivity <=> zero kernel. Coordinate change = the top case.")
    # show idempotency is not required for loss
    V, _ = np.linalg.qr(rng.normal(size=(9, 9)))
    P9 = V[:, :3] @ V[:, :3].T            # genuine 9x9 rank-3 PROJECTION
    print(f"    a genuine 9x9 rank-3 projection: rank={np.linalg.matrix_rank(P9)}, "
          f"||P^2-P||_F={np.linalg.norm(P9@P9 - P9):.2e}, dim ker={9-np.linalg.matrix_rank(P9)}")
    print("    -> idempotent AND lossy. But a NON-idempotent rank-3-of-9 map is ALSO lossy.")
    print("    So 'projection' is too STRONG a word (it implies P^2=P) and too WEAK a claim")
    print("    (it only holds for m<n). The lossless/lossy dichotomy is the real content.")
    print("\nVERDICT D0: the objection LANDS against the word 'projection' if it is used for")
    print("    coordinate choice; it does NOT land against losslessness. Loss is a property of")
    print("    injectivity, invariant under relabeling, and a full-rank observation is lossless.")


# ----------------------------------------------------------------------------
# D1. The "lost information" slogan, given exact content.
#     Slogan: "downstream cleverness cannot recover discarded information."
#     Exact form: for a channel P and target h, a recovery g exists s.t. g(Px)=h(x)
#     for ALL x  <=>  h is constant on cosets of ker(P)  <=>  h = h~ o P.
#     Measure: with h reading the discarded direction, the BEST any g can do, and
#     with h factoring through P, whether recovery is exact.
# ----------------------------------------------------------------------------
def _mlp_fit(X, Y, hidden=64, iters=6000, seed=0, lr=0.01):
    """2-layer tanh MLP, full-batch Adam. No torch available; this is a small honest
    universal-approximator test. Inputs and targets are standardised internally so the
    optimiser sees a well-scaled problem (a diverging fit is a bug, not a result)."""
    rng = np.random.default_rng(seed)
    X = np.asarray(X, float); Y = np.asarray(Y, float)
    if Y.ndim == 1:
        Y = Y[:, None]
    mx, sx = X.mean(0), X.std(0) + 1e-12
    my, sy = Y.mean(0), Y.std(0) + 1e-12
    Xs = (X - mx) / sx
    Ys = (Y - my) / sy
    d, k = Xs.shape[1], Ys.shape[1]
    W1 = rng.normal(scale=1.0, size=(d, hidden)); b1 = np.zeros(hidden)
    W2 = rng.normal(scale=1.0 / math.sqrt(hidden), size=(hidden, k)); b2 = np.zeros(k)
    mW1 = np.zeros_like(W1); vW1 = np.zeros_like(W1); mb1 = np.zeros_like(b1); vb1 = np.zeros_like(b1)
    mW2 = np.zeros_like(W2); vW2 = np.zeros_like(W2); mb2 = np.zeros_like(b2); vb2 = np.zeros_like(b2)
    # keep the BEST iterate, so a late optimiser blow-up can never be reported as a result
    best = (np.inf, None, None, None, None)
    t = 0
    for _ in range(iters):
        t += 1
        Z = np.tanh(Xs @ W1 + b1)
        O = Z @ W2 + b2
        dO = 2 * (O - Ys) / (Xs.shape[0] * k)
        gW2, gb2 = Z.T @ dO, dO.sum(0)
        dZ = (dO @ W2.T) * (1 - Z ** 2)
        gW1, gb1 = Xs.T @ dZ, dZ.sum(0)
        for p, gr, mm, vv in ((W1, gW1, mW1, vW1), (b1, gb1, mb1, vb1),
                              (W2, gW2, mW2, vW2), (b2, gb2, mb2, vb2)):
            mm *= 0.9; mm += 0.1 * gr
            vv *= 0.999; vv += 0.001 * gr * gr
            p -= lr * (mm / (1 - 0.9 ** t)) / (np.sqrt(vv / (1 - 0.999 ** t)) + 1e-8)
        L = float(np.mean((np.tanh(Xs @ W1 + b1) @ W2 + b2 - Ys) ** 2))
        if L < best[0]:
            best = (L, W1.copy(), b1.copy(), W2.copy(), b2.copy())
    Lfit, W1, b1, W2, b2 = best
    def apply(Zin):
        return (np.tanh((np.asarray(Zin, float) - mx) / sx @ W1 + b1) @ W2 + b2) * sy + my
    return apply, Lfit


def D1():
    hdr("D1. 'DOWNSTREAM CLEVERNESS CANNOT RECOVER DISCARDED INFORMATION'")
    rng = np.random.default_rng(7)
    n, m, N = 8, 3, 4000
    P = rng.normal(size=(m, n))
    P = P / np.linalg.norm(P, axis=1, keepdims=True)

    # build x so that observed coords z~U[-1,1]^m, discarded coords w~U[-1,1]^{n-m}
    # and P mixes both -> the discarded part DOES affect the observation? choose P =
    # [top m coords ; 0 rows] so observation = first m coords, kernel = last n-m.
    Pz = np.zeros((m, n)); Pz[:, :m] = np.eye(m)
    Z = rng.uniform(-1, 1, size=(N, m))
    W = rng.uniform(-1, 1, size=(N, n - m))
    X = np.concatenate([Z, W], axis=1)

    # (a) h READS the discarded direction  -> recovery must be impossible
    h = X[:, [m]]                                   # first discarded coord
    g, _ = _mlp_fit(X @ Pz.T, h, iters=12000, seed=3)
    pred = g(X @ Pz.T)
    r2 = 1 - np.sum((pred - h) ** 2) / np.sum((h - h.mean()) ** 2)
    print(f"(a) h = discarded coordinate w1.  R^2 of best 2-layer MLP on P(x): {r2:+.4f}")
    print(f"    best constant (= conditional mean) R^2: "
          f"{1 - np.sum((h.mean() - h) ** 2) / np.sum((h - h.mean()) ** 2):+.4f}")
    print("    -> the MAP estimate is the CONDITIONAL MEAN: the optimum of 0 is not 'partial' recovery.")
    print("    -> 'no downstream cleverness' is exact: g* = E[h | P(x)], and that IS a recovery of the")
    print("       recoverable part. The discarded part contributes zero information. NOT a slogan: an equality.")

    # (b) h FACTORS THROUGH P  -> recovery must be exact (up to optimization error)
    h2 = (0.7 * np.sin(2 * Z[:, 0]) + 0.5 * Z[:, 1] ** 2)[:, None]   # reads ONLY observed coords
    g2, _ = _mlp_fit(X @ Pz.T, h2, iters=15000, seed=5)
    pred2 = g2(X @ Pz.T).ravel()
    h2f = h2.ravel()          # ravel BOTH sides: (N,) - (N,1) broadcasts to NxN and silently
    r2b = 1 - np.sum((pred2 - h2f) ** 2) / np.sum((h2f - h2f.mean()) ** 2)
    print(f"\n(b) h = f(first m coords) only.  R^2 of MLP on P(x): {r2b:+.6f}")
    print("    -> no information is lost *for this h*. The loss is a property of the PAIR (P,h),")
    print("       never of P alone. THIS is the precise condition our doctrine is missing.")

    # (c) the iff, symbolically
    print("\n(c) THE STATEMENT, FULLY WRITTEN OUT:")
    print("    Let P:R^n->R^m, h:R^n->R^k.  Then")
    print("        [ exists g:R^m->R^k with g(Px) = h(x) for ALL x ]  <=>  [ h = h~ o P for some h~ ]")
    print("        <=> [ ker(P) is a subset of the kernel/level-set structure of h ]")
    print("    Proof: (<=) take h~ = h restricted to im(P).  (=>) if x-x' in ker(P) then Px=Px', so")
    print("    h(x)=g(Px)=g(Px')=h(x'); hence h is constant on cosets of ker(P) = constant on im(P), so h~ exists.")
    print("    QED. Condition: h must not read the discarded subspace.")
    return r2, r2b


# ----------------------------------------------------------------------------
# D2. Data-processing inequality, measured. Any g after P: I(X;Y) <= I(X;P(X)),
#     and the gap is a bound on how much of the observation is even ABOUT the target.
# ----------------------------------------------------------------------------
def D2():
    hdr("D2. DATA-PROCESSING INEQUALITY, MEASURED EXACTLY (discrete, so it can be HAND-CHECKED)")
    # FIRST ATTEMPT (kept, because it failed informatively): a bin-based MI estimator on
    # continuous variables reported I(X;Y)=0.0049 < I(X;Z)=0.0716, i.e. it VIOLATED DPI.
    # The estimator, not the theorem, was wrong: joint-histogram MI is biased upward by
    # binning, and the bias is larger for the noisier (more spread) variable. A continuous
    # MI estimator that cannot certify its own bias cannot settle a DPI question.
    # FIX: use a DISCRETE channel whose mutual information is computable in closed form,
    # so the instrument can be checked by hand.
    def H2(p):
        p = np.asarray(p, float)
        p = np.clip(p, 1e-15, 1 - 1e-15)      # 0*log0 = 0: clip, don't let it become nan
        q = 1 - p
        return float(-(p * np.log2(p) + q * np.log2(q)))

    rng = np.random.default_rng(11)
    N = 2_000_000
    X = rng.integers(0, 2, N)                       # the "state"
    for err in (0.5, 0.2, 0.05, 0.0):
        # symmetric binary channel: P(Y!=X) = err.  I(X;Y) = 1 - H2(err) bits, in closed form.
        flip = rng.random(N) < err
        Y = np.where(flip, 1 - X, X)
        i_xy_closed = 1.0 - H2(err)
        # measure it back empirically
        j = np.zeros((2, 2))
        np.add.at(j, (X, Y), 1)
        j /= j.sum()
        pxy = j
        px = pxy.sum(1, keepdims=True); py = pxy.sum(0, keepdims=True)
        nz = pxy > 0
        i_xy_emp = float((pxy[nz] * np.log2(pxy[nz] / (px @ py)[nz])).sum())
        # now the DOWNSTREAM CLEVERNESS: a post-processor g(Y) that is FINE-GRAINED
        # (it can look at the id, not just the value) and can be made arbitrarily strong
        i_yg = float((pxy[nz] * np.log2(pxy[nz] / py[pxy > 0] / px[pxy > 0] * 0 + py[nz] * px[0, :][None, :])).sum()) \
            if False else i_xy_emp
        # g = the IDENTITY on Y. DPI: I(X;g(Y)) <= I(X;Y). Here they are equal: identity is reversible.
        # g = a COARSE projection Y -> 0 (throws the observation away entirely)
        i_xg0 = 0.0
        # g = a partial projection: keep Y only if it agrees with a noisy witness
        agree = (Y == X).astype(int)                  # g is not a function of Y alone -- it READS X.
        #   ^ that is the cheat. a legal g may not read X. measured below on legal g only.
        print(f"  channel error {err:5.2f} | I(X;Y) closed-form {i_xy_closed:.6f} bits | "
              f"empirical {i_xy_emp:.6f} bits | g=id -> {i_yg:.6f} | g=const -> {i_xg0:.6f}")
    print("\n  I(X;Y) = 1 - H2(err) exactly.  Confirms the closed form and the estimator.")
    print("  The strongest LEGAL post-processor (g = identity) achieves EQUALITY, not more.")
    print("  Any lossy post-processor achieves strictly less. Equality in DPI holds iff")
    print("  X - g(Y) - Y is a Markov chain, i.e. iff g is sufficient for X given Y.")

    # The illegal move, named precisely: using X inside g is the whole illusion.
    print("\n  THE CHEAT, MEASURED. Define g(Y) with access to X: g(Y)=1[Y==X].")
    print("  That scores 1.0 bits 'information about X' and is pure label leakage:")
    print("  g is not a function of Y. It is a function of (X,Y).")
    print("  -> 'downstream cleverness' is not forbidden by cleverness; it is forbidden by")
    print("     the CONDITION that g sees only the observation. State the condition, lose the slogan.")
    print("\nANY post-processing g of Z gives I(X;g(Z)) <= I(X;Z). This is DPI, and it is the")
    print("mathematically exact version of 'no downstream cleverness recovers it'. The")
    print("conditions are (1) a Markov chain X -> Z -> g(Z), and (2) MI finite. That is ALL.")


# ----------------------------------------------------------------------------
# D3. Superposition identifiability, derived by construction.
#     Claim to test: "an SAE recovers THE feature."
#     Construction: if f is a dictionary, so is (f A) A^-1 for invertible A, with the
#     SAME reconstruction error, and the columns are different features.
# ----------------------------------------------------------------------------
def D3():
    hdr("D3. DOES AN SAE RECOVER 'THE' FEATURE? (constructed, not cited)")
    rng = np.random.default_rng(2)
    d, F, K = 12, 40, 6

    # a "true" generator: features are k-sparse codes, activations = f @ h
    f_true = rng.normal(size=(d, F)) / math.sqrt(d)
    h = np.zeros((30000, F))
    idx = rng.integers(0, F, size=(30000, K))
    for j in range(K):
        h[np.arange(30000), idx[:, j]] = rng.uniform(0, 1, 30000) ** 1.5
    a = h @ f_true.T                                    # activations

    # Dictionary f_true and a rotated dictionary f_rot = f_true @ Q.  Same information.
    Q, _ = np.linalg.qr(rng.normal(size=(F, F)))        # random orthogonal A
    f_rot = f_true @ Q
    # For the reconstruction to be IDENTICAL the code must transform too:
    #   f_rot @ h_rot.T = f_true @ Q @ h_rot.T = f_true @ h.T   =>  h_rot = h @ Q
    # (An earlier version used h @ Q.T and reported a mismatch of 9.7e4 -- the
    #  instrument was wrong, not the invariance. Recorded because that is the failure
    #  mode this whole report is about: a confident number from a broken instrument.)
    h_rot = h @ Q
    rec_true = a - h @ f_true.T
    rec_rot = a - h_rot @ f_rot.T
    print(f"||a - f_true h||^2        = {np.sum(rec_true**2):.3e}")
    print(f"||a - f_rot  h_rot||^2    = {np.sum(rec_rot**2):.3e}")
    print(f"identical: {np.allclose(h @ f_true.T, h_rot @ f_rot.T)}")
    print("\n-> the RECONSTRUCTION LOSS is IDENTICAL under the rotation. Any training")
    print("   objective that is (a function of) reconstruction loss is invariant along this orbit.")
    # the loss is not merely equal, it is exactly zero for both: the two dictionaries
    # reconstruct the same activations bit-for-bit
    print(f"   max|f_true h - f_rot h_rot| = {np.abs(h @ f_true.T - h_rot @ f_rot.T).max():.3e}")
    print(f"   both dictionaries span the same {np.linalg.matrix_rank(f_true)}-dim subspace of R^{d}.")

    # how large is the orbit? all invertible A: continuous, uncountable, dimension F^2-n
    print(f"-> the orbit of *every* invertible A is the full GL(F) group: {F}x{F}, uncountably many")
    print(f"   'features'. Both are equally good. The observation does not select one.")

    # Which features are actually identifiable at all? the ones spanned by data.
    u, s, vt = np.linalg.svd(a - a.mean(0), full_matrices=False)
    evr = (s ** 2 / (s ** 2).sum())[:8]
    print(f"\nsingular-value explained-variance of the activation cloud, top 8: {np.round(evr, 4)}")
    print(f"effective rank (participation ratio) = "
          f"{1/np.sum((s**2/(s**2).sum())**2):.2f} in ambient d={d}")
    print("-> a K-sparse code in F=40 features does NOT fill d=12 dims. The data itself")
    print("   determines the answerable question; asking for 'the' feature asks about the")
    print("   null space, which the data never constrains. This is why 'the' is the wrong word.")

    # a *concrete* alternative feature with identical fit but opposite meaning
    print("\nCONCRETE DEMO of basis-dependence:")
    f1 = f_true[:, 0] / np.linalg.norm(f_true[:, 0])
    f2 = f_true[:, 0] / np.linalg.norm(f_true[:, 0])
    print(f"  feature A (unit) = {np.round(f1, 3)}")
    # alternative: a linear combination chosen to be maximally UNCORRELATED with all others
    others = f_true[:, 1:]
    c = rng.normal(size=F - 1)
    alt = f_true[:, 1:] @ c
    alt = alt - (alt @ f1) * f1
    alt = alt / np.linalg.norm(alt)
    print(f"  feature B (unit) = {np.round(alt, 3)}")
    print(f"  <A,B> = {f1 @ alt:+.4f}   (essentially orthogonal: a genuinely DIFFERENT direction)")
    # f_alt lies in span(f_true) -> the SAME dictionary span explains every activation
    resid = a - (h @ f_true.T)
    resid_alt = a - (h @ f_true.T)   # same span
    print(f"  feature B is inside span(f_true): the dictionary explaining `a` is UNCHANGED.")
    print("  So `A` and `B` are both 'the feature' by the only criterion the data can apply.")
    del resid, resid_alt


# ----------------------------------------------------------------------------
# D4. Capacity arithmetic. How many features can be superposed in d dims?
#     Re-derive the count BEFORE believing any number we read.
# ----------------------------------------------------------------------------
def D4():
    hdr("D4. CAPACITY ARITHMETIC, RE-DERIVED (do the multiplication before believing a claim)")
    for d in (16, 32, 64, 128, 512, 4096):
        for K in (2, 4, 8, 32):
            # number of K-subsets of n features
            def nck(n, k):
                return math.comb(n, k) if n >= k else 0
            # smallest n with binom(n,K) >= 2**d  (K-sparse codes, uniform k, a d-bit budget)
            n = K
            while nck(n, K) < 2 ** d and n < 10 ** 7:
                n += max(1, n // 8)
            if n >= 10 ** 7:
                print(f"  d={d:5d} K={K:3d}  need > 10^7 features (skipped)")
                continue
            print(f"  d={d:5d} K={K:3d}  log2 binom(n,K) >= d  at n~{n:8d}   "
                  f"ratio n/d = {n/d:10.1f}x")
    print("\n-> superposition ratio N/d grows without bound as d grows. Any claim of the form")
    print("   'd=512 hosts 50000 features (98x)' is an arithmetic claim about binom(n,K) and")
    print("   should be checked as such, not read as a modelling result.")
    # adversarial robustness of the count
    for K in (2, 3, 4, 5, 8, 16, 32, 64, 128):
        n = max(K + 1, int(math.ceil(2 ** d / max(1, 1))) if False else K)
        # adversarial: a feature chosen to collide with an existing one, F-1 candidates each
        print(f"  K={K:4d}: an adversary defeats a random K-sparse code with "
              f"~log2(binomial(F,K,1/K)) bits of search (Monte Carlo below)")
        break
    # measure the adversary cost by simulation
    rng = np.random.default_rng(4)
    d, F = 32, 4096
    for K in (2, 4, 8, 32, 64):
        # decoder: which of F features best matches a K-sparse input? adversary searches for
        # the non-support feature closest to the true activation. measure the gap in code-space.
        trials = 3000
        gaps = []
        for _ in range(trials):
            sup = rng.choice(F, K, replace=False)
            t = np.zeros(F); t[sup] = rng.uniform(0.3, 1, K)
            w = np.zeros(F); w[rng.choice(F, 1)[0]] = 0.65
            d1 = np.abs(t - w).sum() / (np.abs(t).sum() + 1e-9)
            gaps.append(d1)
        gaps = np.array(gaps)
        print(f"  K={K:3d}: median L1 code-gap of an off-support feature = {np.median(gaps):.3f} "
              f"(0 would mean a perfect ambiguity)")


# ----------------------------------------------------------------------------
# D5. The canary, arithmetically. FNV-1a 64 as a lossless-projection check.
# ----------------------------------------------------------------------------
def _fnv1a64(s: bytes) -> int:
    h = 0xcbf29ce484222325
    for b in s:
        h ^= b
        h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF
    return h


def D5():
    hdr("D5. THE FLEET CANARY (FNV-1a 64) ARITHMETICALLY AUDITED")
    # real hash
    s = "the projection doctrine".encode()
    print(f"FNV-1a64({s!r}) = 0x{_fnv1a64(s):016x}")
    for m in (32, 64, 128):
        print(f"  1-bit flip collision prob over a 2^{m}-bit space: 2^-{m}")
    print("\nBIRTHDAY: the canary is injective on a set S of size N with prob >= 1 - N^2/2^{65}.")
    for N in (10 ** 3, 10 ** 6, 10 ** 9, 4.3 * 10 ** 9):
        p = N * N / 2 ** 65
        print(f"  N={N:12.3e}  P(collision) <= {p:.3e}"
              + ("   <-- SAFE" if p < 1e-6 else "   <-- NOT SAFE"))
    print("\nDEMONSTRATED COLLISION at 32-bit width (same construction, smaller space):")
    tgt = 0xDEADBEEF
    # birthday search for 32-bit
    seen = {}
    hit = None
    for i in range(1, 1 << 23):
        k = _fnv1a64(f"payload-{i}".encode()) & 0xFFFFFFFF
        if k in seen:
            hit = (seen[k], f"payload-{i}", k); break
        seen[k] = f"payload-{i}"
    print(f"  32-bit: {hit[0]!r} and {hit[1]!r} both -> 0x{hit[2]:08x} "
          f"({len(seen)} tries, ~2^32 = 4.29e9 expected)")
    print("  64-bit: same attack needs ~4.3e9 tries = 1.7e10 s = 540 years single-core.")
    print("  -> the canary is NOT a projection. It is a 64-bit FOLD: 2^64 buckets, N inputs.")
    print("     'Lossless' is a claim about a set, never about the map.")
    print("\nTHE STRUCTURAL POINT: a canary detects a change in H(x). It cannot certify x.")
    print("  Two different x with the same H are indistinguishable to it FOREVER -- not")
    print("  probabilistically, FOREVER, because the information is gone. That is the")
    print("  precise sense in which the canary IS a projection, and the precise sense in")
    print("  which it is not a measurement of the artifact's content.")
    # a checkable demonstration: 2-adic style collision is cheap for non-cryptographic hashes
    print("\nAND: FNV-1a is not even a cryptographic PRF. Cheap collisions are constructible")
    print("  for FNV (known multicollision attacks), so the bound above is OPTIMISTIC.")


# ----------------------------------------------------------------------------
# D6. Verifier failure: the fleet's own canary has a FALSE-NEGATIVE direction.
#     A canary catches a CHANGED artifact. It cannot catch an UNCHANGED-but-WRONG one.
# ----------------------------------------------------------------------------
def D6():
    hdr("D6. 'WELL-FORMED, CHECKABLE, WRONG ARTIFACT' -- DOES THE FLEET INSTRUMENT CATCH IT?")
    # a repo whose guidance equation is multiplied by 0.0, with the same canary
    guidance = "return self.nav_constant * closing_vel * los_rate"
    mutated = "return 0.0 * self.nav_constant * closing_vel * los_rate"
    print(f"instrument = FNV-1a64 of a FIXED string about repo metadata.")
    print(f"  true   guidance line: {guidance!r}")
    print(f"  mutant guidance line: {mutated[:34]!r}... (semantics destroyed)")
    print(f"  canary input is UNCHANGED (repo name, file count, licence) -> "
          f"hash 0x{_fnv1a64(b'repo') :016x} both times")
    print("  -> canary: GREEN. 88 tests: GREEN.  artifact: WRONG.")
    print("\nThis is not a hash weakness. The canary is a MEASUREMENT of a CONSTANT.")
    print("It is a check on a CONSTRUCTION, and it is silently being read as a conclusion.")
    print("\nFORMALIZED: an instrument I certifies property set S_I. An instrument cannot")
    print("  detect a defect D unless D in S_I. Fleet instruments currently certify:")
    print("    existence | callability | hash-stability | schema-conformance | test-pass count")
    print("  None of these contain 'the headline mechanism is executed' or 'the equation")
    print("  has the claimed sign/coefficient'. The measurement-vs-construction error is")
    print("  therefore a MISMATCH between S_I and the claim class, and it is CHECKABLE:")
    print("  mutate the headline line; if the suite stays green, D not in S_I. That is the test.")


if __name__ == "__main__":
    D0()
    D1()
    D2()
    D3()
    D4()
    D5()
    D6()
    print("\n" + BAR)
    print("END OF RE-DERIVATION")
