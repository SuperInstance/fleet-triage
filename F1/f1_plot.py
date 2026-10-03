"""
f1_plot.py -- minimal SVG line plots, pure stdlib.  Log-y is mandatory:
these trajectories span six decades and a linear axis shows nothing.
"""
import html
import math
import os

PAL = ["#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2",
       "#be185d", "#65a30d", "#9333ea", "#ea580c"]


def _esc(s):
    return html.escape(str(s))


class Axes:
    def __init__(self, w, h, xlim, ylim, title="", xlabel="", ylabel="",
                 note=""):
        self.w, self.h = w, h
        self.x0, self.x1 = xlim
        self.y0, self.y1 = ylim
        self.title, self.xlabel, self.ylabel, self.note = title, xlabel, ylabel, note
        self.body = []
        self.ml, self.mr, self.mt, self.mb = 92, 210, 52, 62

    def px(self, x):
        L, R = self.ml, self.w - self.mr
        t = (math.log(max(x, 1e-300)) - math.log(self.x0)) / (math.log(self.x1) - math.log(self.x0))
        return L + t * (R - L)

    def py(self, y):
        T, B = self.mt, self.h - self.mb
        t = (math.log(max(y, 1e-300)) - math.log(self.y0)) / (math.log(self.y1) - math.log(self.y0))
        return B - t * (B - T)

    def decade_ticks(self, axis):
        a, b = self.x0, self.x1
        t = []
        e = int(math.floor(math.log10(a)))
        while 10.0 ** e <= b * 1.0001:
            for m in (1, 2, 5):
                v = m * 10.0 ** e
                if a <= v <= b:
                    t.append(v)
            e += 1
        return t

    def grid(self):
        for yv in self.decade_ticks("y"):
            y = self.py(yv)
            lab = f"{yv:g}"
            self.body.append(f'<line x1="{self.ml}" y1="{y:.1f}" x2="{self.w-self.mr}" '
                             f'y2="{y:.1f}" stroke="#e5e7eb" stroke-width="1"/>')
            self.body.append(f'<text x="{self.ml-8}" y="{y+4:.1f}" font-size="11" '
                             f'text-anchor="end" fill="#6b7280" font-family="monospace">{lab}</text>')
        for xv in self.decade_ticks("x"):
            x = self.px(xv)
            self.body.append(f'<line x1="{x:.1f}" y1="{self.mt}" x2="{x:.1f}" '
                             f'y2="{self.h-self.mb}" stroke="#f3f4f6" stroke-width="1"/>')
            self.body.append(f'<text x="{x:.1f}" y="{self.h-self.mb+18}" font-size="11" '
                             f'text-anchor="middle" fill="#6b7280" font-family="monospace">{xv:g}</text>')
        self.body.append(f'<rect x="{self.ml}" y="{self.mt}" width="{self.w-self.ml-self.mr}" '
                         f'height="{self.h-self.mt-self.mb}" fill="none" stroke="#9ca3af"/>')
        self.body.append(f'<text x="{(self.ml+self.w-self.mr)/2:.0f}" y="{self.h-14}" '
                         f'font-size="13" text-anchor="middle" fill="#111827">{_esc(self.xlabel)}</text>')
        self.body.append(f'<text transform="translate(20,{(self.mt+self.h-self.mb)/2:.0f}) rotate(-90)" '
                         f'font-size="13" text-anchor="middle" fill="#111827">{_esc(self.ylabel)}</text>')
        if self.title:
            self.body.append(f'<text x="{self.ml}" y="30" font-size="16" font-weight="600" '
                             f'fill="#111827">{_esc(self.title)}</text>')
        if self.note:
            for i, ln in enumerate(self.note.split("\n")):
                self.body.append(f'<text x="{self.w-self.mr+10}" y="{self.mt+14+i*15}" '
                                 f'font-size="11" fill="#374151" font-family="monospace">{_esc(ln)}</text>')

    def series(self, pts, label, color, dash=None, width=2.0):
        if not pts:
            return
        d = " ".join(("M" if i == 0 else "L") + f"{self.px(x):.1f},{self.py(y):.1f}"
                     for i, (x, y) in enumerate(pts) if y > 0)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        self.body.append(f'<path d="{d}" fill="none" stroke="{color}" '
                         f'stroke-width="{width}"{da}/>')
        ly = self.mt + 14 + len([b for b in self.body]) * 0
        self.legends.append((label, color, dash))

    def render(self):
        s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
             f'viewBox="0 0 {self.w} {self.h}">',
             f'<rect width="{self.w}" height="{self.h}" fill="white"/>']
        s += self.body
        y = self.mt + 4
        for lab, col, dash in self.legends:
            da = f' stroke-dasharray="{dash}"' if dash else ""
            s.append(f'<line x1="{self.w-self.mr+10}" y1="{y}" x2="{self.w-self.mr+34}" '
                     f'y2="{y}" stroke="{col}" stroke-width="2.5"{da}/>')
            for i, chunk in enumerate(_wrap(lab, 30)):
                s.append(f'<text x="{self.w-self.mr+40}" y="{y+4+i*12}" font-size="10.5" '
                         f'fill="#111827" font-family="monospace">{_esc(chunk)}</text>')
            y += 12 * len(_wrap(lab, 30)) + 6
        s.append("</svg>")
        return "\n".join(s)


