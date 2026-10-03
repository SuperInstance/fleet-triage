"""
TIME-QUERY: the three modes, the anchor, and the test that decides whether
the interface can lie.

  mode 1  full_rate(...)   30 fps -> 300 pages over 10 s
  mode 2  sampled(...)      3 fps ->  30 pages over 10 s
  mode 3  observe(...)      1 reference + k diffs + triggers, evidence both ways

THE THREE DECIDING TESTS (run first, in run.py):
  T1 STILL   scene held still, correct anchor   -> diff MUST be empty
  T2 MOVED   scene moved slightly, same anchor  -> diff MUST be non-empty
  T3 STALE   reference advanced, old anchor     -> MUST DECLINE, not diff

An interface that returns a plausible diff in all three cases is a green badge.
"""

import math
import time
from ascii_substrate import (Rasterizer, build_scene, focal_for, unpack_color,
                             hostile_pose)

# ------------------------------------------------------------------ signal ---


class ControlFailure(Exception):
    """The abstention operation, applied to OBSERVATION rather than to answers.
    Same doctrine as abstain-gate / selectlib's ControlFailure: declining to
    answer.  Here: declining to observe."""


class Observation(object):
    """The ONE shared observation path.  Every mode, every lane, every trigger
    comes through capture().  This is the correlated resource the design
    predicts will bottleneck (n_eff ~= 2 concentrated in the observation layer)."""

    def __init__(self, w=60, h=26, dither_seed=777):
        self.w, self.h = w, h
        self.focal = focal_for(w)
        self.raster = Rasterizer(w, h, dither_seed=dither_seed)
        self.cam = (0.0, 1.5, 0.0, 1.2, 0.0)
        self.epoch = 0                      # bumps whenever the reference advances
        self._cache = {}
        self.captures = 0                  # instrumentation
        self.cache_hits = 0
        self.raster_seconds = 0.0

    def capture(self, t):
        """t is simulation time in seconds.  Deterministic: same t -> same frame."""
        key = round(t, 9)
        if key in self._cache:
            self.cache_hits += 1
            return self._cache[key]
        t0 = time.time()
        f = self.raster.raster(int(round(t * 60)), build_scene(t), self.cam, self.focal)
        self.raster_seconds += time.time() - t0
        self.captures += 1
        self._cache[key] = f
        return f

    def advance_reference(self):
        """The reference page moves on.  Every outstanding anchor is now stale."""
        self.epoch += 1


# ------------------------------------------------------------------ anchor ---


class Anchor(object):
    """A projector with an ordinal.  If the ordinal is wrong the projector lies,
    so the ordinal travels with the reference and is checked on every use."""

    __slots__ = ("epoch", "t", "frame", "digest", "provenance")

    def __init__(self, obs, t):
        self.epoch = obs.epoch
        self.t = t
        self.frame = obs.capture(t)
        self.digest = self.frame.digest()
        self.provenance = self.frame.provenance

    def describe(self):
        return "anchor(t=%.4fs, epoch=%d, digest=%08x, %dx%d, %s)" % (
            self.t, self.epoch, self.digest, self.frame.w, self.frame.h,
            self.provenance)


def _check(anchor, obs):
    if anchor.epoch != obs.epoch:
        raise ControlFailure(
            "STALE ANCHOR: reference was advanced (epoch %d -> %d) after this "
            "anchor was taken at epoch %d.  A diff against it would look like a "
            "diff and be confidently wrong.  DECLINING TO OBSERVE."
            % (anchor.epoch, obs.epoch, anchor.epoch))


# -------------------------------------------------------------------- diff ---


def diff(anchor, obs, t, channels=("char", "color")):
    """Cell-wise diff.  BOTH channels are carried, because the char is depth and
    the colour is identity -- a char-only diff is a diff over a channel that
    cannot tell you what anything is."""
    _check(anchor, obs)
    cur = obs.capture(t)
    ref = anchor.frame
    changed, per_channel = [], {"char": 0, "color": 0}
    for i in range(obs.w):
        for j in range(obs.h):
            dc = ("char" in channels) and ref.data[i][j] != cur.data[i][j]
            dk = ("color" in channels) and ref.color[i][j] != cur.color[i][j]
            if dc:
                per_channel["char"] += 1
            if dk:
                per_channel["color"] += 1
            if dc or dk:
                changed.append((i, j, ref.data[i][j], cur.data[i][j],
                                ref.color[i][j], cur.color[i][j],
                                ref.owner_name(i, j), cur.owner_name(i, j)))
    return {"n_changed": len(changed), "per_channel": per_channel,
            "cells": changed, "frame": cur}


# ------------------------------------------------------------------ MODES ----


