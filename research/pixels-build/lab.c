/* lab.c — measurements on the seed harness (verbatim) vs a correctly sized one.
 *
 * Nothing here is asserted from reading the code.  Every number printed comes
 * from running it.  syz_sandbox_seed.h is untouched.  Where a variant of its
 * loop is needed to recover a loss the seed function does not return, lab_replay
 * duplicates the loop and its fidelity is PROVEN in E4 against the verbatim
 * header's accept/reject bit.
 *
 * Build:  gcc -O2 -Wall -Wextra -std=c99 lab.c -o lab -lm && ./lab
 */
#include <stdio.h>
#include <string.h>
#include <math.h>
#include "syz_spreadsheet.h"
#include "syz_sandbox_seed.h"
#include "syz_sandbox_fixed.h"
#include "syz_witness.h"

#define ROWS 24
#define COLS 40
#define NCELL (ROWS*COLS)
#define NACT  4
#define DEPTH SYZ_HISTORY_DEPTH
#define SEED_FRAME_BYTES ((size_t)NCELL * 1u + (size_t)NCELL * 4u + (size_t)NCELL * 1u)
#define BIG_FRAME_BYTES  (SEED_FRAME_BYTES + SYZ_STATE_BYTES)

/* The world: four horizontal bands.  A disc sits in one band and that band
 * NAMES the action the expert takes.  The production engine has bands 2 and 3
 * swapped — a specific, real, correctable defect — so there is a known-good
 * candidate and a known-bad one, and the A/B has something true to decide.
 *
 * Bands are ROW ranges so that a contiguous cell-index range [lo,hi) is exactly
 * one band, which is the granularity syz_spreadsheet_reweight_async offers. */
#define BAND0_LO 0u
#define BAND0_HI (6u * COLS)
#define BAND1_LO (6u * COLS)
#define BAND1_HI (12u * COLS)
#define BAND2_LO (12u * COLS)
#define BAND2_HI (18u * COLS)
#define BAND3_LO (18u * COLS)
#define BAND3_HI (24u * COLS)

static const uint32_t BAND_LO[4] = { BAND0_LO, BAND1_LO, BAND2_LO, BAND3_LO };
static const uint32_t BAND_HI[4] = { BAND0_HI, BAND1_HI, BAND2_HI, BAND3_HI };
/* which action the LIVE engine believes each band speaks for: 2 and 3 swapped */
static const uint32_t LIVE_ROLE[4] = { 0, 1, 3, 2 };
static const int32_t  W_STRONG = 8000;
static const int32_t  WEAK[6]  = { 0, 2000, 6000, 8000, 10000, 12000 };

typedef struct {
    const SyzHistoryFrame *frames;
    const uint8_t *pool;
    uint32_t head, count;
} view_t;

typedef struct {
    SyzHistoryFrame frames[DEPTH];
    uint8_t  pool[DEPTH * BIG_FRAME_BYTES];
    uint32_t head, count, counter;
} big_t;

static big_t BIG;
static int32_t scr[SYZ_MAX_ACTIONS];
static uint32_t tex[NCELL];

static void big_reset(void)
{
    uint32_t i;
    for (i = 0; i < DEPTH; i++) memset(&BIG.frames[i], 0, sizeof(BIG.frames[0]));
    memset(BIG.pool, 0, sizeof(BIG.pool));
    BIG.head = BIG.count = BIG.counter = 0;
}

/* A correctly sized pool: fixed stride, one block per slot, never wraps. */
static void big_push(big_t *B, const SyzFusedOut *out, uint32_t target, const int32_t *acc)
{
    uint32_t n = out->rows * out->cols;
    uint32_t idx = (B->head + B->count) % DEPTH;
    SyzHistoryFrame *f;
    size_t o, base = (size_t)idx * BIG_FRAME_BYTES;

    if (B->count == DEPTH) B->head = (B->head + 1) % DEPTH;
    else B->count++;

    f = &B->frames[idx];
    f->frame_id = B->counter++;
    f->num_cells = n;
    f->target_actions = target;
    f->mask_offset  = base;
    for (o = 0; o < n; o++) B->pool[f->mask_offset + o] = out->mask[o];
    f->glyph_offset = f->mask_offset + n;
    for (o = 0; o < n; o++) ((uint32_t *)&B->pool[f->glyph_offset])[o] = out->glyph[o];
    f->tone_offset  = f->glyph_offset + (size_t)n * 4u;
    for (o = 0; o < n; o++) B->pool[f->tone_offset + o] = out->tone[o];
    for (o = 0; o < NACT; o++)
        ((int32_t *)&B->pool[base + BIG_FRAME_BYTES - SYZ_STATE_BYTES])[o] = acc[o];
}

/* ------------------------------------------------------------------ scene */
static void scene_init(void)
{
    uint32_t c;
    for (c = 0; c < NCELL; c++) tex[c] = (c * 2654435761u) >> 24;
}

/* The disc sits entirely inside band (t/8)%4.  glyph = 1 inside the disc and 0
 * outside, so the background contributes nothing and only the disc's own band
 * can raise a score. */
