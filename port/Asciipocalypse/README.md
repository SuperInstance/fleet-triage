# Asciipocalypse — headless port + projection-loss extractor

Upstream: `github.com/wonrzrzeczny/Asciipocalypse` (cloned 2026-10-02), unmodified
except for `INSTRUMENTATION.patch`, which shows **every** edit (10 files).

* `ASCII_FPS/` — the game. Project files ported to net9.0; `Rasterizer.cs`,
  `Scene.cs`, `Console.cs`, `HUD.cs` are upstream sources with the instrumentation
  added.
* `Headless/` — the extractor. Replaces *only* the MonoGame `Game` subclass
  (`ASCII_FPS.cs`) with a host that owns no window, no `GraphicsDevice`, no
  `SpriteBatch` and no keyboard. Textures are read from PNG on the CPU.
* `analysis/` — the measurements. `runall.py` produces every number in
  `../../PROJECTION-LOSS.md`; `validate.py` certifies the scene→cell correspondence
  against each object's own projected geometry.
* `datasets/` — 20 runs: scene-graph ground truth, back-projection probe and
  metadata for every one; full `frames.bin` for two of them.

## Run it

```sh
cd Headless && dotnet build
dotnet run --no-build -- --frames 200 --observe 1 --seed 11 --rseed 33 \
           --floor 1 --dist 42 --out /tmp/fx/run_111
cd ../analysis && python3 runall.py && python3 validate.py '/tmp/fx/run_*'
```

`--observe 1` places the camera on a free post near the nearest monster and keeps the
placement only if the real z-buffer agrees the monster wins at least one cell.
`--observe 0` is a free walk. `--eyeeasy 1` switches to the game's other projection
(`Rasterizer.cs:124`).
