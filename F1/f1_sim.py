"""
f1_sim.py -- the demonstration and the controls.

Pure stdlib.  Two families of dynamics:

  LATTICE  (N=256 ring, one field, variance is a spatial average so it is
            a decent estimator on its own)
    - diffusive averaging operators, deterministic
    - discontinuous averaging operators   (attack on claim 4)
    - the paper's SDE: D lap phi - k(phi-phi*) + sigma xi, integrated in
      the Fourier basis where it is exactly diagonal

  POPULATION (M independent replicates of an N-cell federation)
    - because the paper's "variance" is ambiguous, and the ambiguity
      changes the answer.  We measure the variance about the ENSEMBLE
      mean and the self-averaged population variance, separately.

Every operator records a variance trajectory.  The trajectory is the
measurement; a snapshot is not.
"""
import math
import random

LOG = math.log


# ======================================================================
# helpers
# ======================================================================

def var_about_own_mean(x):
    n = len(x)
    m = sum(x) / n
    return sum((v - m) ** 2 for v in x) / n


def logspace(a, b, n):
    if a <= 0 or b <= 0:
        raise ValueError
    la, lb = LOG(a), LOG(b)
    return [math.exp(la + (lb - la) * i / (n - 1)) for i in range(n)]


def mean(xs):
    return sum(xs) / len(xs)


def median3(a, b, c):
    if a < b:
        a, b = b, a
    if b < c:
        b = c
        if a < b:
            b = a
    return b


# ======================================================================
# LATTICE: deterministic averaging operators
# ======================================================================

def op_global_mean(x, rng):
    """Full consensus.  The most complete averaging the system has."""
    m = sum(x) / len(x)
    return [m] * len(x)


def op_neighbour_mean(x, rng, D=0.25):
    """phi_i <- (1-2D) phi_i + D (phi_{i-1} + phi_{i+1}).
    'mean field update over a lattice' -- explicit Laplacian diffusion."""
    n = len(x)
    y = [0.0] * n
    for i in range(n):
        y[i] = (1.0 - 2.0 * D) * x[i] + D * (x[i - 1] + x[(i + 1) % n])
    return y


def op_neighbour_mean_maxstep(x, rng, D=0.5):
    """The same operator at the largest stable step: replaces each cell
    with the mean of its two neighbours.  Still a pure averaging operator,
    now a full 100% replacement per step."""
    n = len(x)
    return [0.5 * (x[i - 1] + x[(i + 1) % n]) for i in range(n)]


def op_median3(x, rng):
    """DISCONTINUOUS but still deterministic averaging.
    Claim 4 says discontinuity defeats the F1 collapse.  Watch it not."""
    n = len(x)
    return [median3(x[i - 1], x[i], x[(i + 1) % n]) for i in range(n)]


def op_quantised_mean(x, rng, levels=8):
    """DISCONTINUOUS by construction: round to a coarse lattice, then
    average.  Another discontinuous averaging operator."""
    n = len(x)
    m = sum(x) / n
    sd = math.sqrt(var_about_own_mean(x)) + 1e-12
    step = 4.0 * sd / levels
    q = [round((v - m) / step) * step for v in x]
    mm = sum(q) / n
    return [0.5 * v + 0.5 * mm for v in q]


def op_rank1_projector(x, rng):
    """THE PAPER'S QUANTUM MECHANISM, as a linear projector:
    project the field onto the uniform direction.  This is literally the
    average operator.  One step."""
    m = sum(x) / len(x)
    return [m] * len(x)


def op_orthocomplement_projector(x, rng):
    """A DIFFERENT projector: project OUT the uniform direction.
    This one DOES make the uniform state unreachable -- in one step --
    and it is the single most information-destroying operator available:
    its kernel is the entire uniform direction."""
    m = sum(x) / len(x)
    return [v - m for v in x]


