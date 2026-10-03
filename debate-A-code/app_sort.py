"""APP 2: `sort` -- a DIFFERENT practitioner job, a DIFFERENT state, a DIFFERENT
render, the SAME seam. "I have 40 changed files and 90 minutes. What do I read
first?"  This app is NOT a rename of sift: different state type, different
enumeration rules, different render, different question text.

It exists to test C3 -- whether a judge written for sift runs here UNCHANGED.
"""
from __future__ import annotations
import ast, hashlib
from dataclasses import dataclass
from pathlib import Path
from seam import Option, View, FEATURE_SCHEMA, run_app

@dataclass(frozen=True)
class Rev:
    oid: str
    task: str
    symptom: str        # what the reviewer sees: the diffstat + the time budget
    files: tuple        # (relpath, n_lines_changed, n_public_symbols)
    oracle: str

def enumerate_sites(obs: Rev) -> tuple[Option, ...]:
    out = []
    for i, (rel, nlines, nsym) in enumerate(obs.files):
        out.append(Option(id=f"{rel}#hunk",
                          state={"rel": rel, "nlines": nlines, "nsym": nsym,
                                 "text": f"{rel}: {nlines} lines changed, {nsym} public symbols"},
                          text=f"{rel} ({nlines} lines, {nsym} symbols)"))
    return tuple(out)

def render_sort(options, obs: Rev, style: str) -> View:
    n = len(options); items = []; fab = set()
    for i, o in enumerate(options):
        st = o.state
        # This app has NO traceback and NO symptom naming a function. Three of
        # the seven contract features have no honest value here. It must supply
        # neutrals and DECLARE that it did.
        f = {"in_trace": 0.0, "depth": -1.0, "same_file": 0.0,
             "has_literal": 0.0, "named": 0.0,
             "size": min(1.0, st["nlines"] / 120.0),
             "rank_prior": i / max(1, n - 1)}
        fab |= {"in_trace", "depth", "same_file", "has_literal", "named"}
        body = st["text"] if style == "source" else st["rel"]
        items.append((o.id, body, f))
    return View(oid=obs.oid,
                question=f"{obs.task}\n{obs.symptom}\nPick the ONE file to read first.",
                items=tuple(items),
                extra={"fabricated": tuple(sorted(fab)), "tier": "sort", "n_options": n})

def app2_sha() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

def run(obs: Rev, chooser, style: str = "source") -> dict:
    return run_app(enumerate_sites, render_sort, obs, chooser, style)