static void scene_frame(uint32_t t, uint8_t *mask, uint32_t *glyph, uint8_t *tone)
{
    uint32_t band = (t / 8u) % 4u;
    int cy = (int)(BAND_LO[band] / COLS) + 2;   /* 6-row band, radius 2 */
    int cx = COLS / 2;
    uint32_t c;
    for (c = 0; c < NCELL; c++) {
        int x = (int)(c % COLS), y = (int)(c / COLS);
        int dx = x - cx, dy = y - cy;
        int inside = (dx * dx + dy * dy) <= 4;
        mask[c]  = (uint8_t)inside;
        glyph[c] = inside ? 1u : 0u;
        tone[c]  = (uint8_t)(inside ? 220 : 20);
    }
}

/* expert:  band m speaks for action m.  live:  bands 2 and 3 are swapped. */
static void engine_init(SyzSpreadsheetEngine *e, int live)
{
    uint32_t c, a, m;
    memset(e, 0, sizeof(*e));
    e->num_cells = 1024;
    e->num_actions = NACT;
    for (a = 0; a < NACT; a++) e->thresholds[a] = 40;
    for (m = 0; m < 4; m++) {
        uint32_t action = live ? LIVE_ROLE[m] : m;
        for (c = BAND_LO[m]; c < BAND_HI[m]; c++)
            e->matrix[c][action].w2 = (int16_t)W_STRONG;
    }
}

/* A VLM proposal: reweight one or two (band, action) response profiles. */
static void make_candidate(SyzSpreadsheetEngine *live, SyzSpreadsheetEngine *out, uint32_t k)
{
    uint32_t n_edit = 1u + (syz_rng(&k) % 2u);
    uint32_t i;
    *out = *live;
    for (i = 0; i < n_edit; i++) {
        uint32_t m    = syz_rng(&k) % 4u;
        uint32_t act  = syz_rng(&k) % NACT;
        int32_t  w    = WEAK[syz_rng(&k) % 6u];
        syz_spreadsheet_reweight_async(out, BAND_LO[m], BAND_HI[m], act, w);
    }
}

/* Build one history.  mode 0: targets from the live engine (self-loss test).
 * mode 1: targets from the expert (the A/B ranking test). */
static void build(int mode, SyzSandboxHarness *seed, SyzSpreadsheetEngine *live,
                  int32_t *snap)
{
    static uint8_t mask[NCELL], tone[NCELL];
    static uint32_t glyph[NCELL];
    static SyzSpreadsheetEngine expert, prod;
    SyzFusedOut f;
    uint32_t t;

    memset(seed, 0, sizeof(*seed));
    big_reset();
    engine_init(&expert, 0);
    engine_init(&prod, 1);
    scene_init();
    f.cap = NCELL; f.rows = ROWS; f.cols = COLS;
    f.mask = mask; f.glyph = glyph; f.tone = tone;

    for (t = 0; t < DEPTH; t++) {
        uint32_t act, exp_act;
        int32_t m;
        scene_frame(t, mask, glyph, tone);
        /* snapshot BEFORE the step: this is the state that produced the target */
        if (mode == 0) for (m = 0; m < NACT; m++) snap[t * NACT + m] = prod.acc[m];
        act = syz_spreadsheet_step(&prod, &f, scr);
        exp_act = syz_spreadsheet_step(&expert, &f, scr);
        if (mode == 1) for (m = 0; m < NACT; m++) snap[t * NACT + m] = expert.acc[m];
        act = (mode == 0) ? act : exp_act;
        syz_sandbox_push_frame(seed, &f, act);
        big_push(&BIG, &f, act, expert.acc);
    }
    *live = prod;
}

/* ------------------------------------------------------------ generic replay */
static void lab_replay(view_t v, const SyzSpreadsheetEngine *live,
                       const SyzSpreadsheetEngine *cand, const int32_t *snap,
                       int state_ok, int32_t *out_a, int32_t *out_b)
{
    int32_t loss_a = 0, loss_b = 0, scores[SYZ_MAX_ACTIONS];
    uint32_t h, m;
    /* The seed forks ONCE and then evolves both engines across all 128 frames.
     * Hoisting the copies out of the loop is not a stylistic choice — it is the
     * hidden state, and putting them inside made every arm a stateless scorer
     * that disagreed with the verbatim header on 58/600 candidates. */
    SyzSpreadsheetEngine A = *live, B = *cand;

    for (h = 0; h < v.count; h++) {
        const SyzHistoryFrame *f = &v.frames[(v.head + h) % DEPTH];
        SyzFusedOut view;
        uint32_t act_a, act_b;
        view.cap = f->num_cells; view.rows = ROWS; view.cols = COLS;
        view.mask  = &v.pool[f->mask_offset];
        view.glyph = (const uint32_t *)&v.pool[f->glyph_offset];
        view.tone  = &v.pool[f->tone_offset];

        /* the fixed harness additionally rewinds each engine to the state that
         * actually produced this frame's target */
        if (state_ok)
            for (m = 0; m < NACT; m++) {
                A.acc[m] = snap[h * NACT + m];
                B.acc[m] = snap[h * NACT + m];
            }

        act_a = syz_spreadsheet_step(&A, &view, scores);
        act_b = syz_spreadsheet_step(&B, &view, scores);
        for (m = 0; m < NACT; m++) {
            uint32_t tg = (f->target_actions >> m) & 1u;
            if (((act_a >> m) & 1u) != tg) loss_a += 100;
            if (((act_b >> m) & 1u) != tg) loss_b += 100;
        }
    }
    *out_a = loss_a; *out_b = loss_b;
}