def op_lowrank_projector(x, rng, r=4, seed=0):
    """Project onto a random rank-r subspace chosen independently of x.
    The uniform state is generically NOT in the range, so it is
    unreachable.  Entirely classical.  The residual diversity is set by r
    and NOT by any sigma/k."""
    n = len(x)
    rr = random.Random(seed)
    basis = []
    for _ in range(r):
        v = [rr.gauss(0, 1) for _ in range(n)]
        # orthonormalise against what we have
        for b in basis:
            d = sum(v[i] * b[i] for i in range(n))
            for i in range(n):
                v[i] -= d * b[i]
        nrm = math.sqrt(sum(t * t for t in v))
        if nrm < 1e-9:
            return list(x)
        basis.append([t / nrm for t in v])
    m = sum(x) / n
    xc = [v - m for v in x]
    y = [0.0] * n
    for b in basis:
        d = sum(xc[i] * b[i] for i in range(n))
        for i in range(n):
            y[i] += d * b[i]
    return y


# ======================================================================
# LATTICE: stochastic operators -- the paper's SDE, in the Fourier basis
#
#   dphi/dt = D lap phi - k(phi - phi*) + sigma xi ,  periodic
#
#   mode m:  dphi_m/dt = -(k + D q_m^2) phi_m + sigma xi_m
#   q_m^2 = 4 sin^2(pi m / N)
#   stationary variance of mode m:  sigma^2 / (2 (k + D q_m^2))
#   field variance  =  sum_m   (Parseval)
# ======================================================================

def fourier_q2(N):
    return [4.0 * math.sin(math.pi * m / N) ** 2 for m in range(N)]


def sde_fourier(sigma, k, D, N, steps, burn, seed, record, dt=None):
    """Integrate the paper's equation mode-by-mode.

    Uses the EXACT Ornstein-Uhlenbeck transition for each mode
        phi <- e^{-lambda dt} phi + sigma sqrt((1-e^{-2 lambda dt})/(2 lambda)) z
    which has zero discretisation bias, so the only error left is Monte
    Carlo.  The result must then reproduce
        V_mode = sigma^2/(2 lambda),  lambda = k + D q^2
    to within the Monte-Carlo error -- which is a real test of the
    closed form and not a test of my integrator.
    """
    rng = random.Random(seed)
    q2 = fourier_q2(N)
    phi = [0.0] * N
    lmax = k + D * max(q2)
    if dt is None:
        dt = 0.5 / lmax
    a = [math.exp(-(k + D * q2[m]) * dt) for m in range(N)]
    s = [sigma * math.sqrt((1.0 - math.exp(-2.0 * (k + D * q2[m]) * dt))
                           / (2.0 * (k + D * q2[m]))) for m in range(N)]
    traj = []
    nrec = len(record)
    ri = 0
    acc = 0.0
    cnt = 0
    for t in range(steps + burn):
        phi = [a[m] * phi[m] + s[m] * rng.gauss(0, 1) for m in range(N)]
        if t >= burn:
            acc += sum(v * v for v in phi)   # proper time average, every step
            cnt += 1
            t2 = t - burn
            if ri < nrec and t2 == record[ri]:
                traj.append((record[ri], sum(v * v for v in phi)))
                ri += 1
    return traj, dt, acc / cnt


def uniform_state_reachable(op, N, seed, **kw):
    """CLAIM 4 FALSIFICATION TEST, run directly.
    Feed a CONSTANT field to the operator.  If the operator returns a
    constant field, the uniform state is reachable (in zero steps) and
    absorbing.  Claim 4 says a discontinuous operator makes it
    'unreachable rather than merely slow'."""
    rng = random.Random(seed)
    x = [0.7] * N
    for _ in range(3):
        x = op(x, rng, **kw)
    spread = max(x) - min(x)
    return {"max_minus_min_after_3_steps": spread,
            "reachable_in_zero_steps": spread < 1e-12}


