// Frame extractor.  Runs the real simulation + the real Rasterizer, headless,
// and writes one record per frame:
//
//   frames.bin   fixed-width per-cell arrays  (char, colour8, z, texId, ownerId)
//   ground.json  per-frame scene-graph ground truth
//   meta.json    provenance
//
// Nothing here reconstructs a frame.  Every number comes out of Rasterizer.Raster()
// on a live Scene.

using ASCII_FPS.GameComponents;
using ASCII_FPS.GameComponents.Enemies;
using ASCII_FPS.Scenes;
using Microsoft.Xna.Framework;
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;

namespace ASCII_FPS
{
    public static class Program
    {
        static int W = 160, H = 90, NFRAMES = 120;
        static Vector3 spawn;
        static int SeedGame, SeedRaster;
        static string OutDir;
        static int Stride = 11;
        static char[] snapCh;
        // Rasterizer.cs:22, verbatim -- index 0 is the NEAREST bucket
        static readonly string FOG = "@" + "&" + "#" + "8x*,:. ";   // ch, colour8, z, owner, tex, hud-overwritten

        static List<string> ownerTable = new List<string>();
        static Dictionary<string, int> ownerIds = new Dictionary<string, int>();
        static List<string> texTable = new List<string>();
        static Dictionary<string, int> texIds = new Dictionary<string, int>();

        public static int Main(string[] argv)
        {
            var a = Args(argv);
            W = a.GetValueOrDefault("w", 160);
            H = a.GetValueOrDefault("h", 90);
            NFRAMES = a.GetValueOrDefault("frames", 120);
            SeedGame = a.GetValueOrDefault("seed", 12345);
            SeedRaster = a.GetValueOrDefault("rseed", 777);
            OutDir = args.TryGetValue("out", out string od) ? od : "frames";
            Directory.CreateDirectory(OutDir);

            // --- texture path: CPU-side PNG read into AsciiTexture (option 2) ---
            HeadlessAssets.LoadAll(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "ASCII_FPS", "Content"));

            // --- BALANCED identity scene: the de-degenerate task.  Rendered by the game's
            // --- own Rasterizer; only the choice of meshes changes.
            if (a.GetValueOrDefault("probe", 0) == 1)
                return RunProbe(a, W, H, NFRAMES, SeedGame, SeedRaster, OutDir);

            System.Console.WriteLine($"headless: {W}x{H} x{NFRAMES} gameSeed={SeedGame} ditherSeed={SeedRaster} out={OutDir} tex={HeadlessAssets.Loaded.Count}");
            Rasterizer.EyeEasy = a.GetValueOrDefault("eyeeasy", 0) == 1;
            Rasterizer.Gamma = 0f;
            Rasterizer.RandomSeed = SeedRaster;
            SceneGenerator.RandomSeed = SeedGame;

            var game = new ASCII_FPS();
            var console = new Console(W, H);
            var raster = new Rasterizer(console);
            game.HUD = new HUD(game, console);
            game.ResetGame(ASCII_FPS.Difficulty, SeedGame, a.GetValueOrDefault("floor", 1));

            snapCh = new char[W * H];
            var snapCol = new byte[W * H];
            var gt = new List<Dictionary<string, object>>();
            var backproj = new List<Dictionary<string, object>>();
            var gt_spawn = new List<Vector3>();
            using var bin = new BinaryWriter(File.Create(Path.Combine(OutDir, "frames.bin")));

            // script: a list of (dx,dz,rotDelta) the player applies, dt=1/60

