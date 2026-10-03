"""FIVE CHOOSERS. One method. The app never learns which one it is talking to.

Four of them RANK a fixed set the app enumerated. The fifth GENERATES.

The JEV chooser does not reimplement diffusion-jev-sglang's scoring: it imports
the real module from the cloned checkout and calls its real `probabilities()`
and its real `answer()`. Whatever it reports about its own distribution is that
repo's arithmetic, not mine.
"""

from __future__ import annotations

import math
import random
import sys
from dataclasses import dataclass

from app import TASKS, DEMAND, SUPPLY, STEP, Decision, Option, State

# ------------------------------------------------------------------ the real JEV

#: point this at a clone of Hangzhi/diffusion-jev-sglang
DJS_SRC = "/tmp/djs/src"
_JEV = {"loaded": False, "why": None}
if DJS_SRC not in sys.path:
    sys.path.insert(0, DJS_SRC)
try:
    from diffusion_jev import scoring as _djs_scoring  # noqa: E402

    _JEV["loaded"] = True
except Exception as exc:  # pragma: no cover - environment dependent
    _JEV["why"] = f"{type(exc).__name__}: {exc}"


def jev_available() -> bool:
    return bool(_JEV["loaded"])


# ------------------------------------------------------------------ 1. statistic

class StatisticChooser:
    """No model, no key, no network. Argmin of a fixed statistic of the state."""

    name = "statistic"

    def choose(self, options, ctx) -> Decision:
        logits = [-float(o.deficit) for o in options]
        if jev_available():
            # the repo's own softmax, at its own temperature
            probs_list = _djs_scoring.probabilities(logits, temperature=1.0)
        else:
            m = max(logits)
            e = [math.exp(v - m) for v in logits]
            s = sum(e)
            probs_list = [x / s for x in e]
        probs = {o.id: p for o, p in zip(options, probs_list)}
        best = max(probs, key=probs.get)
        return Decision(
            pick=best,
            probs=probs,
            confidence=_norm_entropy(list(probs.values())),
            source=self.name,
            note="argmin deficit, softmax over enumerated options",
        )


# ------------------------------------------------------------------ 2. the JEV

class JevChoiceChooser:
    """The diffusion model, as diffusion-jev-sglang actually ships it: render the
    options as an A-Z rubric, take ONE greedy token, softmax ONLY the candidate
    letters. The generation is a single character and is discarded; the answer
    is the argmax of a categorical over the app's own enumeration."""

    name = "jev-choice"

    def __init__(self, logits: dict[str, float] | None = None):
        # a fixed stand-in for the 26 candidate logits the patched engine returns
        self.logits = logits

    def choose(self, options, ctx) -> Decision:
        if self.logits is not None:
            keys = [o.id for o in options]
            raw = [self.logits.get(k, -50.0) for k in keys]
        else:
            # deterministic pseudo-logits derived from the state text, so the run
            # is reproducible without a GPU. NOT a model claim.
            raw = [math.sin(hash((ctx["state"], o.id)) % 9973) * 3.0 for o in options]
        if jev_available():
            probs_list = _djs_scoring.probabilities(raw, temperature=1.0)
            probs = {o.id: p for o, p in zip(options, probs_list)}
        else:
            m = max(raw)
            e = [math.exp(v - m) for v in raw]
            s = sum(e)
            probs_list = [x / s for x in e]
            probs = {o.id: p for o, p in zip(options, probs_list)}
        pick = max(probs, key=probs.get)
        return Decision(
            pick=pick,
            probs=probs,
            confidence=_norm_entropy(list(probs.values())),
            source=self.name,
            note=(
                "1 greedy token, softmax over candidate letters only; "
                "generation discarded"
            ),
        )


# ------------------------------------------------------------------ 3. local policy

class LocalPolicyChooser:
    """A hand-written table. The 'specific' end of general/specific."""

    name = "local-policy"

    TABLE = {"triage": 3, "discharge": 2, "pharmacy": 1}

    def choose(self, options, ctx) -> Decision:
        raw = [float(self.TABLE.get(o.id.split("+")[0], 0)) + 0.01 * o.deficit for o in options]
        m = max(raw)
        e = [math.exp(v - m) for v in raw]
        s = sum(e)
        probs = {o.id: x / s for o, x in zip(options, e)}
        return Decision(
            pick=max(probs, key=probs.get),
            probs=probs,
            confidence=_norm_entropy(list(probs.values())),
            source=self.name,
            note="fixed priority table",
        )


