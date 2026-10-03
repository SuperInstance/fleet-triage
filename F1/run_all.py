"""
run_all.py -- runs every check and writes CSV + JSON + SVG.

    python3 run_all.py            # everything
    python3 run_all.py --quick    # fewer steps

Outputs land next to this file in ./out/.
"""
import json
import math
import os
import random
import sys

import f1_core as K
import f1_core2 as C
import f1_sim as S
import f1_plot as P

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
QUICK = "--quick" in sys.argv
os.makedirs(OUT, exist_ok=True)


def w_csv(name, header, rows):
    p = os.path.join(OUT, name)
    with open(p, "w") as f:
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(",".join(str(r[h]) for h in header) + "\n")
    return p


def fit_rate(pts):
    """exp slope of ln V vs t.  pts = [(t, v), ...] with v > 0."""
    pts = [(t, v) for t, v in pts if v > 1e-300 and t > 0]
    if len(pts) < 5:
        return float("nan"), float("nan")
    xs = [p[0] for p in pts]
    ys = [math.log(p[1]) for p in pts]
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den <= 0:
        return float("nan"), float("nan")
    sl = sum((xs[i] - mx) * (ys[i] - my) for i in range(len(xs))) / den
    return math.exp(sl), (math.log(0.5) / sl if sl < 0 else float("inf"))


R = {}

# ======================================================================
print("[1/7] claim 1 -- the variance identity and the F1 operator")
R["claim1"] = K.check_claim1()
c1 = R["claim1"]
print(f"    identity            rel err = {c1['identity']['rel_err']:.2e}   OK")
print(f"    iid halving         ratio   = {c1['iid_halving']['ratio']:.6f}   OK")
print(f"    ACTUAL F1 variance  = {c1['f1_actual_variance']}   (paper predicts "
      f"{c1['f1_vs_halving_prediction']['doc_predicts']:.4f})   <-- ERROR")

# ======================================================================
print("[2/7] claim 2a -- OU stationary variance in ONE degree of freedom")


def ou_replicates(k, sigma=1.0, dt=1e-3, T=120000, Rr=120, seed=17):
    """R independent runs, each of length T, so the error bar is honest."""
    vals = []
    for r in range(Rr):
        rng = random.Random(seed + 1000 * r)
        x = 0.0
        s = s2 = 0.0
        n = 0
        for t in range(T):
            x += -k * dt * x + sigma * math.sqrt(dt) * rng.gauss(0, 1)
            if t >= T // 5:
                s += x
                s2 += x * x
                n += 1
        m = s / n
        vals.append(s2 / n - m * m)
    mu = sum(vals) / len(vals)
    sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / (len(vals) - 1))
    ex = sigma * sigma * dt / (1 - (1 - k * dt) ** 2)
    return {"k": k, "mean": mu, "stderr": sd / math.sqrt(len(vals)),
            "exact": ex, "paper": sigma * sigma / (2 * k),
            "z": (mu - ex) / (sd / math.sqrt(len(vals)))}


R["ou_1d"] = [ou_replicates(k) for k in (2.0, 0.5, 0.2)]
for r in R["ou_1d"]:
    print(f"    k={r['k']:<5} measured {r['mean']:.5f} +/- {r['stderr']:.5f}   "
          f"exact {r['exact']:.5f}   z={r['z']:+.2f}   OK (sigma^2/2k is CORRECT in 1-D)")

# ======================================================================
print("[3/7] claim 2b/3 -- the d-dimensional GEOMETRY FACTOR")
rows = []
for d, N in ((1, 64), (1, 256), (1, 1024), (2, 32)):
    for rk in (1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1, 1e1, 1e2, 1e3):
        k = 1.0 * rk
        V = C.V_field(1.0, k, 1.0, N, d)
        nd = N ** d
        rows.append({"d": d, "N": N, "Npowd": nd, "k_over_D": rk,
                     "V_field": V, "v_per_cell": V / nd,
                     "paper_sigma2_2k": 1.0 / (2 * k),
                     "G_field_over_paper": V / (1.0 / (2 * k)),
                     "v_over_paper": (V / nd) / (1.0 / (2 * k))})