            // spawn: the game spawns the player at the map centre; find an open spot near
            // it using the game's own collision test, so the walk is not stuck on frame 1
            var sc = game.Scene;
            Vector3 spawn = new Vector3(0f, 0f, 0f);
            bool spawnOk = false;
            for (float r = 0f; r < 60f && !spawnOk; r += 2.5f)
                for (float th = 0f; th < 6.28f && !spawnOk; th += 0.5f)
                {
                    var p0 = new Vector3((float)(r * Math.Cos(th)), 0f, (float)(r * Math.Sin(th)));
                    bool clear = true;
                    for (int d = 0; d < 8 && clear; d++)
                    {
                        var dir = new Vector3((float)Math.Cos(d * 0.7854), 0f, (float)Math.Sin(d * 0.7854));
                        clear = sc.CheckMovement(p0, dir * 3f, PlayerStats.thickness, ObstacleLayerMask.Everything);
                    }
                    if (clear) { spawn = p0; spawnOk = true; }
                }
            sc.Camera.CameraPos = spawn;
            gt_spawn.Add(spawn);

            // --- mode "observe": the camera is placed where the monsters are.
            // The scene is untouched; only the observer's position is scripted.
            // Labelled in meta.json: camera_placement = scripted.
            int observe = a.GetValueOrDefault("observe", 0);
            int viewDist = a.GetValueOrDefault("dist", 42);

            for (int f = 0; f < NFRAMES; f++)
            {
                float dt = 1f / 60f;
                var cam = game.Scene.Camera;
                Vector3 real;
                if (observe == 1)
                {
                    // hold an observation post near the monster cluster, drift slowly
                    if (f % 40 == 0) PlaceObserver(game, raster, viewDist, f);
                    real = game.Scene.SmoothMovement(cam.CameraPos, new Vector3((float)Math.Cos(cam.Rotation + 1.57f), 0, (float)Math.Sin(cam.Rotation + 1.57f)) * 6f * dt, PlayerStats.thickness, ObstacleLayerMask.Everything);
                    cam.CameraPos += real;
                }
                else
                {
                    // scripted player: walk; when the level blocks us, turn.  Movement goes
                    // through Scene.SmoothMovement, the game's own collision response.
                    float c = (float)Math.Cos(cam.Rotation), s = (float)Math.Sin(cam.Rotation);
                    Vector3 wish = new Vector3(c, 0, s) * 20f * dt;       // 20 u/s, the game's own speed
                    real = game.Scene.SmoothMovement(cam.CameraPos, wish, PlayerStats.thickness, ObstacleLayerMask.Everything);
                    if (real.Length() < wish.Length() * 0.35f)
                    {
                        for (int turn = 1; turn <= 4; turn++)            // try 45/90/135/180 deg
                        {
                            float a2 = cam.Rotation + turn * 0.7854f;
                            var alt = new Vector3((float)Math.Cos(a2), 0, (float)Math.Sin(a2)) * 20f * dt;
                            var r2 = game.Scene.SmoothMovement(cam.CameraPos, alt, PlayerStats.thickness, ObstacleLayerMask.Everything);
                            if (r2.Length() > alt.Length() * 0.5f) { real = r2; cam.Rotation = a2; break; }
                        }
                    }
                    cam.CameraPos += real;
                }
                int prx = (int)(cam.CameraPos.X / SceneGenerator.tileSize + SceneGenerator.size / 2f);
                int pry = (int)(cam.CameraPos.Z / SceneGenerator.tileSize + SceneGenerator.size / 2f);
                if (prx >= 0 && prx < SceneGenerator.size && pry >= 0 && pry < SceneGenerator.size)
                    game.Scene.Visited[prx, pry] = true;          // as PlayerLogic does

                game.Scene.UpdateGameObjects(dt);
                raster.Raster(game.Scene);
                // --- snapshot the PURE 3D frame, before any HUD overlay ---
                for (int i = 0; i < W; i++)
                    for (int j = 0; j < H; j++)
                    {
                        snapCh[i * H + j] = console.Data[i, j];
                        snapCol[i * H + j] = console.Color[i, j];
                    }
                game.HUD.Draw();

                // ---- per-cell record, straight out of the rasterizer ----
                for (int i = 0; i < W; i++)
                {
                    for (int j = 0; j < H; j++)
                    {
                        char c0 = snapCh[i * H + j];
                        bin.Write((byte)(char.IsHighSurrogate(c0) ? 63 : c0));
                        bin.Write(snapCol[i * H + j]);
                        bin.Write(raster.CellZ[i, j]);
                        bin.Write((ushort)OwnerId(raster.CellOwner[i, j]));
                        bin.Write((ushort)TexIdOf(raster.CellTexId[i, j]));
                        // did the HUD overwrite this cell?  then it is not rasterizer output
                        bin.Write((byte)(console.Data[i, j] == c0 && console.Color[i, j] == snapCol[i * H + j] ? 0 : 1));
                    }
                }

                gt.Add(GroundTruth(game, raster, f, a.GetValueOrDefault("floor", 1)));
                backproj.Add(BackProject(game, raster, f));
            }

