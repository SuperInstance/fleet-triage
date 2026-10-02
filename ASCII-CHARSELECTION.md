# What the character actually encodes — and it is not identity

2026-10-02. Read `ASCIIPOCALYPSE.md` first; this corrects it.
**Three findings, one of which refutes a prediction I wrote six hours ago and
scored in `PREDICTIONS.md`.**

---

## 1. The glyph is a depth ramp. The colour is the object.

`ASCII_FPS/Geometry/Rasterizer.cs:22` and `:129-131`:

```csharp
private const string fogString = "@&#8x*,:. ";        // 10 characters

int fogId = (z < 0) ? 0
          : Math.Min((int)(Math.Pow(z, 10) * fogString.Length + offset[i, j]),
                     fogString.Length - 1);
console.Data[i, j]  = fogString[fogId];                       // ← character = DEPTH
console.Color[i, j] = Mathg.ColorTo8Bit(triangle.Texture.Sample(uv) * (1f + Gamma));  // ← colour = IDENTITY
```

> **The character is a function of `z` and nothing else. It does not know what
> object it is looking at.** The colour is a direct sample of that object's
> texture.

**So the two channels are not redundant views of the same thing — they are
orthogonal, and only one of them carries identity.**

---

## 2. MY PREDICTION IS REFUTED. I was backwards.

`PREDICTIONS.md` records, as a live prediction:

> *"for this game, the char arm and the colour arm should be nearly equally
> informative, and collapsing to char-only should lose little"*

**I reasoned that from the projection ladder — L1 colour-collapsed scored 0.8947
against L0 lossless 0.8831, so colour-collapse retained ~99% of recoverable
value — and I never checked whether this game's channels carried the same
information.**

**They do not.** In the ladder's task colour was a *redundant* channel and its
discard was cheap. **Here colour is the only channel carrying identity, and the
char arm is blind to identity by construction.** The L1 drop will be
catastrophic, not slight.

> **The same projection is cheap in one substrate and fatal in another, and you
> cannot predict which without knowing what each channel actually carries.**

**This is a correction to the doctrine, not just to a prediction.** The ladder
result is not a general law about colour; it is a fact about a task where the
channels agreed. **I generalised a measurement from a task without checking the
structure of the new one, which is the same error as calling `BattenSpline`
prose-only from ten greps.**

**Also note what this kills.** "Tile makers" keyed on glyph is not viable, because
the glyph is a function of depth — *a tile read from characters is a depth reading
with a false identity attached.* **The tile must be keyed on colour, and the
character must be demoted to a depth cue.**

---

## 3. The game is NOT deterministic. There is no seed.

`Rasterizer.cs:26`:  `rand = new Random();`  — **unseeded**, and it drives

```csharp
offset[i, j] = (float)rand.NextDouble() - 0.5f;   // Rasterizer.cs:36
```

which is **per-cell dither added to the depth index**. The character layer is
therefore **randomly dithered, differently on every run.**

> **Two identical runs produce different character buffers. Any frame-level
> measurement of this game is noise until the seed is controllable.**

**This has to be patched before any number means anything.** A lane that measured
the same bot twice, got two answers, and blamed the bot or the metric would have
been wrong twice, and neither of the available explanations is the right one.

**Required change: `new Random(seed)` and expose the seed.** Then every frame in
every report names the seed it was produced under. This is the
`CONNECT-4 ground truth` pattern — **a digest and a seed are what turn a demo
into a measurement.**

---

## 4. The texture blocker is smaller than I thought

`ASCII_FPS/AsciiTexture.cs` is **53 lines**, and the whole texture dependency is
confined to its **constructor**:

```csharp
public AsciiTexture(Texture2D texture) {
    Color[] color1d = new Color[256 * 256];   // reads once, at construction
    ...
}
public Vector3 Sample(Vector2 uv) { ... }      // pure data, no device
```

**`Sample()` operates on plain data.** The `Texture2D` is needed to get the
pixels *in*, once.

> **So headless does not require beating MGCB. It requires replacing one
> constructor** — read the 43 PNGs into a `Color[256*256]` on the CPU and build
> the `AsciiTexture` directly. **No `GraphicsDevice`, no content pipeline, no
> `.xnb`.**

**Which also means the game ships a built-in projection switch.** `Rasterizer.cs:124`:

```csharp
if (EyeEasy) {
    float d = Math.Clamp(1f - (float)Math.Pow(z, 25), 0f, 1f);
    console.Data[i, j] = '@';                                  // every cell '@'
    console.Color[i, j] = ... * d * (1f + Gamma);              // depth only in brightness
}
```

`EyeEasy` discards depth from the character channel **entirely** and moves it
into colour brightness. **So the game already contains both projections, one flag
apart** — which makes it a natural A/B: *the same scene, the same texture, the
same instant, two projections, and the task score under each is a direct
measurement of what each projection carries.*

**That is the projection ladder, live, inside a game, with a ground truth to score
against.** It is the strongest instrument anyone in this account has had for
testing the central doctrine.

---

## What to do with this, in order

1. **Seed the `Random`.** Without it, nothing else is measurable.
2. **Replace the `AsciiTexture` constructor** with a CPU-side PNG read. Unblocks
   headless.
3. **Score the same frames under both projections** against the scene graph. The
   delta is the cost of the character channel, measured.
4. **Key tiles on colour, not glyph.** The glyph is depth.

**And the honest caveat: the character channel may be doing useful work as a
*depth* cue even though it carries no identity.** A bot can tell "close" from
"far" from the glyph. What it cannot do is tell "monster" from "wall" from the
glyph alone. **Both halves of that sentence are results, and the second one is
the one that matters.**