def _wrap(s, n):
    out, cur = [], ""
    for word in str(s).split(" "):
        if len(cur) + len(word) + 1 > n and cur:
            out.append(cur)
            cur = word
        else:
            cur = (cur + " " + word).strip()
    if cur:
        out.append(cur)
    return out


def _mk(xlim, ylim, **kw):
    a = Axes(940, 560, xlim, ylim, **kw)
    a.legends = []
    a.grid()
    return a


def _save(a, path):
    with open(path, "w") as f:
        f.write(a.render())


def _floor(series, eps):
    out = []
    for x, y in series:
        out.append((x, max(y, eps)))
    return out


# ----------------------------------------------------------------------

def make_all(R, OUT):
    # 1. deterministic + discontinuous lattice operators
    lat = R["lattice"]
    lo = min(v for r in lat for _, v in r["traj"] if v > 0)
    hi = max(v for r in lat for _, v in r["traj"])
    a = _mk((1, 4000), (max(lo * 0.5, 1e-9), hi * 2),
            title="Deterministic averaging on a 256-cell ring: variance trajectory",
            xlabel="generation", ylabel="V = field variance about its own mean",
            note="paper claims V_n = V_0 * 2^-n\n(halflife 1 generation) for all of these.")
    for i, r in enumerate(lat):
        a.series(_floor(r["traj"], 1e-9), r["operator"], PAL[i % len(PAL)])
    _save(a, os.path.join(OUT, "1-collapse-operators.svg"))

    # 2. the paper's equation, simulated, vs sigma^2/(2k)
    sims = R["sde_sim"]
    a = _mk((1, 20000), (1e-4, 3e2),
            title="The paper's own equation, integrated mode-by-mode (N=128, D=sigma=1)",
            xlabel="time step", ylabel="V_field = sum over all modes",
            note="solid   = simulated field variance\n"
                 "dashed  = paper's sigma^2/(2k)\n"
                 "dotted  = exact sum_m sigma^2/(2(k+Dq^2))")
    for i, s in enumerate(sims):
        a.series(_floor(s["traj"], 1e-9), f"k={s['k']:g}  simulated", PAL[i])
        a.series([(1, s["paper_sigma2_2k"]), (20000, s["paper_sigma2_2k"])],
                 f"k={s['k']:g}  paper", PAL[i], dash="5,4", width=1.6)
        a.series([(1, s["exact"]), (20000, s["exact"])],
                 f"k={s['k']:g}  exact", PAL[i], dash="2,3", width=1.4)
    _save(a, os.path.join(OUT, "2-sde-vs-paper.svg"))

    # 3. geometry factor
    g = R["geometry"]
    a = _mk((1e-5, 1e4), (1e-3, 1e4),
            title="Geometry factor  G = V_field / (sigma^2/2k):  the factor the paper omits",
            xlabel="k / D", ylabel="G  (paper predicts 1, flat)",
            note="N=64, d=1 (N^d=64)\nN=256, d=1 (N^d=256)\nN=1024, d=1 (N^d=1024)\n"
                 "N=32, d=2 (N^d=1024)\n\nG -> N^d when k >> D q_max^2\n"
                 "G -> 1   when k << D q_min^2")
    seen = set()
    i = 0
    for r in g:
        key = (r["d"], r["N"])
        if key in seen:
            continue
        seen.add(key)
        pts = [(x["k_over_D"], x["G_field_over_paper"]) for x in g
               if (x["d"], x["N"]) == key]
        a.series(pts, f"d={r['d']} N={r['N']} (N^d={r['Npowd']})", PAL[i % len(PAL)])
        i += 1
    a.series([(1e-5, 1), (1e4, 1)], "paper: G = 1", "#dc2626", dash="6,4")
    _save(a, os.path.join(OUT, "3-geometry-factor.svg"))

    # 3b. per-cell
    a = _mk((1e-5, 1e4), (1e-3, 1e3),
            title="Per-cell variance vs the paper's sigma^2/(2k)",
            xlabel="k / D", ylabel="V_field / N^d  divided by  sigma^2/(2k)",
            note="the ONLY normalisation under which the\npaper can be right at all\n\n"
                 "d=1 N=256\nd=2 N=32\n\nratio = 1 only for k/D >~ 100,\ni.e. k >> D (L/pi)^2")
    i = 0
    seen = set()
    for r in g:
        key = (r["d"], r["N"])
        if key in seen:
            continue
        seen.add(key)
        a.series([(x["k_over_D"], x["v_over_paper"]) for x in g if (x["d"], x["N"]) == key],
                 f"d={r['d']} N={r['N']}", PAL[i % len(PAL)])
        i += 1
    a.series([(1e-5, 1), (1e4, 1)], "paper", "#dc2626", dash="6,4")
    _save(a, os.path.join(OUT, "3b-per-cell-ratio.svg"))

    # 4. population: spread AND self-averaged
    pop = R["population"]
    a = _mk((1, 1000), (1e-6, 2),
            title="Federation dynamics: two different 'variances'",
            xlabel="generation", ylabel="variance",
            note="SOLID  = spread about the ensemble mean\n"
                 "DASHED = self-averaged: each population's\n"
                 "         variance about its OWN mean\n\n"
                 "the second is what a participant sees,\nand the one that matters for a federation")
    for i, r in enumerate(pop):
        a.series(_floor([(g, sp) for g, sp, sa in r["spread_traj"]], 1e-9),
                 r["operator"], PAL[i % len(PAL)])
    for i, r in enumerate(pop):
        a.series(_floor([(g, sa) for g, sp, sa in r["spread_traj"]], 1e-9),
                 r["operator"], PAL[i % len(PAL)], dash="4,3", width=1.5)
    _save(a, os.path.join(OUT, "4-population-two-variances.svg"))

    # 5. controls
    ctl = R["controls_mismatch"]
    a = _mk((1, 1000), (1e-6, 20),
            title="CONTROL: recombination correlated with the private signal",
            xlabel="generation", ylabel="self-averaged variance",
            note="the thesis requires the stochasticity be\n"
                 "INDEPENDENT of the private data e_i.\n\n"
                 "if correlated recombination also holds\n"
                 "the variance, the requirement is weaker\n"
                 "than claimed.  (here: much worse --\n"
                 "it is inverted.)")
    for i, r in enumerate(ctl):
        a.series(_floor([(g, sa) for g, sp, sa in r["traj"]], 1e-9),
                 r["control"], PAL[i % len(PAL)], width=2.4)
    _save(a, os.path.join(OUT, "5-control-mismatched-recombination.svg"))

    # 6. seed + initial condition controls
    a = _mk((1, 3000), (1e-6, 2),
            title="CONTROLS: seed and initial condition",
            xlabel="generation (diffusive averaging, N=256)",
            ylabel="field variance",
            note="not an artefact of one starting point")
    for i, (name, d) in enumerate(R["control_init"].items()):
        a.series(_floor(d["traj"], 1e-9), f"init: {name}", PAL[i % len(PAL)])
    _save(a, os.path.join(OUT, "6-control-initial-conditions.svg"))

    # 7. the F2 mechanism: same operator, with/without state dependence
    f2 = R["f2_mechanism"]
    a = _mk((1, 3000), (1e-5, 0.3),
            title="F2's actual mechanism: diploid Wright-Fisher, random mating",
            xlabel="generation", ylabel="self-averaged variance",
            note="started MONOMORPHIC; only the operator\n"
                 "can create diversity\n\n"
                 "s=0  -> independent stochasticity (what the\n"
                 "       thesis licenses): diversity dies on a\n"
                 "       ~N-generation timescale\n"
                 "s>0  -> state-dependent (heterozygote\n"
                 "       advantage = F2's 1:2:1): diversity held\n\n"
                 "max possible = 0.25,  HW 1:2:1 = 0.125")
    for i, r in enumerate(f2):
        a.series(_floor([(g, sa) for g, sp, sa in r["traj"]], 1e-9),
                 f"w_Aa = {r['w_Aa']:.2f}   halflife {r['halflife_gen']:.0f} gen",
                 PAL[i % len(PAL)], width=2.4)
    _save(a, os.path.join(OUT, "7-f2-mechanism.svg"))

    # 8. ablation: is any term inert?
    ab = R["ablation"]
    a = _mk((1e-3, 1e2), (1e-3, 1e2),
            title="Ablation: is any term in the paper's equation doing nothing?",
            xlabel="k", ylabel="per-cell stationary variance",
            note="paper: sigma^2/(2k), a straight line\n"
                 "with slope -1 and no D anywhere\n\n"
                 "D=0 : exactly the paper's answer\n"
                 "D=1 : the diffusion term changes it by\n"
                 "       up to 3x and bends the slope\n"
                 "k=0 : NO stationary state at all --\n"
                 "       V grows as sigma^2 t without bound,\n"
                 "       which is delocalisation, not 'one blob'")
    for i, r in enumerate(ab):
        if r["k"] == 0:
            continue
        a.series([(1e-3, 1.0 / (2 * r["k"])), (1e2, 1.0 / (2 * r["k"]))],
                 f"paper, k={r['k']}", PAL[i], dash="5,4", width=1.4)
    for i, r in enumerate(ab):
        if r["k"] == 0:
            continue
        a.series([(1e-3, 1.0 / (2 * r["k"])), (1e2, r["v_per_cell"])],
                 f"actual, k={r['k']} D={r['D']}", PAL[(i + 3) % len(PAL)], width=2.4)
    _save(a, os.path.join(OUT, "8-ablation.svg"))
