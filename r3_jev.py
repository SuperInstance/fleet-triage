#!/usr/bin/env python3
"""
r3_jev.py — the awesome-jev game pattern against exact minimax ground truth.

INHERITS /workspace/synergy_jev.py (plumbing fine, scoring wrong three times).
The fix is here. Metric + results: projects/fleet-triage/r3-JEVPATTERN.md

==============================================================================
THE METRIC — Oracle Agreement (OA). Stated before it is run.
==============================================================================
  1. deterministic code enumerates the legal columns          (free, the pattern)
  2. the policy names ONE column per ply, for whichever side is to move.
     The policy is the sole decision-maker at EVERY ply and has NO colour
     allegiance -- it is a move-selection function, not a player.
  3. roll out to termination. No ply cap.
  4. W in {0, 1, NONE}; 0 = the START side-to-move won, 1 = the other, NONE = no four.
  5. OA = 1 iff W != NONE and (W == 0) == (v0 > 0)

     v0 > 0  ->  the start side-to-move must finish the game the winner.
     v0 < 0  ->  the start side-to-move must LOSE.

     "A policy that wins from a losing position is WRONG, not good."
==============================================================================

==============================================================================
THE ORIENTATION — and the inherited script had this backwards
==============================================================================
The export is `mask pos value` (3 columns, verified: col2 is a strict subset of
col1 on 54,166/54,166 rows). `v` is the value FOR THE SIDE TO MOVE, i.e. the
player with FEWER stones -- NOT for a fixed "p0" and NOT for the first player.

GATE (hard): for every row whose side to move has an IMMEDIATE winning move, the
side to move must win. Measured 34,242/34,242 = 1.0000 consistent. The opposite
convention scores 0.0000. Nothing is scored unless this gate passes at 1.0000.

This is the sixth bit-level trap in this export and the most expensive one: the
inherited docstring said "value from p0's perspective", which is FALSE, and the
inherited `load()` also unpacked FOUR fields from a THREE-column file.
"""
import os, sys, json, time, random, urllib.request, urllib.error

W, H = 7, 6
EXPORT = os.environ.get('C4_EXPORT', '/workspace/c4gt/c4_ground_truth.txt')
KEY_ENV = 'TYPESAFEAI_KEY'

# ----------------------------------------------------------------- bitboard
# column c, row r (0 = bottom) -> bit c*7 + r, sentinel at c*7+6 (unused here).
def heights(pos):
    return [sum(1 for r in range(H) if (pos >> (7 * c + r)) & 1) for c in range(W)]

def legal(pos):
    """DETERMINISTIC ENUMERATION. this half is the design, and it is free."""
    hs = heights(pos)
    return [c for c in range(W) if hs[c] < H]

def has_won(pos):
    for c in range(W - 3):
        for r in range(H):
            if all((pos >> (7 * (c + k) + r)) & 1 for k in range(4)): return True
    for c in range(W):
        for r in range(H - 3):
            if all((pos >> (7 * c + (r + k))) & 1 for k in range(4)): return True
    for c in range(W - 3):
        for r in range(H - 3):
            if all((pos >> (7 * (c + k) + (r + k))) & 1 for k in range(4)): return True
            if all((pos >> (7 * (c + k) + (r + 3 - k))) & 1 for k in range(4)): return True
    return False

def pop(b):
    return bin(b).count('1')

# ----------------------------------------------------------------- the gate
def orientation_gate(rows):
    """Refuse to report anything unless the value convention is 1.0000 consistent.
    This is the 'prove it is defined before you report a score' precondition, and
    it is the test that would have caught all three inherited metrics."""
    ok = bad = noforce = 0
    for (mask, pos, v0) in rows:
        a, b = pos, mask & ~pos
        mover, other = (a, b) if pop(a) <= pop(b) else (b, a)
        mv = legal(mover)
        if not any(has_won(mover | 1 << (7 * c + heights(mover)[c])) for c in mv):
            noforce += 1
            continue
        if (v0 > 0): ok += 1
        else: bad += 1
    tot = max(ok + bad, 1)
    return {'forced_win_rows': ok + bad, 'consistent': ok, 'consistent_frac': ok / tot,
            'no_forced_win': noforce}