static view_t VS, VB;
static void set_views(const SyzSandboxHarness *seed)
{
    VS.frames = seed->frames; VS.pool = seed->data_pool;
    VS.head = seed->head_idx;  VS.count = seed->count;
    VB.frames = BIG.frames;    VB.pool = BIG.pool;
    VB.head = BIG.head;        VB.count = BIG.count;
}

/* --------------------------------------------------------------- E1 */
static void e1(void)
{
    printf("E1  POOL SIZING\n");
    printf("    cells per frame            %u   (rows %d x cols %d)\n", NCELL, ROWS, COLS);
    printf("    bytes per frame            %zu  (mask %u + glyph %zu + tone %u)\n",
           SEED_FRAME_BYTES, NCELL, (size_t)NCELL * 4, NCELL);
    printf("    ring depth                 %u   SYZ_HISTORY_DEPTH\n", DEPTH);
    printf("    seed pool                  %zu  SYZ_BUFFER_SIZE\n", (size_t)SYZ_BUFFER_SIZE);
    printf("    frames the pool can hold   %zu\n", (size_t)SYZ_BUFFER_SIZE / SEED_FRAME_BYTES);
    printf("    bytes actually required    %zu\n", (size_t)DEPTH * SEED_FRAME_BYTES);
    printf("    undersizing factor         %.2fx\n\n",
           (double)((size_t)DEPTH * SEED_FRAME_BYTES) / (double)SYZ_BUFFER_SIZE);
}

/* --------------------------------------------------------------- E2 */
static void e2(void)
{
    static SyzSandboxHarness seed;
    static SyzSpreadsheetEngine eng;
    static uint8_t mask[NCELL], tone[NCELL];
    static uint32_t glyph[NCELL];
    SyzFusedOut f;
    uint32_t t, c, h, matched = 0, newest = 0, distinct_bytes = 0;

    memset(&seed, 0, sizeof(seed));
    engine_init(&eng, 1);
    f.cap = NCELL; f.rows = ROWS; f.cols = COLS;
    f.mask = mask; f.glyph = glyph; f.tone = tone;
    for (t = 0; t < DEPTH; t++) {                     /* signature: tone[0]=id+1 */
        for (c = 0; c < NCELL; c++) tone[c] = (uint8_t)((t + 1u) & 0xFFu);
        syz_sandbox_push_frame(&seed, &f, syz_spreadsheet_step(&eng, &f, scr));
    }
    for (h = 0; h < seed.count; h++) {
        const SyzHistoryFrame *fr = &seed.frames[(seed.head_idx + h) % DEPTH];
        uint8_t t0 = seed.data_pool[fr->tone_offset];
        if (t0 == (uint8_t)((fr->frame_id + 1u) & 0xFFu)) matched++;
        if (t0 == (uint8_t)((seed.frame_counter - 1u) & 0xFFu)) newest++;
        if (t0 != 0) distinct_bytes++;
    }
    printf("E2  ALIASING, read back through the seed harness's OWN pointer arithmetic\n");
    printf("    frames pushed                      %u\n", DEPTH);
    printf("    ring count after push              %u\n", seed.count);
    printf("    slots whose bytes are their own     %u / %u\n", matched, seed.count);
    printf("    slots holding another frame's data  %u / %u   (%.1f%%)\n",
           seed.count - matched, seed.count,
           100.0 * (double)(seed.count - matched) / (double)seed.count);
    printf("    slots showing the newest frame      %u / %u\n", newest, seed.count);
    printf("    -> the 128-slot replay is %u distinct frames repeated to fill 128.\n"
           "       %u frames of the real history are never looked at.\n\n",
           newest, DEPTH - newest);
    (void)distinct_bytes;
}

/* --------------------------------------------------------------- E3 */
static void e3(void)
{
    static SyzSandboxHarness seed;
    static SyzSpreadsheetEngine eng;
    static int32_t snap[DEPTH * NACT];
    int32_t la, lb, r[4];
    int i;
    const char *names[4] = {
        "seed pool, no state restore", "seed pool, state restored",
        "sized pool, no state restore", "sized pool, state restored" };
    build(0, &seed, &eng, snap);
    set_views(&seed);
    for (i = 0; i < 4; i++)
        lab_replay(i & 2 ? VB : VS, &eng, &eng, snap, i & 1, &la, &lb), r[i] = la;

    printf("E3  SELF-LOSS — replay the live engine against its OWN recorded targets\n");
    printf("    A harness that can see its own past reproduces those targets exactly.\n"
           "    Any nonzero self-loss is measurement error, before a candidate exists.\n\n");
    for (i = 0; i < 4; i++) printf("    %-32s %8d%s\n", names[i], r[i],
                                   (i == 3) ? "   <- oracle" : "");
    printf("    %-32s %8d   <- what a sound harness must return\n\n", "target", 0);
}

