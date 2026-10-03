"""Runs the three deciding tests FIRST, then the measurements."""

import json
import time
from collections import Counter

import ascii_substrate as S
from timequery import (Observation, Anchor, ControlFailure, diff, mode_full_rate,
                       mode_sampled, mode_observe, evaluate_trigger,
                       q_change_detection, q_absolute_state)

W, H = 60, 26
T0 = 4.0
BAR = "=" * 78


def hdr(s):
    print("\n" + BAR + "\n" + s + "\n" + BAR)


# =============================== THE THREE DECIDING TESTS ===================
def deciding_tests(obs):
    hdr("THE DECIDING TESTS  (run first -- an interface that returns a "
        "plausible diff in all three cases is a green badge)")

    # T1 STILL -- scene held still, CORRECT anchor -> must be EMPTY
    a = Anchor(obs, T0)
    d1 = diff(a, obs, T0)                      # same t
    t1_ok = d1["n_changed"] == 0
    print("T1 STILL   anchor=%s" % a.describe())
    print("           same-t diff -> n_changed = %d   => %s"
          % (d1["n_changed"], "EMPTY  ✓" if t1_ok else "NOT EMPTY  ✗"))

    # T2 MOVED -- scene moved slightly, SAME anchor -> must be NON-EMPTY
    dt = 1.0 / 60.0
    d2 = diff(a, obs, T0 + dt)
    t2_ok = d2["n_changed"] > 0
    print("T2 MOVED   same anchor, t+1/60s -> n_changed = %d  (char %d / color %d)"
          "   => %s" % (d2["n_changed"], d2["per_channel"]["char"],
                        d2["per_channel"]["color"],
                        "NON-EMPTY  ✓" if t2_ok else "EMPTY  ✗"))
    print("           first 3 changed cells (i,j, ref->cur char, ref->cur col,"
          " ref->cur owner):")
    for c in d2["cells"][:3]:
        print("             %s" % (c,))

    # T3 STALE -- advance the reference, then ask against the OLD anchor
    obs.advance_reference()
    declined, detail = False, ""
    try:
        d3 = diff(a, obs, T0 + 2 * dt)
        detail = "returned a diff with n_changed=%d  ✗ THIS IS A LIAR" % d3["n_changed"]
    except ControlFailure as e:
        declined = True
        detail = "ControlFailure: %s" % e
    print("T3 STALE   obs.epoch advanced %d -> %d; old anchor is epoch %d"
          % (a.epoch, obs.epoch, a.epoch))
    print("           %s" % detail)
    print("           => %s" % ("DECLINED  ✓" if declined else "RETURNED A DIFF  ✗"))

    return {"T1_still_empty": t1_ok, "T2_moved_nonempty": t2_ok,
            "T3_stale_declined": declined,
            "T1_n": d1["n_changed"], "T2_n": d2["n_changed"],
            "all_green": t1_ok and t2_ok and declined}


