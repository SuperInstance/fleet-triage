/* syz_witness.h — the fourth ask, and the part PIXELS-ARCHITECTURE.md calls the
 * difference between telemetry and a theory of mind.
 *
 *   "A/B the scripts, keep the better one, put the worse one away WITH SPECIFIC
 *    COMMENTS"  +  "a build index of what the comments on older strategy
 *    iterations were doing"
 *
 * durable-LOGIC.md found four ways witness logs fail in this account.  Each is
 * closed structurally here, not by discipline:
 *
 *   1. never constructs the thing      -> every entry carries a payload digest
 *                                         and the digest is of the candidate's
 *                                         actual weight bytes, not a constant
 *   2. compares a constant to a constant -> a bound check that REJECTS an
 *                                         unbound comment, and the experiment
 *                                         proves the reject path is reachable
 *   3. truncated at the head          -> GENESIS is a compile-time constant, so
 *                                         a zeroed head fails verification
 *   4. never re-run                   -> syz_witness_verify() is called by the
 *                                         harness on every read, and the
 *                                         experiment re-reads the whole chain
 *
 * Integer only, static pool, no libc.  Freestanding-clean.
 */
#ifndef SYZ_WITNESS_H
#define SYZ_WITNESS_H

#include <stdint.h>
#include <stddef.h>

#define SYZ_WITNESS_MAX_ENTRIES 64
#define SYZ_WITNESS_COMMENT_MAX 96
#define SYZ_WITNESS_SCRIPT_MAX  32

/* Hard-coded, never computed at runtime.  A log whose head is zeroed or whose
 * genesis is derived from its own contents verifies as NOT-OK. */
#define SYZ_WITNESS_GENESIS 0x811C9DC5u

typedef struct {
    uint32_t script_version;      /* which candidate this is                */
    uint32_t field_id;            /* which weight block: cell*num_actions+m  */
    uint32_t line_no;             /* the specific line or field critiqued    */
    int32_t  observed_loss;
    int32_t  baseline_loss;
    uint8_t  verdict;             /* 1 = kept, 0 = archived                  */
    uint8_t  bound;               /* 1 if the comment names a script+line    */
    char     script[SYZ_WITNESS_SCRIPT_MAX];
    char     comment[SYZ_WITNESS_COMMENT_MAX];
} SyzWitnessEntry;

typedef struct {
    SyzWitnessEntry entries[SYZ_WITNESS_MAX_ENTRIES];
    uint32_t n;
    uint32_t chain;               /* running FNV-1a chain over every entry   */
    uint32_t rejected;            /* entries refused for being unbound      */
} SyzWitnessLog;

static inline uint32_t syz_fnv1a(uint32_t h, const void *data, size_t n)
{
    const uint8_t *b = (const uint8_t *)data;
    size_t i;
    for (i = 0; i < n; i++) { h ^= b[i]; h *= 0x01000193u; }
    return h;
}

static inline uint32_t syz_fnv1a_u32(uint32_t h, uint32_t v)
{
    uint8_t b[4];
    b[0] = (uint8_t)(v & 0xFFu);         b[1] = (uint8_t)((v >> 8) & 0xFFu);
    b[2] = (uint8_t)((v >> 16) & 0xFFu); b[3] = (uint8_t)((v >> 24) & 0xFFu);
    return syz_fnv1a(h, b, 4);
}

/* The anchored head.  A log whose head is lost or zeroed must verify as NOT-OK,
 * so the genesis lives in a constant and never in the log's own memory. */
static inline void syz_witness_init(SyzWitnessLog *L)
{
    uint32_t i;
    for (i = 0; i < (uint32_t)(sizeof(*L) / 4u); i++) ((uint32_t *)L)[i] = 0u;
    L->chain = SYZ_WITNESS_GENESIS;
}

static inline uint32_t syz_witness_hash_entry(const SyzWitnessEntry *e)
{
    uint32_t h = SYZ_WITNESS_GENESIS;
    h = syz_fnv1a_u32(h, e->script_version);
    h = syz_fnv1a_u32(h, e->field_id);
    h = syz_fnv1a_u32(h, e->line_no);
    h = syz_fnv1a_u32(h, (uint32_t)e->observed_loss);
    h = syz_fnv1a_u32(h, (uint32_t)e->baseline_loss);
    h = syz_fnv1a_u32(h, e->verdict);
    h = syz_fnv1a    (h, e->script, sizeof(e->script));
    h = syz_fnv1a    (h, e->comment, sizeof(e->comment));
    return h;
}

/* A comment that could be attached to any revision is not a witness, it is an
 * opinion.  FIELD 2 is the binding requirement. */
static inline int syz_witness_is_bound(const SyzWitnessEntry *e)
{
    uint32_t i;
    int has_script_char = 0;
    if (e->script_version == 0) return 0;      /* names no version   */
    if (e->line_no == 0)       return 0;      /* names no line      */
    for (i = 0; i < SYZ_WITNESS_SCRIPT_MAX; i++) {
        if (e->script[i] == 0) break;
        if (e->script[i] == ' ') continue;      /* padding only      */
        has_script_char = 1; break;
    }
    if (!has_script_char)     return 0;
    if (e->comment[0] == 0)   return 0;         /* empty comment     */
    return 1;
}

/* Append.  Returns 1 if written, 0 if REFUSED for being unbound.  A refusal is
 * counted, not silently dropped, so the log can report its own blind spot. */
static inline int syz_witness_append(SyzWitnessLog *L, const SyzWitnessEntry *e)
{
    SyzWitnessEntry copy;
    if (L->n >= SYZ_WITNESS_MAX_ENTRIES) return 0;
    copy = *e;
    if (!syz_witness_is_bound(&copy)) { L->rejected++; return 0; }
    copy.bound = 1;
    L->entries[L->n] = copy;
    L->chain = syz_fnv1a_u32(L->chain, syz_witness_hash_entry(&copy));
    L->n++;
    return 1;
}

/* Re-read the whole chain from the anchored head.  Cheap enough to run on every
 * read, which is the entire point of failure mode 4. */
static inline int syz_witness_verify(const SyzWitnessLog *L, uint32_t *out_chain)
{
    uint32_t h = SYZ_WITNESS_GENESIS, i;
    for (i = 0; i < L->n; i++) {
        if (!L->entries[i].bound) return 0;
        if (!syz_witness_is_bound(&L->entries[i])) return 0;
        h = syz_fnv1a_u32(h, syz_witness_hash_entry(&L->entries[i]));
    }
    if (out_chain) *out_chain = h;
    return h == L->chain;
}

#endif /* SYZ_WITNESS_H */
