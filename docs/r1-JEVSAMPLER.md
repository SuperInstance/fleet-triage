# r1-JEVSAMPLER — the rung is a property of the cell

**Lane:** JEV tunes, something fast samples, MicroMoth-quilt drives it locally.
**Branch:** `r1-jevsampler` (in `fleet-triage`). Proposed changes to `gh-dungeons` are a
patch, not a push.
**Status:** STUB — design + first runnable cell. Run evidence in §7 as it lands.

---

## 1. The question I'm answering, stated so it can be falsified

> *When you lose the judge, what exactly do you lose?*

The stock answer is "less accuracy". **That answer is wrong here, and it is wrong because
it assumes every cell was attesting the same kind of thing.** It wasn't. Two populations,
two different failure modes, and the honest degradation report has to name which cells
stopped being trustworthy.

| population | what it attests | what losing the judge costs |
|---|---|---|
| **TYPED cells** | a world-state, against a ground truth the dungeon already holds | the **witness** — an independent second opinion. Content survives (the world is deterministic), attestation does not. |
| **PREFERENCE cells** | a utility, against nothing | **nothing structural.** It was always a draw. Losing the judge changes the *distribution*, not the *meaning*. |

So: **losing JEV costs you the witness on typed cells, and costs you a re-parameterised
draw on preference cells. Those are not the same loss and no single accuracy number can
express both.** The whole design is about keeping them separate *in the render*, not just
in a log.

## 2. The classifier: what makes a cell TYPED

Not a vibe, and not a config flag. A test I can run:

> **A cell is TYPED iff its option set is a closed, mutually-exclusive, jointly-exhaustive
> set of *world-states* AND the dungeon already holds a ground truth for it. A cell is a
> PREFERENCE iff every option is admissible and the answer only changes utility.**

Operationally: **does a ground-truth oracle exist for this cell?** If yes → typed, and the
oracle is what makes the judge's output *checkable* rather than merely *well-formed*.

The test is per-cell, decided at cell-construction time, and written down in the source
(`Kind` on the cell literal, plus a test that fails if a cell has a judge but no oracle).

| cell | option set | oracle in `GameState`? | kind | rung |
|---|---|---|---|---|
| `terrain@x,y` | `{corridor, wall, door, item, monster, player}` | yes — `Dungeon.Tiles` + entities | **TYPED** | JEV → MicroMoth |
| `behind_door@x,y` | `{lock, trap, creature, empty, illusory}` | yes — derived from `TileDoor` + level seed | **TYPED** | JEV → MicroMoth |
| `next_move` | `{advance, retreat, hold, detour}` | **no** — all four are legal moves | PREFERENCE | sampler only |
| `attack_or_pass` | `{attack, pass, reposition}` | **no** | PREFERENCE | sampler only |

Note the asymmetry this forces, and it is the whole point: **a preference cell never goes
to JEV, even when the API is up and even when it would be free.** Not as an optimisation —
as a correctness property. A judge handed `{advance, retreat, hold, detour}` will happily
return one, and that return will be *shaped like a world-state it is not*, and the policy
will start reading confidence off a preference. The sampler and the judge optimise
different things; **a rung that is wrong for a cell changes the policy's meaning, it does
not merely cost latency.**

## 3. The rungs, and what each one is allowed to do

```
RungJEV        slow, structured, typed, networked   -> returns a DISTRIBUTION over a closed set
RungSampler    fast, stochastic, unstructured       -> returns a DRAW from a distribution
RungMicroMoth  local, no API, no network            -> returns a point estimate + NO witness
```

The rule that makes the ladder mean something:

> **Only `RungJEV` may mint a witness.** The other two rungs may answer the cell; they may
> not certify it. A typed cell answered by a non-JEV rung is rendered as its answer with
> the witness mark *absent* — never as a lower-confidence witness.

Because the witness is a separate channel from the answer, losing rung 1 does not blank
the cell. **It un-witnesses it.** That is what makes the degradation per-cell instead of
global: the dungeon keeps playing, the glyphs stay correct, and exactly the cells whose
kind demanded an independent attestation are the ones that show the scar.

## 4. The three-run ladder, and the diff that proves the boundary is real