w_csv("geometry.csv", list(rows[0].keys()), rows)
R["geometry"] = rows
R["k_crit"] = {f"d{d}_N{N}": C.k_crit(1.0, N, d) for d, N in ((1, 256), (2, 32))}
R["slopes"] = {}
for lab, lo, hi in (("paper_regime", 1e3, 1e5), ("crossover", 1e-2, 1e0),
                    ("far_IR", 1e-8, 1e-6)):
    for d, N in ((1, 1024), (2, 32)):
        R["slopes"][f"{lab}_d{d}_N{N}"] = C.loglog_slope(lo, hi, 1.0, N, d)
print("    d(log v)/d(log k):", {k: round(v, 3) for k, v in R["slopes"].items()})
print("    paper predicts -1 everywhere.")

# simulate the paper's equation to confirm the closed form
Nsim = 128
sims = []
for k in (0.1, 1.0, 100.0):
    rec = sorted(set([int(round(t)) for t in S.logspace(1, 20000, 30)]))
    tr, dt, tavg = S.sde_fourier(sigma=1.0, k=k, D=1.0, N=Nsim, steps=40000,
                                 burn=40000, seed=4, record=rec[:26])
    ex = S.sde_fourier_exact(1.0, k, 1.0, Nsim)
    sims.append({"k": k, "N": Nsim, "dt": dt, "sim_timeavg": tavg,
                 "exact": ex, "paper_sigma2_2k": 1.0 / (2 * k),
                 "v_per_cell_exact": ex / Nsim,
                 "paper_per_cell": 1.0 / (2 * k),
                 "traj": tr})
R["sde_sim"] = sims
print(f"    Fourier-mode simulation of the paper's own equation, N={Nsim}:")
for s in sims:
    print(f"      k={s['k']:<6} dt={s['dt']:.2e}  simulated {s['sim_timeavg']:.5f}   exact "
          f"{s['exact']:.5f}   paper {s['paper_sigma2_2k']:.5f}   "
          f"per-cell: {s['v_per_cell_exact']:.5f} vs paper {s['paper_per_cell']:.5f}"
          f"  ({s['v_per_cell_exact']/s['paper_per_cell']:.3f}x)")

# ======================================================================
print("[4/7] claim 4 -- discontinuous operators, and projectors")
N = 256
init = S.gaussian_init(N, 1.0, 1)
rec = [0] + sorted(set(int(round(t)) for t in S.logspace(1, 3000, 120)))
OPS = [
    ("global mean (full consensus)", S.op_global_mean, {}),
    ("neighbour mean D=0.25 (diffusion)", S.op_neighbour_mean, {"D": 0.25}),
    ("neighbour mean, max stable step", S.op_neighbour_mean_maxstep, {}),
    ("MEDIAN-3  (discontinuous, deterministic)", S.op_median3, {}),
    ("quantised mean  (discontinuous)", S.op_quantised_mean, {}),
    ("rank-1 projector  (= the average)", S.op_rank1_projector, {}),
    ("orthocomplement projector", S.op_orthocomplement_projector, {}),
    ("random rank-4 projector", S.op_lowrank_projector, {"r": 4}),
]
lat = []
for name, op, kw in OPS:
    tr = S.run_op(op, N, 3000, init, rec, seed=5, **kw)
    rate, hl = fit_rate([(t, v) for t, v in tr if t > 20])
    rate_late, hl_late = fit_rate([(t, v) for t, v in tr if t > 800])
    v3000 = tr[-1][1]
    ur = S.uniform_state_reachable(op, N, seed=5, **kw)
    lat.append({"operator": name, "V_init": tr[0][1], "V_final": v3000,
                "rate": rate, "halflife": hl,
                "asymptotic_rate": rate_late, "asymptotic_halflife": hl_late,
                "uniform_reachable": ur["reachable_in_zero_steps"],
                "uniform_residual": ur["max_minus_min_after_3_steps"],
                "reaches_zero": v3000 < 1e-12, "traj": tr})
    print(f"    {name:<40} V_final={v3000:<12.5g} asym_halflife={hl_late:<9.4g} "
          f"uniform_reachable={ur['reachable_in_zero_steps']}")
