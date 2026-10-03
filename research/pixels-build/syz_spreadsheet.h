/* syz_spreadsheet.h — integer-only control engine, built to run the seed set's
 * harness for real.  Everything the seed set describes is implemented here so
 * that syz_sandbox.h has something to actually fork, replay and score.
 *
 * Two deliberate properties, both load-bearing for the experiments:
 *
 *  1. HIDDEN STATE.  `acc[]` is a leaky integrator.  The seed set ships
 *     "Layer 2 Temporal Neural Controller" documents, so temporal state is
 *     intended, and a spreadsheet with accumulators is the obvious reading.
 *     This is what makes the harness's Markov precondition non-trivial.
 *
 *  2. SYZ_CELLS_OVERRUN is left to the caller.  The seed set declares a
 *     1024-cell engine but pushes 24x40 = 960-cell frames in one place and
 *     16x16 = 256-cell frames in another.  We reproduce the unguarded read.
 */
#ifndef SYZ_SPREADSHEET_H
#define SYZ_SPREADSHEET_H

#include <stdint.h>
#include <stddef.h>

#define SYZ_MAX_ACTIONS 16
#define SYZ_MAX_CELLS  1024

typedef struct { int16_t w0, w1, w2, w3; int32_t bias; } SyzActionWeight;

typedef struct {
    uint32_t cap, rows, cols;
    uint8_t  *mask;
    uint32_t *glyph;
    uint8_t  *tone;
} SyzFusedOut;

typedef struct {
    uint32_t num_cells;
    uint32_t num_actions;
    SyzActionWeight matrix[SYZ_MAX_CELLS][SYZ_MAX_ACTIONS];
    int32_t  thresholds[SYZ_MAX_ACTIONS];
    int32_t  acc[SYZ_MAX_ACTIONS];   /* hidden state */
    uint64_t t;
} SyzSpreadsheetEngine;

/* The live step.  `n` is NOT clamped to e->num_cells on purpose. */
static inline uint32_t syz_spreadsheet_step(SyzSpreadsheetEngine *e,
                                            const SyzFusedOut *f,
                                            int32_t *scores)
{
    uint32_t n = f->rows * f->cols;      /* may exceed e->num_cells */
    uint32_t act = 0;
    uint32_t m, i;

    if (n == 0) return 0;

    for (m = 0; m < e->num_actions; m++) {
        int32_t s = 0;
        for (i = 0; i < n; i++) {
            const SyzActionWeight *w = &e->matrix[i][m];
            s += (int32_t)f->tone[i]  * (int32_t)w->w0;
            s += (int32_t)f->mask[i]  * (int32_t)w->w1;
            s += (int32_t)(f->glyph[i] & 0xFFu) * (int32_t)w->w2;
            s += (int32_t)w->w3;
        }
        s += e->matrix[0][m].bias;
        s /= (int32_t)n;
        scores[m] = s;
        e->acc[m] = (e->acc[m] * 3 + s) / 4;   /* leaky integrator: hidden state */
        if (e->acc[m] > e->thresholds[m]) act |= (1u << m);
    }
    e->t++;
    return act;
}

/* The asynchronous reweight the VLM callback calls. */
static inline void syz_spreadsheet_reweight_async(SyzSpreadsheetEngine *e,
                                                 uint32_t lo, uint32_t hi,
                                                 uint32_t action, int32_t new_w)
{
    uint32_t i;
    if (action >= SYZ_MAX_ACTIONS) return;
    if (hi > SYZ_MAX_CELLS) hi = SYZ_MAX_CELLS;
    for (i = lo; i < hi; i++) e->matrix[i][action].w2 = (int16_t)new_w;
}

/* Deterministic LCG.  No libc RNG, no float, identical on every host. */
static inline uint32_t syz_rng(uint32_t *s)
{
    *s = *s * 1664525u + 1013904223u;
    return *s >> 8;
}

#endif /* SYZ_SPREADSHEET_H */
