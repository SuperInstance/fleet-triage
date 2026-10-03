// A BALANCED identity scene, rendered by the game's own Rasterizer.
//
// The first re-render run was degenerate: 99.99% of cells were wall texture, so the
// task was "which brick", and a re-projection score of 0.9856 measured frequency,
// not representation.  This file builds the control the brief asks for -- N object
// identities at MATCHED depth, in equal pixel proportion, so the only thing that
// distinguishes them is what the colour channel carries.
//
// Nothing here fakes a render.  The meshes are real Triangle lists, the textures are
// the game's own AsciiTextures read from the real PNGs, and Rasterizer.Raster() does
// the z-buffering, depth ramp and colour quantisation exactly as it does in the game.
// What this file changes is WHICH meshes are in the scene -- the "specific" layer.

using ASCII_FPS.GameComponents;
using ASCII_FPS.Scenes;
using Microsoft.Xna.Framework;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace ASCII_FPS
{
    /// One flat quad facing the camera, textured with one of the game's own textures.
    public class Probe : GameObject
    {
        public string Identity;          // the ground-truth label for this probe
        public override void Update(float deltaTime) { }
        public override void Save(BinaryWriter w) { }

        public Probe(MeshObject mesh, string identity) : base(mesh) { Identity = identity; }
    }

    public static class ProbeScene
    {
        // Six of the game's own textures, chosen so identity is carried by COLOUR.
        // The three barrel_* textures are EXCLUDED on purpose: in the headless path they
        // render ~99% black (colour8 == 0 for 99% of their cells) even though the PNGs
        // are fully opaque and mid-brightness, so their identity is simply not in the
        // colour channel and they cannot be told apart.  See RERENDER-BALANCED.md.
        static readonly (string key, string field)[] TEX = {
            ("monster",         "monsterTexture"),
            ("poison_monster",  "poisonMonsterTexture"),
            ("spinny_boi",      "spinnyBoiTexture"),
            ("ice_monster",     "iceMonsterTexture"),
            ("shotgun_dude",    "shotgunDudeTexture"),
            ("ice_shotgun_dude","iceShotgunDudeTexture"),
        };
        public static string[] Identities { get { return TEX.Select(t => t.key).ToArray(); } }

        public static AsciiTexture Tex(string id)
        {
            foreach (var t in TEX)
                if (t.key == id)
                {
                    var f = typeof(Assets).GetField(t.field);
                    return f != null ? (AsciiTexture)f.GetValue(null) : null;
                }
            return null;
        }

        /// <summary>
        /// Build a scene containing only probes.  Every probe is the same size and the
        /// same distance from the camera, laid out in a row, so each identity wins a
        /// near-identical number of cells.  depth is a parameter so the depth-matching
        /// claim is explicit and adjustable.
        /// </summary>
        public static List<Probe> Build(ASCII_FPS game, int nIdent, float depth, float spread, float size)
        {
            var probes = new List<Probe>();
            var cam = game.Scene.Camera;
            cam.CameraPos = Vector3.Zero;
            cam.Rotation = 0f;                        // Camera.Forward at rot 0 is (0,0,1) = +Z

            int n = Math.Max(2, Math.Min(nIdent, TEX.Length));
            // symmetric GRID, not a row: a row puts the outermost probes on the frustum
            // edge where clipping eats them, which silently unbalances the class mix --
            // exactly the degeneracy this scene exists to remove.
            int cols = (n + 1) / 2;
            int rows = 2;
            float sx = spread, sy = spread * 0.55f;
            for (int i = 0; i < n; i++)
            {
                int r = i / cols, c = i % cols;
                int inRow = Math.Min(cols, n - r * cols);
                float cx = inRow > 1 ? -sx / 2f + sx * c / (inRow - 1) : 0f;
                float cy = rows > 1 ? sy / 2f - sy * r / (rows - 1) : 0f;
                string id = TEX[i].key;
                var tex = Tex(id);
                if (tex == null) continue;
                // Quad vertices are LOCAL to the mesh; MeshObject.Position supplies the
                // world translation.  Putting world coords in both places translates the
                // probes twice and pushes the outer ones off the frustum.
                var a = new Vector3(-size,  size, 0f);
                var b = new Vector3( size,  size, 0f);
                var c2 = new Vector3( size, -size, 0f);
                var d = new Vector3(-size, -size, 0f);
                var tris = new List<Triangle>
                {
                    new Triangle(a, b, c2, tex, new Vector2(0, 0), new Vector2(1, 0), new Vector2(1, 1)),
                    new Triangle(a, c2, d, tex, new Vector2(0, 0), new Vector2(1, 1), new Vector2(0, 1)),
                };
                var mesh = new MeshObject(tris, new Vector3(cx, cy, depth), 0f);
                var pr = new Probe(mesh, id);
                pr.Game = game;
                probes.Add(pr);
            }
            return probes;
        }
    }
}