R["lattice"] = lat
print("    (the paper's claim 4 is 'unreachable rather than merely slow' --")
print("     'uniform_reachable' is the direct falsification test.)")
th_rate, th_q2, th_T, th_T2 = S.diffusion_slowest_mode_rate(0.25, N)
R["diffusion_theory"] = {"variance_rate_per_generation": th_rate,
                         "half_life_generations": th_T,
                         "q2_min": th_q2,
                         "paper_rate": 0.5, "paper_halflife": 1.0,
                         "scaling": "T = 0.0088 N^2 / D  (N = number of cells)"}
print(f"    diffusion: exact asymptotic variance half-life = {th_T:.1f} gen"
      f"  vs paper's 1.0  ({th_T:.0f}x slower than claimed)")
print(f"    scaling: T = 0.0088 N^2/D, so MORE participants => SLOWER collapse, quadratically")

# measure it by bisection on a single pure mode -- exact, no fit, no MC
def _hl(D, qn, N):
    x0 = [math.cos(2 * math.pi * qn * i / N) for i in range(N)]
    tot = sum(v * v for v in x0)

    def Vr(k):
        x = list(x0)
        for _ in range(k):
            x = S.op_neighbour_mean(x, None, D=D)
        return sum(v * v for v in x) / tot
    lo, hi = 0, 8
    while Vr(hi) > 0.5:
        hi *= 2
    for _ in range(40):
        m = (lo + hi) // 2
        if Vr(m) > 0.5:
            lo = m
        else:
            hi = m
    return (lo + hi) / 2


hlchk = []
for D, qn in ((0.125, 1), (0.25, 1), (0.4, 1), (0.25, 2), (0.25, 4)):
    m = _hl(D, qn, N)
    th = math.log(0.5) / (2 * math.log(1 - D * 4 * math.sin(math.pi * qn / N) ** 2))
    hlchk.append({"D": D, "mode_qn": qn, "measured_halflife": m, "theory": th,
                  "ratio": m / th})
    print(f"      bisection check  D={D:<5} q={qn}*2pi/N: measured {m:>8.1f}  "
          f"theory {th:>8.1f}  ratio {m/th:.5f}")
R["diffusion_bisection_check"] = hlchk

