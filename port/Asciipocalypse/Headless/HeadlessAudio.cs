// [INSTRUMENTATION 6/6] SoundEffect.Play() needs an audio device, which a headless
// Linux container has none of (OpenAL: "Could not open /dev/dsp").  The 23 call sites
// `Assets.x.Play()` were rewritten to `HeadlessAudio.Play("x")`, which does nothing.
// No simulation logic changes: Play() returns void and touches no game state.
namespace ASCII_FPS
{
    public static class HeadlessAudio
    {
        public static int calls = 0;
        public static void Play(string what) { calls++; }
    }
}
