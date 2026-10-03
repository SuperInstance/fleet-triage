// Headless host for Asciipocalypse.  Replaces ONLY the MonoGame Game subclass
// (ASCII_FPS.cs) which owns the window, GraphicsDeviceManager, SpriteBatch and
// Keyboard.  Everything else -- Rasterizer, Scene, Zone, Console, HUD, PlayerLogic,
// the scene generators -- is the upstream file, byte for byte.
//
//   no Game/GameWindow/GraphicsDevice/SpriteBatch/SoundEffect is constructed here.

using ASCII_FPS.GameComponents;
using ASCII_FPS.Scenes;
using ASCII_FPS.Scenes.Generators;
using Microsoft.Xna.Framework.Graphics;
using Microsoft.Xna.Framework;
using System;
using System.Collections.Generic;
using System.Linq;

namespace ASCII_FPS
{
    public class ASCII_FPS
    {
        public const string VERSION = "v1.2";

        // surface the GL host provided to Controls/MainMenuGroup; never exercised headless
        public bool IsActive => true;
        public static DisplayMode[] resolutions = new DisplayMode[0];

        public Scene Scene { get; set; }
        public PlayerStats PlayerStats { get; set; }
        public HUD HUD { get; set; }

        public static int Difficulty { get; set; } = 0;

        public static bool enableDebug = false;
        public static int triangleCount = 0;
        public static int triangleCountClipped = 0;
        public static int zonesRendered = 0;
        public static int frames = 0;
        public static float timeElapsed = 0f;
        public static float fps = 0f;
        public static string additionalDebug = "";

        public SceneGenerator SelectGenerator(int floor, int seed)
        {
            List<Func<SceneGenerator>> gens = new List<Func<SceneGenerator>>
            {
                () => new SceneGeneratorJungle(this, floor),
                () => new SceneGeneratorLava(this, floor),
                () => new SceneGeneratorIce(this, floor)
            };
            Mathg.Shuffle(new Random(seed), gens);
            gens.Insert(0, () => new SceneGeneratorDefault(this, floor));
            return gens[((floor - 1) / 4) % gens.Count].Invoke();
        }

        // --- identical to ASCII_FPS.ResetGame, minus the sound effect ---
        public void ResetGame(int difficulty, int seed, int floor = 1)
        {
            PlayerStats = new PlayerStats
            {
                difficulty = difficulty,
                health = 100f,
                maxHealth = 100f,
                maxArmor = 100f,
                armor = 100f,
                armorProtection = 0.3f,
                dead = false,
                hit = false,
                floor = floor,
                seed = seed
            };
            Scene = SelectGenerator(floor, seed).Generate();
            Scene.Camera = new Camera(0.5f, 1000f, (float)Math.PI / 2.5f, 16f / 9f);
            Scene.Visited[SceneGenerator.size / 2, SceneGenerator.size / 2] = true;
            HUD.Scene = Scene;
        }
    }
}