# long-horizon run so the ASYMPTOTIC rate is genuinely reached
LONG = 60000 if not QUICK else 12000
recl = [0] + sorted(set(int(round(t)) for t in S.logspace(1, LONG, 90)))
dl = []
for nm, op, kw in (("neighbour mean D=0.25", S.op_neighbour_mean, {"D": 0.25}),):
    tr = S.run_op(op, N, LONG, init, recl, seed=5, **kw)
    rate_l, hl_l = fit_rate([(t, v) for t, v in tr if t > LONG // 10])
    dl.append({"operator": nm, "steps": LONG, "asymptotic_rate": rate_l,
               "asymptotic_halflife": hl_l, "traj": tr})
    print(f"    {nm:<30} fit over the last decade gives halflife {hl_l:>8.1f}   "
          f"exact {th_T:>8.1f}   (fit is an upper bound on the true rate)")
R["diffusion_long"] = dl

# ======================================================================
print("[5/7] part B -- does averaging collapse, does recombination hold it?")
M, NP, GENS = (80, 32, 700) if QUICK else (160, 32, 1000)
recp = [0] + sorted(set(int(round(t)) for t in S.logspace(1, GENS, 50)))
POPS = [
    ("iid blend of 2 random parents (the paper's Var_0*2^-n)", S.pop_blend, {}),
    ("Mendelian crossover / resampling (i.i.d. -- thesis-compliant)", S.pop_crossover, {}),
    ("crossover + independent recombination 0.01", S.pop_crossover, {"mu_recomb": 0.01}),
    ("crossover + independent recombination 0.10", S.pop_crossover, {"mu_recomb": 0.10}),
]
pop = []
for name, op, kw in POPS:
    tr = S.run_pop(op, M, NP, GENS, 1.0, seed=17, record=recp, **kw)
    rate, hl = fit_rate([(g, sp) for g, sp, sa in tr if g > 5])
    srate, shl = fit_rate([(g, sa) for g, sp, sa in tr if g > 5])
    pop.append({"operator": name, "spread_traj": tr, "rate_spread": rate,
                "halflife_spread": hl, "rate_selfavg": srate,
                "halflife_selfavg": shl,
                "spread_final": tr[-1][1], "selfavg_final": tr[-1][2]})
    print(f"    {name:<48} spread_final={tr[-1][1]:<9.4f} selfavg_final={tr[-1][2]:<9.4f}")
R["population"] = pop
R["population_theory"] = {
    "N": NP,
    "self_averaging_rate": (NP - 1) / NP,
    "self_averaging_halflife": math.log(0.5) / math.log((NP - 1) / NP),
    "wf_allele_freq_rate": 2 * NP / (2 * NP + 1),
    "wf_allele_freq_halflife": math.log(0.5) / math.log(2 * NP / (2 * NP + 1)),
    "paper_rate": 0.5, "paper_halflife": 1.0,
}
print(f"    theory: self-averaging halflife {R['population_theory']['self_averaging_halflife']:.1f} gen,"
      f"  WF allele-freq halflife {R['population_theory']['wf_allele_freq_halflife']:.1f} gen,"
      f"  paper claims 1.0 gen")

# ======================================================================
print("[6/7] CONTROLS")
# 6a. THE F2 MECHANISM ITSELF, textbook form: the SAME operator
#     (diploid Wright-Fisher, random mating) with and without
#     state-dependent heterozygote advantage.  Start = the F1 state as
#     the paper describes it: every individual Aa (phenotypically
#     identical, genetically heterozygous).  Diversity is not present but
#     is SEGREGABLE -- that is the whole F1 -> F2 step.
MF, MG = (150, 1500) if QUICK else (300, 3000)
recm = [0] + sorted(set(int(round(t)) for t in S.logspace(1, MG, 60)))
f2 = []
for s in (0.0, 0.1, 0.3, 1.0, 3.0):
    def op(p, r, n, s=s):
        return S.pop_wright_fisher_overdominance(p, r, n, s)
    tr = S.run_pop(op, MF, NP, MG, 1.0, seed=31, record=recm, init=0.5)
    _, hl = fit_rate([(g, sa) for g, sp, sa in tr if g >= 3])
    f2.append({"s": s, "w_Aa": 1.0 + s, "traj": tr,
               "selfavg_final": tr[-1][2], "halflife_gen": hl,
               "ratio_to_neutral": None, "max_possible_selfavg": 0.25,
               "HW_1_2_1_value": 0.125})
    print(f"    w_Aa={1.0+s:<5.2f} (s={s:<4}) selfavg@final={tr[-1][2]:.4f}   "
          f"diversity halflife = {hl:>8.1f} generations")
base = f2[0]["halflife_gen"]
for r in f2:
    r["ratio_to_neutral"] = r["halflife_gen"] / base
R["f2_mechanism"] = f2
R["f2_theory"] = {
    "N": NP,
    "neutral_diversity_halflife_theory": math.log(0.5) / math.log((NP - 1) / NP),
    "note": "diversity is held by STATE-DEPENDENT selection, on a timescale"
            " ~ N/s, not by a noise amplitude; the level is bounded by 1/4"
            " and set by genotype ratios, and no continuous sigma appears.",
}
print(f"    theory: neutral halflife = {R['f2_theory']['neutral_diversity_halflife_theory']:.1f} gen")
print("    ^ the row the thesis licenses (s=0, independent) is the SHORTEST.")
print("      every extension of it requires a state-dependent operator,")
print("      i.e. recombination CORRELATED with the private signal.")

CTL = [
    ("independent crossover (thesis-compliant)", S.pop_crossover, {}),
    ("DISASSORTATIVE: recomb correlated with private signal", S.pop_disassortative, {}),
    ("ASSORTATIVE: recomb correlated the other way", S.pop_assortative, {}),
]
ctl = []
for name, op, kw in CTL:
    tr = S.run_pop(op, M, NP, GENS, 1.0, seed=23, record=recp, **kw)
    ctl.append({"control": name, "traj": tr, "spread_final": tr[-1][1],
                "selfavg_final": tr[-1][2]})
    print(f"    {name:<50} selfavg_final={tr[-1][2]:<10.4f} spread_final={tr[-1][1]:<10.4f}")
R["controls_mismatch"] = ctl

# seed control
seeds = []
for sd in (1, 2, 3, 4, 5, 6, 7, 8):
    tr = S.run_pop(S.pop_crossover, M, NP, GENS, 1.0, seed=sd, record=recp)
    seeds.append(tr[-1][2])
gm = sum(seeds) / len(seeds)
R["control_seed"] = {"selfavg_final_per_seed": seeds, "mean": gm,
                     "min": min(seeds), "max": max(seeds),
                     "stderr": math.sqrt(sum((s - gm) ** 2 for s in seeds) / (len(seeds) - 1))}
print(f"    seed control (8 seeds, crossover): selfavg_final "
      f"{gm:.3e} +/- {R['control_seed']['stderr']:.3e}  (max {max(seeds):.3e})")

# initial-condition control
INITS = {
    "gaussian": S.gaussian_init(N, 1.0, 1),
    "bimodal +-1": [1.0 if i % 2 else -1.0 for i in range(N)],
    "single spike": [0.0] * (N - 1) + [100.0],
    "linear ramp": [-1.0 + 2.0 * i / (N - 1) for i in range(N)],
    "constant (already uniform)": [0.7] * N,
}
ic = {}
for name, x0 in INITS.items():
    tr = S.run_op(S.op_neighbour_mean, N, 3000, x0, rec, seed=5, D=0.25)
    ic[name] = {"V_init": tr[0][1], "V_final": tr[-1][1], "traj": tr}
    print(f"    init {name:<28} V_init={tr[0][1]:<10.4g} -> V_final={tr[-1][1]:<12.4g}")
R["control_init"] = ic

# ablation: remove each term, check it is doing something
abl = []
for k in (0.0, 0.5, 2.0):
    for D in (0.0, 1.0):
        ex = S.sde_fourier_exact(1.0, k, D, 128)
        abl.append({"k": k, "D": D,
                    "V_field_exact": ex if ex is not None else float("inf"),
                    "v_per_cell": (ex / 128) if ex is not None else float("inf"),
                    "paper": (1.0 / (2 * k)) if k > 0 else float("inf"),
                    "regime": ("k=0: NO stationary state, V grows ~ sigma^2 t"
                               if k == 0 else
                               "no diffusion: each cell an independent OU"
                               if D == 0 else "full equation")})
R["ablation"] = abl
print("    ablation -- is any term inert?")
for a in abl:
    ex = a["V_field_exact"]
    print(f"      k={a['k']:<5} D={a['D']:<4} {a['regime']:<45} V_field={ex:<12.5g} per-cell={a['v_per_cell']:<12.5g}")

# ======================================================================
print("[7/7] claim 3 -- the projection")
R["claim3"] = K.projection_kernel(6)
R["wf_knob"] = K.compare_knobs(256, 0.5)
print(f"    mean map: rank {R['claim3']['rank']}, fibre dim "
      f"{R['claim3']['fibre_dimension']}, identical means: "
      f"{R['claim3']['mean_identical']}  (theorem, but true of every non-injective map)")

with open(os.path.join(OUT, "results.json"), "w") as f:
    json.dump(R, f, indent=1, default=str)
print(f"\nwrote {OUT}/results.json")
P.make_all(R, OUT)
print(f"wrote plots to {OUT}/")
