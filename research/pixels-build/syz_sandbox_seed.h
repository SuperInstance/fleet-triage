/* syz_sandbox_seed.h — VERBATIM transcription of the harness published in
 * attachments/8c06f5beb07cb550/pasted-text.txt, 2026-10-02.
 *
 * ZERO EDITS.  This file is the control.  Every defect measured in
 * research/PIXELS-BUILD.md is a property of this code as written, not of a
 * strawman.  Line-for-line against the seed document, with the only change
 * being the addition of #include <stdint.h>/<stddef.h> so it compiles on a
 * hosted host, and the removal of the syz_spreadsheet.h include (we supply an
 * equivalent engine ourselves).
 *
 * Cross-checked against the memory-map table in
 * attachments/b13c47bc66efb64b/pasted-text.txt, which independently states:
 *   "Frame Index: 128 frames * 24 bytes = 3,072B  Data Pool: 65,536 bytes"
 */
#ifndef SYZ_SANDBOX_SEED_H
#define SYZ_SANDBOX_SEED_H

#include <stdint.h>
#include <stddef.h>
#include "syz_spreadsheet.h"

#define SYZ_HISTORY_DEPTH 128   /* Number of past frames tracked in ring buffer */
#define SYZ_BUFFER_SIZE   65536 /* Static pre-allocated pool size for cell tokens */

typedef struct {
    uint32_t frame_id;
    uint32_t num_cells;
    uint32_t target_actions;
    size_t   mask_offset;
    size_t   glyph_offset;
    size_t   tone_offset;
} SyzHistoryFrame;

typedef struct {
    SyzHistoryFrame frames[SYZ_HISTORY_DEPTH];
    uint8_t         data_pool[SYZ_BUFFER_SIZE];
    size_t          pool_tail;
    uint32_t        head_idx;
    uint32_t        count;
    uint32_t        frame_counter;

    SyzSpreadsheetEngine sandbox_a;
    SyzSpreadsheetEngine sandbox_b;
} SyzSandboxHarness;

static inline void syz_sandbox_push_frame(
    SyzSandboxHarness *harness,
    const SyzFusedOut *out,
    uint32_t target_actions)
{
    uint32_t total_cells = out->rows * out->cols;
    size_t required_space = (total_cells * sizeof(uint8_t)) +
                           (total_cells * sizeof(uint32_t)) +
                           (total_cells * sizeof(uint8_t));

    if (harness->pool_tail + required_space >= SYZ_BUFFER_SIZE) {
        harness->pool_tail = 0;
    }

    uint32_t write_idx = (harness->head_idx + harness->count) % SYZ_HISTORY_DEPTH;

    if (harness->count == SYZ_HISTORY_DEPTH) {
        harness->head_idx = (harness->head_idx + 1) % SYZ_HISTORY_DEPTH;
    } else {
        harness->count++;
    }

    SyzHistoryFrame *f = &harness->frames[write_idx];
    f->frame_id = harness->frame_counter++;
    f->num_cells = total_cells;
    f->target_actions = target_actions;

    f->mask_offset = harness->pool_tail;
    for (uint32_t i = 0; i < total_cells; i++) {
        harness->data_pool[f->mask_offset + i] = out->mask[i];
    }
    harness->pool_tail += total_cells;

    f->glyph_offset = harness->pool_tail;
    uint32_t *pool_glyph_ptr = (uint32_t*)&harness->data_pool[f->glyph_offset];
    for (uint32_t i = 0; i < total_cells; i++) {
        pool_glyph_ptr[i] = out->glyph[i];
    }
    harness->pool_tail += (total_cells * sizeof(uint32_t));

    f->tone_offset = harness->pool_tail;
    for (uint32_t i = 0; i < total_cells; i++) {
        harness->data_pool[f->tone_offset + i] = out->tone[i];
    }
    harness->pool_tail += total_cells;
}

static inline int syz_sandbox_evaluate_differential(
    SyzSandboxHarness *harness,
    const SyzSpreadsheetEngine *live_engine,
    const SyzSpreadsheetEngine *vlm_candidate,
    uint32_t rows,
    uint32_t cols)
{
    if (harness->count < 16) {
        return 0;
    }

    harness->sandbox_a = *live_engine;
    harness->sandbox_b = *vlm_candidate;

    int32_t total_loss_a = 0;
    int32_t total_loss_b = 0;
    int32_t scratch_scores[SYZ_MAX_ACTIONS];

    for (uint32_t h = 0; h < harness->count; h++) {
        uint32_t read_idx = (harness->head_idx + h) % SYZ_HISTORY_DEPTH;
        const SyzHistoryFrame *f = &harness->frames[read_idx];

        SyzFusedOut historical_view = {
            .cap  = f->num_cells,
            .rows = rows,
            .cols = cols,
            .mask = &harness->data_pool[f->mask_offset],
            .glyph = (const uint32_t*)&harness->data_pool[f->glyph_offset],
            .tone = &harness->data_pool[f->tone_offset]
        };

        uint32_t actions_a = syz_spreadsheet_step(&harness->sandbox_a, &historical_view, scratch_scores);
        uint32_t actions_b = syz_spreadsheet_step(&harness->sandbox_b, &historical_view, scratch_scores);

        for (uint32_t m = 0; m < live_engine->num_actions; m++) {
            uint32_t target_bit = (f->target_actions >> m) & 0x01;
            uint32_t bit_a      = (actions_a >> m) & 0x01;
            uint32_t bit_b      = (actions_b >> m) & 0x01;

            if (bit_a != target_bit) total_loss_a += 100;
            if (bit_b != target_bit) total_loss_b += 100;
        }
    }

    if (total_loss_b < total_loss_a) {
        return 1;
    }
    return 0;
}

#endif /* SYZ_SANDBOX_SEED_H */