def mode_full_rate(obs, t0, dur, fps=30):
    """MODE 1.  Everything, at the requested rate.  30 fps x 10 s = 300 pages."""
    n = int(round(dur * fps))
    step = 1.0 / fps
    pages = [obs.capture(t0 + k * step).page() for k in range(n)]
    return {"mode": "full_rate", "fps": fps, "pages": len(pages),
            "chars": sum(len(p) for p in pages), "text": pages,
            "provenance": obs.capture(t0).provenance}


def mode_sampled(obs, t0, dur, fps=3):
    """MODE 2.  Sampled.  Cheap, and it ALIASES -- the failure nobody warns
    you about, because sampling feels like throwing information away when it
    is throwing away a specific class of it."""
    n = int(round(dur * fps))
    step = 1.0 / fps
    pages, times = [], []
    for k in range(n):
        t = t0 + k * step
        pages.append(obs.capture(t).page())
        times.append(t)
    return {"mode": "sampled", "fps": fps, "pages": len(pages),
            "chars": sum(len(p) for p in pages), "text": pages,
            "sample_times": times, "provenance": obs.capture(t0).provenance}


def mode_observe(obs, anchor, times, triggers=()):
    """MODE 3.  One reference page + k diffs + triggers.

    The diffs are L4 (irreversible: they keep the change and drop the state),
    which is precisely why the reference page is in the payload.
    """
    _check(anchor, obs)
    diffs = [diff(anchor, obs, t) for t in times]
    return {"mode": "observe",
            "reference": {"t": anchor.t, "epoch": anchor.epoch,
                          "page": anchor.frame.page(),
                          "provenance": anchor.provenance},
            "diffs": [{"t": t, "n_changed": d["n_changed"],
                       "per_channel": d["per_channel"],
                       "cells": d["cells"]} for t, d in zip(times, diffs)],
            "triggers": [evaluate_trigger(obs, anchor, tr) for tr in triggers],
            "chars": len(anchor.frame.page()) +
                     sum(len(str(d["cells"])) for d in diffs)}


# ---------------------------------------------------------------- trigger ----


def evaluate_trigger(obs, anchor, trig):
    """The LLM supplies an ASSUMPTION OF NEED.  The system returns evidence FOR
    or AGAINST it.  An interface that can only confirm is a cache with a query
    language."""
    _check(anchor, obs)
    kind = trig["kind"]
    if kind == "still":
        # The ASSUMPTION is about the OBJECT, so the verdict is taken from the
        # SCENE GRAPH (the pose), and the frame-level diff is the EVIDENCE.
        # An earlier version judged 'moved' by per-cell overlap, which a fast
        # object never has -- it leaves no cell owned by itself on both sides,
        # so a moving hostile read as OCCLUDED.  That instrument could not fail.
        t = trig["t"]
        d = diff(anchor, obs, t)
        k = trig["target"].split("_")[-1]
        try:
            k = int(k)
        except ValueError:
            k = None            # a static scene object has no pose
        p0 = hostile_pose(anchor.t, k) if k is not None else None
        p1 = hostile_pose(t, k) if k is not None else None
        moved_world = (p0 is not None and
                       (abs(p0["x"] - p1["x"]) + abs(p0["y"] - p1["y"]) +
                        abs(p0["z"] - p1["z"])) > 1e-6)
        def owned(f):
            return set((i, j) for j in range(obs.h) for i in range(obs.w)
                       if f.owner_name(i, j) == trig["target"])
        ref_set, cur_set = owned(anchor.frame), owned(obs.capture(t))
        lost, gained = ref_set - cur_set, cur_set - ref_set
        if trig.get("static"):
            # a static target: only occlusion can change its cells
            v = "UPHELD" if (ref_set == cur_set) else "OCCLUDED"
            stance = ("the target's own cells are unchanged; something moved in "
                      "front of it -- NEITHER for nor against" if v == "OCCLUDED"
                      else "no evidence either way")
            truth_moved = False
        else:
            v = "REFUTED" if moved_world else "UPHELD"
            stance = ("evidence AGAINST the assumption of need" if v == "REFUTED"
                      else "no evidence either way")
            truth_moved = moved_world
        # does the FRAME-LEVEL evidence agree with the scene-graph truth?
        evidence_says_moved = bool(lost or gained)
        return {"trigger": trig, "verdict": v,
                "evidence": {"world_pose_ref": None if p0 is None else
                                 [round(p0["x"], 4), round(p0["y"], 4),
                                  round(p0["z"], 4)],
                             "world_pose_now": None if p1 is None else
                                 [round(p1["x"], 4), round(p1["y"], 4),
                                  round(p1["z"], 4)],
                             "moved_in_world": moved_world,
                             "footprint_cells_lost": len(lost),
                             "footprint_cells_gained": len(gained),
                             "n_cells_changed_total": d["n_changed"],
                             "frame_evidence_says_moved": evidence_says_moved},
                "truth_moved": truth_moved,
                "frame_agrees_with_world": evidence_says_moved == truth_moved,
                "stance": stance}
    if kind == "present":
        t = trig["t"]
        f = obs.capture(t)
        n = sum(1 for j in range(obs.h) for i in range(obs.w)
                if f.owner_name(i, j) == trig["target"])
        return {"trigger": trig, "verdict": "CONFIRMED" if n else "REFUTED",
                "evidence": {"cells_owned": n},
                "stance": ("evidence FOR the assumption of need" if n
                           else "evidence AGAINST the assumption of need")}
    if kind == "char_only_present":
        # Does the CHARACTER channel alone separate the target from the walls?
        # The previous version filtered on colour and so confirmed by
        # construction -- a colour test wearing a char costume.  The real
        # question is SEPARABILITY: if the two glyph sets overlap, no amount of
        # reading the characters can tell them apart.
        t = trig["t"]
        f = obs.capture(t)
        tgt, oth = set(), set()
        for j in range(obs.h):
            for i in range(obs.w):
                o = f.owner[i][j]
                if o is None:
                    continue
                if o["id"] == trig["target"]:
                    tgt.add(f.data[i][j])
                elif o["id"] in trig["against"]:
                    oth.add(f.data[i][j])
        overlap = tgt & oth
        # Do the COLOURS separate them where the glyphs do not?  This is the
        # arm that makes the comparison honest: same frame, two channels.
        ctgt, coth = set(), set()
        for j in range(obs.h):
            for i in range(obs.w):
                o = f.owner[i][j]
                if o is None:
                    continue
                if o["id"] == trig["target"]:
                    ctgt.add(f.color[i][j])
                elif o["id"] in trig["against"]:
                    coth.add(f.color[i][j])
        col_overlap = ctgt & coth
        return {"trigger": trig,
                "verdict": "REFUTED" if overlap else "CONFIRMED",
                "evidence": {"target_glyphs": "".join(sorted(tgt)),
                             "other_glyphs": "".join(sorted(oth)),
                             "glyph_overlap": "".join(sorted(overlap)),
                             "n_glyph_overlap": len(overlap),
                             "n_target_colours": len(ctgt),
                             "n_other_colours": len(coth),
                             "colour_overlap": len(col_overlap),
                             "target_colours": " ".join("%02x" % c for c in sorted(ctgt)),
                             "channel": "char only"},
                "stance": ("glyph sets OVERLAP: the character channel cannot "
                           "tell the target from the walls, because the glyph "
                           "is a function of z and z alone" if overlap
                           else "glyph sets are disjoint AT THIS DEPTH")}
    raise ValueError(kind)