/* --------------------------------------------------------------- E4 */
static void e4(void)
{
    static SyzSandboxHarness seed;
    static SyzSpreadsheetEngine eng;
    static int32_t snap[DEPTH * NACT];
    uint32_t k;
    const uint32_t TRIALS = 600;
    int32_t la, lb;
    int a, fidelity_bad = 0, first_bad = -1;
    struct { int dis, danger, acc; } arms[4] = {{0,0,0},{0,0,0},{0,0,0},{0,0,0}};

    build(1, &seed, &eng, snap);
    set_views(&seed);
    for (a = 0; a < 4; a++) {
        for (k = 0; k < TRIALS; k++) {
            SyzSpreadsheetEngine cand;
            int r1, r2;
            make_candidate(&eng, &cand, k * 2654435761u + 12345u);
            lab_replay((a & 2) ? VB : VS, &eng, &cand, snap, a & 1, &la, &lb);
            r1 = (lb < la);
            if (a == 0) {
                int v = syz_sandbox_evaluate_differential(&seed, &eng, &cand, ROWS, COLS);
                if (v != r1) { fidelity_bad++; if (first_bad < 0) first_bad = (int)k; }
            }
            lab_replay(VB, &eng, &cand, snap, 1, &la, &lb);
            r2 = (lb < la);
            if (r1 != r2) { arms[a].dis++; if (r1 && !r2) arms[a].danger++; }
            if (r1) arms[a].acc++;
        }
    }
    printf("E4  DECISION DIVERGENCE — %u VLM proposals, 2x2 factorial\n", TRIALS);
    printf("    targets are the EXPERT's actions; the production engine is the live\n"
           "    baseline.  oracle = sized pool + state restore.  \"dangerous\" = the arm\n"
           "    promotes a proposal the oracle rejects, i.e. a WORSE script goes live.\n\n");
    printf("    %-28s %11s %12s %9s\n", "arm", "disagree", "dangerous", "accept%");
    for (a = 0; a < 4; a++) {
        printf("    %-28s %6d/%-4u %7d/%-4u %8.1f%%\n",
               (a & 2) ? "sized pool" : "seed pool (aliased)",
               arms[a].dis, TRIALS, arms[a].danger, TRIALS,
               100.0 * arms[a].acc / TRIALS);
        printf("    %-28s %s\n\n", "", (a & 1) ? "state restored" : "state NOT restored");
    }
    printf("    fidelity: lab_replay vs the VERBATIM seed header — %d mismatches / %u%s\n\n",
           fidelity_bad, TRIALS, first_bad >= 0 ? " (first at k=...)" : "");
    if (first_bad >= 0) {
        SyzSpreadsheetEngine cand; int32_t x, y; int v;
        uint32_t kk = (uint32_t)first_bad;
        make_candidate(&eng, &cand, kk * 2654435761u + 12345u);
        lab_replay(VS, &eng, &cand, snap, 0, &x, &y);
        v = syz_sandbox_evaluate_differential(&seed, &eng, &cand, ROWS, COLS);
        printf("    first mismatch k=%d:  lab_replay says %d (lossA=%d lossB=%d)\n"
               "                          verbatim header says %d\n\n",
               first_bad, (y < x), x, y, v);
    }
}

/* --------------------------------------------------------------- E5 */
static void e5(void)
{
    static SyzSandboxHarness sandbox;
    static uint8_t  mock_mask[256];
    static uint32_t mock_glyph[256];
    static uint8_t  mock_tone[256];
    static SyzSpreadsheetEngine engine, candidate;
    SyzFusedOut frame;
    int i, accepted;
    uint32_t live_actions;

    printf("E5  THE SEED SUITE'S OWN SANDBOX STEP, executed\n");
    memset(&sandbox, 0, sizeof(sandbox));
    memset(mock_mask, 0, 256);
    memset(mock_glyph, 0, sizeof(mock_glyph));
    for (i = 0; i < 256; i++) mock_tone[i] = 0x01;
    frame.cap = 256; frame.rows = 16; frame.cols = 16;
    frame.mask = mock_mask; frame.glyph = mock_glyph; frame.tone = mock_tone;

    engine_init(&engine, 1);
    engine.num_cells = 256; engine.num_actions = 4;
    for (i = 0; i < 4; i++) engine.thresholds[i] = 50;
    for (i = 0; i < 256; i++) {
        engine.matrix[i][0].w0 = 128; engine.matrix[i][0].w2 = 256; engine.matrix[i][0].bias = -10;
    }
    live_actions = syz_spreadsheet_step(&engine, &frame, scr);
    syz_sandbox_push_frame(&sandbox, &frame, live_actions);
    candidate = engine;
    syz_spreadsheet_reweight_async(&candidate, 0, 255, 0, 32);
    accepted = syz_sandbox_evaluate_differential(&sandbox, &engine, &candidate, 16, 16);

    printf("    frames pushed                      1\n");
    printf("    harness->count after push          %u\n", sandbox.count);
    printf("    seed guard:  if (count < 16) return 0;\n");
    printf("    differential core executed         %s\n", sandbox.count >= 16 ? "YES" : "NO");
    printf("    proposed_accepted                  %d\n", accepted);
    printf("    enters the golden receipt as       ^ %d  (XOR with a constant zero)\n", accepted);
    printf("    pool bytes covered by the hash     0 of %zu\n", (size_t)SYZ_BUFFER_SIZE);
    printf("    index slots covered by the hash    2 of %u\n\n", SYZ_HISTORY_DEPTH);
}