def sde_fourier_exact(sigma, k, D, N):
    q2 = fourier_q2(N)
    if k <= 0.0:
        # no stationary distribution at all: the k=0 mode is a free
        # particle and V grows without bound, ~ sigma^2 t.
        return None
    return sum(sigma * sigma / (2.0 * (k + D * q)) for q in q2)


def diffusion_slowest_mode_rate(D, N):
    """Exact asymptotic decay of the VARIANCE under
    phi_i <- (1-2D)phi_i + D(phi_{i-1}+phi_{i+1}) on an N-ring.

    Amplification of Fourier mode q:   a(q) = 1 - 2D(1-cos q) = 1-4D sin^2(q/2)
    The VARIANCE is |a|^2, so V(t) = a^(2t) and the half-life is
        T = ln(1/2) / (2 ln a)      <-- the factor of 2 matters
    The slowest mode is the smallest nonzero q = 2 pi / N, so the collapse
    time is set by the LARGEST length scale:  T ~ N^2 / (8 D pi^2 / 0.693).
    """
    q2min = 4.0 * math.sin(math.pi / N) ** 2
    a = 1.0 - D * q2min
    rate = a * a                      # variance ratio per generation
    T = math.log(0.5) / math.log(rate) if 0 < rate < 1 else float("inf")
    return rate, q2min, T, math.log(0.5) / (2 * math.log(a))


# ======================================================================
# LATTICE trajectories for the deterministic operators
# ======================================================================

def run_op(op, N, steps, init, record, seed, **kw):
    rng = random.Random(seed)
    x = list(init)
    out = []
    ri = 0
    nrec = len(record)
    for t in range(steps + 1):
        if ri < nrec and t == record[ri]:
            out.append((t, var_about_own_mean(x)))
            ri += 1
        if t < steps:
            x = op(x, rng, **kw)
    return out


def gaussian_init(N, sd, seed):
    rng = random.Random(seed)
    return [rng.gauss(0, sd) for _ in range(N)]


# ======================================================================
# POPULATION: the federation model, M replicates
# ======================================================================

def pop_blend(pops, rng, N):
    """'Recombination' as the mean of two random parents, WITH replacement.
    This is what the paper's Var_n = Var_0 2^(-n) literally computes --
    and it is an AVERAGING operator, so it is an F1, not an F2."""
    for p in pops:
        for i in range(N):
            a = rng.randrange(N)
            b = rng.randrange(N)
            p[i] = 0.5 * (p[a] + p[b])


def pop_crossover(pops, rng, N, mu_recomb=0.0):
    """Mendelian crossover on a scalar: a child takes one parent's value or
    the other's, at random.  No blending, so no averaging.  Optional
    symmetric recombination rate mu_recomb toward a random *other* cell."""
    for p in pops:
        for i in range(N):
            a = rng.randrange(N)
            b = rng.randrange(N)
            p[i] = p[a] if rng.random() < 0.5 else p[b]
        if mu_recomb > 0.0:
            for i in range(N):
                if rng.random() < mu_recomb:
                    p[i] = p[rng.randrange(N)]


def pop_disassortative(pops, rng, N, strength=1.0):
    """MISMATCHED-RECOMBINATION CONTROL.
    The child prefers the parent OPPOSITE to itself, i.e. recombination
    maximally correlated with the private signal.  The thesis requires the
    stochasticity be independent of e_i.  This is the opposite."""
    for p in pops:
        m = sum(p) / N
        for i in range(N):
            # pick the parent farthest from p[i]: the most informative mate
            best, bd = 0, -1.0
            for _ in range(3):
                c = rng.randrange(N)
                d = abs(p[c] - p[i])
                if d > bd:
                    bd, best = d, c
            p[i] = p[best] if rng.random() < 0.5 else p[i]
        _ = m


def pop_assortative(pops, rng, N):
    """The other mismatch: recombination correlated POSITIVELY -- the child
    copies the parent most similar to itself.  Also violates the
    independence requirement, in the other direction."""
    for p in pops:
        for i in range(N):
            best, bd = 0, 1e18
            for _ in range(3):
                c = rng.randrange(N)
                d = abs(p[c] - p[i])
                if d < bd:
                    bd, best = d, c
            p[i] = p[best] if rng.random() < 0.5 else p[i]


