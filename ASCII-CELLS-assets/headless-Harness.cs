using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using ASCII_FPS;
using ASCII_FPS.GameComponents;
using ASCII_FPS.GameComponents.Enemies;
using ASCII_FPS.Scenes;
using ASCII_FPS.Scenes.Generators;
using Headless;
using Microsoft.Xna.Framework;

namespace ASCII_FPS
{
    /// <summary>A GameObject that only exists to carry a marker mesh for the ground-truth pass.</summary>
    public class MarkerObject : GameObject
    {
        public MarkerObject(MeshObject m) : base(m) { }
        public override void Update(float dt) { }
        public override void Save(BinaryWriter w) { }
    }

    public class Harness
    {
        const string CONTENT = "/tmp/asciipoc/ASCII_FPS/Content/";
        static AsciiTexture FLAT_GREEN;   // ground-truth marker texture
        static AsciiTexture FLAT_RED;     // second marker texture (unused, kept for symmetry)

        static System.Reflection.FieldInfo ZBUF;

        public static int Main(string[] args)
        {
            string outDir = args.Length > 0 ? args[0] : "/tmp/frames";
            int nScenes = args.Length > 1 ? int.Parse(args[1]) : 20;
            int posesPerScene = args.Length > 2 ? int.Parse(args[2]) : 6;
            Directory.CreateDirectory(outDir);

            LoadAssets();
            MakeMarkers();
            ZBUF = typeof(Rasterizer).GetField("zBuffer", BindingFlags.NonPublic | BindingFlags.Instance);

            // --- Roster census, by EXECUTION not by filename -----------------------
            var roster = new SortedDictionary<string, int>();
            var rosterByGen = new SortedDictionary<string, SortedDictionary<string, int>>();
            for (int s = 0; s < 160; s++)
            {
                int floor = 1 + (s / 4) % 20;          // 100 floors per generator, floors 1..20
                if (s % 40 == 0) System.Console.Error.WriteLine($"census {s}/160 floor {floor} ...");
                ASCII_FPS g = NewGame();
                Scene sc = MakeScene(g, floor);
                string gen = sc.GetType().Name.Replace("SceneGenerator", "");
                if (!rosterByGen.TryGetValue(gen, out var sub)) { sub = new SortedDictionary<string, int>(); rosterByGen[gen] = sub; }
                foreach (GameObject go in sc.gameObjects)
                {
                    string k = go.GetType().Name;
                    roster[k] = roster.TryGetValue(k, out int n) ? n + 1 : 1;
                    sub[k] = sub.TryGetValue(k, out int m) ? m + 1 : 1;
                }
            }
            using (StreamWriter sw = new StreamWriter(Path.Combine(outDir, "roster.txt")))
            {
                sw.WriteLine("# GameObject subclasses observed in scene.gameObjects over 160 generated floors (40 per generator)");
                sw.WriteLine("# (execution census: every object placed by the real SceneGenerator)");
                foreach (var kv in roster) sw.WriteLine($"{kv.Key}\t{kv.Value}");
                sw.WriteLine();
                sw.WriteLine("# broken down by generator, 40 floors each, floors 1..10");
                foreach (var g in rosterByGen)
                {
                    sw.WriteLine($"## {g.Key}");
                    foreach (var kv in g.Value) sw.WriteLine($"{kv.Key}\t{kv.Value}");
                }
            }
            System.Console.WriteLine("roster: " + string.Join(", ", roster.Select(kv => kv.Key + "=" + kv.Value)));

            // --- Frames --------------------------------------------------------------
            var cells = new Dictionary<string, int>();
            int markerOverlap = 0, markerCells = 0, totalCells = 0, realMarkerCells = 0;
            int written = 0;
            var glyphHist = new int[128];
            var colourHist = new Dictionary<int, int>();

            for (int s = 0; s < nScenes; s++)
            {
                ASCII_FPS g = NewGame();
                int floor = 1 + (s % 6);
                Scene scene = MakeScene(g, floor);
                g.Scene = scene;
                scene.Camera = new Camera(0.5f, 1000f, (float)Math.PI / 2.5f, 16f / 9f);
                scene.Visited[SceneGenerator.size / 2, SceneGenerator.size / 2] = true;

                var console = new Console(160, 90);
                var maskConsole = new Console(160, 90);
                var raster = new Rasterizer(console);
                var maskRaster = new Rasterizer(maskConsole);

                // Camera poses: the room-centre view, then one per living monster.
                // Pose 0 is the game's own start view: the centre room, looking along +Z.
                var poses = new List<(Vector3 pos, float rot, string tag)>();
                poses.Add((new Vector3(0f, 0f, 0f), 0f, "start"));
                // Poses 1.. are monster-facing, at four stand-off distances, so the fog ramp
                // is sampled across its whole range ON the same object. This is what tests the
                // depth-encoding claim directly: does the glyph change with distance?
                float[] dists = { 9f, 16f, 26f, 40f };
                int mi = 0;
                foreach (GameObject go in scene.gameObjects.OfType<Monster>())
                {
                    Vector3 m = go.Position;
                    for (int d = 0; d < dists.Length && mi < 64; d++)
                    {
                        float ang = (float)(mi * 2.399963f);
                        Vector3 off = new Vector3((float)Math.Cos(ang), 0f, (float)Math.Sin(ang)) * dists[d];
                        Vector3 p = new Vector3(m.X + off.X, 0f, m.Z + off.Z);
                        Vector3 dir = new Vector3(m.X - p.X, 0f, m.Z - p.Z);
                        poses.Add((p, (float)Math.Atan2(dir.X, dir.Z),
                            "mon_" + go.GetType().Name + "_d" + (int)dists[d]));
                        mi++;
                    }
                }
                if (posesPerScene < poses.Count) poses = poses.Take(posesPerScene).ToList();

                for (int p = 0; p < poses.Count; p++)
                {
                    var pose = poses[p];
                    scene.Camera.CameraPos = pose.pos;
                    scene.Camera.Rotation = pose.rot;

                    // PASS 1: the real frame.
                    raster.Raster(scene);
                    // Ground truth depth: the game's own z-buffer, read out of the Rasterizer.
                    float[,] z = (float[,])ZBUF.GetValue(raster);

                    // PASS 2: ground-truth "is an enemy visible here" mask. Same scene, same
                    // camera, same z-buffer; the ONLY change is that every enemy triangle gets
                    // a flat marker texture. Zones are untouched, so occlusion is identical.
                    var realObjects = scene.gameObjects;
                    var markers = new List<GameObject>();
                    foreach (GameObject go in realObjects)
                    {
                        if (go is Monster)
                        {
                            MeshObject src = go.MeshObject;
                            var tris = new List<Triangle>();
                            foreach (Triangle t in src.triangles)
                                tris.Add(new Triangle(t.V0, t.V1, t.V2, FLAT_GREEN, t.UV0, t.UV1, t.UV2));
                            markers.Add(new MarkerObject(new MeshObject(tris, src.Position, src.Rotation)));
                        }
                    }
                    scene.gameObjects = markers;
                    maskRaster.Raster(scene);
                    scene.gameObjects = realObjects;

                    using (var sw = new StreamWriter(Path.Combine(outDir, $"scene{s:000}_pose{p:00}.txt")))
                    {
                        sw.WriteLine("# Asciipocalypse frame -- EXTRACTED by executing the game's own Rasterizer.Raster()");
                        sw.WriteLine($"# scene {s} floor {floor} pose {p} tag {pose.tag} cam=({pose.pos.X:0.0},{pose.pos.Y:0.0},{pose.pos.Z:0.0}) rot={pose.rot:0.000}");
                        sw.WriteLine($"# console {160}x90  triangles={ASCII_FPS.triangleCount} clipped={ASCII_FPS.triangleCountClipped} zones={ASCII_FPS.zonesRendered}");
                        sw.WriteLine("# DATA -- Console.Data[i,j], the 10-character fog ramp @&#8x*,:. selected by the z-buffer");
                        for (int j = 0; j < 90; j++)
                        {
                            var sb = new System.Text.StringBuilder(160);
                            for (int i = 0; i < 160; i++) sb.Append(console.Data[i, j]);
                            sw.WriteLine(sb.ToString());
                        }
                        sw.WriteLine("# COLOR -- Console.Color[i,j] as 2 hex digits: R:3 G:3 B:2 packed, 00..ff");
                        for (int j = 0; j < 90; j++)
                        {
                            var sb = new System.Text.StringBuilder(320);
                            for (int i = 0; i < 160; i++) sb.Append(console.Color[i, j].ToString("x2", CultureInfo.InvariantCulture));
                            sw.WriteLine(sb.ToString());
                        }
                        sw.WriteLine("# Z -- the game's own zBuffer, NDC depth, -1 near .. +1 far; '---' = no surface");
                        for (int j = 0; j < 90; j++)
                        {
                            var sb = new System.Text.StringBuilder(160 * 6);
                            for (int i = 0; i < 160; i++)
                            {
                                float zz = z[i, j];
                                sb.Append(zz >= 1f ? "    --- " : (zz.ToString("0.000", CultureInfo.InvariantCulture) + "   ").Substring(0, 8));
                            }
                            sw.WriteLine(sb.ToString());
                        }
                        sw.WriteLine("# LABEL_ENEMY -- '1' where the nearest surface is a living enemy (marker-texture pass)");
                        for (int j = 0; j < 90; j++)
                        {
                            var sb = new System.Text.StringBuilder(160);
                            for (int i = 0; i < 160; i++) sb.Append(maskConsole.Color[i, j] == 56 ? '1' : '0');
                            sw.WriteLine(sb.ToString());
                        }
                        for (int j = 0; j < 90; j++)
                            for (int i = 0; i < 160; i++)
                            {
                                totalCells++;
                                bool e = maskConsole.Color[i, j] == 56;
                                if (e) { markerCells++; if (console.Color[i, j] == 56) markerOverlap++; }
                                if (console.Color[i, j] == 56) realMarkerCells++;
                                glyphHist[Math.Min(127, (int)console.Data[i, j])]++;
                                colourHist.TryGetValue(console.Color[i, j], out int c); colourHist[console.Color[i, j]] = c + 1;
                            }
                    }
                    written++;
                }
            }

            using (var sw = new StreamWriter(Path.Combine(outDir, "census.txt")))
            {
                sw.WriteLine($"# cells total {totalCells}");
                sw.WriteLine($"# cells where the enemy marker texture won the z-buffer: {markerCells}");
                sw.WriteLine($"# of those, how many the REAL frame also shows as colour 0x38 (marker code): {markerOverlap}");
                sw.WriteLine($"# FALSE POSITIVES: marked cells whose real-frame colour is NOT the marker code: {(markerCells - markerOverlap)}");
                sw.WriteLine($"# FALSE NEGATIVES: real-frame cells that are 0x38 but were not marked: {realMarkerCells}");
                sw.WriteLine($"# real-frame cells with colour 0x38: {realMarkerCells}");
                sw.WriteLine("# distinct glyphs observed in real frames: char count");
                foreach (var c in " @&#8x*,:.") sw.WriteLine($"#   '{c}'  {glyphHist[(int)c]}");
                for (int gi = 0; gi < 128; gi++)
                    if (!" @&#8x*,:.".Contains((char)gi) && glyphHist[gi] > 0)
                        sw.WriteLine($"#   U+{gi:0000}  {glyphHist[gi]}");
                sw.WriteLine("# distinct colours observed: " + colourHist.Count);
            }
            System.Console.WriteLine($"wrote {written} frames to {outDir}");
            return 0;
        }