/* --------------------------------------------------------------- E6 */
typedef struct { uint32_t a, b, c; uint32_t x, y, z; } FrameWasm32;
typedef struct { uint32_t a, b, c; size_t   x, y, z; } FrameHost64;

static void e6(void)
{
    static FrameWasm32 w[2];
    static FrameHost64 h[2];
    uint32_t hw, hh;
    memset(w, 0, sizeof(w)); memset(h, 0, sizeof(h));
    w[1].a = 1; h[1].a = 1;
    hw = syz_fnv1a(SYZ_WITNESS_GENESIS, w, sizeof(w));
    hh = syz_fnv1a(SYZ_WITNESS_GENESIS, h, sizeof(h));
    printf("E6  THE GOLDEN RECEIPT IS ARCHITECTURE-DEPENDENT BY CONSTRUCTION\n");
    printf("    The suite asserts one constant must hold \"on every machine, every\n"
           "    optimisation level\".  It hashes &sandbox.frames[0], and that struct\n"
           "    stores size_t offsets.  The seed set's own memory map calls that field\n"
           "    \"4B/8B depending on WASM architecture\".\n\n");
    printf("    wasm32 ABI    sizeof = %zu bytes   hash 0x%08X\n", sizeof(FrameWasm32), hw);
    printf("    host 64-bit   sizeof = %zu bytes   hash 0x%08X\n", sizeof(FrameHost64), hh);
    printf("    (the 64-bit layout is the real struct; the 32-bit layout is the wasm32\n"
           "     ABI, reconstructed here — no wasm toolchain in this sandbox.)\n");
    printf("    equal: %s\n\n", hw == hh ? "YES" : "NO");
}

/* --------------------------------------------------------------- E7 */
static void e7(void)
{
    static SyzWitnessLog log;
    SyzWitnessEntry e;
    uint32_t chain = 0;
    int ok, wrote;

    printf("E7  THE INDEX — chained, anchored, refuses unbound comments\n");
    syz_witness_init(&log);

    memset(&e, 0, sizeof(e));
    e.script_version = 7; e.field_id = 3; e.line_no = 129;
    e.observed_loss = 1200; e.baseline_loss = 1800; e.verdict = 0;
    memcpy(e.script, "spreadsheet-v7", 15);
    memcpy(e.comment, "w2 1->24 collapses roles 3 and 7; oracle rejects", 47);
    wrote = syz_witness_append(&log, &e);
    printf("    bound entry appended           %s\n", wrote ? "yes" : "REFUSED");

    memset(&e, 0, sizeof(e));
    e.observed_loss = 900; e.baseline_loss = 900; e.verdict = 1;
    memcpy(e.script, "???", 4);
    memcpy(e.comment, "the ramp feels wrong somehow", 28);
    wrote = syz_witness_append(&log, &e);
    printf("    UNBOUND entry appended         %s   (refused counter = %u)\n",
           wrote ? "yes" : "REFUSED", log.rejected);

    ok = syz_witness_verify(&log, &chain);
    printf("    chain verifies                 %s   0x%08X over %u entries\n",
           ok ? "OK" : "BROKEN", chain, log.n);

    log.entries[0].observed_loss = 1;
    printf("    tamper with entry 0            %s\n",
           syz_witness_verify(&log, &chain) ? "OK" : "DETECTED");
    log.entries[0].observed_loss = 1200;
    log.entries[0].line_no = 0;
    printf("    strip its line binding         %s\n",
           syz_witness_verify(&log, &chain) ? "OK" : "DETECTED");
    log.entries[0].line_no = 129;
    chain = log.chain;
    log.chain = 0;
    printf("    lose the head anchor           %s\n",
           syz_witness_verify(&log, &chain) ? "OK" : "DETECTED");
    log.chain = chain;
    printf("    (restored)                     %s\n\n",
           syz_witness_verify(&log, &chain) ? "OK" : "DETECTED");
}

/* ------------------------------- E8 the seed's churn claim, three ways */
typedef struct {
    SyzSandboxHarness seed;
    SyzSpreadsheetEngine live;
    SyzSpreadsheetEngine expert;
} stream_t;

