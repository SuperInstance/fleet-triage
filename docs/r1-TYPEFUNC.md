# r1-TYPEFUNC — the dungeon as a state function

**Lane:** Casey's lunch-theory claim, built as code.
**Status:** STUB — design + first runnable cell. Round 1, ~10 min mark.
**Repo:** `SuperInstance/gh-dungeons` @ `/workspace/work/gh-dungeons` (Go, tcell, BSP).
**Branch:** `naming-door` in `fleet-triage` (this file). All `gh-dungeons` changes are local until forked.

---

## 0. The claim under test

> *I might not know where I'm going to eat or what I'll order when I get there,
> but my decisions procedurally iterate from my state … and the reason is never
> spelled out in my head, because I was listening to the radio and I let
> system-one take the path of least resistance instead of building a chain of
> thought to prove one way or another.*

The question nobody else in this fleet is answering:
**how many of an agent's decisions are actually justified, and does making them justified improve play?**

Casey's prediction: **no, and worse.** I have not measured it. Round 1 measures the count; the round where
forcing justification on is A/B'd against this is where the prediction gets tested.

---

## 1. Architecture — four constraints, four mechanisms

| Brief | Mechanism | Where |
|---|---|---|
| A decision is a **function of state**, not a deliberation | `OptionSet` is computed from state, never from a prompt. There is no chain-of-thought field. | `statefunc/optionset.go` |
| The action space is **time-indexed** | Turn budget. Every turn spent elsewhere removes the long-wait options. | `pruner_budget.go` |
| The state includes **other agents**, and they change the **objective** | `Objective` is a field, not a constant. `FISH_FOR_COMPANION` rewrites it. | `objective.go` |
| Most decisions are **not justified because never deliberated** | `justified=false` is the *default and the common case*. A deliberator is a *fallback for a pruned-to-empty set*, not a per-move step. | `decide.go` |

### 1.1 Cells are JEV subjects; `criteria` is the type

A cell is a glyph with an address. Its **`Criteria()` is its type** — a closed set, and a judge can
only return one of those. There is exactly one way of typing things in this lane.

```go
type Cell interface {
    Glyph() rune      // the character
    Addr() Addr       // x,y — the cell's identity
    Criteria() []string // THE TYPE. closed set. no second typing path.
    Cost() int         // turns to traverse — this is what makes the space time-indexed
}
```

Glyphs already exist in the upstream game: `TileWall '#'`, `TileFloor` renders a character from the
scanned `CodeFile` line, `TileDoor '>'`, entity symbols. **The glyph array is the quilt; the code is
the adjacency between cells.** A corridor glyph adjacent to a door glyph is a different cell graph
than the same characters shuffled — and §3 makes that falsifiable, not asserted.

### 1.2 The option-pruner is a real pruner, not a prompt

Per turn: enumerate the 8 adjacent cells → each is a typed action → **prune by state** → act.
The pruner is a *list of composable funcs*, so the three-policy lane can wrap it rather than replace it.

```go
type Pruner func(State, Action) Reason   // Reason != nil => pruned, with the reason kept
```

The log records **`len(options) -> len(surviving)` every turn.** That number dropping is the deliverable.

### 1.3 Justified vs defaulted — the actual measurement

A decision is **justified** iff a deliberator was invoked for it, i.e. iff the option set collapsed to
**zero** and a fallback had to be named. Otherwise the agent took whatever survived, and the
reason is **not recorded, because there was none.** That is the whole point: `Reason` is empty for
`justified=false` moves, exactly as in the brief.

> A model that emits a chain of thought on every move is not modelling this agent. **It is doing
> something the agent does not do.** So there is no per-move CoT field in this lane, and forcing one
> is a *separate measured condition* (`-justify=always`), not the default.

### 1.4 The counterfactual — "what a deliberating agent would have done"

For every defaulted decision, compute the **best pruned option by static utility**, and log what the
agent did instead. That gap is the number nobody in this fleet has measured.

### 1.5 The loop runs without the model

`statefunc` drives `GameState` **headless** — no `tcell.NewScreen()`. The model is an *optional*
deliberator: if it is nil, slow, or refuses, the agent still moves. **If the loop stalls when the model
is slow, that is a finding and I report it.** (`-model=none` is the default for round 1 so the game
provably continues without one.)

---

## 2. The runnable cell (round 1)

`statefunc/` — new package inside the clone. Entry point runs a headless dungeon with the pruner and
emits a JSONL decision log.

```
go run ./cmd/statefunc -seed 42 -turns 400 -out /workspace/work/runs/typefunc-s42.jsonl
```

- one JSON object per decision: `{t, from, to, options_before, options_after, pruned:[{glyph,reason}],
  objective, party, justified, deliberator_used, counterfactual, took}`
- run summary to stdout: option count over time, justified count, defaulted count, counterfactual gap.

**First 10 minutes' deliverable:** this file, the package skeleton, the pruner, and one verified run
in the real dungeon.

---

## 3. Falsification of "the dungeon is a font" (glyphs-as-relations)

If the same multiset of glyphs, shuffled, produces the same option counts and the same score, then the
cells are a font and the adjacency carries nothing. Test: **shuffle the glyph assignment, hold the
tile graph fixed, re-run, compare option-count trajectories and score.** If they are identical, the
ontology is decorative and I say so in the report.

---

## 4. Composability with the syncopation lane

- `Pruner` is a list, `Policy` is an interface, and the deliberator is injected. The three-policy
  lane owns policy *selection*; this lane owns the *option set* those policies choose from.
- Nothing here assumes a single policy. The default run uses one static policy purely as a control.

## 5. Open / next

- [ ] `statefunc` package compiling and running headless in the real dungeon ← **now**
- [ ] option-count trajectory, justified vs defaulted, counterfactual gap
- [ ] shuffle test (§3)
- [ ] `-justify=always` arm, same seeds, to test "does justifying improve play"
- [ ] extract as a standalone module if it earns it