        static ASCII_FPS NewGame()
        {
            var g = new ASCII_FPS();
            g.PlayerStats = new PlayerStats { health = 100f, maxHealth = 100f, armor = 100f, maxArmor = 100f, floor = 1 };
            return g;
        }

        static Scene MakeScene(ASCII_FPS g, int floor)
        {
            SceneGenerator gen;
            switch (floor % 4)
            {
                case 1: gen = new SceneGeneratorJungle(g, floor); break;
                case 2: gen = new SceneGeneratorLava(g, floor); break;
                case 3: gen = new SceneGeneratorIce(g, floor); break;
                default: gen = new SceneGeneratorDefault(g, floor); break;
            }
            return gen.Generate();
        }

        static void MakeMarkers()
        {
            FLAT_GREEN = FlatTexture(0f, 0.9f, 0f);
            FLAT_RED = FlatTexture(0.9f, 0f, 0f);
        }

        /// <summary>A 256x256 AsciiTexture of one constant colour, built exactly like TextureForge.Load.</summary>
        static AsciiTexture FlatTexture(float r, float g, float b)
        {
            var colors = new Vector3[256, 256];
            for (int j = 0; j < 256; j++)
                for (int i = 0; i < 256; i++)
                    colors[i, j] = new Vector3(r, g, b);
            return TextureForge.FromColors(colors);
        }

        static void LoadAssets()
        {
            foreach (FieldInfo f in typeof(Assets).GetFields())
            {
                var attr = f.GetCustomAttribute<AssetPathAttribute>();
                if (attr == null) continue;
                if (f.FieldType == typeof(AsciiTexture))
                    f.SetValue(null, TextureForge.Load(CONTENT + attr.Path + ".png"));
                else if (f.FieldType == typeof(OBJContentPipelineExtension.OBJFile))
                    f.SetValue(null, ObjReader.Read(CONTENT + attr.Path + ".obj"));
                else if (f.FieldType == typeof(Microsoft.Xna.Framework.Audio.SoundEffect))
                    f.SetValue(null, null);
            }
        }
    }
}
