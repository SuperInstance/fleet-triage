"""THE APP. This file is the thing whose hash must not change when choosers change.

A capacity-allocation app. The app owns the world, the legality rules, and the
enumeration. A chooser never invents an option; it only ranks what the app hands it.

This is deliberately small. The claim under test is about the SEAM, not about
allocation. Every number here is chosen so that the enumeration is genuinely
finite and genuinely the app's own business.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict

# ---------------------------------------------------------------- the world

TASKS = ("triage", "discharge", "pharmacy")
DEMAND = {"triage": 7, "discharge": 5, "pharmacy": 3}
SUPPLY = 11
STEP = 2  # the app's own quantum: it only ever moves whole lots of `STEP` units


@dataclass(frozen=True)
class State:
    """Allocation of the supply across the tasks. The app's entire world state."""

    alloc: tuple[int, ...]
    spent: int

    def text(self) -> str:
        parts = ", ".join(f"{t}={a}" for t, a in zip(TASKS, self.alloc))
        return f"alloc[{parts}] spent={self.spent}/{SUPPLY}"


@dataclass(frozen=True)
class Option:
    """One legal move, as the app understands it. The app mints these; the
    chooser only ever reads them."""

    id: str
    state: State
    text: str
    deficit: int  # total unmet demand after the move; a fixed statistic of state


    def commit(self, alloc: tuple[int, ...]) -> State:
        """A generated configuration arrives as a POINT, not an id. The
        app must learn to accept it. This method IS the seam leak: it exists
        only because a chooser stopped ranking."""
        if len(alloc) != len(TASKS):
            raise ValueError("commit: wrong arity")
        return _mk(tuple(alloc))


@dataclass(frozen=True)
class Decision:
    """What a chooser returns. `pick` is an option id or None (refusal).
    `probs` is a distribution over option ids or None (honest 'I have no
    distribution'). `confidence` is a scalar IN [0,1] and is NEVER a substitute
    for a distribution."""

    pick: str | None
    probs: dict[str, float] | None
    confidence: float | None
    source: str
    note: str = ""


# ---------------------------------------------------------------- the rules

def _mk(alloc: tuple[int, ...]) -> State:
    return State(alloc=alloc, spent=sum(alloc))


def legal_moves(state: State) -> tuple[Option, ...]:
    """THE ENUMERATION. One task, one lot, per option.

    This is a rank-1 product space: (#tasks) x (#lots that fit). It is finite,
    it is the app's, and it is the constraint the whole lane is about.
    """
    out: list[Option] = []
    for i, task in enumerate(TASKS):
        room = SUPPLY - state.spent
        lots = min(DEMAND[task] - state.alloc[i], room) // STEP
        for k in range(1, lots + 1):
            nxt = list(state.alloc)
            nxt[i] += k * STEP
            st = _mk(tuple(nxt))
            out.append(
                Option(
                    id=f"{task}+{k * STEP}",
                    state=st,
                    text=f"move {k * STEP} to {task}",
                    deficit=sum(max(0, DEMAND[t] - a) for t, a in zip(TASKS, st.alloc)),
                )
            )
    return tuple(out)


def apply_option(state: State, opt_id: str) -> State:
    """The app applies a move BY ID. This is the hard local constraint: the app
    can only execute what it named. See leak_probe() in run.py."""
    for o in legal_moves(state):
        if o.id == opt_id:
            return o.state
    raise KeyError(f"app cannot apply unknown move {opt_id!r}")


def view(state: State) -> dict:
    """Read-only render handed to choosers. Choosers get data, not authority."""
    return {
        "state": state.text(),
        "supply": SUPPLY,
        "demand": dict(DEMAND),
        "step": STEP,
    }


# ---------------------------------------------------------------- the loop

def play(chooser, max_turns: int = 12) -> dict:
    """One episode. The app drives; the chooser only speaks at the seam.

    `chooser=None` is a RUN MODE, not a fallback: the app must still terminate.
    """
    state = _mk((0, 0, 0))
    turns: list[dict] = []
    refusals = 0
    for _ in range(max_turns):
        options = legal_moves(state)
        if not options:
            break
        if chooser is None:
            turns.append({"state": state.text(), "turn": "no-chooser", "refusal": False})
            break
        d = chooser.choose(options, view(state))
        if d.pick is None:
            refusals += 1
            turns.append(
                {
                    "state": state.text(),
                    "turn": "REFUSED",
                    "source": d.source,
                    "confidence": d.confidence,
                    "note": d.note,
                    "refusal": True,
                }
            )
            break
        if d.pick not in {o.id for o in options}:
            # A chooser handed back something the app never offered. The app does
            # NOT silently accept it. This is the leak, surfaced at runtime.
            turns.append(
                {
                    "state": state.text(),
                    "turn": "OFF-CATALOG",
                    "source": d.source,
                    "pick": d.pick,
                    "note": d.note,
                    "refusal": False,
                }
            )
            break
        state = apply_option(state, d.pick)
        turns.append(
            {
                "state": state.text(),
                "turn": d.pick,
                "source": d.source,
                "probs": d.probs,
                "confidence": d.confidence,
                "refusal": False,
            }
        )
    return {
        "final": state.text(),
        "deficit": sum(max(0, DEMAND[t] - a) for t, a in zip(TASKS, state.alloc)),
        "refusals": refusals,
        "turns": turns,
    }


def app_sha() -> str:
    """The measurement. sha256 of THIS file's bytes, excluding nothing."""
    with open(__file__, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def app_digest() -> str:
    return app_sha()[:16]
