"""APP 1: `sift` -- "the tool said the wrong thing. Which line of MY code is it?"

A practitioner problem with a deadline today. The local account has ~36 repos of
real verification tools. Every one of them emits findings. When a finding is WRONG,
the engineer must decide where in their own code the tool's assumption broke.

THE APP IS CHOOSER-AGNOSTIC. It has no scoring, no ranking, no preference.
It: (1) holds state, (2) enumerates the legal candidate sites, (3) renders them.
A judge decides. This file's sha256 is asserted identical across judge swaps.
"""
from __future__ import annotations
import ast, hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from seam import Option, View, FEATURE_SCHEMA, run_app

# ── STATE ────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Obs:
    oid: str
    task: str            # what the practitioner was doing
    symptom: str         # what the tool actually printed (REAL, harvested)
    module: str          # the file the engineer suspects
    trace: tuple         # REAL harvested frames: (file, line, func)
    oracle: str          # documented root cause -- held by the SCORER, never shown
    tier: str            # "A" traceback visible, "B" symptom only
    root: str = "/workspace/projects"

# ── ENUMERATION ──────────────────────────────────────────────────────────────
def enumerate_sites(obs: Obs) -> tuple[Option, ...]:
    """Deterministic. No judgment. Every legal place the tool's assumption could
    live: each top-level def/class, each method, and each module-level statement
    block, in source order. Stable ids = file::qualname@line."""
    path = Path(obs.root) / obs.module
    src = path.read_text()
    tree = ast.parse(src)
    lines = src.splitlines()
    out: list[Option] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            end = getattr(node, "end_lineno", node.lineno)
            body = "\n".join(lines[node.lineno - 1:end])
            out.append(Option(
                id=f"{obs.module}::{node.name}@{node.lineno}",
                state={"kind": type(node).__name__, "name": node.name,
                       "lineno": node.lineno, "end": end, "src": body},
                text=f"{type(node).__name__} {node.name} (L{node.lineno}-{end})",
            ))
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.Expr, ast.If, ast.For,
                               ast.While, ast.Try, ast.With)):
            end = getattr(node, "end_lineno", node.lineno)
            body = "\n".join(lines[node.lineno - 1:end])
            name = getattr(getattr(node, "targets", [None])[0], "id", None) \
                   if isinstance(node, ast.Assign) else type(node).__name__
            out.append(Option(
                id=f"{obs.module}::<{name}>@{node.lineno}",
                state={"kind": type(node).__name__, "name": name or type(node).__name__,
                       "lineno": node.lineno, "end": end, "src": body},
                text=f"module-level {name or type(node).__name__} (L{node.lineno}-{end})",
            ))
    return tuple(out)

# ── RENDER ───────────────────────────────────────────────────────────────────
def _features(obs: Obs, opt: Option, order: int, n: int) -> tuple[dict, list]:
    """Compute the CONTRACT feature vector. Features the app cannot know are
    supplied as neutral AND RECORDED as fabricated -- the cost of the seam."""
    st = opt.state
    on_trace = [i for i, f in enumerate(obs.trace)
                if f["func"] == st["name"] and f["line"] == st["lineno"]]
    fab: list[str] = []
    if obs.tier == "B":
        # The engineer has a wrong OUTPUT, not a traceback. There is no
        # traceback feature to compute. These two are fabricated, not guessed.
        fab += ["in_trace", "depth"]
        f = {"in_trace": 0.0, "depth": -1.0}
    else:
        if on_trace:
            f = {"in_trace": 1.0, "depth": float(min(on_trace))}
        else:
            fab += ["depth"]          # not on the trace: depth is undefined
            f = {"in_trace": 0.0, "depth": -1.0}
    f["same_file"] = 1.0
    f["has_literal"] = 0.0
    f["named"] = 1.0 if st["name"] and st["name"] in obs.symptom else 0.0
    f["size"] = min(1.0, (st["end"] - st["lineno"] + 1) / 120.0)
    f["rank_prior"] = order / max(1, n - 1)
    for k in FEATURE_SCHEMA:
        f.setdefault(k, 0.0)
    return f, fab

def render_sift(options: tuple[Option, ...], obs: Obs, style: str) -> View:
    n = len(options)
    items, fab_seen = [], set()
    for i, o in enumerate(options):
        feats, fab = _features(obs, o, i, n)
        fab_seen.update(fab)
        st = o.state
        if style == "source":
            body = st["src"][:400]
        elif style == "sig":
            body = st["src"].splitlines()[0][:200] if st["src"] else ""
        else:
            raise ValueError(f"unknown render style {style!r}")
        items.append((o.id, f"{o.text}\n{body}", feats))
    return View(
        oid=obs.oid,
        question=(f"You are debugging this real failure.\nTASK: {obs.task}\n"
                  f"SYMPTOM (verbatim tool output):\n{obs.symptom}\n"
                  f"Pick the ONE site that is the true root cause."),
        items=tuple(items),
        extra={"fabricated": tuple(sorted(fab_seen)), "tier": obs.tier,
               "n_options": n, "style": style},
    )

APP1_SHA = None
def app1_sha() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

def run(obs: Obs, chooser, style: str = "source") -> dict:
    return run_app(enumerate_sites, render_sift, obs, chooser, style)