# ------------------------------------------------------ the two questions ----


def q_change_detection(obs, anchor, t, target, mode):
    """QUESTION 1: 'did X change between the reference and t?'  Computable answer.

    TRUTH is the OWNED CELL SET, not the cell count: counting cells misses a
    target whose cells swapped position, which is how the first version of this
    test produced a FALSE on a target that had genuinely not changed shape.
    """
    def owned(f):
        return set((i, j) for j in range(obs.h) for i in range(obs.w)
                   if f.owner_name(i, j) == target)
    truth_changed = owned(obs.capture(t)) != owned(anchor.frame)
    if mode == "observe":
        d = diff(anchor, obs, t)
        got = any(target in (c[6], c[7]) for c in d["cells"])
        return {"answer": got, "truth": truth_changed,
                "correct": got == truth_changed, "cost_cells_compared": obs.w * obs.h}
    if mode == "full_rate":
        # the reader must find the change across a window it did not choose
        return {"answer": None, "truth": truth_changed, "correct": None,
                "cost_cells_compared": obs.w * obs.h * 20,
                "note": "reader must diff the pages itself"}
    raise ValueError(mode)


def q_absolute_state(obs, anchor, t, pos, mode):
    """QUESTION 2: 'what is at position P right now?'  Computable answer."""
    i, j = pos
    truth = obs.capture(t).owner_name(i, j)
    if mode == "observe":
        _check(anchor, obs)
        d = diff(anchor, obs, t)
        hit = [c for c in d["cells"] if c[0] == i and c[1] == j]
        if hit:
            got = hit[0][7]
        else:
            got = anchor.frame.owner_name(i, j)      # reference + no diff = state
        return {"answer": got, "truth": truth, "correct": got == truth,
                "via": "reference+diff"}
    if mode == "diff_only":
        # L4: irreversible projection, no reference to reconstruct from
        return {"answer": "UNKNOWN", "truth": truth, "correct": False,
                "via": "diff alone is L4; the state was projected away"}
    if mode == "full_rate":
        return {"answer": truth, "truth": truth, "correct": True,
                "via": "direct read of page t"}
    raise ValueError(mode)