# ----------------------------------------------------------------- policies
def p_leftmost(pos, opp, moves, ctx):
    return moves[0]

def make_random(seed_base):
    def f(pos, opp, moves, ctx):
        return random.Random(seed_base * 1000003 + ctx['row'] * 97 + ctx['ply']).choice(moves)
    return f

def p_l6(pos, opp, moves, ctx):
    """THE FREE STATISTIC. L6: six column heights + per-column occupancy.
    Kept BYTE-IDENTICAL to synergy_jev.py heuristic() -- s = h*2 + hole*3, argmax.
    It is colour-blind (reads pos, never opp) and that is preserved deliberately:
    the 0.9871 belongs to THIS feature and quietly changing the comparator would
    make the headline unfalsifiable. Flagged, not fixed."""
    hs = heights(pos)
    best, bs = None, -1e9
    for c in range(W):
        h = hs[c]
        if h >= H: continue
        s = h * 2 + (1 if ((pos >> (7 * c + h)) & 1) else 0) * 3
        if s > bs: best, bs = c, s
    return best if best in moves else moves[0]

# ----------------------------------------------------------------- rollout
def rollout(mask, pos, policy, rowidx):
    """Policy drives BOTH sides to termination.
    Returns (W, plies) with W in {0,1,None}; 0 = the START side to move won."""
    a, b = pos, mask & ~pos
    if pop(a) <= pop(b):
        cur, nxt, me = a, b, 0          # me = the start side to move
    else:
        cur, nxt, me = b, a, 1
    ply = 0
    while True:
        moves = legal(cur)
        if not moves:
            return None, ply            # board full, no four -> draw
        c = policy(cur, nxt, moves, {'ply': ply, 'row': rowidx})
        if c not in moves:
            return None, ply            # illegal pick -> treated as a draw, tallied
        h = heights(cur)[c]
        cur = cur | 1 << (7 * c + h)
        ply += 1
        if has_won(cur):
            return me, ply
        cur, nxt = nxt, cur

def score(rows, policy):
    """OA, plus the two orientation controls and the draw tally."""
    ok = bad = draws = 0
    ok_neg = 0          # control A: same rollouts, -sign(v0)
    ok_p0 = 0           # control B: the INHERITED reading (value from a fixed
                        # 'p0' = the player with >= as many stones = first player)
    plysum = 0
    for i, (mask, pos, v0) in enumerate(rows):
        W, ply = rollout(mask, pos, policy, i)
        plysum += ply
        a, b = pos, mask & ~pos
        first_is_me = (pop(a) <= pop(b))          # tie -> p0 convention says p0 moves
        if W is None:
            draws += 1
        else:
            if (W == 0) == (v0 > 0): ok += 1
            if (W == 0) == (v0 < 0): ok_neg += 1
            # inherited reading: p0 is a FIXED player (the one with more stones,
            # ties to the mover), and v is claimed to be p0's value.
            p0_is_me = first_is_me
            if ((W == 0) == p0_is_me) == (v0 > 0): ok_p0 += 1
    n = len(rows)
    return {'oa': ok / n, 'oa_negated': ok_neg / n, 'oa_inherited_p0': ok_p0 / n,
            'draws': draws, 'n': n, 'mean_plies': plysum / n}

