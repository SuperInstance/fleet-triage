/* poolassert.c — this file is EXPECTED TO FAIL TO COMPILE.
 *
 * It is the one-line check the seed harness would need and does not have: the
 * static pool must be able to hold SYZ_HISTORY_DEPTH frames.  The constants
 * below are the seed set's own, taken from attachments/8c06f5beb07cb550 and
 * cross-checked against the memory-map table in
 * attachments/b13c47bc66efb64b ("Frame Index: 128 frames * 24 bytes" and
 * "Data Pool: 65,536 bytes").
 *
 * `make verify` compiles this and treats the COMPILER ERROR as the pass.
 * If it ever compiles cleanly, the check is broken and the result is a lie.
 */
#define SYZ_HISTORY_DEPTH 128
#define SYZ_BUFFER_SIZE   65536
#define ROWS 24
#define COLS 40
#define CELLS (ROWS * COLS)
#define FRAME_BYTES (CELLS * 1u + CELLS * 4u + CELLS * 1u)

typedef char pool_must_hold_the_whole_ring[
    (SYZ_BUFFER_SIZE >= SYZ_HISTORY_DEPTH * FRAME_BYTES) ? 1 : -1];

int main(void) { return (int)sizeof(pool_must_hold_the_whole_ring); }