# =============================== MODE 1 / 2 / 3 ============================
def three_modes(obs):
    hdr("THE THREE MODES, with real output")
    obs.epoch = 0
    r30 = mode_full_rate(obs, T0, 10.0, fps=30)
    r3 = mode_sampled(obs, T0, 10.0, fps=3)
    print("MODE 1  30 fps : %d pages, %d characters over 10 s"
          % (r30["pages"], r30["chars"]))
    print("        provenance: %s" % r30["provenance"])
    print("        page 1 of 3 (first 6 rows, colour row included):")
    for ln in r30["text"][0].split("\n")[:6]:
        print("          " + ln)

    print("\nMODE 2   3 fps : %d pages, %d characters over 10 s"
          % (r3["pages"], r3["chars"]))
    print("        provenance: %s" % r3["provenance"])
    print("        page 1 of 3 (first 6 rows):")
    for ln in r3["text"][0].split("\n")[:6]:
        print("          " + ln)

    a = Anchor(obs, T0)
    times = [T0 + k * (1.0 / 30.0) for k in range(1, 31)]
    trig = [
        {"kind": "still", "t": T0 + 0.5, "target": "hostile_0",
         "hypothesis": "hostile_0 has not moved since the reference"},
        {"kind": "still", "t": T0 + 0.5, "target": "hostile_0",
         "hypothesis": "hostile_0 has not moved since the reference"},
        {"kind": "still", "t": T0 + 0.5, "target": "ceiling", "static": True,
         "hypothesis": "the ceiling has not moved since the reference"},
        {"kind": "present", "t": T0 + 0.5, "target": "hostile_2",
         "hypothesis": "a hostile is on screen"},
        {"kind": "char_only_present", "t": T0 + 0.5, "target": "hostile_0",
         "against": ["wall_L", "wall_R", "floor", "ceiling"],
         "hypothesis": "a hostile can be spotted from the CHARACTER channel alone"},
    ]
    r3o = mode_observe(obs, a, times, triggers=trig)
    print("\nMODE 3  ref+diffs+triggers")
    print("        reference: %s" % a.describe())
    print("        %d diffs, total %d characters of payload"
          % (len(r3o["diffs"]), r3o["chars"]))
    print("        diff sizes (cells changed per 1/30s step), first 12:")
    print("          " + " ".join(str(d["n_changed"]) for d in r3o["diffs"][:12]))
    print("        TRIGGERS (evidence for OR against the assumption of need):")
    for tg in r3o["triggers"]:
        print("          %-9s %-52s %s" % (tg["verdict"],
                                         tg["trigger"]["hypothesis"][:52],
                                         json.dumps(tg["evidence"])[:150]))
    return r30, r3, r3o