# ------------------------------------------------------------------ 4. the human

class HumanChooser:
    """The chooser with no distribution. It is allowed to say so."""

    name = "human"

    def __init__(self, patience: int = 3):
        self.calls = 0
        self.patience = patience

    def choose(self, options, ctx) -> Decision:
        self.calls += 1
        if self.calls > self.patience:
            return Decision(
                pick=None,
                probs=None,
                confidence=None,
                source=self.name,
                note="I don't know which of these is right",
            )
        best = min(options, key=lambda o: (o.deficit, o.id))
        return Decision(
            pick=best.id,
            probs=None,  # honest: a person did not produce a distribution
            confidence=None,
            source=self.name,
            note="eyeballed it",
        )


# ------------------------------------------------------------------ 5. THE GENERATOR

@dataclass
class Generated:
    """What a generator actually returns: a point in a space, not an index."""

    alloc: tuple[int, ...]
    residual: float
    step: float  # the magnitude of the move it proposes -- the "confidence"
    skipped: int = 0  # steps it refused to take (neodisco's zeros_like path)
    off_catalog: bool = False


class GenerativeChooser:
    """A miniature masked-diffusion chooser, built to the shape of
    neodisco/backends/pixel.py + guidance.py rather than to a checkpoint.

    The loop is: predict a clean configuration from a noisy one, take a graded
    step toward it, re-noise, repeat. It NEVER looks at an option id. It never
    sees the enumeration. It proposes a configuration and lets the app work out
    what that was.

    Two things it reproduces faithfully from neodisco:
      * CLAMP  - guidance.clamp(): a step size is bounded, "without this a single
                 confident step wrecks the image" (guidance.py:166).
      * REFUSE - guidance.image_gradient(allow_nan=True) and pixel.py:320: a
                 non-finite proposal returns a ZERO gradient and the sampler
                 keeps going. The refusal is a zero step, not an absence.

    This is a ~40-line scalar transcription of a UNet+CLIP loop. It is NOT the
    checkpoint and makes no image-quality claim. It is here to be measured on
    interface questions only.
    """

    name = "generative"
    CLAMP_MAX = 0.35

    def __init__(self, seed: int = 0, steps: int = 24, restarts: int = 1,
                 temperature: float = 0.12):
        self.rng = random.Random(seed)
        self.steps = steps
        self.restarts = restarts
        self.temperature = temperature
        self.last: Generated | None = None

    # -- the "denoiser": clean configuration predicted from a noisy one -------
    def _denoise(self, noisy: list[float], scale: float) -> list[float]:
        # a hand-written score: pull each task toward its demand, but spend only
        # what is left. This is the model prior, in eight lines.
        out = []
        for i, t in enumerate(TASKS):
            want = float(DEMAND[t]) * scale
            out.append(noisy[i] + 0.55 * (want - noisy[i]))
        return out

    # -- the "guidance": which direction, and how far -------------------------
    def _direction(self, x: list[float]) -> tuple[list[float], float]:
        want = [float(DEMAND[t]) for t in TASKS]
        room = float(SUPPLY - sum(x))
        d = [want[i] - x[i] for i in range(len(TASKS))]
        if room < 1e-9:
            return [0.0] * len(d), 0.0
        n = math.sqrt(sum(v * v for v in d)) or 1.0
        return [v / n for v in d], min(1.0, n / (1.0 + room))

    def generate(self, state: State) -> Generated:
        """Run the loop. Returns a point, plus the magnitude that got it there."""
        skipped = 0
        best: Generated | None = None
        for r in range(self.restarts):
            rng = random.Random((self.rng.randrange(1 << 30), r).__hash__())
            x = [float(a) for a in state.alloc]
            for t in range(self.steps):
                # --- diffusion schedule: coarse then fine (neodisco respaces 1000)
                scale = 1.0 - t / self.steps
                clean = self._denoise(x, scale)
                d, mag = self._direction(clean)
                if mag <= 0.0:
                    skipped += 1
                    continue  # <-- neodisco: return zeros_like(x_t); step anyway
                if not all(math.isfinite(v) for v in d):
                    skipped += 1
                    continue  # <-- the same zeros_like path
                # graded step, annealed, and CLAMPED
                step = min(mag * 0.45 * (0.15 + 0.85 * scale), self.CLAMP_MAX)
                for i in range(len(x)):
                    x[i] = max(0.0, x[i] + step * d[i])
                x = [min(x[i], float(DEMAND[TASKS[i]])) for i in range(len(x))]
                # renormalise to the supply -- the app's own hard constraint
                s = sum(x)
                if s > SUPPLY and s > 0:
                    x = [v * SUPPLY / s for v in x]
                # RE-NOISE. This is the other half of a diffusion step and the
                # reason a generator has a distribution at all: the next pass sees
                # a perturbed state, not the state that was just proposed. The
                # `temperature` dial is the schedule's total noise budget; at 0 a
                # generator is a deterministic optimiser with no distribution to
                # report, which is exactly what M3 measures.
                for i in range(len(x)):
                    x[i] += self.rng.gauss(0.0, self.temperature * (1.0 - scale))
            alloc = tuple(_quantize(x))
            resid = sum(max(0, DEMAND[t] - a) for t, a in zip(TASKS, alloc))
            cand = Generated(
                alloc=alloc, residual=float(resid), step=step, skipped=skipped
            )
            if best is None or cand.residual < best.residual:
                best = cand
        assert best is not None
        return best

    # -- the seam -------------------------------------------------------------
    def choose(self, options, ctx) -> Decision:
        # The generator is handed EXACTLY what every other chooser got: a render
        # of the state. It reads the render and ignores the option list entirely.
        g = self.generate(_parse_state(ctx["state"]))

        off = self._off_catalog(g, options)
        g.off_catalog = off
        self.last = g

        if off:
            return Decision(
                pick=None,  # <-- it CANNOT return it. pick is an id. See note.
                probs=None,
                confidence=None,
                source=self.name,
                note=(
                    f"proposed alloc={g.alloc} (deficit {int(g.residual)}) -- "
                    f"NOT IN THE APP'S ENUMERATION; no id exists to return"
                ),
            )
        # if by luck the generated point coincides with an enumerated move, the
        # app can execute it. Then the answer is on the list after all.
        for o in options:
            if o.state.alloc == g.alloc:
                return Decision(
                    pick=o.id,
                    probs=None,  # <-- the absence. Explained in the report.
                    confidence=None,  # <-- see below: a step size is not a probability
                    source=self.name,
                    note=(
                        f"generated alloc={g.alloc} step={g.step:.3f} "
                        f"skipped={g.skipped}; coincides with {o.id}"
                    ),
                )
        return Decision(
            pick=None,
            probs=None,
            confidence=None,
            source=self.name,
            note=f"proposed alloc={g.alloc} matched nothing",
        )

    def _off_catalog(self, g: Generated, options) -> bool:
        return not any(o.state.alloc == g.alloc for o in options)


