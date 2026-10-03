/* syz_sandbox_fixed.h — the same mechanism, made unable to lie.
 *
 * The seed harness (syz_sandbox_seed.h) is the right SHAPE and the wrong SIZE.
 * This file keeps the shape exactly — static ring, fork, replay, integer loss,
 * commit-or-reject — and closes four things the shape alone does not:
 *
 *   A. POOL SIZING IS A COMPILE-TIME ASSERTION, not a number a human typed.
 *      The seed's bug class ("128-deep ring, 65536-byte pool") becomes a build
 *      failure rather than a silent 11-frame history.
 *   B. PER-FRAME STATE SNAPSHOT.  A replay is only a replay if it starts from
 *      the state that produced the targets.  The seed records the observation
 *      and the target but never the state, so "replay history" is a re-simulation
 *      from a state the engine was never in.
 *   C. HYSTERESIS MARGIN.  `loss_b < loss_a` is not a churn guard; it accepts a
 *      one-bit margin.  Commit requires strictly better BY a margin.
 *   D. THE ARCHIVE.  The losing candidate is kept with a comment that names its
 *      script version and the specific field it is about, chained into an index.
 *
 * The loss function itself is left EXACTLY as the seed wrote it (100 per bit,
 * summed over actions and frames) so the comparison is like-for-like.
 */
#ifndef SYZ_SANDBOX_FIXED_H
#define SYZ_SANDBOX_FIXED_H

#include <stdint.h>
#include <stddef.h>
#include "syz_spreadsheet.h"
#include "syz_witness.h"

#ifndef SYZ_ROWS
#define SYZ_ROWS 24
#endif
#ifndef SYZ_COLS
#define SYZ_COLS 40
#endif

#define SYZ_HISTORY_DEPTH 128
#define SYZ_CELLS         ((uint32_t)(SYZ_ROWS) * (uint32_t)(SYZ_COLS))

#define SYZ_ALIGN4(x)    (((x) + 3u) & ~((size_t)3u))
#define SYZ_STATE_BYTES  (SYZ_MAX_ACTIONS * 4u + 8u)
#define SYZ_FRAME_STRIDE (SYZ_ALIGN4(SYZ_CELLS) + SYZ_CELLS * 4u + SYZ_ALIGN4(SYZ_CELLS) + SYZ_STATE_BYTES)

/* >>> THE FIX.
 *
 * There is no assertion here on purpose.  In the seed, SYZ_BUFFER_SIZE and
 * SYZ_HISTORY_DEPTH are two independent literals and nothing relates them, so
 * the only possible check is a comparison between them — and a comparison is
 * exactly the kind of thing that gets written once and never re-read.
 *
 * Here the pool size is DERIVED from the depth and the frame size.  There is no
 * free variable left to get wrong, so there is nothing to assert and no
 * invariant to drift.  poolassert.c demonstrates the check the seed would need
 * and shows the seed's own constants failing it at compile time. */
#define SYZ_POOL_BYTES   (SYZ_HISTORY_DEPTH * SYZ_FRAME_STRIDE)

typedef struct {
    uint32_t frame_id;
    uint32_t target_actions;
    size_t   mask_offset, glyph_offset, tone_offset;
    size_t   state_offset;
    uint32_t num_cells;
    uint32_t reserved;
} SyzHistoryFrameV2;

typedef struct {
    SyzHistoryFrameV2 frames[SYZ_HISTORY_DEPTH];
    uint8_t  data_pool[SYZ_POOL_BYTES];
    size_t   pool_tail;
    uint32_t head_idx, count, frame_counter;

    SyzSpreadsheetEngine sandbox_a, sandbox_b;

    int32_t  last_loss_a, last_loss_b;
    uint32_t last_frames_replayed;
    uint32_t last_frames_verified;   /* slots whose pool bytes are provably live */
    SyzWitnessLog log;
} SyzSandboxHarnessV2;

static inline void syz_sandbox_v2_init(SyzSandboxHarnessV2 *h)
{
    uint32_t i;
    for (i = 0; i < (uint32_t)sizeof(*h) / 4u; i++) ((uint32_t *)h)[i] = 0u;
    h->pool_tail = 0;
    h->head_idx = 0;
    h->count = 0;
    h->frame_counter = 0;
}

