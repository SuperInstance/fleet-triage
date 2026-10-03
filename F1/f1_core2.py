"""
f1_core2.py -- the parts that need care: correlated-sample error bars,
the d-dimensional geometry factor, and the fixed-point structure of the
F2 (overdominance) potential.

Split out because these are the three places the paper is most likely
to be wrong and where a sloppy estimator would hide the error.
"""
import math
import random


# ----------------------------------------------------------------------
# An honest variance estimator for a strongly autocorrelated process.
# Batch means: split the series into B blocks, compute the variance of
# each block, and report the spread.  For an AR(1) with correlation time
# tau, Var_hat of a naive estimator has std dev ~ sqrt(2*tau/T) -- at
# N=256, tau=1/k, the naive estimator is useless.
# ----------------------------------------------------------------------

def ou_mc(sigma=1.0, k=0.5, dt=1e-3, steps=2000000, batches=40, seed=3):
    rng = random.Random(seed)
    x = 0.0
    burn = steps // 10
    bl = (steps - burn) // batches
    means, sqs, cnts = [0.0] * batches, [0.0] * batches, [0] * batches
    b = 0
    idx = 0
    npost = steps - burn
    tot = 0
    tot2 = 0
    for t in range(steps):
        x += -k * dt * x + sigma * math.sqrt(dt) * rng.gauss(0, 1)
        if t >= burn:
            means[b] += x
            sqs[b] += x * x
            cnts[b] += 1
            tot += x
            tot2 += x * x
            idx += 1
            if idx * batches // npost > b:
                b = idx * batches // npost
    n = npost
    naive = tot2 / n - (tot / n) ** 2
    bm = [sqs[i] / cnts[i] - (means[i] / cnts[i]) ** 2 for i in range(batches)]
    gmean = sum(bm) / batches
    gvar = sum((v - gmean) ** 2 for v in bm) / (batches - 1)
    se = math.sqrt(gvar / batches)
    exact = sigma * sigma * dt / (1.0 - (1.0 - k * dt) ** 2)
    return {
        "k": k, "sigma": sigma, "dt": dt,
        "batch_means_var": gmean,
        "batch_means_stderr": se,
        "exact_discrete": exact,
        "continuous_sigma2_2k": sigma * sigma / (2.0 * k),
        "z_score_vs_exact": (gmean - exact) / se if se > 0 else None,
        "naive_var": naive,
        "tau_correlation_steps": 1.0 / (k * dt),
    }


# ----------------------------------------------------------------------
# d-DIMENSIONAL GEOMETRY FACTOR.
#
# Periodic box, d dims, N^d cells, unit spacing.
# Laplacian eigenvalues:  -q^2,  q^2 = sum_a 4 sin^2(pi m_a / N).
# Mode m is an independent OU with rate lambda_m = k + D q_m^2.
#   V_mode(m)  = sigma^2 / (2 (k + D q_m^2))
#   V_field    = sum_m V_mode(m)                       (Parseval)
# Paper:  V_field = sigma^2/(2k).   Ratio = G(k, D, N, d).
# ----------------------------------------------------------------------

def V_field(sigma, k, D, N, d=1):
    tot = 0.0
    if d == 1:
        for m in range(N):
            q2 = 4.0 * math.sin(math.pi * m / N) ** 2
            tot += sigma * sigma / (2.0 * (k + D * q2))
    elif d == 2:
        q2a = [4.0 * math.sin(math.pi * m / N) ** 2 for m in range(N)]
        for a in range(N):
            for b in range(N):
                tot += sigma * sigma / (2.0 * (k + D * (q2a[a] + q2a[b])))
    else:
        raise ValueError("d in (1,2)")
    return tot


def geometry(k, D, N, d, sigma=1.0):
    return V_field(sigma, k, D, N, d) / (sigma * sigma / (2.0 * k))


def scan(d, N, rks, D=1.0):
    qmin2 = 4.0 * math.sin(math.pi / N) ** 2
    qmax2 = 4.0 if d == 1 else 8.0
    rows = []
    for rk in rks:
        k = D * rk
        g = geometry(k, D, N, d)
        rows.append({
            "d": d, "N": N, "k_over_D": rk,
            "V_field": V_field(1.0, k, D, N, d),
            "paper_sigma2_2k": 1.0 / (2.0 * k),
            "geometry_factor": g,
            "regime": ("IR-limited  (k << D q_min^2)" if k < 0.1 * D * qmin2
                       else "paper regime (k >> D q_max^2)" if k > 10 * D * qmax2
                       else "crossover"),
        })
    return rows


def loglog_slope(lo, hi, D, N, d, p=14):
    ks = [lo * (hi / lo) ** (i / (p - 1)) for i in range(p)]
    xs = [math.log(k) for k in ks]
    ys = [math.log(V_field(1.0, k, D, N, d)) for k in ks]
    mx, my = sum(xs) / p, sum(ys) / p
    return (sum((xs[i] - mx) * (ys[i] - my) for i in range(p))
            / sum((xs[i] - mx) ** 2 for i in range(p)))


def k_crit(D, N, d=1):
    """Below this k the plateau stops depending on k at all."""
    return D * 4.0 * math.sin(math.pi / N) ** 2


# ----------------------------------------------------------------------
# F2 / OVERDOMINANCE.  The paper models F2 as additive noise in a UNIMODAL
# potential with a linear restoring force.  F2's 1:2:1 is the opposite:
# a BIMODAL potential whose interior point is a SADDLE, not an attractor.
# ----------------------------------------------------------------------

def wf_map(p, wAA, wAa, waa):
    q = 1.0 - p
    wbar = p * p * wAA + 2 * p * q * wAa + q * q * waa
    return (p * p * wAA + p * q * wAa) / wbar


def fixed_points_and_stability(wAA, wAa, waa, lo=1e-9, hi=1 - 1e-9, n=20001):
    """Sign-change scan for fixed points of the single-locus WF map,
    plus |f'(p)| at each."""
    fps = []
    h = (hi - lo) / (n - 1)
    prev_p = lo
    prev_f = wf_map(prev_p, wAA, wAa, waa) - prev_p
    for i in range(1, n):
        p = lo + i * h
        f = wf_map(p, wAA, wAa, waa) - p
        if f == 0.0 or (f < 0) != (prev_f < 0):
            # bisect
            a, b, fa = prev_p, p, prev_f
            for _ in range(80):
                m = 0.5 * (a + b)
                fm = wf_map(m, wAA, wAa, waa) - m
                if (fm < 0) == (fa < 0):
                    a, fa = m, fm
                else:
                    b = m
            r = 0.5 * (a + b)
            d = 1e-7
            der = ((wf_map(r + d, wAA, wAa, waa) - wf_map(r - d, wAA, wAa, waa))
                   / (2 * d))
            fps.append({"p*": r, "abs_f_prime": abs(der),
                        "type": "attracting" if abs(der) < 1 else "repelling"})
        prev_p, prev_f = p, f
    return fps


def f2_from_f1(wAA, wAa, waa, gens=60):
    """F1 cross gives p = 1/2 (or whatever the two parental alleles force).
    Then F2 = random mating of F1s.  Watch the allele frequency."""
    p = 0.5
    traj = [p]
    for _ in range(gens):
        p = wf_map(p, wAA, wAa, waa)
        traj.append(p)
    return traj
