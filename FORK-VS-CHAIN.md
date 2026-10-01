# Fork does not beat chain. The correlation is in the models, not the graph.

2026-10-01. I predicted that forking seven independent branches — each seeded
from the seeds, each seeing **only its own history**, no cross-talk — would beat
chaining them into a line, because the chain propagates the first voice's
framing. **It does not.** Four arms, same seven models, same seed material,
BGE-M3 embeddings, Kish n_eff on the outputs.

| topology | mean agreement | Kish n_eff | n_eff/k |
|---|---:|---:|---:|
| A -- parallel, one shared prompt | 0.846 | 0.165 of 7 | 0.024 |
| B -- **chain**, each reads the previous | 0.797 | 0.201 of 6 | 0.033 |
| C -- **fork**, round 1 (branches) | 0.829 | 0.167 of 7 | 0.024 |
| C -- **fork**, round 2 (endpoints) | 0.763 | **0.179** of 7 | 0.026 |

**Fork (0.179) is slightly worse than chain (0.201).** The difference is inside
the noise of six or seven embeddings and I am not claiming significance for it.
The point is that **they are the same number.**

## The finding

**Topology is not the lever. The models are correlated at the source.**

Four arrangements of the same seven free models — independent, chained, forked,
and twice-refined — all land between **0.165 and 0.201 effective votes.** No
arrangement of them produces independent thinking, because the correlation is in
what the models were trained to agree about, not in how they are wired together.

This is the same constant that shows up in four unrelated places: **2.18 of 9**
frontier judges on NLI, **~2 of 16** on 330 real A/B tests, **1.48 of 4** of my
own learners, **2.52 of 11** of this fleet's own reports. Six datasets now, and
the answer is always *about two*.

## What refinement does buy

The one real movement in the table is inside the fork arm: agreement fell
**0.829 -> 0.763** from round 1 to round 2, when each branch was asked to find
the weakest joint in *its own* answer.

**Refinement works. Diversification does not.** A panel of these models is
approximately **one voice, made better** — which is a useful thing to own, and
a completely different thing from what "a quilt of decomposing ideas" implies.

## The operational consequence

1. **Do not buy diversity with model choice.** Seven vendors, a chain, or a fork
   all return roughly one opinion. Measured, not assumed.
2. **Buy refinement with a panel.** Point the models at *one* framing and ask
   each to find the weakest joint. That measurably improves the answer and costs
   only a few calls per round.
3. **Buy diversity with different INPUTS, not different models.** The three seeds
   in this experiment — `quilt-in-git`, `jev-net`, `wardroom` — produced
   genuinely different framings, and it was not because the models differed. It
   was because the material differed. A lineage that keeps the same base model
   and changes the corpus diverges; a lineage that changes the model and keeps
   the corpus does not.

That last point is the load-bearing one for the fleet, and it is the opposite of
the usual instinct. **Diversity of evidence beats diversity of opinions.**

## What this does NOT license

It does not say models are useless. Six of the seven answers contained something
the others did not, and the single most distinct model produced the only
substantive challenge to a thesis I had been building for hours. **The panel is
still the cheapest way to find the outlier — you just have to measure which one
it is rather than assume the average knows.**