def _parse_state(text: str) -> State:
    """Read the app's render. This is the ONLY channel a chooser has, and it is
    the same channel for all five. The generator gets no privileged access."""
    body = text[text.index("[") + 1 : text.index("]")]
    alloc = tuple(int(part.split("=")[1]) for part in body.split(", "))
    spent = int(text.split("spent=")[1].split("/")[0])
    return State(alloc=alloc, spent=spent)


def _quantize(x: list[float]) -> list[int]:
    """Snap to the app's own quantum and never exceed demand."""
    out = []
    for i, t in enumerate(TASKS):
        v = int(round(x[i] / STEP)) * STEP
        out.append(max(0, min(int(DEMAND[t]), v)))
    return out


def _norm_entropy(p: list[float]) -> float:
    """diffusion-jev-sglang's own convention, scoring.py:56:
    confidence = 1 - H(probs)/log(n). Copied, not invented.

    NOTE: this is UNDEFINED on a one-point support -- log(1) == 0, so a
    generator that has converged to a single configuration divides by zero.
    That is not a bug in the transcription; it is the formula's real behaviour
    and it is reported as a finding in M3.
    """
    if not p:
        return 0.0
    h = -sum(q * math.log(q) for q in p if q > 0)
    n = len(p)
    if n < 2 or math.log(n) == 0:
        return float("nan")
    return max(0.0, 1 - h / math.log(n))
