# Fishing better — what tonight actually taught, and the instrument that came out of it

**Casey is teaching me like a greenhorn. This is the greenhorn's notes, written back so the
teaching can be checked.** Everything here is a real result from the session, with the file
it came from. Nothing is aspirational.

---

## 1. The chart was wrong, and that is the finding

A bathy chart is a *claim about what's down there*. The whole discipline of this project is
that the chart is drawn from **sounding**, and the sounding is the only thing that counts.

Tonight the chart was wrong four separate times, and every one of them was caught the same
way — **by putting a second, independent instrument in the water.**

| the chart said | the sounding said | what caught it |
|---|---|---|
| "5,127 repos" | 5,108, then 5,113 — and it grows | re-deriving, never hardcoding |
| "180,361 reachable 3×3 states" | **5,478**; a 3×3 board has only 3⁹ = **19,683** distinct states | arithmetic, checked against the size of the space |
| "nine subagent dispatches, zero artifacts" | they were there the whole time | I checked at 15 minutes and called them dead |
| "the 4×4 empty board is +1" | **0 — a draw** | a retrograde table and a plain max-min, both independent of my solver |

**The pattern is not "I make mistakes." The pattern is: a single instrument that agrees with
itself is not a sounding, it is an echo.** The number was wrong four times and the *method*
that caught it was the same every time: **ask something that does not share a code path with
the thing you are measuring.**

## 2. Bathy is one beam. Multi-beam is the upgrade.

**Bathy** = a single point measurement. It answers "how deep here?" and nothing else. Tonight
I took thousands of bathy readings: a single `git ls-files` here, a single API call there. Each
is a real measurement. None of them is a *position*.

**Multi-beam** = several instruments sounding the same thing at once, and you only take a fix
when **they agree**. Every trustworthy result tonight came from that:

- **Connect 4 ground truth**: bitboard negamax, *plus* 2,000 random positions against a plain
  max-min with no negation — different representation, different encoding, different search
  shape. 2000/2000.
- **4×4 game value**: retrograde table over 161,029 states, *plus* plain max-min, *plus* my
  solver, which was wrong. Two instruments said 0 and were right.
- **`voxelglyph`**: the seven green pins were one beam. A mutation of the flagship line was
  the second beam, and the flagship **survived** — a 0-byte sweep replacing 140,608 lattice
  points, and `max()` turned into `min()` so the product reported the *narrowest* class as the
  widest blind spot. **7/7 green, product wrong.** A single beam said the fish was there.
- **My own history-bloat signal**: 106 repos flagged, **36 real**, because the denominator
  could be zero and the flag fired by construction.

**The rule I did not have before tonight, and which I now think is the most useful thing
learned: *one beam tells you a depth. Two beams that agree tell you a position. A beam that
disagrees with the chart is not a malfunction — it is the fish.***

That is why I am not deleting the wrong numbers. **A chart that has been corrected by sounding
is worth more than a chart that was never wrong**, because the correction is evidence about the
water. Every concession in `F1-F2-DIFFUSION.md` and `F1-AUDIT.md` is a sounding log.

## 3. "Cross is mixture" — the mistake that had a whole structure built on it

The one that should be taught hardest, because **it was elegant and it was elementary-wrong.**

I argued that averaging two maximally-distant parties halves the variance, therefore uniform
collapse is geometric, therefore averaging is the F1. The auditor's reply:

> A cross is a **product** `p ⊗ q` — a coupling that fixes the phase. The mixture `(p+q)/2` is
> a **marginal** — what you get by **forgetting the phase**. The mixture is precisely the
> operation that discards the information F1 creates.

**I was arguing from the wrong object, and the mistake was attractive precisely because it was
beautiful.** The identity was *exactly* right — verified to 4.5e-16 — and it was attached to
the wrong thing. A correct calculation in the wrong frame is the most dangerous kind of wrong,
because the arithmetic protects you.

**Fishing version:** I had a beautiful, correct formula for the depth at one spot and was
reading it as the depth of the channel. **Depth at one point is not bathymetry.**

## 4. What survives the audit, and it is better than what died

The auditor was told to find the survivors and state them as if it had written them. What
survived is not a consolation prize:

> **S1. Averaging is a linear projection with a non-trivial kernel, and the between-participant
> component of the private data is annihilated by it. This is a theorem, not a heuristic.**

Two federations differing by any zero-sum vector are **indistinguishable forever** — including
through the average's entire trajectory. That is a stronger and more useful claim than the one
I made, and it is a theorem.

**S3** is the practical one: deterministic averaging really does reach uniform, and nothing
recovers what it destroyed — but the rate is `1 − 4D sin²(π/N)`, **∝ N²/D**. **Larger fleets are
further from uniform, not closer.** My claim had the sign of the scaling backwards, and the
correct sign is *good news* for `micromoth-quilt`: **scale buys time.**

**S4** is the reframe worth keeping: it is not *discontinuity* that saves you, it is **breaking
the attractor** — which needs a conserved constraint excluding the uniform direction. The
median-root operator has a permanent non-uniform state at `V = 0.318`. **My instinct was right
and my conclusion was backwards**, and both of those are facts worth having.

## 5. The autopilot problem, honestly

Casey wants autopilot. Here is the true state, measured rather than guessed.

**What autopilot needs and does not have today:** a way to know, without being asked, that a
lane is finished, and whether the thing it produced is what it claimed.

Tonight I made that mistake **twice** and both times it was the same mistake:

- I declared the whole subagent fleet dead at 15 minutes. **They were producing.**
- I nearly "fixed" a solver to match an assertion I had never verified. **Checking
  independently is the whole discipline, and it took me one step from not doing it.**

**A lane's status is a claim. It needs the same multi-beam treatment as any other claim.** One
beam — "did a file appear" — is what I used, and it is exactly the `voxelglyph` error at the
orchestration layer: **the lane existed, the artifact existed, and the artifact was wrong.**

So the lever is not "delegate more." The lever is **instrument the lanes the way I instrument
the fleet** — and that is the tool in `APPROACH.md`'s sibling, `lanes.py`.

## 6. What a greenhorn should take from this, in the boat's terms

1. **One sounding is not a chart.** Two instruments agreeing is a position.
2. **A correct calculation in the wrong frame is worse than a rough one in the right one.** The
   arithmetic will protect you from nothing.
3. **The chart being wrong is not a failure of the chart.** It is a sounding that arrived.
   Keep the log.
4. **The fish is the disagreement.** If your instruments agree with each other and not with
   your expectation, *you* are the thing being measured.
5. **Time is the distance between two soundings.** `N²/D` means the bigger the fleet, the
   longer you have before uniform — and that is a design choice, not a fate.
6. **Nobody fishes the channel alone.** The drag is the agreement; the bathy chart is shared
   memory; the canary is what tells you the chart still matches the bottom.

---

**The honest accounting of this session, as a fishing log:** the chart was wrong four times, one
of my documents was withdrawn in part, one of my own repos shipped a verification suite that
never ran the thing it verified, and two subagent lanes found errors in briefs I wrote. Every
one of those was caught by a second instrument. **The catch rate is the result, not the
losses.**