            var meta = new Dictionary<string, object>
            {
                ["provenance"] = "extracted: Rasterizer.Raster() on a live Scene, headless, seeded",
                ["eye_easy"] = Rasterizer.EyeEasy,
                ["camera_placement"] = a.GetValueOrDefault("observe", 0) == 1 ? "scripted observer post near the nearest monster" : "scripted walk, game collision response",
                ["observe"] = a.GetValueOrDefault("observe", 0),
                ["audio_calls_suppressed"] = HeadlessAudio.calls,
                ["source"] = "github.com/wonrzrzeczny/Asciipocalypse @ HEAD (clone 2026-10-02)",
                ["width"] = W, ["height"] = H, ["frames"] = NFRAMES,
                ["game_seed"] = SeedGame,
                ["floor"] = a.GetValueOrDefault("floor", 1), ["raster_dither_seed"] = SeedRaster,
                ["texture_path"] = "CPU-side PNG read into AsciiTexture (option 2 of the brief)",
                ["textures_loaded"] = HeadlessAssets.Loaded,
                ["nonopaque_alpha_textures"] = HeadlessAssets.AlphaHistogram.Where(k => k.Value > 0).Select(k => k.Key + ":" + k.Value).Cast<object>().ToList(),
                ["cell_stride_bytes"] = Stride,
                ["owner_table"] = ownerTable,
                ["tex_table"] = texTable,
                ["triangles"] = ASCII_FPS.triangleCount,
            };
            File.WriteAllText(Path.Combine(OutDir, "ground.json"), Json(gt));
            File.WriteAllText(Path.Combine(OutDir, "backproj.json"), Json(backproj));
            File.WriteAllText(Path.Combine(OutDir, "meta.json"), Json(new[] { meta }));
            System.Console.WriteLine($"wrote {NFRAMES} frames of {W}x{H} to {OutDir}; owners={ownerTable.Count}");
            return 0;
        }

        // Put the camera near the nearest monster and KEEP the placement only if the
        // real z-buffer says the monster actually won a cell.  The instrument decides,
        // not a geometric argument about where it "should" be visible.
        static void PlaceObserver(ASCII_FPS game, Rasterizer raster, int d, int frame)
        {
            var scene = game.Scene;
            Monster best = null; float bestDist = float.MaxValue; int bestIdx = -1;
            for (int i = 0; i < scene.gameObjects.Count; i++)
            {
                if (scene.gameObjects[i] is Monster m && !m.Destroy)
                {
                    float dd = Vector3.Distance(m.Position, scene.Camera.CameraPos);
                    if (dd < bestDist) { bestDist = dd; best = m; bestIdx = i; }
                }
            }
            if (best == null) return;
            var tgt = best.Position;
            for (int ring = 0; ring < 5; ring++)
            {
                float dd = d * (0.5f + 0.3f * ring);
                for (int a = 0; a < 32; a++)
                {
                    float ang = frame * 0.37f + a * 0.19635f;
                    var p = new Vector3(tgt.X + (float)Math.Cos(ang) * dd, 0f, tgt.Z + (float)Math.Sin(ang) * dd);
                    bool clear = true;
                    for (int k = 0; k < 8 && clear; k++)
                    {
                        var dir = new Vector3((float)Math.Cos(k * 0.7854), 0, (float)Math.Sin(k * 0.7854));
                        clear = scene.CheckMovement(p, dir * 2f, PlayerStats.thickness, ObstacleLayerMask.Everything);
                    }
                    if (!clear) continue;
                    scene.Camera.CameraPos = p;
                    scene.Camera.Rotation = (float)Math.Atan2(tgt.Z - p.Z, tgt.X - p.X);
                    raster.Raster(scene);
                    if (OwnerCount(raster, bestIdx) > 0) return;      // the z-buffer agrees
                }
            }
        }

