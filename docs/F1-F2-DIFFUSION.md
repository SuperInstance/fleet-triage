# F1, F2, and the chaotic-diffuse: what a federated system does to its own variance

**Status: a thesis with a derivation and a test. Nothing here has been measured.** The
derivation is short enough to check by hand and every claim below is falsifiable.

---

## 0. The claim in one line

**In a federated system with sparse per-participant information, variance collapse is not a
convergence problem. It is an information-destruction problem.** The "F1 uniform" state —
everyone agreeing, every weight averaged — is the *maximally unified* state and the
*maximally uninformative* one, and no amount of additional averaging recovers what it
destroyed.

## 1. Why the F1 cross is the right analogy, exactly

Two pure lines, homozygous and maximally distant. Their F1 offspring are **uniform**: every
individual receives one allele from each parent, so every individual is *genetically
heterozygous and phenotypically identical*. **All the between-parent variance is gone in one
generation.**

In distributions, that is not a metaphor. Cross is mixture. If the two parents are
distributions `p` and `q` over a shared space with no covariance between them:

```
Var((p+q)/2) = ( Var(p) + Var(q) + 2·Cov(p,q) ) / 4
             = Var / 2              when Cov = 0
```

**Variance halves in one generation.** Iterate: `Var_n = Var_0 · 2^(-n)`. This is geometric
collapse. It is not slow, and it does not plateau at anything useful.

**This is what averaging across participants does.** FedAvg, any weighted consensus, any mean
field update over a lattice, any "reflect the movement of information across weight" — every
one of them is the mixture operator. **The F1 state is the fixed point of the only operation
the system obviously has.**

## 2. Why F2 breaks it, and this is the whole insight

Mendel's second generation does **not** have less variance than F1. It has *more* — the
classic 1:2:1 phenotypic ratio. And the reason is not a subtlety. It is structural:

- **F1 is a deterministic mixture.** Every F1 individual has the *same* genotype: one allele
  from line A, one from line B. The genotype space of F1 is small — it is the cross product
  of the two parents' alleles, and every individual walks the same path through it.
- **F2 is a stochastic draw over a much larger space.** Each F2 individual gets *independent*
  alleles from two F1 parents, so it lands somewhere different. The reachable genotype set
  is combinatorial, not linear.

**Segregation is variance injection.** Not noise, not perturbation — a change in the *kind of
operator*. F1 applies a **deterministic** mixing operator. F2 applies a **stochastic**
recombination operator.

The generalisation, and this is the thing I would defend:

> **Deterministic averaging collapses variance geometrically. Stochastic recombination
> restores it in one step and can hold it at a set level.** The equilibrium between the two
> is a design parameter, not a property of the data.

## 3. The stationary variance, which is the knob

Put flow and selection and randomness in one equation, over a weight lattice:

```
∂φ/∂t = D∇²φ  −  k·(φ − φ*)  +  σξ
         ─────    ─────────────   ─────
         flow     restoring      stochastic
         (the F1)  selection      (the F2)
```

- `D∇²φ` — diffusion, the movement of information across weight. This is the F1 operator and
  it is what makes everything agree.
- `−k(φ − φ*)` — restoring selection toward some local preference. Gives the system a
  restoring force instead of pure collapse to a point.
- `σξ` — the stochastic term. This is the F2.

Under additive noise and linear restoring selection, the **stationary variance is analytic**:

```
Var(∞) = σ² / (2k)
```

**That is the design knob.** Diversity in the steady state is set by the ratio of the noise
amplitude to the selection strength — **not by the data, not by the topology, not by how
hard anyone iterates.** `σ=0` recovers the F1 collapse. `k→0` recovers total diffusion into
one blob. The interesting regimes are the ones in between, and they are *reachable by
choosing parameters* rather than by hoping.

> **CORRECTION (2026-10-01, after the scout lane).** I presented this as a result. **It is
> textbook.** `Var(∞) = σ²/2k` is **mutation–selection balance**: de Vladar & Barton (2014),
> *Genetics* 204(2) — *"the genetic variance that is maintained by mutation–selection balance
> is `2μ/S` per locus"*. Substitute `σ² ↔ 2μ` and `k ↔ S` and the equation above **is** the
> standard equilibrium, and **the factor of 2 is a convention, not a consequence.** The knob
> is real and the closed form is right. **It is not new, and I should have known that before
> writing it up as a derivation.** What is unclaimed is the *transfer* — reinterpreting it as
> a design parameter for a federated system rather than a fact about breeding.