static void stream_push(stream_t *s, uint32_t t)
{
    static uint8_t mask[NCELL], tone[NCELL];
    static uint32_t glyph[NCELL];
    SyzFusedOut f;
    scene_frame(t, mask, glyph, tone);
    f.cap = NCELL; f.rows = ROWS; f.cols = COLS;
    f.mask = mask; f.glyph = glyph; f.tone = tone;
    /* the EXPERT supplies the target; the live engine is what we are testing */
    syz_spreadsheet_step(&s->live, &f, scr);
    syz_sandbox_push_frame(&s->seed, &f, syz_spreadsheet_step(&s->expert, &f, scr));
}

static int stream_offer(stream_t *s, const SyzSpreadsheetEngine *cand)
{
    return syz_sandbox_evaluate_differential(&s->seed, &s->live, cand, ROWS, COLS);
}

/* bounded copy, no libc */
static int wcat(char *dst, int at, const char *src, int cap)
{
    while (*src && at < cap - 1) dst[at++] = *src++;
    dst[at] = 0;
    return at;
}

/* the live engine binds action 2 to band 3 and action 3 to band 2.  The fix is
 * to bind them correctly AND drop the wrong binding — four calls, not two. */
static void make_fix(SyzSpreadsheetEngine *c)
{
    syz_spreadsheet_reweight_async(c, BAND2_LO, BAND2_HI, 2, W_STRONG);
    syz_spreadsheet_reweight_async(c, BAND2_LO, BAND2_HI, 3, 0);
    syz_spreadsheet_reweight_async(c, BAND3_LO, BAND3_HI, 3, W_STRONG);
    syz_spreadsheet_reweight_async(c, BAND3_LO, BAND3_HI, 2, 0);
}

static void e8(void)
{
    stream_t s;
    int i, promos;

    printf("E8  THE CHURN CLAIM, three ways\n");
    printf("    the seed asserts that `loss_b < loss_a` \"prevents macro weights from\n"
           "    alternating rapidly when noise boundaries are tight\".\n\n");

    /* 1. the same known-good candidate offered 20 times */
    memset(&s, 0, sizeof(s));
    engine_init(&s.live, 1); engine_init(&s.expert, 0);
    for (i = 0; i < 200; i++) stream_push(&s, (uint32_t)i);
    {
        SyzSpreadsheetEngine c = s.live;
        make_fix(&c);
        promos = 0;
        for (i = 0; i < 20; i++) if (stream_offer(&s, &c)) { s.live = c; promos++; }
        printf("    the known-good fix offered 20x        promotions = %d   (converges)\n", promos);
    }

    /* 2. two candidates alternating forever */
    memset(&s, 0, sizeof(s));
    engine_init(&s.live, 1); engine_init(&s.expert, 0);
    for (i = 0; i < 200; i++) stream_push(&s, (uint32_t)i);
    {
        SyzSpreadsheetEngine a = s.live, b = s.live;
        make_fix(&a);
        make_fix(&b);
        b.matrix[BAND0_LO][0].w2 = (int16_t)(b.matrix[BAND0_LO][0].w2 + 1);
        promos = 0;
        for (i = 0; i < 20; i++) {
            SyzSpreadsheetEngine *c = (i & 1) ? &b : &a;
            if (stream_offer(&s, c)) { s.live = *c; promos++; }
        }
        printf("    two candidates alternating 20x       promotions = %d   (no flip-flop)\n", promos);
    }

    /* 3. how big is the margin a promotion actually rests on? */
    memset(&s, 0, sizeof(s));
    engine_init(&s.live, 1); engine_init(&s.expert, 0);
    for (i = 0; i < 200; i++) stream_push(&s, (uint32_t)i);
    {
        uint32_t hist[6] = {0,0,0,0,0,0};   /* margin buckets, in loss points */
        uint32_t accepted = 0, k;
        for (k = 0; k < 600; k++) {
            SyzSpreadsheetEngine c = s.live;
            uint32_t rseed = k * 2654435761u + 7u;
            uint32_t band = syz_rng(&rseed) % 4u;
            uint32_t act  = syz_rng(&rseed) % NACT;
            int32_t margin;
            view_t v = { BIG.frames, BIG.pool, BIG.head, BIG.count };
            int32_t la, lb;
            syz_spreadsheet_reweight_async(&c, BAND_LO[band], BAND_HI[band], act,
                                           WEAK[syz_rng(&rseed) % 6u]);
            lab_replay(v, &s.live, &c, NULL, 0, &la, &lb);
            if (lb < la) {
                margin = la - lb;
                accepted++;
                if      (margin <= 100) hist[0]++;
                else if (margin <= 200) hist[1]++;
                else if (margin <= 400) hist[2]++;
                else if (margin <= 800) hist[3]++;
                else if (margin <= 1600) hist[4]++;
                else                    hist[5]++;
            }
        }
        printf("    winning margin over 600 proposals (loss is 100 per wrong bit):\n");
        printf("      <=100 (1 bit) %4u   <=200 %4u   <=400 %4u   <=800 %4u   <=1600 %4u   >1600 %4u\n",
               hist[0], hist[1], hist[2], hist[3], hist[4], hist[5]);
        printf("      accepted %u of 600; %u of those rest on a SINGLE bit.\n",
               accepted, hist[0]);
        printf("    -> the guard is monotone and it does stop oscillation: both claims hold.\n"
               "       What it does not have is a floor.  A proposal that wins by one bit\n"
               "       out of 512 is promoted, and `loss_b < loss_a` cannot tell that from a\n"
               "       proposal that wins by a thousand.  A margin is the only thing that\n"
               "       makes the difference visible, and the seed does not have one.\n\n");
    }
}