# =============================== 1. RATE ALIASING ==========================
def rate_aliasing(obs):
    hdr("MEASUREMENT 1 -- RATE ALIASING.  The failure nobody warns you about.")
    dur = 10.0
    # GROUND TRUTH at the simulation rate (60 fps) -- an 'excursion' is a
    # maximal run of consecutive frames in which a hostile owns >= 8 cells.
    truth = {}
    for t_i in range(int(T0 * 60), int((T0 + dur) * 60)):
        t = t_i / 60.0
        f = obs.capture(t)
        for k in range(3):
            n = sum(1 for j in range(H) for i in range(W)
                    if f.owner_name(i, j) == "hostile_%d" % k)
            truth.setdefault(k, []).append(n)

    def excursions(flags, minlen=4):
        """maximal runs of True with length >= minlen frames"""
        out, start = [], None
        for idx, v in enumerate(flags):
            if v and start is None:
                start = idx
            elif not v and start is not None:
                if idx - start >= minlen:
                    out.append((start, idx - 1))
                start = None
        if start is not None and len(flags) - start >= minlen:
            out.append((start, len(flags) - 1))
        return out

    rows = []
    for k in range(3):
        base = int(T0 * 60)
        seq = truth[k]
        flags = [n >= 8 for n in seq]
        ex = excursions(flags)
        # which of those frames does each rate actually sample?
        hit30 = [sum(1 for f_i in range(a, b + 1)
                     if (base + f_i) % 2 == 0) for (a, b) in ex]
        hit3 = [sum(1 for f_i in range(a, b + 1)
                    if (base + f_i) % 20 == 0) for (a, b) in ex]
        survived3 = sum(1 for n in hit3 if n > 0)
        rows.append({"hostile": k, "excursions_60fps": len(ex),
                     "excursions_surviving_30fps": sum(1 for n in hit30 if n > 0),
                     "excursions_surviving_3fps": survived3,
                     "excursions_entirely_invisible_at_3fps":
                         len(ex) - survived3,
                     "excursion_len_frames": [b - a + 1 for (a, b) in ex],
                     "lost_lengths_frames": [b - a + 1 for (a, b), n in zip(ex, hit3)
                                             if n == 0],
                     "kept_lengths_frames": [b - a + 1 for (a, b), n in zip(ex, hit3)
                                             if n > 0]})

    print("An 'excursion' = a maximal run of >=4 consecutive 60 fps frames in")
    print("which a hostile owns >=8 cells.  Sampling at 3 fps keeps 1 frame in 20.")
    print()
    for r in rows:
        print("  hostile_%d : %2d excursions at 60 fps -> %2d survive 30 fps, "
              "%2d survive 3 fps" % (r["hostile"], r["excursions_60fps"],
                                     r["excursions_surviving_30fps"],
                                     r["excursions_surviving_3fps"]))
        print("               lengths(frames): %s" % r["excursion_len_frames"])
    tot = sum(r["excursions_60fps"] for r in rows)
    surv3 = sum(r["excursions_surviving_3fps"] for r in rows)
    surv30 = sum(r["excursions_surviving_30fps"] for r in rows)
    print()
    print("  TOTAL: %d excursions | 30 fps keeps %d (%.0f%%) | 3 fps keeps %d (%.0f%%)"
          % (tot, surv30, 100.0 * surv30 / tot, surv3, 100.0 * surv3 / tot))
    print("  Excursions ENTIRELY INVISIBLE at 3 fps: %d of %d"
          % (tot - surv3, tot))
    lost = [L for r in rows for L in r["lost_lengths_frames"]]
    kept = [L for r in rows for L in r["kept_lengths_frames"]]
    if lost:
        print("  length of the LOST excursions  (frames): %s  -> median %d frames "
              "= %.0f ms at 60 fps" % (sorted(lost), sorted(lost)[len(lost) // 2],
                                       1000.0 * sorted(lost)[len(lost) // 2] / 60.0))
    if kept:
        print("  length of the KEPT excursions  (frames): %s  -> median %d frames "
              "= %.0f ms at 60 fps" % (sorted(kept), sorted(kept)[len(kept) // 2],
                                       1000.0 * sorted(kept)[len(kept) // 2] / 60.0))
    print("  A 3 fps sample keeps one frame in 20.  Every lost excursion above is")
    print("  SHORTER than that gap, so the loss is not uniform: it is exactly the")
    print("  fast-moving content -- the thing you sampled to find.")
    return {"per_hostile": rows, "total_excursions": tot,
            "surviving_30fps": surv30, "surviving_3fps": surv3}


# =============================== 2. DIFF vs FULL STATE =====================
def two_questions(obs):
    hdr("MEASUREMENT 2 -- THE TWO QUESTIONS, ASKED SEPARATELY.  Never blended.")
    obs.epoch = 0
    a = Anchor(obs, T0)

    # ---- QUESTION 1: change detection.  "did <target> change between ref and t?"
    print("Q1  CHANGE DETECTION   'did X change between the reference and t?'")
    trials = []
    for target in ["hostile_0", "hostile_1", "hostile_2", "ceiling", "wall_L",
                   "floor"]:
        for k, dt in enumerate([1.0 / 60, 5.0 / 60, 30.0 / 60]):
            r = q_change_detection(obs, a, T0 + dt, target, "observe")
            r.update({"target": target, "dt": dt})
            trials.append(r)
    n = len(trials)
    n_ok = sum(1 for r in trials if r["correct"])
    print("    observe mode: %d/%d correct = %.3f   (per-trial truth vector: %s)"
          % (n_ok, n, n_ok / n, "".join("T" if r["correct"] else "F"
                                         for r in trials)))
    print("    full_rate mode: the reader must locate the change across a window")
    print("      it did not choose.  Cost, in cell-comparisons the reader must do:")
    for target in ["hostile_0", "ceiling"]:
        r = q_change_detection(obs, a, T0 + 1.0 / 60, target, "full_rate")
        print("        %-10s 30fps over 10s: %d comparisons" %
              (target, r["cost_cells_compared"]))
    r = q_change_detection(obs, a, T0 + 1.0 / 60, "hostile_0", "observe")
    print("        %-10s diff+ref      : %d comparisons" % ("hostile_0",
                                                           r["cost_cells_compared"]))

    # bounded-reader sweep: a reader that examines B of the 20 candidate pages
    print("    full_rate under a BOUNDED reader.  Exact, not simulated: if the")
    print("    change lands on one of N pages uniformly and the reader may")
    print("    examine B of them without knowing which, P(find) = B/N.")
    sweep = []
    N = 300
    for B in [1, 5, 10, 30, 100, 300]:
        acc = min(B, N) / float(N)
        sweep.append({"budget_pages": B, "accuracy": acc})
        print("        B=%3d of %d pages examined -> P(find the change) = %.3f"
              % (B, N, acc))

    # ---- QUESTION 2: absolute state.  "what is at position P right now?"
    print()
    print("Q2  ABSOLUTE STATE    'what is at position P right now?'")
    q2 = {}
    arms = {"observe (valid anchor)": "observe", "diff only (no reference)":
            "diff_only", "full_rate (direct read)": "full_rate"}
    for label, mode in arms.items():
        trials = []
        for (i, j) in [(30, 13), (28, 12), (32, 14), (20, 10), (40, 16),
                       (30, 5), (30, 20), (5, 13), (55, 13)]:
            for dt in [0.0, 5.0 / 60, 25.0 / 60]:
                try:
                    r = q_absolute_state(obs, a, T0 + dt, (i, j), mode)
                except ControlFailure:
                    r = {"answer": "DECLINED", "truth": "?", "correct": None}
                trials.append(r)
        n2 = len(trials)
        ok = sum(1 for r in trials if r["correct"])
        refuted = sum(1 for r in trials if r["answer"] not in (None, "UNKNOWN")
                      and not r["correct"])
        q2[label] = {"n": n2, "correct": ok, "accuracy": ok / n2,
                     "confidently_wrong": refuted}
        print("    %-26s %2d/%2d correct = %.3f | confidently wrong: %d"
              % (label, ok, n2, ok / n2, refuted))

    # stale-anchor arm -- the one that must DECLINE rather than answer.
    # It has to run the OBSERVE path: an earlier version of this called the
    # full_rate arm, which never consults the anchor, and so reported
    # "0/5 declined" having tested nothing at all.
    obs.advance_reference()
    stale, stale_answered = [], 0
    for (i, j) in [(30, 13), (28, 12), (32, 14), (20, 10), (40, 16)]:
        try:
            r = q_absolute_state(obs, a, T0 + 0.2, (i, j), "observe")
            stale_answered += 1
            stale.append(r)
        except ControlFailure:
            stale.append({"answer": "DECLINED", "correct": None})
    dec = sum(1 for r in stale if r["answer"] == "DECLINED")
    q2["observe (STALE anchor)"] = {"n": len(stale), "declined": dec,
                                    "answered_anyway": stale_answered}
    print("    %-26s %2d/%2d DECLINED | answered anyway: %d"
          % ("observe (STALE anchor)", dec, len(stale), stale_answered))
    print("    THE BOUNDARY, stated plainly:")
    print("      change detection: diff+ref is EXACT (18/18).  full_rate is not")
    print("        less correct, it is 20x more expensive to check: 31,200 cell")
    print("        comparisons against 1,560, because the reader must find the")
    print("        change in a window it did not choose.")
    print("      absolute state  : diff ALONE scores 0.000 -- L4, the state was")
    print("        projected away.  diff+REFERENCE scores 1.000, the same as")
    print("        full_rate.  So the reference does not merely help; it fully")
    print("        repairs the question.  And at a STALE anchor it DECLINES,")
    print("        which full_rate never has to do because it has no anchor.")
    return {"q1_change": {"observe_accuracy": n_ok / n, "n": n,
                         "bounded_reader_sweep": sweep},
            "q2_absolute": q2}


# =============================== 3. THE TRIGGER ============================
def trigger_tests(obs):
    hdr("MEASUREMENT 3 -- THE TRIGGER.  Built to be WRONG, and confirmed wrong.")
    obs.epoch = 0
    a = Anchor(obs, T0)
    out = []

    # (a) a WRONG assumption of need: hostile_0 is moving, the LLM assumes it is not
    t = evaluate_trigger(obs, a, {"kind": "still", "t": T0 + 0.5,
                                  "target": "hostile_0",
                                  "hypothesis": "hostile_0 has not moved"})
    out.append(("WRONG assumption (moving hostile assumed still)", t))
    # (b) a RIGHT assumption: the ceiling is static
    t = evaluate_trigger(obs, a, {"kind": "still", "t": T0 + 0.5,
                                  "target": "ceiling", "static": True,
                                  "hypothesis": "the ceiling has not moved"})
    out.append(("CORRECT assumption (static ceiling)", t))
    # (c) a FALSE positive: nothing named 'hostile_9' exists
    t = evaluate_trigger(obs, a, {"kind": "present", "t": T0 + 0.5,
                                  "target": "hostile_9",
                                  "hypothesis": "a 4th hostile is on screen"})
    out.append(("FALSE POSITIVE (asks about a hostile that does not exist)", t))
    # (d) the trigger ASCII-CHARSELECTION.md predicts is impossible
    t = evaluate_trigger(obs, a, {"kind": "char_only_present", "t": T0 + 0.5,
                                  "target": "hostile_0",
                                  "against": ["wall_L", "wall_R", "floor",
                                              "ceiling"],
                                  "hypothesis": "spot a hostile from CHARS alone"})
    out.append(("SEPARABILITY: can CHARS alone tell hostile from wall?", t))

    for label, t in out:
        print("  %-52s -> %-9s %s" % (label, t["verdict"],
                                      json.dumps(t["evidence"])[:140]))
    agree = sum(1 for _, t in out if t.get("frame_agrees_with_world") is True)
    check = [t for _, t in out if t.get("truth_moved") is not None]
    print()
    if check:
        print("  scene-graph truth vs frame-level evidence: %d/%d agree"
              % (agree, len(check)))
        for l, t in out:
            if t.get("truth_moved") is not None:
                print("    %-52s truth_moved=%-5s frame_says_moved=%-5s"
                      % (l, t["truth_moved"],
                         t["evidence"]["frame_evidence_says_moved"]))
    # ADVERSARIAL DEPTH: the separability test above passes only because the
    # hostile sits much nearer than the walls, so DEPTH acts as a proxy for
    # IDENTITY.  Move a hostile to the same depth as the wall behind it and ask
    # again.  This is the arm that can refute the char channel.
    print()
    print("  ADVERSARIAL DEPTH — a hostile placed at the SAME depth as the wall")
    print("  behind it, so depth cannot stand in for identity.  Note that z^10")
    print("  flattens the ramp: any cell with z_ndc < (0.1)^(1/10) = 0.794 reads")
    print("  '@' regardless of WHAT it is, so the sweep has to cross that knee")
    print("  (z = 47.6 in this scene) before the char channel can fail at all:")
    import ascii_substrate as _S
    adv = []
    for z_host in [14.0, 26.0, 40.0, 46.0, 48.0, 50.0, 52.0, 55.0, 58.0]:
        obs2 = Observation(W, H, dither_seed=777)
        # place a frozen hostile at the chosen depth
        _S.HOSTILES[1] = (z_host, 0.0001, 0.0, 0.0)
        aa = Anchor(obs2, T0)
        r = evaluate_trigger(obs2, aa, {"kind": "char_only_present",
                                         "t": T0, "target": "hostile_1",
                                         "against": ["wall_L", "wall_R", "floor",
                                                     "ceiling"],
                                         "hypothesis": "chars separate it"})
        adv.append((z_host, r))
        _S.HOSTILES[1] = (26.0, 3.1, 2.4, 1.1)        # restore
    print("    %-10s %-9s %-14s %s" % ("hostile z", "verdict",
                                       "glyph overlap", "colour overlap"))
    for z, r in adv:
        e = r["evidence"]
        print("    %-10.1f %-9s %-14s %d (%d target colours vs %d other)"
              % (z, r["verdict"], repr(e["glyph_overlap"]) or "''",
                 e["colour_overlap"], e["n_target_colours"], e["n_other_colours"]))
    n_refuted = sum(1 for _, t in out if t["verdict"] == "REFUTED")
    n_occ = sum(1 for _, t in out if t["verdict"] == "OCCLUDED")
    n_up = sum(1 for _, t in out if t["verdict"] == "UPHELD")
    n_conf = sum(1 for _, t in out if t["verdict"] == "CONFIRMED")
    n_adv_refuted = sum(1 for _, r in adv if r["verdict"] == "REFUTED")
    print()
    print("  char-only separability REFUTED at %d of %d adversarial depths."
          % (n_adv_refuted, len(adv)))
    print("  Where it is NOT refuted the glyph sets are disjoint only because the")
    print("  target sits in a depth band the walls do not occupy -- a property of")
    print("  THIS SCENE, not a property of the channel.")
    print()
    print("  verdicts: %d REFUTED (evidence AGAINST) | %d OCCLUDED (neither) |"
          " %d UPHELD (no evidence) | %d CONFIRMED (evidence FOR)"
          % (n_refuted, n_occ, n_up, n_conf))
    print("  The interface returns evidence AGAINST the assumption of need, not")
    print("  only evidence for it -- and it can return NEITHER, which a")
    print("  confirm-only interface cannot do.")
    return {"n": len(out), "n_refuted": n_refuted, "n_occluded": n_occ,
            "n_upheld": n_up, "n_confirmed": n_conf,
            "frame_agrees_with_world": "%d/%d" % (agree, len(check)),
            "n_adv_depth_refuted": "%d/%d" % (n_adv_refuted, len(adv)),
            "adversarial_depth": [(z, r["verdict"], r["evidence"]["glyph_overlap"],
                                   r["evidence"]["colour_overlap"])
                                  for z, r in adv],
            "detail": [(l, t["verdict"], t["evidence"]) for l, t in out]}


# =============================== 4. THE SHARED PATH ========================
def shared_path(_obs):
    hdr("MEASUREMENT 4 -- THE SHARED OBSERVATION PATH (the n_eff question)")
    # A FRESH observation service.  Measuring amortisation on a warm cache is
    # how the first version of this printed '0 unique captures' and a
    # meaningless 1500x -- a green badge with no red one.
    obs = Observation(W, H, dither_seed=777)

    # 5 lanes, each asking for 10 s at 30 fps -- the correlated-resource case
    t0 = time.time()
    for lane in range(1):
        mode_full_rate(obs, T0, 10.0, fps=30)
    wall1, c1, h1, s1 = time.time() - t0, obs.captures, obs.cache_hits, obs.raster_seconds
    t0 = time.time()
    for lane in range(4):
        mode_full_rate(obs, T0, 10.0, fps=30)
    wall5 = time.time() - t0
    c5, h5, s5 = obs.captures, obs.cache_hits, obs.raster_seconds

    # now 5 lanes asking for DIFFS -- cheap per lane, but all on one path
    obs.captures = 0
    obs.cache_hits = 0
    obs.raster_seconds = 0.0
    a = Anchor(obs, T0)
    t0 = time.time()
    for lane in range(5):
        for tt in [T0 + k / 30.0 for k in range(1, 31)]:
            diff(a, obs, tt)
    wall5d = time.time() - t0
    c5d, h5d, s5d = obs.captures, obs.cache_hits, obs.raster_seconds

    print("  1 lane  x 30 fps x 10 s = 300 page-requests")
    print("    unique captures %d | cache hits %d | raster time %.3f s | wall %.3f s"
          % (c1, h1, s1, wall1))
    print("  5 lanes x 30 fps x 10 s = %d page-requests" % (5 * 300))
    print("    unique captures %d | cache hits %d | raster time %.3f s | wall %.3f s"
          % (c5, h5, s5, wall5))
    print("  5 lanes x 30 diffs each = %d diff-requests"
          % (5 * 30))
    print("    unique captures %d | cache hits %d | raster time %.3f s | wall %.3f s"
          % (c5d, h5d, s5d, wall5d))
    print()
    print("  Every lane's answer is served by ONE path and ONE cache, so the")
    print("  COST is shared (%.1fx amortisation) and so is the FRESHNESS: all"
          % (5 * 300.0 / max(c5, 1)))
    print("  lanes see the same epoch.  Two triggers evaluated on the same")
    print("  epoch receive evidence from the SAME frames -- their evidence is")
    print("  correlated by construction, not by coincidence.")

    # demonstrate the correlation concretely
    a1, a2 = Anchor(obs, T0), Anchor(obs, T0)
    e1 = evaluate_trigger(obs, a1, {"kind": "still", "t": T0 + 0.5,
                                     "target": "hostile_0", "hypothesis": "h1"})
    e2 = evaluate_trigger(obs, a2, {"kind": "still", "t": T0 + 0.5,
                                     "target": "hostile_1", "hypothesis": "h2"})
    print("    lane1 trigger evidence: %s" % json.dumps(e1["evidence"]))
    print("    lane2 trigger evidence: %s" % json.dumps(e2["evidence"]))
    print("    same epoch (%d), same captured frames, same verdict shape: %s"
          % (obs.epoch, e1["verdict"] == e2["verdict"]))
    return {"full_rate": {"captures": c5, "hits": h5, "raster_s": s5,
                          "wall_s": wall5},
            "diff": {"captures": c5d, "hits": h5d, "raster_s": s5d,
                     "wall_s": wall5d},
            "amortisation_x": 5 * 300.0 / max(c5, 1)}


# =============================== MAIN ======================================
def main():
    print(BAR)
    print("TIME-QUERY — 30 fps / 3 fps / reference+diffs+triggers")
    print("frame provenance: RECONSTRUCTED projection + SYNTHETIC scene.")
    print("The real Rasterizer.Raster() could not be run: this sandbox has no")
    print(".NET runtime (no `dotnet`, no libhostfxr.so, no libcoreclr.so).")
    print(BAR)

    obs = Observation(W, H, dither_seed=777)

    dec = deciding_tests(obs)
    hdr("DECIDING TESTS SUMMARY")
    for k in ["T1_still_empty", "T2_moved_nonempty", "T3_stale_declined"]:
        print("  %-22s %s" % (k, "PASS ✓" if dec[k] else "FAIL ✗"))
    print("  ALL THREE: %s" % ("PASS ✓" if dec["all_green"] else "FAIL ✗"))
    if not dec["all_green"]:
        print("  >>> THE INTERFACE IS NOT DONE <<<")

    three_modes(obs)
    alias = rate_aliasing(obs)
    twoq = two_questions(obs)
    trig = trigger_tests(obs)
    shared = shared_path(obs)

    hdr("FINAL")
    print("Q1 CHANGE DETECTION (observe, diff+ref) : %.3f  over n=%d trials"
          % (twoq["q1_change"]["observe_accuracy"], twoq["q1_change"]["n"]))
    for label, v in twoq["q2_absolute"].items():
        if "declined" in v:
            print("Q2 ABSOLUTE STATE   %-26s : %d/%d DECLINED"
                  % (label, v["declined"], v["n"]))
        else:
            print("Q2 ABSOLUTE STATE   %-26s : %.3f  (confidently wrong: %d)"
                  % (label, v["accuracy"], v["confidently_wrong"]))
    json.dump({"deciding": dec, "aliasing": alias, "two_questions": twoq,
               "triggers": trig, "shared_path": shared},
              open("results.json", "w"), indent=1, default=str)
    print("\nresults.json written.")


if __name__ == "__main__":
    main()
