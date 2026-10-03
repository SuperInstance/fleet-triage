"""
f1_core.py -- exact checks for docs/F1-F2-DIFFUSION.md.

Pure stdlib. No numpy, no scipy. Everything here is either
  (a) an exact algebraic identity, or
  (b) a closed form I derived by hand, or
  (c) a hand-rolled exact linear-algebra result (diagonalised Laplacian).

These are the reference values the Monte-Carlo sims are checked against.
If a sim disagrees with a number in this file, the sim is wrong
(or the paper is wrong -- which is the point).
"""
import math
import random

TAU = 2.0 * math.pi


# ----------------------------------------------------------------------
# CLAIM 1:  Var((p+q)/2) = (Var p + Var q + 2 Cov)/4
# ----------------------------------------------------------------------

def var_of_mean_of_two(vp, vq, cov):
    return (vp + vq + 2.0 * cov) / 4.0


def check_claim1():
    out = {}
    # 1a. the identity itself, by direct sampling
    rng = random.Random(7)
    n = 200000
    p = [rng.gauss(0, 1.0) for _ in range(n)]
    q = [rng.gauss(0, 1.0) for _ in range(n)]
    mp = sum(p) / n
    mq = sum(q) / n
    vp = sum((x - mp) ** 2 for x in p) / n
    vq = sum((x - mq) ** 2 for x in q) / n
    cov = sum((p[i] - mp) * (q[i] - mq) for i in range(n)) / n
    meas = sum(((p[i] + q[i]) / 2.0 - (mp + mq) / 2.0) ** 2 for i in range(n)) / n
    out["identity"] = {
        "Var_p": vp, "Var_q": vq, "Cov_pq": cov,
        "measured_Var_mean": meas,
        "predicted": var_of_mean_of_two(vp, vq, cov),
        "rel_err": abs(meas - var_of_mean_of_two(vp, vq, cov)) / meas,
    }

    # 1b. i.i.d. parents -> exactly V/2.  Verify.
    out["iid_halving"] = {"Var_0": vp, "Var_1": var_of_mean_of_two(vp, vq, 0.0),
                          "ratio": var_of_mean_of_two(vp, vq, 0.0) / vp}

    # 1c. THE F1 CASE. Parents are two FIXED, distinct pure lines; every
    #     offspring gets one allele from each.  There is no sampling and
    #     no averaging of a *population* -- the population becomes a clone.
    a, b = 0.0, 1.0                      # two homozygous lines
    f1 = [(a + b) / 2.0] * 64            # all 64 F1 individuals identical
    m = sum(f1) / len(f1)
    v = sum((x - m) ** 2 for x in f1) / len(f1)
    out["f1_actual_variance"] = v        # -> 0.0, exactly, in ONE generation
    out["f1_vs_halving_prediction"] = {"actual": v, "doc_predicts": vp / 2.0}

    # 1d. geometric law requires WITH-REPLACEMENT i.i.d. draws.
    #     Without replacement (disjoint pairing) the covariance is negative
    #     and the decay is faster; at N=2 it is total in one step.
    for N in (2, 4, 8, 64, 1024):
        c = -1.0 / (N - 1)               # Cov of two distinct draws w/o replacement
        ratio = var_of_mean_of_two(1.0, 1.0, c)
        out.setdefault("without_replacement_ratio", {})[N] = ratio
    out["with_replacement_ratio_all_N"] = 0.5

    return out


# ----------------------------------------------------------------------
# CLAIM 2a: OU stationary variance in ONE degree of freedom = sigma^2/(2k)
# ----------------------------------------------------------------------

def ou_stationary(sigma, k, dt=None):
    """Closed form.  dt=None -> continuous limit.  dt given -> exact
    discrete AR(1) stationary variance sigma^2/(2k - k^2 dt)."""
    if dt is None:
        return sigma * sigma / (2.0 * k)
    return sigma * sigma * dt / (1.0 - (1.0 - k * dt) ** 2)


def check_ou_1d(sigma=1.0, k=0.5, dt=1e-3, steps=400000, seed=11):
    """Simulate x_{t+1} = (1-k dt) x_t + sigma sqrt(dt) z  and
    time-average the variance.  Compare to the closed form."""
    rng = random.Random(seed)
    x = 0.0
    s = 0.0
    s2 = 0.0
    burn = steps // 4
    for t in range(steps):
        x += -k * dt * x + sigma * math.sqrt(dt) * rng.gauss(0, 1)
        if t >= burn:
            s += x
            s2 += x * x
    m = s / (steps - burn)
    meas = s2 / (steps - burn) - m * m
    return {
        "k": k, "sigma": sigma, "dt": dt,
        "measured": meas,
        "exact_discrete": ou_stationary(sigma, k, dt),
        "continuous_sigma2_2k": sigma * sigma / (2.0 * k),
    }


