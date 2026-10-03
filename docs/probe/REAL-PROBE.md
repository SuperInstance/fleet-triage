# The real rasterizer, running headless — and it agrees with my reimplementation

2026-10-02. Every ASCII number in this repository until now came from a **Python
reimplementation** of `Rasterizer.cs:129`. One of those probes had already refuted
another the same night, so none of them were facts about the game. This runs the
**real types, the real arithmetic and the real RNG**, with no reimplementation.

## What was verified, in the game's own code

```
real Console: 9x3, Data type Char[,], Color Byte[,]
real Sample() headless: (0.25,0.5,0.75)  <- no GraphicsDevice, no Texture2D, no .xnb
real offset[0,0] = -0.278256  (one draw per cell, never redrawn)
REAL C# glyph occupancy: @=79.7%  &=5.5% #=3.5% 8=2.6% x=2.1% *=1.7% ,=1.4% :=1.3% .=1.2%  =1.0%
```

| claim | Python reimplementation | REAL C# | verdict |
|---|---|---|---|
| `Console.Data` is `char[,]`, `Color` is `byte[,]` | asserted from source | **confirmed by reflection** | ✅ |
| uniform depth → `'@'` in ~79% of cells | **79.13%** | **79.7%** | ✅ sampling noise |
| the dither is drawn ONCE per cell, unseeded | asserted from source | **`-0.278256`, one draw, never redrawn** | ✅ |
| `AsciiTexture.Sample()` needs no graphics device | predicted from the source | **confirmed — it runs headless** | ✅ |

## The unlock: the texture blocker is solved, and it was the last one

```csharp
public Vector3 Sample(Vector2 uv) {
    return colors[(int)(uv.X * 256) & 0xff, (int)(uv.Y * 256) & 0xff];
}
```

`Sample` is a **pure array read.** So an `AsciiTexture` can be built with
`FormatterServices.GetUninitializedObject` and its private `colors` array
injected by reflection — **no `GraphicsDevice`, no `Texture2D`, no `.xnb`, no
content pipeline, no window.**

> **This confirms the prediction in `ASCIIPORT.md` from reading the source, and
> it removes the last thing standing between this project and running the actual
> game.** Everything downstream — the two-arm colour test, the re-projection
> invariance test, the joint-recovery test, the time-query interface — can now
> run against the real renderer instead of a reimplementation of it.

## What is still NOT measured on the real renderer

Honest scope, because the distinction is the whole point of this document:

- ✅ the ramp, the cell structure, the offset RNG, `Sample()`
- ❌ **the projection pipeline** — `Raster(Scene)` does portal culling, zone
  splitting and z-buffering, and none of that has run yet
- ❌ **texture sampling from real PNGs** — the array is currently a constant, so
  nothing has been proved about identity-in-colour end to end
- ❌ **any frame from the running game**

**So the colour half of every result is still a claim, and the depth half is now
a measurement.** Those are the two channels the whole `joint.py` argument turns
on, and exactly one of them has been upgraded.

## Reproduce

`real_rasterizer_probe.cs` / `.csproj` — references the game's own `Console.cs`
and `AsciiTexture.cs`, plus `MonoGame.Framework.DesktopGL` for the `Vector2/3`
math types. `dotnet run -c Release`. No network at run time.