Same seed, three rungs: `all` / `nojev` / `noapi` (no JEV **and** no local engine). The
acceptance test:

> **If the three runs do not differ in a way explainable from the cell `kind`s alone, the
> rung boundary is decorative and this design is wrong.**

Predicted, before running (writing it down so the run can convict it):

- `noapi` must match `nojev` on **every TYPED cell's content** (MicroMoth is a local
  oracle, so content is preserved) and differ on **every PREFERENCE cell's draw**
  (no engine to draw from → deterministic local policy, a strictly narrower distribution).
- `nojev` must differ from `all` on **witness count only**, for typed cells, and on
  preference draws only through the JEV-tuned weights the sampler consumes.
- A cell kind that shows up in the diff when it shouldn't → the boundary leaked.

## 5. Batching discipline — measured, with the transport separated out

Three things I will measure, not cite:

1. **`noul` subject collapse.** Subjects must be named *explicitly* in the `noul`
   instructions. Unnamed subjects collapse to one shared answer. Measured by asking the
   same N questions batched-named vs batched-anonymous and comparing the answer vectors.
2. **`choice` needs the distribution, never the argmax.** The measurable is the divergence
   between the argmax-indicator distribution and the returned `probabilities` — i.e. how
   much a policy that reads only the argmax silently discards. Report per cell, not as a
   mean.
3. **Transport ≠ schema.** A 503/EOF from this endpoint is not evidence about the request
   shape. Every call carries `(attempts, lastTransportError, schemaErrors)` and a transport
   failure is **never** folded into an empty distribution. An empty result from a dropped
   socket and an empty result from a confident judge must be different types in the code,
   not the same `nil` map.

## 6. First runnable cell (in the real dungeon, not beside it)

`game/rung.go` + `game/rungcell.go` + `cmd/rungsim` — a **headless** runner, because a TUI
cannot be measured against three other lanes in a CI-shaped run. It constructs a real
`GameState` via the real `NewGameState`/`GenerateDungeon` (same seeded RNG, same BSP, same
placement rules), walks a policy over it, and prints the glyph array with per-cell rung
and witness annotation.

The first runnable cell, verbatim in `game/rungcell.go`:

```go
// Rung is the ladder rung a cell is answered on. It is a property of the CELL,
// never a global mode — that is the entire design.
type Rung int
const (
    RungJEV Rung = iota // networked, typed, mints a witness
    RungSampler         // stochastic, draws, cannot mint a witness
    RungMicroMoth       // local, point estimate, cannot mint a witness
)

// Kind is decided by the ORACLE TEST, not by configuration:
// does GameState already hold a ground truth for this cell?
type Kind int
const (
    KindTyped Kind = iota      // closed option set over world-states; oracle exists
    KindPreference            // every option admissible; answer is only utility
)

type Cell struct {
    ID     string
    X, Y   int
    Kind   Kind
    Rung   Rung
    // options IS the type. JEV's `criteria` is this map, and the judge may
    // not return anything outside it.
    Options map[string]bool
}
```

and the first typed cell:

```go
// TerrainCell is TYPED: every option is a world-state, mutually exclusive,
// jointly exhaustive over {corridor,wall,door,item,monster,player}, and
// Dungeon.Tiles + the entity lists already hold the ground truth.
func TerrainCell(x, y int) Cell {
    return Cell{ID: fmt.Sprintf("terrain@%d,%d", x, y), X: x, Y: y,
        Kind: KindTyped, Rung: RungJEV,
        Options: map[string]bool{"corridor":true, "wall":true, "door":true,
                                 "item":true, "monster":true, "player":true}}
}
```

## 7. Where this is going after the stub

- [ ] `cmd/rungsim` renders a real dungeon headlessly with witness marks
- [ ] the three-run ladder diff (`all` / `nojev` / `noapi`) against §4's predictions
- [ ] the noul-collapse and argmax-vs-distribution measurements
- [ ] rung changes stamped on the timeline, and policy comparisons spanning one reported
      `CONFOUNDED` (the syncopation interaction: a rung change inside a system-two's
      unobserved window silently invalidates the evaluation set that only the lag can give)
- [ ] propose the `gh-dungeons` patch as a forkable diff, not a push
