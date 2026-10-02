# r1-NOENGINE — the dungeon that plays itself

**Lane:** script-first. Agents are script writers because the game continues whether or not the model
calls output.
**Status:** STUB — design + first runnable cell, ~8 min mark. Go toolchain installing in parallel.
**Repo:** `SuperInstance/gh-dungeons` @ `/workspace/work/noengine` (Go 1.24, tcell v2.13.7, BSP).
**Branch:** `noengine` in `fleet-triage`. All `gh-dungeons` edits are local until the orchestrator forks.

---

## 0. The claim under test

> *Agents are script writers because it allows the game to continue whether or not the model calls output.*

Most lanes will read this as "add a fallback when the API times out." That is a **retry**, not the
constraint. The constraint is structural:

> **The dungeon must be a function of `(state, script)` and nothing else. A model, if present, may
> only write the script. It may never be on the critical path of a turn.**

I am not claiming this is good architecture. I am claiming it is **measurable**, and measurability is
what this whole fleet is missing.

---

## 1. What the upstream code already gives me (read, do not assume)

`game/game.go:232` `Run()` is a bare `PollEvent` loop. `game/state.go:203` `MovePlayer(dx,dy)` is a
**pure function of the seed and the move list** — `gs.RNG` is `rand.New(rand.NewSource(seed))`,
every mutator is deterministic given the seed. There is no time source, no goroutine, no float in
the movement path.

**So the dungeon is already a script interpreter. It just doesn't have an interpreter API yet.** The
`PollEvent` loop is where a model would get welded in, and that is the only place it must not go.

That is the whole design. Not a new architecture — a **seam in an existing one**, plus a harness
that proves the seam holds when the model is amputated.

---

## 2. Architecture — three cells, one hard rule

```
  ┌─ cell 1: HEADLESS DRIVER ─────────────────────────────────────────┐
  │ tcell.NewSimulationScreen  ── no TTY, no model, no network         │
  │ Game.Run() is replaced by Game.RunHeadless(Script)                │
  │ the script is a []Move. it plays to completion in <1s.            │
  └───────────────────────────────────────────────────────────────────┘
  ┌─ cell 2: THE MEASUREMENT SPINE ───────────────────────────────────┐
  │ every check is a *named, seeded* probe that returns pass/fail      │
  │ and CAN return false. a check that has never returned false        │
  │ is reported as UNTESTED, not PASS.                                │
  └───────────────────────────────────────────────────────────────────┘
  ┌─ cell 3: THE MUTATION HARNESS ───────────────────────────────────┐
  │ faults injected into the policy: zero-multiply, swap, invert cmp  │
  │ reports killed / survived, per fault, with the receipt.           │
  └───────────────────────────────────────────────────────────────────┘
```

**The hard rule, enforced in code:** `policy.Decide(state) -> Move` takes no handle on any model.
The model is reachable only from `Script.Edit()`, which runs on a different goroutine and writes a
new `[]Move` — it can never be inside `Decide`. This is checkable by grep and I will ship the grep.

### 2.1 Cells as typed I/O (the brief's §2, one way only)

A cell is a glyph with an address. `Criteria()` is its type. One typing path, no second:

```go
type Cell interface {
    Glyph() rune        // the character
    Addr() Addr         // x,y — identity
    Criteria() []string // THE TYPE: closed set
    Cost() int          // turns — this is what makes the space time-indexed
}
```

`Typed` is not advisory: a judge may only return a member of `Criteria()`, enforced by a
constructor that refuses an out-of-set value. A cell that returns an empty `Criteria()` is a
programming error, and the constructor panics on it.

---

## 3. What runs in round 1 (the bar, in order)

1. **The dungeon plays with the model amputated.** `go run ./cmd/headless` — no TTY, no API key,
   no network. It prints a run and exits 0. *This is the acceptance test for the whole lane.*
2. **A pasted red.** Every check gets run against a deliberately broken world, and the failing
   output goes in this file verbatim.
3. **A mutation number.** 9 injected faults, killed/survived, no rounding up.
4. **The degeneracy check.** A dungeon whose *own script output* is fed back as its input. **If it
   converges happily, that is the finding and it is the most important line in the report.**
5. **MicroMoth-quilt as rung 3.** Measure whether a local engine is good enough to drive the policy
   with no API call. If it is not, name what is missing. **A rung that cannot carry the weight and
   gets credited for the API's results is the exact failure this lane exists to catch.**

---

## 4. The check that is least trustworthy (declared up front, before I have numbers)

`gs.EnemiesKilled` and `Victory` are **reached by a policy that already knows the map** if anyone
wires a BFS in. A greedy scripted policy will under-clear the level; a BFS policy will beat it; and
neither number tells you anything about the *dungeon*. So:

> **`dungeon_winnable` and `clear_rate` are properties of the POLICY until proven otherwise.**
> I will report the oracle policy (BFS, full map knowledge) beside the blind policy, and I will
> only believe a gap between them. Any single number presented without its oracle is noise.

Recorded before I run anything, so it cannot be retrofitted.

---

## 5. Status / next 90 min

- [x] read the seeds, read the upstream loop
- [x] clone, locate the seam (`Run()` → `PollEvent`)
- [ ] `cmd/headless` + `policy.Decide` + `Script` — **the first runnable cell**
- [ ] seed sweep: 200 seeds, blind vs oracle
- [ ] control battery, run every control, paste the red
- [ ] mutation harness, 9 faults
- [ ] degenerate loop dungeon
- [ ] MicroMoth-quilt rung probe

*The number I expect and the number I will get are probably not the same. Section 4 is why.*
