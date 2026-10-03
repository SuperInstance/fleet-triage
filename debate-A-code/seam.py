"""THE SEAM. Contract only: no domain knowledge, no judgment, no ranking.

If a chooser needs a method that is not here, the seam is decorative and that
is the finding.  One method: choose().
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol, Mapping, Any
import math, time

# ---------------------------------------------------------------- fixed schema
# The View's feature vector.  This is PART OF THE SEAM CONTRACT: a chooser is
# allowed to assume every key exists.  Apps that have no natural value for a key
# must supply a neutral one, and we COUNT how many they had to fabricate.
# That count is the measured cost of the seam.
FEATURE_SCHEMA: tuple[str, ...] = (
    "in_trace",     # 1 if this site is on the real traceback, else 0
    "depth",        # 0 = deepest frame, -1 if not on the traceback
    "same_file",    # 1 if in the file a practitioner opened first
    "has_literal",  # 1 if the site contains the observed wrong literal
    "named",        # 1 if the function name appears in the symptom text
    "size",         # site source size, normalised to [0,1]
    "rank_prior",   # position in the app's enumeration order, [0,1]
)

@dataclass(frozen=True)
class Option:
    id: str                 # stable string, produced by the APP never the chooser
    state: Any              # the world after taking it (here: the AST node + loc)
    text: str               # human-readable label

@dataclass(frozen=True)
class View:
    """Read-only render of the current state, for a chooser to reason over."""
    oid: str
    question: str
    items: tuple[tuple[str, str, Mapping[str, float]], ...]  # (id, text, features)
    extra: Mapping[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class Decision:
    pick: str
    probs: dict[str, float] | None      # None is LEGAL: a hard statistic or a
    confidence: float | None            # human may honestly have no distribution
    source: str

class Chooser(Protocol):
    def choose(self, options: tuple[Option, ...], ctx: View) -> Decision: ...

# ---------------------------------------------------------------- generic driver
class Blocked(Exception):
    """Credential/transport failure. NOT a wrong answer. Counted, never scored."""

def softmax(xs: list[float]) -> dict[int, float]:
    m = max(xs); e = [math.exp(x - m) for x in xs]
    s = sum(e)
    return {i: v / s for i, v in enumerate(e)}

def run_app(enumerate_fn, render_fn, obs, chooser: Chooser, render_style: str) -> dict:
    """THE APP. Chooser-agnostic by construction: it calls choose() once and
    returns whatever came back.  It never sorts by preference and never scores."""
    t0 = time.perf_counter()
    options: tuple[Option, ...] = enumerate_fn(obs)          # general: state+enum
    view: View = render_fn(options, obs, render_style)       # specific: the render
    t_enum = time.perf_counter() - t0
    t1 = time.perf_counter()
    dec = chooser.choose(options, view)                      # THE SEAM. One call.
    t_choose = time.perf_counter() - t1
    fabricated = tuple(view.extra.get("fabricated", ()))
    n_fabricated = len(fabricated)
    return {
        "oid": obs.oid,
        "n_options": len(options),
        "enum_ms": t_enum * 1000,
        "choose_ms": t_choose * 1000,
        "decision": dec,
        "render_style": render_style,
        "fabricated_features": fabricated,
        "n_fabricated": n_fabricated,
    }