        static int OwnerCount(Rasterizer raster, int objIndex)
        {
            int n = 0;
            for (int i = 0; i < raster.CellOwner.GetLength(0); i++)
                for (int j = 0; j < raster.CellOwner.GetLength(1); j++)
                {
                    var t = raster.CellOwner[i, j] as object[];
                    if (t != null && t[0].Equals("obj") && (int)t[1] == objIndex) n++;
                }
            return n;
        }

        static (float, float, float)[] BuildScript(int which)
        {
            // (dx, dz, dRot) per frame -- walks the player around the generated level
            if (which == 0) return new[] { (0f, 1f, 0.0009f) };
            if (which == 1) return new[] { (1f, 0.4f, 0.0006f) };
            if (which == 2) return new[] { (0f, 0f, 0.004f) };
            if (which == 3) return new[] { (0.6f, 0.6f, 0.0012f) };
            return new[] { (0f, 1f, 0f) };
        }

        static int OwnerId(object tag)
        {
            if (tag == null) return 0;
            var a = (object[])tag;
            string key = string.Join("|", a.Select(v => v is Vector3 p ? $"{p.X:F2},{p.Y:F2},{p.Z:F2}" : v.ToString()));
            // [RERENDER FIX] ids start at 1: 0 is reserved for "no owner" (background/sky),
            // so an empty cell can never inherit the first object's label.
            if (!ownerIds.TryGetValue(key, out int id)) { id = ownerTable.Count + 1; ownerTable.Add(key); ownerIds[key] = id; }
            return id;
        }

        static int TexIdOf(int rasterizerTexId)
        {
            if (rasterizerTexId < 0) return 0;
            string name = null;
            foreach (var kv in Rasterizer.texIds) if (kv.Value == rasterizerTexId) { name = kv.Key; break; }
            if (name == null) return 0;
            if (!texIds.TryGetValue(name, out int id)) { id = texTable.Count; texTable.Add(name); texIds[name] = id; }
            return id;
        }

        // ---- ground truth: the scene graph, not the frame ----
        static Dictionary<string, object> GroundTruth(ASCII_FPS game, Rasterizer raster, int frame, int floor)
        {
            var cellsForOwner = new Dictionary<int, int>();
            for (int i = 0; i < W; i++)
                for (int j = 0; j < H; j++)
                {
                    int id = OwnerId(raster.CellOwner[i, j]);
                    cellsForOwner.TryGetValue(id, out int n);
                    cellsForOwner[id] = n + 1;
                }

            var ents = new List<Dictionary<string, object>>();
            int idx = 0;
            foreach (GameObject go in game.Scene.gameObjects)
            {
                var a = new List<object>();
                // recover the owner id of this object's cells by its position
                ents.Add(new Dictionary<string, object>
                {
                    ["idx"] = idx++,
                    ["type"] = go.GetType().Name,
                    ["pos"] = new[] { go.Position.X, go.Position.Y, go.Position.Z },
                    ["triangles"] = go.MeshObject.triangles.Count,
                });
            }

            int totalTri = 0;
            foreach (GameObject go in game.Scene.gameObjects) totalTri += go.MeshObject.triangles.Count;

            return new Dictionary<string, object>
            {
                ["spawn"] = new[] { spawn.X, spawn.Y, spawn.Z },
                ["frame"] = frame,
                ["cam"] = new[] { game.Scene.Camera.CameraPos.X, game.Scene.Camera.CameraPos.Y, game.Scene.Camera.CameraPos.Z, game.Scene.Camera.Rotation },
                ["exit_room"] = new[] { game.Scene.ExitRoom.X, game.Scene.ExitRoom.Y },
                ["n_objects"] = game.Scene.gameObjects.Count,
                ["n_zones"] = game.Scene.zones.Count,
                ["object_triangles"] = totalTri,
                ["scene_triangles"] = game.Scene.TotalTriangles,
                ["rendered_triangles"] = ASCII_FPS.triangleCount,
                ["clipped_triangles"] = ASCII_FPS.triangleCountClipped,
                ["zones_rendered"] = ASCII_FPS.zonesRendered,
                ["objects"] = ents,
                ["cells_per_owner"] = cellsForOwner.ToDictionary(k => k.Key.ToString(), k => k.Value),
            };
        }