# ----------------------------------------------------------------- JEV arm
class Jev:
    """THE PATTERN. one Choice over a closed, enumerated option set.
    answered / transport (503, TLS EOF -- retry, NOT evidence about the request)
    / auth (401 or absent key -- NOT a measurement failure) are three distinct
    states; the inherited script conflated them into one."""
    def __init__(self):
        self.k = os.environ.get(KEY_ENV)
        self.answered = self.transport = self.auth = 0
        self.dists = []        # FULL distributions, never collapsed to a scalar

    def choice(self, state, moves):
        crit = {f"column {c + 1}": None for c in moves}     # values MUST be null
        body = {"model": "jev-latest", "state": state,
                "questions": {"move": {
                    "type": "choice",
                    "instructions": "Which column should the player drop a piece into? Choose exactly one column.",
                    "criteria": crit}}}
        for t in range(4):
            try:
                rq = urllib.request.Request(
                    "https://api.typesafe.ai/v1/systemone",
                    data=json.dumps(body).encode(),
                    headers={"Authorization": f"Bearer {self.k}",
                             "Content-Type": "application/json"},
                    method="POST")
                with urllib.request.urlopen(rq, timeout=60) as x:
                    d = json.loads(x.read())
                a = d["answers"]["move"]
                self.answered += 1
                self.dists.append((a.get("choice"), a.get("confidence"),
                                   a.get("probabilities", {})))
                for c in moves:
                    if a.get("choice") == f"column {c + 1}":
                        return c
                return moves[0]
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    self.auth += 1
                    return None
                self.transport += 1                # 429/5xx: retry, not evidence
                if e.code in (429, 500, 502, 503):
                    time.sleep(3 + 2 * t); continue
                return None
            except Exception:
                self.transport += 1                # TLS EOF and friends
                time.sleep(3)
        return None

    def policy(self, pos, opp, moves, ctx):
        if not self.k:
            return moves[0]      # auth-blocked: caller must not score this arm
        st = (f"Connect-4. The board has pieces of two colours, 6 rows by 7 columns, "
              f"dropped from above and resting in each column. "
              f"Legal columns are {moves}.")
        c = self.choice(st, moves)
        return c if c in moves else None

# ----------------------------------------------------------------- L6 as CLASSIFIER
def l6_balanced_accuracy(rows):
    """The 0.9871 is balanced accuracy of the L6 FEATURE as a win/loss classifier --
    a DIFFERENT instrument from L6-as-move-chooser. Fit it on these same rows so
    the 0.9871 is checked rather than taken on faith."""
    try:
        import numpy as np
    except ImportError:
        return None
    X, y = [], []
    for (mask, pos, v0) in rows:
        hs = heights(mask)
        X.append([float(h) for h in hs] +
                 [float((mask >> (7 * c + hs[c])) & 1) for c in range(W)])
        y.append(1 if v0 > 0 else 0)
    X = np.array(X); y = np.array(y, dtype=float)
    if len(set(y.tolist())) < 2: return None
    w = np.zeros(X.shape[1]); b = 0.0
    for _ in range(6000):
        pz = 1.0 / (1.0 + np.exp(-np.clip(X @ w + b, -30, 30)))
        g = X.T @ (pz - y) / len(y)
        w -= 0.1 * g; b -= 0.1 * float((pz - y).mean())
    pz = (1.0 / (1.0 + np.exp(-np.clip(X @ w + b, -30, 30))) > 0.5).astype(float)
    tpr = float((pz * y).sum() / max(y.sum(), 1))
    tnr = float(((1 - pz) * (1 - y)).sum() / max((1 - y).sum(), 1))
    return (tpr + tnr) / 2