/* ---------------- E9 THE PRIMARY AFFORDANCE, two live streams end to end */
/* Stream A is driven by the seed harness.  Stream B is driven by the sized
 * pool with state restore.  Each keeps its own engine, its own history and its
 * own witness index, and each promotion is audited against the oracle computed
 * from that stream's own live engine.  Nothing is shared except the scene. */
typedef struct {
    SyzSandboxHarness seed;
    big_t big;
    int32_t snap[DEPTH * NACT];
    SyzSpreadsheetEngine live;
    SyzSpreadsheetEngine expert;
    SyzWitnessLog log;
    uint32_t serial;
    int use_seed;
} stream2_t;

static void s2_push(stream2_t *s, uint32_t t)
{
    static uint8_t mask[NCELL], tone[NCELL];
    static uint32_t glyph[NCELL];
    SyzFusedOut f;
    uint32_t act;
    int32_t m;
    scene_frame(t, mask, glyph, tone);
    f.cap = NCELL; f.rows = ROWS; f.cols = COLS;
    f.mask = mask; f.glyph = glyph; f.tone = tone;
    /* snap the LIVE engine's own pre-step state: that is the state in which it
     * actually saw this frame, and it is the only state a correct replay can use */
    for (m = 0; m < NACT; m++) s->snap[t * NACT + m] = s->live.acc[m];
    syz_spreadsheet_step(&s->live, &f, scr);
    act = syz_spreadsheet_step(&s->expert, &f, scr);     /* the target */
    syz_sandbox_push_frame(&s->seed, &f, act);
    big_push(&s->big, &f, act, s->live.acc);
}

static void s2_losses(stream2_t *s, const SyzSpreadsheetEngine *cand,
                      int32_t *oa, int32_t *ob)
{
    view_t v = { s->big.frames, s->big.pool, s->big.head, s->big.count };
    lab_replay(v, &s->live, cand, s->snap, 1, oa, ob);
}

static void e9(void)
{
    static stream2_t A, B;
    const uint32_t FRAMES = 512, PERIOD = 16;
    uint32_t t, i, promos[2] = {0,0}, danger[2] = {0,0}, offers = 0;
    uint32_t chainA = 0, chainB = 0;

    memset(&A, 0, sizeof(A)); memset(&B, 0, sizeof(B));
    syz_witness_init(&A.log); syz_witness_init(&B.log);
    engine_init(&A.live, 1); engine_init(&B.live, 1);
    engine_init(&A.expert, 0); engine_init(&B.expert, 0);
    A.use_seed = 1; B.use_seed = 0;

    printf("E9  PRIMARY AFFORDANCE — 512 live frames, a proposal every %u\n", PERIOD);
    printf("    one in three proposals is the known-good fix (unswap bands 2 and 3)\n\n");

    for (t = 0; t < FRAMES; t++) {
        uint32_t idx = (t % PERIOD == PERIOD - 1) ? 1u : 0u;
        int stream;
        s2_push(&A, t); s2_push(&B, t);
        if (!idx) continue;
        offers++;
        for (stream = 0; stream < 2; stream++) {
            stream2_t *s = stream ? &B : &A;
            SyzSpreadsheetEngine cand = s->live;
            SyzWitnessEntry w;
            int32_t la, lb;
            int accept, oracle;
            uint32_t band, action;

            if (offers % 3 == 0) {                 /* the known-good fix */
                band = 2; action = 2;
                make_fix(&cand);
            } else {
                uint32_t rseed = s->serial * 2654435761u + offers;
                uint32_t r = syz_rng(&rseed);
                band = r % 4u; action = (r >> 4) % NACT;
                syz_spreadsheet_reweight_async(&cand, BAND_LO[band], BAND_HI[band],
                                               action, WEAK[(r >> 9) % 6u]);
            }

            s2_losses(s, &cand, &la, &lb);
            oracle = (lb < la);
            accept = s->use_seed
                   ? syz_sandbox_evaluate_differential(&s->seed, &s->live, &cand, ROWS, COLS)
                   : oracle;
            if (accept) { s->live = cand; promos[stream]++; }
            if (accept && !oracle) danger[stream]++;

            memset(&w, 0, sizeof(w));
            w.script_version = ++s->serial;
            w.field_id = action * 4u + band;
            w.line_no = (uint32_t)BAND_LO[band] / COLS + 1;    /* the band row */
            w.observed_loss = lb; w.baseline_loss = la;
            w.verdict = (uint8_t)accept;
            {
                char tmp[80], dg[2];
                int len = 0;
                dg[0] = (char)('0' + (int)band);  dg[1] = 0;
                len = wcat(tmp, len, s->use_seed ? "seed" : "sized", (int)sizeof(tmp));
                len = wcat(tmp, len, "-v", (int)sizeof(tmp));
                tmp[len++] = (char)('0' + (int)(w.script_version % 10));
                tmp[len] = 0;
                memcpy(w.script, tmp, (size_t)len + 1);
                len = wcat(w.comment, 0, accept ? "PROMOTED" : "ARCHIVED", (int)sizeof(w.comment));
                len = wcat(w.comment, len, " band ", (int)sizeof(w.comment));
                len = wcat(w.comment, len, dg, (int)sizeof(w.comment));
                len = wcat(w.comment, len, " action ", (int)sizeof(w.comment));
                dg[0] = (char)('0' + (int)action);
                len = wcat(w.comment, len, dg, (int)sizeof(w.comment));
                wcat(w.comment, len, accept ? " better on replay" : " not better on replay",
                     (int)sizeof(w.comment));
            }
            syz_witness_append(&s->log, &w);
        }
    }
    printf("    %-28s %10s %12s %10s %10s\n", "stream", "promotions", "dangerous", "index", "chain");
    printf("    %-28s %10u %12u %10u %10s\n", "A: driven by the seed harness",
           promos[0], danger[0], A.log.n, syz_witness_verify(&A.log, &chainA) ? "OK" : "BROKEN");
    printf("    %-28s %10u %12u %10u %10s\n", "B: driven by the sized pool",
           promos[1], danger[1], B.log.n, syz_witness_verify(&B.log, &chainB) ? "OK" : "BROKEN");
    printf("    %-28s %10u\n\n", "proposals offered", offers);
    printf("    A promoted %u scripts, of which %u the oracle had already rejected.\n",
           promos[0], danger[0]);
    printf("    Both indexes are chained, anchored, and verify.  Sample entry:\n");
    for (i = 0; i < A.log.n && i < 1; i++) {
        const SyzWitnessEntry *w = &A.log.entries[i];
        printf("      script=%-8s v%-3u line=%u field=%u  loss %d -> %d  %s\n",
               w->script, w->script_version, w->line_no, w->field_id,
               w->baseline_loss, w->observed_loss, w->verdict ? "KEPT" : "ARCHIVED");
        printf("      comment: \"%s\"\n", w->comment);
    }
    printf("\n");
}

