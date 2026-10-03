// HEADLESS SHIM for SuperInstance/Asciipocalypse.
// Every file under /tmp/asciipoc/ASCII_FPS is compiled BYTE-IDENTICAL (verified by sha256 in
// the report). This file adds NEW types only: the `ASCII_FPS` game class (the real one derives
// from Microsoft.Xna.Framework.Game and needs a GraphicsDevice), a HUD stub, and loaders that
// replace the MonoGame Content Pipeline (which needs a GraphicsDevice) with direct PNG/OBJ reads.
//
// Fidelity claim: the renderer path (Rasterizer, Camera, Mathg, Console, Zone, Scene, SceneGenerator,
// Triangle, MeshObject) is the game's own code, unmodified. The ONLY substitutions are:
//   * asset I/O (PNG->Vector3[,] instead of Texture2D, .obj->OBJFile instead of the content pipeline)
//   * the Game/UI/audio shell, which never touches the rasterizer.

using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using ASCII_FPS;
using ASCII_FPS.GameComponents;
using ASCII_FPS.GameComponents.Loaders;
using ASCII_FPS.Scenes;
using Microsoft.Xna.Framework;

namespace ASCII_FPS
{
    // Stand-in for the real `class ASCII_FPS : Game`. Only the members the renderer/scene code
    // touches are present. Verified by grep over the compiled file set: triangleCount,
    // triangleCountClipped, zonesRendered, PlayerStats, Scene, HUD.
    public class ASCII_FPS
    {
        public const string VERSION = "v1.2";
        public static int Difficulty = 0;
        public static Microsoft.Xna.Framework.Graphics.DisplayMode[] resolutions = new Microsoft.Xna.Framework.Graphics.DisplayMode[0];
        public bool IsActive { get; set; } = true;

        public static int triangleCount = 0;
        public static int triangleCountClipped = 0;
        public static int zonesRendered = 0;

        public PlayerStats PlayerStats = new PlayerStats();
        public HUD HUD;
        public Scene Scene { get; set; }
    }

    // The real HUD draws into a Console; the harness never draws the HUD, so this is
    // constructed but never rendered. The real HUD.cs is compiled unmodified.
}

namespace ASCII_FPS.GameComponents.Loaders
{
    // Only referenced from GameObject.Load via reflection by type name; the harness never saves,
    // but the compiler needs the names to exist. Loaders that need the (excluded) GameSave-free
    // content pipeline are intentionally minimal.
}

namespace Headless
{
    /// <summary>Minimal PNG reader: 8-bit, non-interlaced, colour types 2 (RGB) and 6 (RGBA).</summary>
    public static class Png
    {
        public static byte[,] DecodeRgba(string path, out int w, out int h)
        {
            w = 0; h = 0;
            byte[] data = File.ReadAllBytes(path);
            if (data[0] != 0x89 || data[1] != 'P' || data[2] != 'N' || data[3] != 'G')
                throw new Exception("not a png: " + path);

            int pos = 8;
            int bitDepth = 0, colourType = 0, interlace = 0;
            using MemoryStream idat = new MemoryStream();

            while (pos < data.Length)
            {
                int len = ReadBE32(data, pos);
                string type = System.Text.Encoding.ASCII.GetString(data, pos + 4, 4);
                int body = pos + 8;
                if (type == "IHDR")
                {
                    w = ReadBE32(data, body);
                    h = ReadBE32(data, body + 4);
                    bitDepth = data[body + 8];
                    colourType = data[body + 9];
                    interlace = data[body + 12];
                }
                else if (type == "IDAT")
                {
                    idat.Write(data, body, len);
                }
                else if (type == "IEND")
                {
                    break;
                }
                pos = body + len + 4;
            }

            if (bitDepth != 8) throw new Exception("bitdepth " + bitDepth + " unsupported: " + path);
            if (interlace != 0) throw new Exception("interlaced png unsupported: " + path);
            int channels = colourType == 6 ? 4 : colourType == 2 ? 3 : 0;
            if (channels == 0) throw new Exception("colour type " + colourType + " unsupported: " + path);

            byte[] raw = Inflate(idat.ToArray());
            int stride = w * channels;
            byte[] prev = new byte[stride];
            byte[] cur = new byte[stride];
            byte[] outp = new byte[stride * h];

            int p = 0;
            for (int y = 0; y < h; y++)
            {
                int filter = raw[p++];
                for (int i = 0; i < stride; i++) cur[i] = raw[p + i];
                p += stride;
                for (int i = 0; i < stride; i++)
                {
                    int a = i >= channels ? cur[i - channels] : 0;
                    int b = prev[i];
                    int c = i >= channels ? prev[i - channels] : 0;
                    int v = cur[i];
                    switch (filter)
                    {
                        case 0: break;
                        case 1: v += a; break;
                        case 2: v += b; break;
                        case 3: v += (a + b) / 2; break;
                        case 4:
                        {
                            int pp = a + b - c;
                            int pa = Math.Abs(pp - a), pb = Math.Abs(pp - b), pc = Math.Abs(pp - c);
                            v += (pa <= pb && pa <= pc) ? a : (pb <= pc ? b : c);
                            break;
                        }
                        default: throw new Exception("filter " + filter);
                    }
                    cur[i] = (byte)(v & 0xff);
                }
                Buffer.BlockCopy(cur, 0, outp, y * stride, stride);
                byte[] t = prev; prev = cur; cur = t;
            }

            byte[,] rgba = new byte[4 * w, h];  // four 256x256 planes: R, G, B, A
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                {
                    int o = y * stride + x * channels;
                    rgba[x, y] = outp[o];
                    rgba[x + w, y] = outp[o + 1];
                    rgba[x + 2 * w, y] = outp[o + 2];
                    rgba[x + 3 * w, y] = channels == 4 ? outp[o + 3] : (byte)255;
                }
            return rgba;
        }

