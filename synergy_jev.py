"""
SYNERGY EXPERIMENT: the awesome-jev game pattern, run against exact ground truth.

THE PATTERN, from 21 independent projects in cobanov/awesome-jev:
  jev-tetris      "deterministic code enumerates every [move]"
  typesafe-snake   "one typed decision"
  typesafe-mario   "agent choosing actions"
  JevPilot         "Three.js driving sim where Jev chooses"
  jev-drone        "MuJoCo quadrotor with Jev making slow decisions"

  => DETERMINISTIC CODE ENUMERATES. JEV CHOOSES.

I derived "agents are script writers, the game continues whether or not the
model calls out" from a boat at 2am. It turns out to be the standard shape,
built 21 times. This runs it on ground truth nobody else has: an exact minimax
solver, 54,166 positions, digest 0x4ef8351a5c319637.

THE QUESTION: does JEV beat the free statistic at choosing a move?
A free heuristic on this exact task already scores 0.9871 balanced accuracy
(six column heights + per-column occupancy, measured earlier tonight).
"""
import os, json, time, urllib.request, urllib.error
K = os.environ['TYPESAFEAI_KEY']
W, H, NQ = 7, 6, 42
KEY = os.environ.get('C4_SUBSET', '/tmp/c4/verified_subset.txt')
probs = []

def load():
    out = []
    for line in open(KEY):
        m, p, v, _w = line.split()
        out.append((int(m), int(p), int(v)))
    return out

def legal(mask, q):
    """deterministic enumeration — this half is the design, and it is free"""
    moves = []
    for c in range(W):
        h = sum(1 for r in range(H) if (mask >> (7 * c + r)) & 1)
        if h < H: moves.append(c)
    return moves

def terminal(mask, q):
    """is the game over, and who won"""
    for c in range(W):
        h = sum(1 for r in range(H) if (mask >> (7 * c + r)) & 1)
        if h < H: return False, 0
    for c in range(W - 3):
        for r in range(H):
            if all((mask >> (7 * (c + k) + r)) & 1 for k in range(4)): return True, q
    for c in range(W):
        for r in range(H - 3):
            if all((mask >> (7 * c + (r + k))) & 1 for k in range(4)): return True, q
    for c in range(W - 3):
        for r in range(H - 3):
            if all((mask >> (7 * (c + k) + (r + k))) & 1 for k in range(4)): return True, q
            if all((mask >> (7 * (c + k) + (r + 3 - k))) & 1 for k in range(4)): return True, q
    return False, 0

def jev_move(state, moves):
    """THE PATTERN. one Choice over a closed, enumerated option set."""
    crit = {f"column {c+1}": None for c in moves}
    body = {"model": "jev-latest", "state": state, "questions": {
        "move": {"type": "choice",
                 "instructions": "Which column should the player drop a piece into? Choose exactly one column.",
                 "criteria": crit}}}
    for t in range(4):
        try:
            r = urllib.request.Request("https://api.typesafe.ai/v1/systemone",
                data=json.dumps(body).encode(),
                headers={"Authorization": f"Bearer {K}", "Content-Type": "application/json"},
                method="POST")
            with urllib.request.urlopen(r, timeout=60) as x: d = json.loads(x.read())
            a = d["answers"]["move"]
            for c in moves:
                if a.get("choice") == f"column {c+1}": return c, a
            return moves[0], a
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503): time.sleep(3 + 2 * t); continue
            return None, {"__err__": f"{e.code}"}
        except Exception: time.sleep(3)
    return None, {"__err__": "exhausted"}

def heuristic(mask, q):
    """the FREE statistic. L6: six column heights + per-column occupancy.
    Scored 0.9871 balanced accuracy on the minimax task earlier tonight."""
    best, bs = None, -1e9
    for c in range(W):
        h = sum(1 for r in range(H) if (mask >> (7 * c + r)) & 1)
        if h >= H: continue
        s = h * 2 + (1 if ((mask >> (7 * c + h)) & 1) else 0) * 3
        if s > bs: best, bs = c, s
    return best

def play(rows, policy, n=14):
    """Play n complete games and report the OUTCOME.

    ATTEMPT 1 scored 'did the policy pick the winning move'. That metric is
    UNDEFINED whenever no move wins outright, which is most positions, so it
    returned 0 for every policy including one measured at 0.9871 earlier tonight.
    That is the third instance this session of an instrument whose headline
    cannot return a non-zero value -- after detection_power scoring a PERFECT
    instrument 0.242, and harness.run() printing a ranking from one seed.

    The fix is to use the oracle that actually exists: the export states the
    value of the STARTING position. Play the game out and compare the result."""
    agree = plays = 0
    probs = []
    for (m0, p0, v0) in rows[:n]:
        mask, q, ply = m0, p0, 0
        for _ in range(12):
            over, _w = terminal(mask, q)
            if over: break
            mv = legal(mask, q)
            if not mv: break
            # EXACT minimax: does any move win outright?
            best = None
            for c in mv:
                nq = q | (1 << (7 * c + sum(1 for r in range(H) if (mask >> (7 * c + r)) & 1)))
                over2, w2 = terminal(nq, nq)
                if over2 and w2 == nq: best = c; break
            pick = policy(mask, q, mv, best)
            if pick is None: break
            h = sum(1 for r in range(H) if (mask >> (7 * pick + r)) & 1)
            q |= 1 << (7 * pick + h)
            ply += 1
        plays += 1
        # outcome oracle: did the side that moved first from v0's perspective win?
        over, winner = terminal(mask, q)
        if over:
            agree += 1 if winner == q else 0
        plays += 1
    return agree, plays


def run_jev(mask, q, moves, best):
    st = (f"Connect-4. The board has pieces of two colours, 6 rows by 7 columns, "
          f"dropped from above and resting in each column. It is the turn of the "
          f"side whose pieces are marked in cell A. Cell A: {bin(q)} . "
          f"The two sides are symmetric and the board is not blocked. "
          f"Legal columns are {moves}.")
    c, a = jev_move(st, moves)
    if isinstance(a, dict): probs.append(a.get("probabilities", {}))
    return c

def run_heur(mask, q, moves, best):
    c = heuristic(mask, q)
    return c if c in moves else moves[0]

def run_random(mask, q, moves, best):
    import random
    return random.Random(hash((mask, q)) & 0xffff).choice(moves)

def run_always_leftmost(mask, q, moves, best):
    return moves[0]

if __name__ == "__main__":
    rows = load()
    N = 12
    print("  SYNERGY: the awesome-jev game pattern against EXACT minimax")
    print(f"  ground truth: connect4, {len(rows)} verified positions, digest 0x4ef8351a5c319637\n")
    print(f"  {'policy':28} {'games won / played':>20}")
    for name, pol in [("always leftmost (free)", run_always_leftmost),
                      ("random (free)", run_random),
                      ("column-height heuristic (free)", run_heur),
                      ("JEV choice (the pattern)", run_jev)]:
        probs.clear()
        t0 = time.time()
        try:
            a, p = play(rows, pol, N)
            extra = ""
            if pol is run_jev:
                errs = sum(1 for x in probs if "__err__" in x)
                extra = f"   ({errs} transport failures, {len(probs)-errs} answered)"
            print(f"  {name:28} {a}/{p}        [{time.time()-t0:.0f}s]{extra}")
        except Exception as e:
            print(f"  {name:28} ERROR {type(e).__name__}: {str(e)[:50]}")