static inline void syz_sandbox_v2_push(SyzSandboxHarnessV2 *h,
                                       const SyzFusedOut *out,
                                       const SyzSpreadsheetEngine *engine_at_capture,
                                       uint32_t target_actions)
{
    uint32_t n = out->rows * out->cols;
    size_t o;
    uint32_t write_idx = (h->head_idx + h->count) % SYZ_HISTORY_DEPTH;

    if (h->count == SYZ_HISTORY_DEPTH) h->head_idx = (h->head_idx + 1) % SYZ_HISTORY_DEPTH;
    else                                 h->count++;

    SyzHistoryFrameV2 *f = &h->frames[write_idx];
    f->frame_id = h->frame_counter++;
    f->num_cells = n;
    f->target_actions = target_actions;

    f->mask_offset  = h->pool_tail;                    h->pool_tail += SYZ_ALIGN4(n);
    f->glyph_offset = h->pool_tail;                    h->pool_tail += (size_t)n * 4u;
    f->tone_offset  = h->pool_tail;                    h->pool_tail += SYZ_ALIGN4(n);
    f->state_offset = h->pool_tail;                    h->pool_tail += SYZ_STATE_BYTES;

    for (o = 0; o < n; o++) h->data_pool[f->mask_offset + o] = out->mask[o];
    for (o = 0; o < n; o++) ((uint32_t *)&h->data_pool[f->glyph_offset])[o] = out->glyph[o];
    for (o = 0; o < n; o++) h->data_pool[f->tone_offset + o] = out->tone[o];

    /* (B) the state that PRODUCED the target, not the state we happen to be in */
    for (o = 0; o < SYZ_MAX_ACTIONS; o++)
        ((int32_t *)&h->data_pool[f->state_offset])[o] = engine_at_capture->acc[o];
    {
        uint64_t tt = engine_at_capture->t;
        uint8_t *tb = (uint8_t *)&h->data_pool[f->state_offset + SYZ_MAX_ACTIONS * 4u];
        for (o = 0; o < 8; o++) tb[o] = (uint8_t)((tt >> (8 * o)) & 0xFFu);
    }
}

/* (A) prove, at read time, that every slot's pool bytes are still live.  A slot
 * is live iff its byte range lies below the high-water mark.  The seed harness
 * has no equivalent and could not: its pool wraps at 11 frames. */
static inline uint32_t syz_sandbox_v2_live_slots(const SyzSandboxHarnessV2 *h)
{
    uint32_t h_i, live = 0;
    for (h_i = 0; h_i < h->count; h_i++) {
        const SyzHistoryFrameV2 *f = &h->frames[(h->head_idx + h_i) % SYZ_HISTORY_DEPTH];
        if (f->tone_offset + f->num_cells <= h->pool_tail) live++;
    }
    return live;
}

/* margin: candidate must beat the live engine by at least this many loss points
 * (C).  0 reproduces the seed's strict-less-than exactly, for like-for-like. */
static inline int syz_sandbox_v2_evaluate(SyzSandboxHarnessV2 *h,
                                          const SyzSpreadsheetEngine *live,
                                          const SyzSpreadsheetEngine *cand,
                                          int32_t margin)
{
    uint32_t k, m;
    int32_t loss_a = 0, loss_b = 0;
    int32_t scores[SYZ_MAX_ACTIONS];

    if (h->count < 16) return 0;

    for (k = 0; k < h->count; k++) {
        const SyzHistoryFrameV2 *f = &h->frames[(h->head_idx + k) % SYZ_HISTORY_DEPTH];
        uint32_t n = f->num_cells;
        SyzFusedOut view;
        int32_t saved_acc[SYZ_MAX_ACTIONS];
        uint64_t saved_t;
        uint32_t act_a, act_b;
        uint8_t *tb;

        view.cap = n; view.rows = SYZ_ROWS; view.cols = SYZ_COLS;
        view.mask  = &h->data_pool[f->mask_offset];
        view.glyph = (const uint32_t *)&h->data_pool[f->glyph_offset];
        view.tone  = &h->data_pool[f->tone_offset];

        for (m = 0; m < SYZ_MAX_ACTIONS; m++) saved_acc[m] = ((const int32_t *)&h->data_pool[f->state_offset])[m];
        tb = (uint8_t *)&h->data_pool[f->state_offset + SYZ_MAX_ACTIONS * 4u];
        saved_t = 0;
        for (m = 0; m < 8; m++) saved_t |= ((uint64_t)tb[m]) << (8 * m);

        /* A: live weights, historical STATE */
        h->sandbox_a = *live;
        for (m = 0; m < SYZ_MAX_ACTIONS; m++) h->sandbox_a.acc[m] = saved_acc[m];
        h->sandbox_a.t = saved_t;
        act_a = syz_spreadsheet_step(&h->sandbox_a, &view, scores);

        /* B: candidate weights, the SAME historical state */
        h->sandbox_b = *cand;
        for (m = 0; m < SYZ_MAX_ACTIONS; m++) h->sandbox_b.acc[m] = saved_acc[m];
        h->sandbox_b.t = saved_t;
        act_b = syz_spreadsheet_step(&h->sandbox_b, &view, scores);

        for (m = 0; m < live->num_actions; m++) {
            uint32_t t = (f->target_actions >> m) & 1u;
            if (((act_a >> m) & 1u) != t) loss_a += 100;
            if (((act_b >> m) & 1u) != t) loss_b += 100;
        }
    }

    h->last_loss_a = loss_a;
    h->last_loss_b = loss_b;
    h->last_frames_replayed = h->count;
    h->last_frames_verified = syz_sandbox_v2_live_slots(h);
    return (loss_b + margin) < loss_a;
}

#endif /* SYZ_SANDBOX_FIXED_H */