# ----------------------------------------------------------------------
# CLAIM 2b: the SAME equation on a d-dimensional lattice.
#
#   dphi/dt = D lap phi - k(phi - phi*) + sigma xi,   periodic b.c.
#
# On a periodic box the Laplacian is diagonalised by the Fourier basis, so
# mode q is an INDEPENDENT OU process with relaxation rate
#       lambda_q = k + D q^2
# (the -k(phi-phi*) term acts on every mode; there is no exempt k=0 mode).
# Stationary variance of mode q:  V_q = sigma^2 / (2 lambda_q).
#
# The FIELD variance is the sum over modes:
#       V_field = (sigma^2/2) * sum_q 1/(k + D q^2)
#
# sigma^2/(2k) is recovered ONLY if lambda_q = k for every mode, i.e. only
# if k >> D q_max^2.  Everything else is a geometry factor.
# ----------------------------------------------------------------------

def field_variance_exact(sigma, k, D, N, d=1):
    """Exact stationary field variance by summing the diagonalised modes.

    Convention: phi(x) = sum_m phi_m exp(i q_m x), Parseval gives
    (1/N^d) sum_x |phi_x|^2 = sum_m |phi_m|^2.  So V_field = sum_m V_m.
    q_m = 2 sin(pi m / N) for the d=1 unit-spacing ring Laplacian.
    """
    total = 0.0
    n_mode = 0
    for idx in _mode_indices(N, d):
        q2 = _q2(idx, N, d)
        total += sigma * sigma / (2.0 * (k + D * q2))
        n_mode += 1
    return total, n_mode