        // ---- recoverability probe -------------------------------------------------
        // For every scene object the z-buffer actually showed, back-project the centre
        // of its cells into the world, using (a) the depth the GLYPH encodes and (b) the
        // true depth, and compare both with the object position held in the scene graph.
        //   err_glyph  = what a downstream reader gets from the frame
        //   err_oracle = the same pipeline with perfect depth, i.e. pure raster loss
        static Dictionary<string, object> BackProject(ASCII_FPS game, Rasterizer raster, int frame)
        {
            var cam = game.Scene.Camera;
            var inv = Matrix.Invert(cam.CameraSpaceMatrix);
            float n = cam.Near, f = cam.Far;
            float nw = 2f * n * (float)Math.Tan(cam.Fov / 2);
            float nh = nw / cam.AspectRatio;
            var outp = new List<Dictionary<string, object>>();

            var cellSum = new Dictionary<int, double[]>();
            for (int i = 0; i < W; i++)
                for (int j = 0; j < H; j++)
                {
                    var t = raster.CellOwner[i, j] as object[];
                    if (t == null || !t[0].Equals("obj")) continue;
                    int idx = (int)t[1];
                    if (!cellSum.TryGetValue(idx, out var acc)) { acc = new double[6]; cellSum[idx] = acc; }
                    char g = snapCh[i * H + j];
                    int k = FOG.IndexOf(g);
                    acc[0] += i; acc[1] += j; acc[2] += 1;
                    acc[3] += k >= 0 ? Math.Pow((k + 0.5) / 10.0, 0.1) : double.NaN;
                    acc[4] += (k >= 0) ? 1 : 0;
                    acc[5] += raster.CellZ[i, j];
                }

            foreach (var kv in cellSum)
            {
                int idx = kv.Key;
                if (idx >= game.Scene.gameObjects.Count) continue;
                var go = game.Scene.gameObjects[idx];
                var acc = kv.Value;
                int ncell = (int)acc[2];
                double ci = acc[0] / ncell, cj = acc[1] / ncell;
                double zt = acc[4] > 0 ? acc[3] / acc[4] : double.NaN;
                double zo = acc[5] / ncell;
                Vector3 truth = go.Position;
                var wg = Project((float)ci, (float)cj, (float)zt, inv, n, f, nw, nh);
                var wo = Project((float)ci, (float)cj, (float)zo, inv, n, f, nw, nh);
                // the game's own matrices, forward: where does the true position land?
                var vclip = Vector4.Transform(
                    new Vector4(Vector3.Transform(truth, cam.CameraSpaceMatrix), 1f), cam.ProjectionMatrix);
                float pi = (vclip.X / vclip.W + 1f) * 0.5f * W;
                float pj = (-vclip.Y / vclip.W + 1f) * 0.5f * H;
                // the object's OWN geometry, projected with the game's matrices:
                // the screen box the z-buffer ought to have filled.
                float bi0 = float.MaxValue, bi1 = float.MinValue, bj0 = float.MaxValue, bj1 = float.MinValue;
                var wsm = go.MeshObject.WorldSpaceMatrix * cam.CameraSpaceMatrix;
                int cto = 0, ctj = 0;
                foreach (Triangle tr in go.MeshObject.triangles)
                {
                    foreach (Vector3 vv in new[] { tr.V0, tr.V1, tr.V2 })
                    {
                        var vc = Vector3.Transform(vv, wsm);
                        if (vc.Z <= 0.01f) continue;
                        var v4 = Vector4.Transform(new Vector4(vc, 1f), cam.ProjectionMatrix);
                        float fi = (v4.X / v4.W + 1f) * 0.5f * W;
                        float fj = (-v4.Y / v4.W + 1f) * 0.5f * H;
                        bi0 = Math.Min(bi0, fi); bi1 = Math.Max(bi1, fi);
                        bj0 = Math.Min(bj0, fj); bj1 = Math.Max(bj1, fj);
                        cto++; ctj++;
                    }
                }
                if (cto == 0) { bi0 = bi1 = bj0 = bj1 = 0; }
                int oi0 = int.MaxValue, oi1 = int.MinValue, oj0 = int.MaxValue, oj1 = int.MinValue;
                {
                    var yy2 = new List<int>(); var xx2 = new List<int>();
                    for (int i = 0; i < W; i++) for (int j = 0; j < H; j++)
                    { var tt = raster.CellOwner[i, j] as object[]; if (tt != null && tt[0].Equals("obj") && (int)tt[1] == idx) { xx2.Add(i); yy2.Add(j); } }
                    if (xx2.Count > 0) { oi0 = xx2.Min(); oi1 = xx2.Max(); oj0 = yy2.Min(); oj1 = yy2.Max(); }
                }
                outp.Add(new Dictionary<string, object>
                {
                    ["geom_bbox"] = new[] { bi0, bi1, bj0, bj1 },
                    ["cells_bbox"] = new[] { (float)oi0, (float)oi1, (float)oj0, (float)oj1 },
                    ["obj"] = idx,
                    ["type"] = go.GetType().Name,
                    ["cells"] = ncell,
                    ["centroid_i"] = (float)ci, ["centroid_j"] = (float)cj,
                    ["true_i"] = pi, ["true_j"] = pj,
                    ["z_true_mean"] = (float)zo,
                    ["z_glyph_mean"] = float.IsNaN((float)zt) ? float.NaN : (float)zt,
                    ["hit_own_cell"] = (int)Math.Round(pi) >= 0 && (int)Math.Round(pi) < W && (int)Math.Round(pj) >= 0 && (int)Math.Round(pj) < H
                                        ? ((int)Math.Round(pj) * W + (int)Math.Round(pi) >= 0 ? raster.CellOwner[(int)Math.Round(pi), (int)Math.Round(pj)] != null
                                          && (raster.CellOwner[(int)Math.Round(pi), (int)Math.Round(pj)] as object[])[1].Equals(idx) : false)
                                        : false,
                    ["true_dist"] = (float)Vector3.Distance(truth, cam.CameraPos),
                    ["err_glyph"] = float.IsNaN((float)zt) ? float.NaN : Vector3.Distance(wg, truth),
                    ["err_oracle_depth"] = Vector3.Distance(wo, truth),
                });
            }
            return new Dictionary<string, object> { ["frame"] = frame, ["cam"] = new[] { cam.CameraPos.X, cam.CameraPos.Y, cam.CameraPos.Z, cam.Rotation }, ["objects"] = outp };
        }

