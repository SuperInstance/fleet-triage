# r1 — SYNCOPATION: the deliberately-blind system-two

**Lane:** Casey's most original idea, made runnable.
**Status:** STUB — design + first runnable cell. Round 1.
**Question nobody else is answering:** *does deliberate blindness, correctly implemented, produce better play than a designer that can see everything?*

---

## 0. What `gh-dungeons` already gives me (read before designing)

Cloned `SuperInstance/gh-dungeons` @ HEAD, 1.2 MB, Go 1.24, module `github.com/SuperInstance/gh-dungeons`.

The facts that shaped the design:

| fact | file | why it matters |
|---|---|---|
| `Run()` blocks on `tcell.PollEvent()` | `game/game.go:236` | **The dungeon has no tick loop of its own.** It is a human-driven blocking loop. A policy-driven autonomous loop does not exist and must be supplied. |
| `New()` calls `tcell.NewScreen()` | `game/game.go:155` | Fails without a TTY. Headless needs a different entry, not `New()`. |
| The whole simulation is drivable headless | `game/state.go:58,203` | `NewGameState(codeFiles, seed, w, h)` + `MovePlayer(dx,dy)` runs the *entire* turn economy — auto-attack, `moveEnemies`, `enemyAttacks`, visibility, level gen. **No fork needed.** |
| One `*GameState` per world | `game/state.go:58` | A shadow policy needs its own world. `NewGameState` is a constructor, not a singleton — so three live worlds is legal, not a hack. |
| `RNG` is a seeded `*rand.Rand` | `state.go:65` | Fair A/B: same seed ⇒ same dungeon, same monsters, same everything. |

**Conclusion: zero changes to `gh-dungeons` are required for round 1.** The lane is a consumer of the package. (Fork request, deferred, in §7.)

---

## 1. The architecture

```
                    ┌──────────── THE WORLD (goroutine, 20 Hz, 600 ticks per cadence) ────────────┐
                    │  gs0 = GameState(seed S)  ← THE REAL DUNGEON. The player is here.         │
                    │  gs1 = GameState(seed S)  ← shadow, unseen                                │
                    │  gs2 = GameState(seed S)  ← shadow, unseen                                │
                    │  move = ACTIVE_POLICY.act(view(gs_active))                                 │
                    └───────────────┬─────────────────────────────────────────────────────────────┘
                                    │ every tick: a TelemetrySample, per world
                                    ▼
                    ┌──────────── THE EXPERIMENT (recorder) ────────────────────────────────────┐
                    │  owns all three worlds' telemetry. Writes IntervalClosed records.          │
                    │  ⚠ emits to `auditBus` — read ONLY by the log writer, never by system-two │
                    └───────────────┬─────────────────────────────────────────────────────────────┘
                                    │ closed intervals only, ≥1 generation stale
                                    ▼
                    ┌──────────── SYSTEM-TWO (goroutine) ──────────────────────────────────────┐
                    │  blocked on a WALL-CLOCK DEADLINE for the whole cadence.                  │
                    │  On wake it may read: reports for CLOSED intervals only.                   │
                    │  On wake it MUST emit: (a) which policy to promote, (b) which to demote.  │
                    │  It has NOT read the open interval. It CANNOT. See §2.                      │
                    └───────────────────────────────────────────────────────────────────────────┘
```

### The blindness is enforced by construction, not by discipline

`PolicyReport` — the *only* type system-two can ever receive:

```go
type PolicyReport struct {
    Policy      string
    IntervalID  int
    ClosedAt    time.Time     // this interval is OVER
    Ticks       int
    HPStart, HPEnd, Damage, Kills, Levels, Score int
    // NOTE: no field can carry live data. There is no "current" pointer.
    //       The type is not a view into a world; it is a value, already finished.
}
```

There is no method on `PolicyReport` that reads a `GameState`. System-two *cannot* observe a
shadow, because the thing it observes is a finished number, not a handle. This is the part I
am least willing to compromise on: if I had given system-two a `func() Telemetry` closure, the
closure would resolve during the cadence and the lag would be theatre.

Runtime proof, not a comment — see the self-test in §5, cell **ST-2**.

---

## 2. Cadence: **30 seconds**, and why

Casey's brief says 30s. I keep it, and the reason is quantitative, not deference:

- The world ticks at 20 Hz ⇒ one cadence = **600 turns**. That is the smallest interval at
  which a policy's *character* separates from its *noise*. Under ~200 turns, "did it lose
  4 HP" is a coin flip and the designer is choosing blind in a way that is not interesting —
  it is choosing at random.