def _mode_indices(N, d):
    if d == 1:
        for m in range(-(N // 2), N - (N // 2)):
            yield (m,)
    else:
        for a in range(N):
            for b in range(N):
                yield (a, b)


def _q2(idx, N, d):
    s = 0.0
    for a in idx:
        s += 4.0 * math.sin(math.pi * a / N) ** 2
    return s


def geometry_factor(k, D, N, d=1):
    """V_field / (sigma^2 / 2k) -- the factor the paper omits."""
    V, _ = field_variance_exact(1.0, k, D, N, d)
    return V / (1.0 / (2.0 * k))


def check_geometry():
    """Scan k/D over four decades at several domain sizes, in d=1 and d=2.
    The paper's answer is a flat line at 1.0."""
    rows = []
    D = 1.0
    for d, N in ((1, 256), (1, 1024), (2, 64)):
        for rk in (1e-4, 1e-3, 1e-2, 1e-1, 1.0, 1e1, 1e2, 1e3):
            k = D * rk
            V, nmodes = field_variance_exact(1.0, k, D, N, d)
            naive = 1.0 / (2.0 * k)
            rows.append({
                "d": d, "N": N, "k_over_D": rk,
                "V_field": V,
                "paper_sigma2_2k": naive,
                "ratio": V / naive,
                "k_critical": _k_crit(D, N, d),
                "regime": ("k << D q_min^2 (IR-dominated)"
                           if k < 0.05 * D * _q_min2(N, d)
                           else "k >> D q_max^2 (paper's regime)"
                           if k > 20.0 * D * _q_max2(N, d)
                           else "crossover"),
            })
    return rows


def _q_min2(N, d):
    return 4.0 * math.sin(math.pi / N) ** 2


def _q_max2(N, d):
    if d == 1:
        return 4.0
    return 8.0


def _k_crit(D, N, d):
    return D * _q_min2(N, d)


def scaling_exponent(klo, khi, D=1.0, N=1024, d=1, p=8):
    """log-log slope of V_field vs k, by finite differences on a geometric
    ladder.  Paper predicts -1.  Single-mode predicts -1."""
    ks = [klo * (khi / klo) ** (i / (p - 1)) for i in range(p)]
    Vs = [field_variance_exact(1.0, k, D, N, d)[0] for k in ks]
    # least-squares slope on logs
    xs = [math.log(k) for k in ks]
    ys = [math.log(v) for v in Vs]
    mx = sum(xs) / p
    my = sum(ys) / p
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(p))
    den = sum((xs[i] - mx) ** 2 for i in range(p))
    return num / den


# ----------------------------------------------------------------------
# CLAIM 3: averaging is many-to-one.
# Mean is the linear projection onto span{1}; kernel = zero-sum subspace.
# That is a theorem.  What is NOT a theorem is that it is special.
# ----------------------------------------------------------------------

def projection_kernel(n, basis_seed=0):
    """Return a basis of the kernel of the mean map R^n -> R,
    plus a witness pair (e, e') with identical mean but different content."""
    rng = random.Random(basis_seed)
    ker = []
    for i in range(1, n):
        v = [1.0] * n
        v[0] = 1.0
        v[i] = -1.0
        s = sum(v)
        for j in range(n):
            v[j] -= s / n
        ker.append(v)

    # witness: two federations differing by a kernel vector
    e = [rng.gauss(0, 1) for _ in range(n)]
    w = [e[j] + ker[0][j] for j in range(n)]
    m1 = sum(e) / n
    m2 = sum(w) / n
    return {
        "kernel_dim": len(ker),
        "codomain_dim": 1,
        "rank": 1,
        "fibre_dimension": n - 1,
        "mean_e": m1, "mean_e_prime": m2,
        "mean_identical": abs(m1 - m2) < 1e-12,
        "L2_distance_between_the_two_federations": math.sqrt(
            sum((e[j] - w[j]) ** 2 for j in range(n))),
        "variance_e": sum((x - m1) ** 2 for x in e) / n,
        "variance_e_prime": sum((x - m2) ** 2 for x in w) / n,
    }


# ----------------------------------------------------------------------
# CLAIM 4: what actually collapses, and at what rate.
#
# The paper says Var_n = Var_0 * 2^(-n) for "averaging".
# There are FOUR different operators hiding under that word, with four
# different decay laws.  Here are the exact rates.
# ----------------------------------------------------------------------

def halflife_geometric(rate):
    """rate = V_{n+1}/V_n  ->  generations for V to halve."""
    return math.log(0.5) / math.log(rate)


def wright_fisher_rate(Ndip):
    """Diploid Wright-Fisher.  Heterozygosity ratio per generation:
           H_{t+1}/H_t = 2Ndip / (2Ndip + 1)
       This is the classic neutral result.  The half-life is ~1.386*2Ndip
       generations, i.e. it SCALES WITH POPULATION SIZE."""
    return 2.0 * Ndip / (2.0 * Ndip + 1.0)


def wright_fisher_stationary_var(Ndip, mu):
    """Var of allele frequency at the drift/mutation equilibrium:
           Var(p*) = mu(1-mu) / (2Ndip + 1)
       Compare the paper's sigma^2/(2k) -- unbounded in sigma."""
    return mu * (1.0 - mu) / (2.0 * Ndip + 1.0)


def wright_fisher_mutation_stationary_var(Ndip, mu, nu):
    """WF with symmetric two-way mutation rate nu.  Exact fixed point of
           Var' = (1-2nu)^2 Var + (1/(2Ndip)) (mu(1-mu) - Var)
       gives  Var* = mu(1-mu) / (1 + 2*Ndip*4*nu*(1-nu))
    i.e.  Var* = mu(1-mu) / (1 + 8 Ndip nu (1-nu)).
    THIS is the real design knob: 1/(2Ne) loss rate, nu injection rate."""
    return mu * (1.0 - mu) / (1.0 + 8.0 * Ndip * nu * (1.0 - nu))


def paper_knob(sigma, k):
    return sigma * sigma / (2.0 * k)


def compare_knobs(Ndip=256, mu=0.5):
    rows = []
    for nu in (0.0, 1e-4, 1e-3, 1e-2, 1e-1, 0.5):
        rows.append({
            "nu": nu,
            "true_WF_knob": wright_fisher_mutation_stationary_var(Ndip, mu, nu),
            "max_possible_mu(1-mu)": mu * (1.0 - mu),
        })
    return rows


def overdominance_equilibrium(mu, s):
    """F2's 1:2:1 is NOT a linear restoring force.  It is a BIMODAL
    potential:  w(AA)=1, w(Aa)=1+s, w(aa)=1.
    Allele frequency p of A,  a = w_AA, b = w_Aa, c = w_aa:
        p' = (p^2 a + p q b) / wbar
    That map has FIXED POINTS at 0 and 1 and an UNSTABLE one at the
    overdominance equilibrium; 1:2:1 is a *saddle*, not an attractor.
    So the doc's -k(phi-phi*) mean-attractor cannot represent it."""
    a, b, c = 1.0, 1.0 + s, 1.0

    def step(p):
        q = 1.0 - p
        wbar = p * p * a + 2 * p * q * b + q * q * c
        return (p * p * a + p * q * b) / wbar

    # F1 cross: p = 1/2 exactly, one individual
    p = 0.5
    traj = [p]
    for _ in range(40):
        p = step(p)
        traj.append(p)
    return {"s": s, "traj": traj, "converges_to": traj[-1]}


def if_all_results():
    return {
        "claim1": check_claim1(),
        "ou_1d": check_ou_1d(),
        "claim3_projection": projection_kernel(6),
        "wf_rates": {
            "N=32": {"rate": wright_fisher_rate(32),
                     "halflife_gen": halflife_geometric(wright_fisher_rate(32))},
            "N=256": {"rate": wright_fisher_rate(256),
                      "halflife_gen": halflife_geometric(wright_fisher_rate(256))},
            "N=4096": {"rate": wright_fisher_rate(4096),
                       "halflife_gen": halflife_geometric(wright_fisher_rate(4096))},
        },
        "knobs": compare_knobs(),
        "overdominance": overdominance_equilibrium(0.5, 0.2),
    }


if __name__ == "__main__":
    import json
    r = if_all_results()
    print(json.dumps(r, indent=2, default=str))