        // inverse of Rasterizer.RenderTriangles' projection.  Note w_clip = z_cam, so
        // z_ndc = A + B/z and the screen coordinates are divided by w before the NDC map.
        static Vector3 Project(float i, float j, float z, Matrix inv, float n, float f, float nw, float nh)
        {
            float xNdc = 2f * i / W - 1f;
            float yNdc = -(2f * j / H - 1f);
            float zc = 2f * f * n / ((f + n) - (f - n) * z);   // z_cam from z_ndc
            var cam = new Vector4(xNdc * zc * nw / (2f * n), -yNdc * zc * nh / (2f * n), zc, 1f);
            Vector4 w = Vector4.Transform(cam, inv);
            return new Vector3(w.X, w.Y, w.Z);
        }

        // ---------------------------------------------------------------------
        // BALANCED IDENTITY SCENE
        //
        // N identities, MATCHED depth, matched quad size, so the class mix is set by
        // geometry rather than by how much wall happened to be in frame.  The scene
        // graph is identical on every frame; only the observer moves, so the train/test
        // split over frames is a real split and the scene is genuinely held fixed.
        // ---------------------------------------------------------------------
        static int RunProbe(Dictionary<string, int> a, int W, int H, int NFRAMES,
                            int SeedGame, int SeedRaster, string OutDir)
        {
            Rasterizer.EyeEasy = a.GetValueOrDefault("eyeeasy", 0) == 1;
            Rasterizer.Gamma = 0f;
            Rasterizer.RandomSeed = SeedRaster;
            SceneGenerator.RandomSeed = SeedGame;
            int nIdent = a.GetValueOrDefault("nident", 8);
            float depth = a.GetValueOrDefault("depth", 60) / 1f;
            float spread = a.GetValueOrDefault("spread", 46) / 1f;
            float size = a.GetValueOrDefault("size", 34) / 1f;

            var game = new ASCII_FPS();
            var console = new Console(W, H);
            var raster = new Rasterizer(console);
            game.HUD = new HUD(game, console);
            game.ResetGame(ASCII_FPS.Difficulty, SeedGame, a.GetValueOrDefault("floor", 1));

            // strip the maze: the point is to hold identity balanced, not to look at walls
            game.Scene.gameObjects.Clear();
            game.Scene.zones.Clear();

            var probes = ProbeScene.Build(game, nIdent, depth, spread, size);
            foreach (var p in probes) game.Scene.gameObjects.Add(p);
            System.Console.WriteLine($"probe: {probes.Count} identities at depth={depth} spread={spread} size={size} "
                + $"W={W} H={H} EyeEasy={Rasterizer.EyeEasy} ditherSeed={SeedRaster}");

            var ownerNames = new List<string> { "none" };
            var ownerIdx = new Dictionary<string, int>();
            int OwnerOf(object tag)
            {
                if (tag == null) return 0;
                var t = (object[])tag;
                string key = "obj|" + t[3];                 // identity == the texture name
                if (!ownerIdx.TryGetValue(key, out int id)) { id = ownerNames.Count; ownerNames.Add(key); ownerIdx[key] = id; }
                return id;
            }

            using var bin = new BinaryWriter(File.Create(Path.Combine(OutDir, "frames.bin")));
            var perFrame = new List<Dictionary<string, object>>();

            for (int f = 0; f < NFRAMES; f++)
            {
                // small observer drift: the world is still, the viewpoint is not.  This is
                // what makes the frame split a real generalisation test.  Kept small: a
                // large drift walks probes off the frustum edge and re-creates the very
                // class imbalance this scene exists to remove.
                var cam = game.Scene.Camera;
                float t = f / (float)Math.Max(1, NFRAMES - 1);
                cam.CameraPos = new Vector3((float)Math.Sin(t * 2.2) * 0.8f, (float)Math.Sin(t * 3.1) * 0.5f, 0f);
                cam.Rotation = (float)Math.Sin(t * 1.7) * 0.02f;

                raster.Raster(game.Scene);

                var counts = new List<Dictionary<string, object>>();
                for (int i = 0; i < W; i++)
                    for (int j = 0; j < H; j++)
                    {
                        bin.Write((byte)console.Data[i, j]);
                        bin.Write(console.Color[i, j]);
                        bin.Write(raster.CellZ[i, j]);
                        bin.Write((ushort)OwnerOf(raster.CellOwner[i, j]));
                        bin.Write((ushort)0);
                        bin.Write((byte)0);
                    }
                // the custom Json writer handles Dictionary<string,object>, not
                // Dictionary<string,int> -- emit a list of pairs instead
                var tally = new Dictionary<int, int>();
                for (int i = 0; i < W; i++)
                    for (int j = 0; j < H; j++)
                    {
                        int oid = OwnerOf(raster.CellOwner[i, j]);
                        if (oid > 0) tally[oid] = tally.TryGetValue(oid, out int n) ? n + 1 : 1;
                    }
                foreach (var kv in tally)
                    counts.Add(new Dictionary<string, object>
                    {
                        ["identity"] = ownerNames[kv.Key],
                        ["cells"] = kv.Value,
                    });
                perFrame.Add(new Dictionary<string, object>
                {
                    ["frame"] = f,
                    ["cam"] = new[] { cam.CameraPos.X, cam.CameraPos.Y, cam.CameraPos.Z, cam.Rotation },
                    ["cells_per_identity"] = counts,
                    ["depth"] = depth,
                });
            }

            var meta = new Dictionary<string, object>
            {
                ["provenance"] = "extracted: Rasterizer.Raster() on a BALANCED probe scene built in the game's own scene graph, headless, seeded",
                ["balanced"] = true,
                ["n_identities"] = probes.Count,
                ["identities"] = probes.Select(p => p.Identity).ToList(),
                ["matched_depth"] = depth,
                ["matched_quad_size"] = size,
                ["eye_easy"] = Rasterizer.EyeEasy,
                ["width"] = W, ["height"] = H, ["frames"] = NFRAMES,
                ["game_seed"] = SeedGame, ["raster_dither_seed"] = SeedRaster,
                ["cell_stride_bytes"] = Stride,
                ["owner_table"] = ownerNames,
                ["texture_path"] = "CPU-side PNG read into AsciiTexture",
            };
            File.WriteAllText(Path.Combine(OutDir, "ground.json"), Json(perFrame));
            File.WriteAllText(Path.Combine(OutDir, "meta.json"), Json(new[] { meta }));
            System.Console.WriteLine($"wrote {NFRAMES} balanced frames of {W}x{H} to {OutDir}; identities={ownerNames.Count - 1}");
            return 0;
        }