**Casey's "many many generations to stabilize and cross-mix to have a true chaotic-diffuse"**
is this curve. Not a metaphor for it. The curve, with the plateau being the F2 equilibrium
and the overshoot being the chaotic transient before selection re-establishes the band.

## 4. Why this is worse than a convergence problem in the federated case

The standard worry about averaging is that it converges slowly, or to the wrong place. Both
are recoverable: more rounds, better step sizes.

**The F1 problem is not that.** Consider `n` participants, each holding a sparse observation
set. Let participant `i`'s local estimate be `θ̂_i = θ* + e_i` where the `e_i` are the part of
participant `i`'s knowledge that **nobody else has**. This is not noise. It is the entire
reason the participant is in the federation.

After full averaging, the system knows `mean(θ̂_i)`, which contains:

- `θ*` — the consensus, recovered
- `mean(e_i)` — the average of the private parts, which is **not any of them**
- **nothing else**

`e_1, e_2, …, e_n` are gone. Not shrunk — **destroyed.** They were irretrievable the moment
the mean was taken, because the mean is not invertible. **Two federations with completely
different private knowledge can produce bit-identical averages.**

This is the sharp statement:

> **Averaging is many-to-one. Anything it maps to the same point is, to the federation,
> the same forever.** With sparse per-participant information, the between-participant
> variance *is* the information, and the mean is precisely the operation that destroys it.

This is why the F1 state is so seductive and so fatal. It *looks* like success. The loss
function goes down. The weights agree. **And the agreement is the damage.**

## 5. What the sociology observation is actually pointing at

> "a lot happening in socialology that sees and reflects the movement of information across weight"

Two directions of reading, and they have different prescriptions:

**(a) Reflection as measurement.** An observer reads the ripple pattern and infers what was
injected. This is a *read-out* of the F2 structure from outside. It works precisely because
the transient before equilibration is chaotic and information-rich. **The transient is the
signal.** A system observed after equilibration has thrown its information away, which is
why sociology's own methods — narrative, ethnography, discourse — are instruments of
observation *of people who have not yet averaged*.

**(b) Reflection as a term in the operator.** If a system can observe itself mid-flow and
feed that back, the effective operator is no longer the diffusion operator. It has a term
that depends on the current pattern. **This is a different dynamical system, not a noisy
version of the same one.**

I think (b) is the more consequential and I would want it tested. The observation is cheap
(you can watch the ripples) and it changes the operator rather than the parameters.

## 6. Where MothQuantum and micromoth-quilt would have to act

I want to be careful, because I can state the requirement precisely and I should not pretend
to state the mechanism.

**The requirement.** In the equation above, the term that gets you out of the F1 state is
`σξ`, and its job is to inject *variance* while injecting *no information*. Any noise that
correlates with the participants' private knowledge re-imports the thing the averaging just
destroyed, which is not a bug but it does not help: it means the diversity is fake, because
it is recoverable from the private data anyway.

**So the randomness must be independent of `e_i`.** That is a real, checkable constraint, and
it is sharper than "add noise."

**What quantum randomness would have to do differently from classical.** Classical Gaussian
noise gives `Var(∞) = σ²/2k` for a linear restoring term — a clean, well-understood law. Two
things would make the quantum case genuinely different rather than decorative:

1. **Non-Gaussian amplitude structure.** If the "noise" is an amplitude drawn from a
   superposition and the update projects it, the effective injected variance is not
   σ² and the stationary law changes shape. The plateau stops being `σ²/2k` and becomes
   something with structure. **That is testable: measure the variance spectrum of the
   equilibrium and check whether it is Gaussian.**
2. **Discontinuous updates.** A projector is not a small step. A small-diffusion limit does
   not apply, and the F1 collapse — which is a *continuum* result — may not happen at all.
   **That is the strongest version of the claim: a quantum-discontinuous update is not a
   noisy F1, it is not an F1, and the uniform state may be unreachable rather than
   merely unstable.**

The second is the interesting one. **The collapse is a theorem about continuous averaging.
Break the continuity and you do not get a better-averaged version; you get a different
system.**

**Why `micromoth-quilt` is the right substrate rather than a metaphor.** The F2 requirement is
that recombination be *stochastic per-participant* rather than *deterministic per-round*.
A lattice of small independent agents, each with its own private `e_i`, each applying its own
stochastic operator, is the literal shape of F2 recombination. Not a swarm averaging a
centroid — a population in which **the parents differ**, so the children are not all the same.