- 600 turns is also long enough that the dungeon **advances a floor or two**, so the
  decision has consequences downstream of itself.
- The cadence is a **wall-clock `time.Duration` in one place** (`policy.Clock.Cadence`),
  read by one `time.Ticker` in one goroutine. It is not a loop-count parameter. Setting it
  to 0 does not make the designer instant; it makes the designer **busy-spin**, which starves
  the world goroutine and visibly changes the dungeon's behaviour. That degradation is the
  point of cell **ST-3**.

**Sweep:** {0, 2, 8, 30} s. 30s is the headline; the sweep exists so that "is 30 special?"
is answerable rather than assumed.

---

## 3. First runnable cell

Target: proves the world ticks, three policies live, and a toggle is a visible event.

**Cell 1 — `run` (3 policies, cadence 30s, 3 toggles ≈ 90 s wall-clock).**
Emits, to stdout and to `r1-artifacts/syncopation-r1.jsonl`:
- a rendered ASCII frame of the real dungeon every 2 s, **with the active policy named in the frame header**;
- one `TOGGLE` event line at each toggle: `t=61.4s  DEMOTE p-berserker  (chooser=system-two, blind)  PROMOTE p-thrifty`;
- the unobserved-window table (§4).

```
$ go run ./cmd/syncopate -seed 7 -cadence 30s -toggles 3 -frame 2s
```

*Status: written, not yet executed. Go toolchain was absent from the sandbox and is being
installed as of this stub.*

---

## 4. The deliverable table

Emitted as markdown + JSONL. One row per demotion. **The two `saw`/`did` columns are the
whole product** — they are the asymmetry, made legible.

| # | policy | interval | what it did (telemetry) | who demoted it | could that chooser see it? | what actually happened (retro) |
|---|---|---|---|---|---|---|
| 1 | p-seeker | t=30.0–60.0 | *pending* | system-two | **no** | *pending* |
| 2 | p-berserker | t=60.0–90.0 | *pending* | system-two | **no** | *pending* |

`what it did` = the report handed to system-two **at the moment it chose**.
`what actually happened` = the same interval, re-read **after** the choice, by the auditor.
Where the two disagree in *decision-relevant* ways, that row is a blind-donation cost.

---

## 5. Cells planned

| id | cell | what it proves |
|---|---|---|
| ST-1 | `run` | 3 live worlds, real cadence, visible toggles. |
| ST-2 | `blindness-selftest` | **Falsifiable proof** that system-two cannot read a live world. Attempts to leak and asserts it fails. |
| ST-3 | `cadence-zero` | Set cadence 0. Show the world goroutine starve. Report the degradation, do not fix it. |
| AB-1 | `syncopated` | Arm A: blind demotion. |
| AB-2 | `oracle` | Arm B: **same cadence, same seed, same designer** — but the interval report is delivered *at* the decision. Isolates *information at the decision point* as the only variable. |
| AB-3 | `score` | Aggregate + the verdict. |

**AB-2 is deliberately not a synchronous designer.** If Arm B watched in real time it would
also change the world's behaviour, confounding information with interference. Holding cadence
fixed in both arms is the only way the comparison means anything. A true cadence-0 arm is
ST-3, and is reported as a *different* experiment.

---

## 6. Risks I already know about

1. **Three `GameState`s × 20 Hz is cheap; three `GameState`s × 3 arms × sweep is not.**
   Mitigate: sweep fewer seeds, report per-seed not pooled. Say so if it bites.
2. **The dungeon may not be seed-stable** if `generateLevel` reaches for time or a global.
   Unverified. If it is, the A/B is void and I must say so rather than ship a beautiful
   unfair comparison. *Check first, before any result is claimed.*
3. **Policies are scripts, not a model** — required (agents are script writers) but it means
   "better policy" means "better among this repertoire", not "better in general".
4. **A finding I expect to have to take seriously:** blind demotion may simply be *worse*,
   and if the cost is large enough to swamp the effect, that is the result, not a bug in the
   experiment.

---

## 7. Fork request (deferred, not blocking round 1)

None required. If the toggle should be visible **in the tcell game** rather than in an ASCII
frame, that needs one upstream change: `Game` needs a `Tick()` that the existing
`PollEvent` loop calls on a timer, plus a policy hook. I am **not** proposing that until the
headless harness has earned it. Proposed in a later round, per the brief.

---

*Design belongs to this lane. The brief it came from is in `GH-DUNGEONS-SEEDS.md` §5 and is
not restated here, because the point of this document is to disagree with it productively.*
