// CPU-side asset loading.  Replaces MonoGame's ContentManager + Texture2D for
// textures (option 2 of the brief) and the MGCB-only OBJImporter for models.
//
//   * AsciiTexture is built by reflection on its private `colors` field, so the
//     AsciiTexture class itself is untouched except for the `Name` label.
//   * 29 PNGs -> Vector3[256,256], exactly the layout AsciiTexture.Sample reads.

using Microsoft.Xna.Framework;
using OBJContentPipelineExtension;
using SixLabors.ImageSharp;
using SixLabors.ImageSharp.PixelFormats;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;

namespace ASCII_FPS
{
    public static class HeadlessAssets
    {
        public static int Tex256 = 256;
        public static List<string> Loaded = new List<string>();
        public static Dictionary<string, int> AlphaHistogram = new Dictionary<string, int>();
        public static bool AnyNonOpaqueAlpha = false;

        public static AsciiTexture LoadPng(string path, string name)
        {
            using var img = Image.Load<Rgba32>(path);
            if (img.Width != 256 || img.Height != 256)
                throw new Exception($"{path}: not 256x256");

            var colors = new Vector3[256, 256];
            int nonOpaque = 0;
            img.ProcessPixelRows(a =>
            {
                for (int j = 0; j < 256; j++)
                {
                    var row = a.GetRowSpan(j);
                    for (int i = 0; i < 256; i++)
                    {
                        ref var p = ref row[i];
                        colors[i, j] = new Vector3(p.R / 255f, p.G / 255f, p.B / 255f);
                        if (p.A != 255) nonOpaque++;
                    }
                }
            });
            AlphaHistogram[name] = nonOpaque;
            if (nonOpaque > 0) AnyNonOpaqueAlpha = true;

            var t = (AsciiTexture)RuntimeHelpers.GetUninitializedObject(typeof(AsciiTexture));
            typeof(AsciiTexture).GetField("colors", BindingFlags.NonPublic | BindingFlags.Instance)
                               .SetValue(t, colors);
            typeof(AsciiTexture).GetProperty("ID").SetValue(t, HeadlessAssetRegistry.Register(t));
            t.Name = name;
            Loaded.Add(name);
            return t;
        }

        // minimal OBJ -> OBJFile (the struct MGCB's importer would have filled)
        public static OBJFile LoadObj(string path)
        {
            var verts = new List<Vector3>();
            var uvs = new List<Vector2>();
            var triV = new List<int>();
            var triT = new List<int>();
            foreach (string raw in File.ReadAllLines(path))
            {
                string line = raw.Trim();
                if (line.Length == 0 || line[0] == '#') continue;
                var parts = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                if (parts[0] == "v")
                {
                    verts.Add(new Vector3(F(parts[1]), F(parts[2]), F(parts[3])));
                }
                else if (parts[0] == "vt")
                {
                    uvs.Add(new Vector2(F(parts[1]), F(parts[2])));
                }
                else if (parts[0] == "f")
                {
                    // fan-triangulate, exactly as MGCB's OBJProcessor does
                    var fv = new List<int>();
                    var ft = new List<int>();
                    for (int k = 1; k < parts.Length; k++)
                    {
                        var seg = parts[k].Split('/');
                        fv.Add(I(seg[0]));
                        ft.Add(seg.Length > 1 && seg[1].Length > 0 ? I(seg[1]) : 0);
                    }
                    for (int k = 1; k + 1 < fv.Count; k++)
                    {
                        triV.Add(fv[0]); triT.Add(ft[0]);
                        triV.Add(fv[k]); triT.Add(ft[k]);
                        triV.Add(fv[k + 1]); triT.Add(ft[k + 1]);
                    }
                }
            }
            System.Console.WriteLine($"  obj {Path.GetFileName(path)}: v={verts.Count} vt={uvs.Count} triV={triV.Count} triT={triT.Count}");
            return new OBJFile
            {
                vertices = verts.ToArray(),
                texcoords = uvs.ToArray(),
                triangleVertices = triV.ToArray(),
                triangleTexcoords = triT.ToArray()
            };
        }

        static int I(string s)
        {
            int v = int.Parse(s);
            return v > 0 ? v - 1 : v; // OBJ is 1-based, negatives count from the end
        }
        static float F(string s) => float.Parse(s, System.Globalization.CultureInfo.InvariantCulture);

        // Assets.LoadAssets() by reflection: no ContentManager, no .xnb, no device.
        public static bool AUDIO_OK = false;

        public static void LoadAll(string contentRoot)
        {
            FieldInfo[] fields = typeof(Assets).GetFields();
            foreach (FieldInfo field in fields)
            {
                var attr = field.GetCustomAttribute<AssetPathAttribute>();
                if (attr == null) continue;
                if (field.FieldType == typeof(AsciiTexture))
                {
                    string png = Path.Combine(contentRoot, attr.Path + ".png");
                    field.SetValue(null, LoadPng(png, attr.Path));
                }
                else if (field.FieldType == typeof(OBJFile))
                {
                    field.SetValue(null, LoadObj(Path.Combine(contentRoot, attr.Path + ".obj")));
                }
                else if (field.FieldType == typeof(Microsoft.Xna.Framework.Audio.SoundEffect))
                {
                    // a real CPU-constructed SoundEffect: no device needed to build one.
                    // If this platform has no audio backend Play() will throw, and we fall
                    // back to null (see AUDIO_OK) rather than editing the game's call sites.
                    try { field.SetValue(null, new Microsoft.Xna.Framework.Audio.SoundEffect(new byte[8820], 44100, Microsoft.Xna.Framework.Audio.AudioChannels.Mono)); }
                    catch { field.SetValue(null, null); }
                }
                // SpriteFont stays null: nothing in the headless path reads it
            }
            try
            {
                var snd = new Microsoft.Xna.Framework.Audio.SoundEffect(new byte[8820], 44100, Microsoft.Xna.Framework.Audio.AudioChannels.Mono);
                snd.Play();
                AUDIO_OK = true;
            }
            catch (Exception e) { AUDIO_OK = false; System.Console.WriteLine("  audio unavailable: " + e.GetType().Name + " -- monsters held outside AttackDistance"); }
        }
    }

    public static class HeadlessAssetRegistry
    {
        static readonly List<AsciiTexture> list = new List<AsciiTexture>();
        public static int Register(AsciiTexture t) { int id = list.Count; list.Add(t); return id; }
    }
}