## 7. Falsification, stated so it can be attacked

| Prediction | If it fails |
|---|---|
| Averaging variance decays geometrically, `2^(-n)` | My model of the operator is wrong. Check whether the real operator is a mean at all. |
| The equilibrium variance is `σ²/2k`, Gaussian | Something is injecting structure. Look for a hidden shared state. |
| **The F1 uniform state is reachable and absorbing** under deterministic averaging | Strongest claim, and the most falsifiable. If the system does not collapse, my operator model is wrong. |
| Two federations with different private knowledge produce **identical** averages | If not, the private information is recoverable and the whole framing weakens. This is directly checkable and I am confident. |
| Quantum-discontinuous update makes the uniform state **unreachable**, not merely slow | If the collapse still happens, quantum randomness here is decoration and I should say so. |

**The last row is the load-bearing one and it is cheap to test.**

## 7b. Prior art — what the scout lane found, and what it took away

I sent a lane to try to break this. **It succeeded, in four places, and I am recording all of
them rather than the flattering parts.**

### Taken away

1. **`σ²/2k` is 50-year-old textbook.** Mutation–selection balance, `2μ/S` per locus. See
   the correction in §3. I derived it as if it were new.
2. **The phenomenon is already named in the federated literature.** Tian, Al-Ars, Kitsak &
   Hofstee (2024), *"Vanishing Variance Problem in Fully Decentralized Neural-Network
   Systems"*, arXiv:2404.04616. **The observation is not new.** I had not heard of it.
3. **The "destruction" reading is weakened inside the genetic frame.** The Bulmer effect
   redistributes variance among loci rather than destroying it, so variance per locus is not
   conserved under the mechanism I invoked. I overstated.
4. **"Fruit-fly decomposition" is not a body of work I want.** The scout traced it to FFOA
   (Fly-Finder/Open-Alpha of a literature) and VMD. **Zero occurrences in the fleet.** The
   term should be dropped rather than reclaimed.

### Surviving, and sharper for having been attacked

1. **The framing gap is real and the scout verified it.** Eight targeted searches across arXiv
   and OpenAlex: **every paper frames non-IID heterogeneity as slow convergence, never as
   information loss.** SCAFFOLD (arXiv:1910.06378, 709 citations) names it *client drift* and
   means **gradient** variance. FedAvg (McMahan et al., 5,115 citations) does not treat
   heterogeneity as a loss of information at all. **Concept-space variance is a different
   quantity from gradient variance, and nobody is conflating them because nobody is claiming
   it.**
2. **Tian et al. frame it as an optimisation defect** — vanishing variance breaks Xavier
   initialisation and kills activations. My claim is that it is an **information** defect. The
   same arithmetic, a different reading, and the information reading is the one that does not
   go away when you fix the optimiser.
3. **The mean-field machinery has not been applied here.** OpenAlex
   `title.search:"mean field federated learning"` returns **15 works total.** The tools to
   reason about this exist; nobody has pointed them at it.
4. **The operator distinction — deterministic averaging versus stochastic recombination — is
   the part no paper makes.** That is where the contribution is, and it is narrower than the
   whole document but it is defensible.

### A fleet finding that is not about me

The scout checked the 26xx.* arXiv IDs the fleet cites and found **two that return 404**:
`2610.00001` and `2609.50000`, both cited twice. Four more resolved to real papers but with
**titles the fleet did not match** — one is described in the fleet as a memory-poisoning
defence and is actually *"Injection-Execution Dissociation"*; another is cited as "Music-JEPA
with LeCun" and is *"Music-JEPA: Learning a World Model of Sound"*. **Something in the
citation path is generating plausible identifiers.** Six checked, two fabricated, two
mismatched, two honest.

## 8. What I do not know

- **Whether this is already named somewhere — ANSWERED, and the answer is partly yes.** See
  §7b. The phenomenon is named; the framing and the operator distinction are not.
- Whether "movement of information across weight" in the sociological literature means what
  I have made it mean here.
- Whether the F2 recombination reading survives contact with a real substrate, or whether
  `micromoth-quilt` turns out to be a mean field with extra steps — which is a live and
  unglamorous possibility.
- **What the right `k` is, and therefore what the right target diversity is.** The formula
  tells you the knob exists. It does not tell you where to set it, and that is the entire
  design question.