# ----------------------------------------------------------------- main
def main():
    rows = [tuple(map(int, l.split())) for l in open(EXPORT) if l.strip()]
    print(f"  export  {EXPORT}")
    print(f"  {len(rows)} rows, columns {set(len(l.split()) for l in open(EXPORT) if l.strip())}")
    print(f"  v=+1 {sum(1 for r in rows if r[2] > 0)}   v=-1 {sum(1 for r in rows if r[2] < 0)}"
          f"   v=0 {sum(1 for r in rows if r[2] == 0)}")
    print(f"  col2 subset of col1: {sum(1 for a, b, v in rows if b & ~a == 0)}/{len(rows)}")

    g = orientation_gate(rows)
    print(f"\n  ORIENTATION GATE  {g['consistent']}/{g['forced_win_rows']} = "
          f"{g['consistent_frac']:.4f}   (rows with no forced win: {g['no_forced_win']})")
    if g['consistent_frac'] != 1.0:
        print("  *** GATE FAILED. Refusing to report any score. ***")
        sys.exit(1)
    print("  gate passed: v>0 <=> the side to move wins. Reporting proceeds.\n")

    n = int(os.environ.get('N_POS', '2000'))
    step = max(1, len(rows) // n)
    SAMPLE = rows[::step][:n]
    print(f"  sample: {len(SAMPLE)} rows, every {step}th of {len(rows)}\n")

    print(f"  {'policy':34} {'OA':>7} {'OA(-)':>7} {'OA(p0)':>7} {'draws':>6} {'plies':>6}")
    res = {}
    arms = [("always leftmost (free control)", p_leftmost),
            ("random seed 20261002 (free)", make_random(20261002)),
            ("column-height+occupancy L6 (free)", p_l6)]
    for name, pol in arms:
        t0 = time.time()
        r = score(SAMPLE, pol); res[name] = r
        print(f"  {name:34} {r['oa']:7.4f} {r['oa_negated']:7.4f} "
              f"{r['oa_inherited_p0']:7.4f} {r['draws']:6d} {r['mean_plies']:6.1f}"
              f"  [{time.time() - t0:.1f}s]")

    bal = l6_balanced_accuracy(rows)
    if bal is not None:
        l6oa = res["column-height+occupancy L6 (free)"]['oa']
        print(f"\n  L6 as a win/loss CLASSIFIER (all {len(rows)} rows): balanced acc {bal:.4f}")
        print(f"  L6 as a MOVE-CHOOSER (same feature, played out to termination):"
              f" OA {l6oa:.4f}   gap {bal - l6oa:+.4f}")

    j = Jev()
    n_jev = int(os.environ.get('N_JEV', '0'))
    if n_jev and j.k:
        S = SAMPLE[:n_jev]
        t0 = time.time()
        r = score(S, j.policy)
        print(f"\n  {'JEV choice (the pattern)':34} {r['oa']:7.4f} {r['oa_negated']:7.4f} "
              f"{r['oa_inherited_p0']:7.4f} {r['draws']:6d} {r['mean_plies']:6.1f}"
              f"  [{time.time() - t0:.0f}s]")
        print(f"    answered {j.answered}  transport {j.transport}  auth {j.auth}")
        ps = [v for _, _, pr in j.dists for v in pr.values() if v is not None]
        if ps:
            ps.sort()
            print(f"    distributions kept: {len(ps)} scalar probs, "
                  f"median p(argmax) {ps[len(ps)//2]:.3f}, "
                  f"frac p(argmax)<0.5 {sum(1 for v in ps if v < .5)/len(ps):.3f}")
        res['JEV choice (the pattern)'] = r
    else:
        why = "N_JEV=0" if not n_jev else f"{KEY_ENV} absent"
        print(f"\n  JEV choice (the pattern): NOT RUN -- {why}")
        print("    AUTH/absence condition, not a transport failure. Not scored as a")
        print("    JEV loss, and no free policy was substituted for the JEV column.")
        res['JEV choice (the pattern)'] = None

    out = os.environ.get('OUT', '/tmp/r3_jev_results.json')
    with open(out, 'w') as f:
        json.dump({'n_rows': len(rows), 'n_sample': len(SAMPLE), 'gate': g,
                   'free': res, 'l6_bal_acc': bal}, f, indent=1)
    print(f"\n  results -> {out}")

if __name__ == '__main__':
    main()