def pop_measure(pops, mu0):
    """Two different 'variances', because the paper never says which:
      spread  -- variance about the ENSEMBLE mean mu0: how much diversity
                 is left in the fleet as a whole
      selfavg -- mean of each population's variance about ITS OWN mean:
                 what a participant that cannot see mu0 actually sees.
                 This is the one that matters, and it is the one that
                 collapses."""
    M = len(pops)
    N = len(pops[0])
    sp = 0.0
    sa = 0.0
    for p in pops:
        mp = sum(p) / N
        v = 0.0
        for v_ in p:
            v += (v_ - mu0) ** 2
        sp += v / N
        sa += var_about_own_mean(p)
    return sp / M, sa / M


# ----------------------------------------------------------------------
# THE REAL F2 MECHANISM, in its textbook form.
#
# F2's 1:2:1 is HETEROZYGOTE ADVANTAGE: a BIMODAL fitness landscape.
# Random mating under overdominance sits at a stable internal equilibrium
# with the genotype ratio 1:2:1 forever, and the between-individual
# variance is PERMANENT and self-averaging.
#
# Remove the advantage (w = 1 everywhere) and the SAME operator is
# neutral Wright-Fisher: the allele frequency is conserved but the
# within-population diversity is lost to drift at rate (N-1)/N per
# generation.
#
# The difference between those two rows is a function of the CURRENT
# STATE -- i.e. it is correlated with the private signal.  That is the
# whole finding, and it is the opposite of the thesis's requirement.
# ----------------------------------------------------------------------

def pop_wright_fisher_overdominance(pops, rng, N, s=0.0):
    """Diploid, one locus, gamete pool, random mating, viability selection.

    s > 0  : heterozygote advantage  -> polymorphism maintained (this is F2)
    s = 0  : neutral                 -> drift destroys it

    Values are stored as the individual's allele-A FRACTION in {0,.5,1},
    so the self-averaged variance is directly comparable to the runs above
    and saturates at 1/4 (the maximum possible).
    """
    for p in pops:
        # expand each individual's stored allele-A fraction into two
        # homologues, giving the diploid genotype pool for random mating
        g = []
        for v in p:
            if v < 0.25:
                g += [0, 0]
            elif v > 0.75:
                g += [1, 1]
            else:
                g += [0, 1]
        new = []
        for _ in range(N):
            a = g[rng.randrange(len(g))]
            b = g[rng.randrange(len(g))]
            w = (1.0 + s) if a != b else 1.0
            new.append((a, b, w))
        tot = sum(w for _, _, w in new)
        keep = [(a, b) for a, b, w in new if rng.random() < w / tot * N]
        while len(keep) < N:
            a, b, _ = new[rng.randrange(N)]
            keep.append((a, b))
        for i in range(N):
            a, b = keep[i]
            p[i] = 0.5 * (a + b)


def pop_overdominance(pops, rng, N, s=0.3):
    return pop_wright_fisher_overdominance(pops, rng, N, s)


def pop_neutral(pops, rng, N):
    return pop_wright_fisher_overdominance(pops, rng, N, 0.0)


def run_pop(op, M, N, gens, sd, seed, record, init=None, **kw):
    rng = random.Random(seed)
    if init is None:
        pops = [[rng.gauss(0.0, sd) for _ in range(N)] for _ in range(M)]
    else:
        pops = [[float(init)] * N for _ in range(M)]
    mu0 = (sum(pops[0]) / N if init is not None else 0.0)
    traj = []
    ri = 0
    for g in range(gens + 1):
        if ri < len(record) and g == record[ri]:
            sp, sa = pop_measure(pops, mu0)
            traj.append((g, sp, sa))
            ri += 1
        if g < gens:
            op(pops, rng, N, **kw)
    return traj