        public static Dictionary<string, string> args = new Dictionary<string, string>();

        static Dictionary<string, int> Args(string[] argv)
        {
            var d = new Dictionary<string, int>();
            for (int i = 0; i < argv.Length - 1; i++)
                if (argv[i].StartsWith("--"))
                {
                    if (int.TryParse(argv[i + 1], NumberStyles.Integer, CultureInfo.InvariantCulture, out int v)) d[argv[i].Substring(2)] = v;
                    else args[argv[i].Substring(2)] = argv[i + 1];
                }
            return d;
        }

        public static string Json(object o)
        {
            var sb = new StringBuilder();
            Write(sb, o);
            return sb.ToString();
        }

        static void Write(StringBuilder sb, object o)
        {
            if (o == null) { sb.Append("null"); return; }
            if (o is string s) { sb.Append('"').Append(s.Replace("\\", "\\\\").Replace("\"", "\\\"")).Append('"'); return; }
            if (o is bool b) { sb.Append(b ? "true" : "false"); return; }
            if (o is float f) { sb.Append(f.ToString("R", CultureInfo.InvariantCulture)); return; }
            if (o is double dd) { sb.Append(dd.ToString("R", CultureInfo.InvariantCulture)); return; }
            if (o is int or short or byte or long or ushort) { sb.Append(Convert.ToString(o, CultureInfo.InvariantCulture)); return; }
            if (o is Dictionary<string, object> d)
            {
                sb.Append('{');
                bool first = true;
                foreach (var kv in d) { if (!first) sb.Append(','); first = false; sb.Append('"').Append(kv.Key).Append("\":"); Write(sb, kv.Value); }
                sb.Append('}');
                return;
            }
            if (o is System.Collections.IEnumerable en && !(o is string))
            {
                sb.Append('[');
                bool first = true;
                foreach (object e in en) { if (!first) sb.Append(','); first = false; Write(sb, e); }
                sb.Append(']');
                return;
            }
            if (o is IEnumerable<object> lst)
            {
                sb.Append('[');
                bool first = true;
                foreach (var e in lst) { if (!first) sb.Append(','); first = false; Write(sb, e); }
                sb.Append(']');
                return;
            }
            sb.Append(o.ToString());
        }
    }
}