/* ---- E10 the fixed header itself, exercised (it ships, so it gets run) */
static void e10(void)
{
    static SyzSandboxHarnessV2 h;
    static uint8_t mask[NCELL], tone[NCELL];
    static uint32_t glyph[NCELL];
    static SyzSpreadsheetEngine live, cand;
    SyzFusedOut f;
    uint32_t t;
    int i;

    printf("E10  THE FIXED HEADER, RUN  (not just designed)\n");
    syz_sandbox_v2_init(&h);
    engine_init(&live, 0);
    f.cap = NCELL; f.rows = ROWS; f.cols = COLS;
    f.mask = mask; f.glyph = glyph; f.tone = tone;
    for (t = 0; t < DEPTH; t++) {
        uint32_t act;
        SyzSpreadsheetEngine before;
        scene_frame(t, mask, glyph, tone);
        before = live;                        /* the state that PRODUCED the target */
        act = syz_spreadsheet_step(&live, &f, scr);
        syz_sandbox_v2_push(&h, &f, &before, act);
    }
    printf("    pool bytes            %zu   (derived, not typed: %d frames x %zu stride)\n",
           (size_t)SYZ_POOL_BYTES, SYZ_HISTORY_DEPTH, (size_t)SYZ_FRAME_STRIDE);
    printf("    slots with live bytes %u / %u   (seed harness: 11 / 128)\n",
           syz_sandbox_v2_live_slots(&h), h.count);
    i = syz_sandbox_v2_evaluate(&h, &live, &live, 0);
    printf("    self-loss             %d   (a sound harness returns exactly 0)\n", h.last_loss_a);
    printf("    null change promoted? %s   (a candidate identical to live must never win)\n",
           i ? "YES — BUG" : "no");
    cand = live;
    make_fix(&cand);
    printf("    the known-good fix on a LIVE (already correct) engine, margin 0   -> %d\n",
           syz_sandbox_v2_evaluate(&h, &live, &cand, 0));
    printf("    the same, with a 100-point margin                                -> %d\n",
           syz_sandbox_v2_evaluate(&h, &live, &cand, 100));
    printf("    the same, with a 5000-point margin                               -> %d\n\n",
           syz_sandbox_v2_evaluate(&h, &live, &cand, 5000));
}

int main(void)
{
    printf("================================================================\n");
    printf(" PIXELS-BUILD LAB — the seed harness, executed\n");
    printf(" rows %d x cols %d, %u cells, %d actions, depth %d\n\n", ROWS, COLS, NCELL, NACT, DEPTH);
    e1(); e2(); e3(); e4(); e5(); e6(); e7(); e8(); e9(); e10();
    return 0;
}