        static byte[] Inflate(byte[] z)
        {
            // zlib wrapper: skip 2-byte header, feed raw deflate to DeflateStream.
            using MemoryStream src = new MemoryStream(z, 2, z.Length - 2);
            using DeflateStream ds = new DeflateStream(src, CompressionMode.Decompress);
            using MemoryStream dst = new MemoryStream();
            ds.CopyTo(dst);
            return dst.ToArray();
        }

        static int ReadBE32(byte[] b, int o) => (b[o] << 24) | (b[o + 1] << 16) | (b[o + 2] << 8) | b[o + 3];
    }

    /// <summary>
    /// Loads a PNG into a REAL AsciiTexture instance. The private `colors` field is populated
    /// with exactly the data AsciiTexture's own constructor would have produced:
    /// colors[i,j] = color1d[i + j*256].ToVector3() == (R/255, G/255, B/255).
    /// AsciiTexture.Sample() -- the only sampling the renderer uses -- is the game's own code.
    /// </summary>
    public static class TextureForge
    {
        static readonly System.Reflection.FieldInfo ColorsField =
            typeof(AsciiTexture).GetField("colors", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        static readonly System.Reflection.MethodInfo RegisterMethod =
            typeof(AsciiTexture).GetMethod("Register",
                System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        static readonly List<AsciiTexture> Registered = new List<AsciiTexture>();

        public static AsciiTexture Load(string pngPath)
        {
            int w, h;
            byte[,] rgba = Png.DecodeRgba(pngPath, out w, out h);
            if (w != 256 || h != 256) throw new Exception("texture must be 256x256: " + pngPath);

            // Rasterise into the game's expected linear layout: colors[i + j*256]
            Vector3[] flat = new Vector3[256 * 256];
            for (int j = 0; j < 256; j++)
                for (int i = 0; i < 256; i++)
                    flat[i + j * 256] = new Vector3(rgba[i, j] / 255f, rgba[i + w, j] / 255f, rgba[i + 2 * w, j] / 255f);

            Vector3[,] colors = new Vector3[256, 256];
            for (int j = 0; j < 256; j++)
                for (int i = 0; i < 256; i++)
                    colors[i, j] = flat[i + j * 256];

            return FromColors(colors);
        }

        /// <summary>Builds an AsciiTexture around an already-populated colours array.</summary>
        public static AsciiTexture FromColors(Vector3[,] colors)
        {
            AsciiTexture t = (AsciiTexture)System.Runtime.Serialization.FormatterServices
                .GetUninitializedObject(typeof(AsciiTexture));
            ColorsField.SetValue(t, colors);
            RegisterMethod.Invoke(null, new object[] { t });
            Registered.Add(t);
            return t;
        }
    }

    /// <summary>Wavefront OBJ reader, matching what MonoGame's OBJContentPipelineExtension produces.</summary>
    public static class ObjReader
    {
        public static OBJContentPipelineExtension.OBJFile Read(string path)
        {
            List<Vector3> verts = new List<Vector3>();
            List<Vector2> uvs = new List<Vector2>();
            List<int> tv = new List<int>();
            List<int> tt = new List<int>();

            foreach (string lineRaw in File.ReadAllLines(path))
            {
                string line = lineRaw.Trim();
                if (line.Length == 0 || line[0] == '#') continue;
                string[] tok = line.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
                if (tok[0] == "v")
                    verts.Add(new Vector3(F(tok[1]), F(tok[2]), F(tok[3])));
                else if (tok[0] == "vt")
                    uvs.Add(new Vector2(F(tok[1]), F(tok[2])));
                else if (tok[0] == "f")
                {
                    for (int i = 1; i + 2 < tok.Length; i++)
                    {
                        Add(tok[i], ref tv, ref tt);
                        Add(tok[i + 1], ref tv, ref tt);
                        Add(tok[i + 2], ref tv, ref tt);
                    }
                }
            }
            return new OBJContentPipelineExtension.OBJFile
            {
                vertices = verts.ToArray(),
                texcoords = uvs.ToArray(),
                triangleVertices = tv.ToArray(),
                triangleTexcoords = tt.ToArray()
            };
        }

        static void Add(string face, ref List<int> tv, ref List<int> tt)
        {
            string[] p = face.Split('/');
            tv.Add(int.Parse(p[0]) - 1);
            tt.Add(p.Length > 1 && p[1].Length > 0 ? int.Parse(p[1]) - 1 : 0);
        }

        static float F(string s) => float.Parse(s, System.Globalization.CultureInfo.InvariantCulture);
    }
}
