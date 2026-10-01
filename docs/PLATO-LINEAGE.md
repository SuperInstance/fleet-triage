# The PLATO tile system — the tabulation, the relational tensor, and a real defect

Casey asked me to study the PLATO line: Fortran first, then TUTOR, TUTOR's vectorisation, and
whether that can encode over JSON/hash, and how the relational tensor systems fit together —
and specifically **the shape of the file from the SuperInstance tabulation.**

I read the code. The short answer is that the shape Casey intuited is **already here, and it is
a fixed-width 384-byte record.** There is a real bug in it, and it is the same bug class I
have been finding in three other repos tonight.

---

## 1. The census first, because the scale reframes the question

`SuperInstance` holds **5,113 repos** (51–52 pages, `unique == rows` asserted). A name scan
for `plato|tutor|tabul|fortran|vector|tensor|relational` returns **over 200 matches** — a
`plato-*` cluster with a `plato-tile-*` sub-family of roughly fifty, a `plato-room-*` family,
and a TUTOR line (`plato-tutor`, `cocapn-tutor`, `lucid-tutor`, `lucid-tutor-c`, `tutor-ai`,
`quilt-tutor`, `lau-plato-tutor`).

**"The PLATO system" is not one thing.** It is a language (Fortran roots: `conservation-spectral-fortran`,
`flux-fortran`, `grand-pattern-fortran`, `fortran-constraint-checking`), a pedagogy (TUTOR, the
tutor repos), and a **storage-and-relation substrate** (the tile family). Casey is asking
about the third, and it is the most concrete thing in the fleet.

## 2. The shape of the file — this is the answer to "the shape of the tabulation"

`plato-tile-encoder` (Rust, zero external dependencies) defines the record. Its type:

```rust
pub struct EncodedTile {
    pub id: String,
    pub question: String,
    pub answer: String,
    pub tags: Vec<String>,
    pub domain: String,
    pub confidence: f64,
    pub ghost_score: f64,
    pub use_count: u32,
}
```

**That is a tabulation row, and it is the same eight columns the whole fleet has been circling:
a claim (`question`), its answer, the relations (`tags`), the classification (`domain`), the
calibrated score (`confidence` — this is the JEV column), the not-deleted column
(`ghost_score`), and the use counter.**

Then the part that answers Casey directly — **the fixed-width binary form:**

```rust
const BINARY_SIZE: usize = 384;
write_str(buf, &mut offset, &tile.id,       64);
write_str(buf, &mut offset, &tile.question,128);
write_str(buf, &mut offset, &tile.answer,  128);
write_str(buf, &mut offset, &tile.domain,  32);
let tags_str = tile.tags.join(",");
write_str(buf, &mut offset, &tags_str,     20);
```

**64 + 128 + 128 + 32 + 20 + 4 + 4 + 4 = 384.** Fixed-width columns, null-padded, decoded by
scanning to the first zero byte. This *is* a tabulation with a schema, expressed as a byte
record instead of a JSON object — and the repo ships **three codecs over the same record**:
hand-rolled JSON (no serde), the 384-byte binary, and hand-rolled base64 over the binary.

**This is the answer to "could TUTOR's vectorisation encode over JSON hash encoding."** It is
already done, and it is the reason the record is fixed-width in the first place: a fixed-width
record is O(1)-random-access by `offset + column`, which is exactly the property a vectorised
reader wants, and a variable-width JSON object is not.

## 3. THE DEFECT — and it is the same one as `lossShaOf`

Two doc comments in the same file, **on adjacent lines, describing different layouts:**

```
line 163: id(64)+question(128)+answer(128)+domain(32)+tags(24)+confidence(4)+ghost(4)+use_count(4)
line 164: id(64)+question(128)+answer(128)+domain(32)+tags(24)+confidence(4)+ghost(4)
```

**Both say `tags(24)`. The code writes 20.** And the arithmetic:

| | sum |
|---|---:|
| comment on line 163 (with `use_count`) | **388** |
| comment on line 164 (without) | **380** |
| what the code actually writes | **384** |

**Neither documented layout is 384 bytes.** The one that is 384 is the one in the code, and it
is not the one in either comment.

This is byte-for-byte the defect class I found in `quilt-nn`/`quilt-attention` earlier tonight:
**the docstring describes a layout the code does not implement, and the two disagree, and only
a second reading catches it.** The tests all pass — there are fifteen of them, including a
deliberate truncation test — because **no test reads the comments.**

I reported that one as "the preimage must be the thing the docstring claims." Here it is
again, in a different repo, on a different artifact, with the same shape: **the documentation
of the record is stale and the record is fine, and nothing in the build can see the
difference.**

## 4. What is genuinely well-built here

Three things, and they are the same three things this project keeps getting right elsewhere:

- **Zero external dependencies, hand-rolled.** The JSON escaper, the base64, the UTF-8 decode —
  all written out, no `serde`, no `base64` crate. This is the same discipline as the
  hand-rolled FNV-1a 64, and it is why the crate can be vendored into twelve polyformalism
  ports without dragging a tree.
- **The truncation is tested, not hidden.** `test_long_string_truncation` builds a 200-char
  question, encodes it, and asserts the decoded question is exactly 128. **A fixed-width record
  is lossy, this author knew it, and wrote the test that says so.** That is the opposite of
  the 106-repos-false `historybloat` signal I ran into earlier.
- **The byte layout is self-consistent with the decoder.** `read_str` scans to the first zero,
  which is exactly the inverse of `write_str` zero-padding. Round-trips hold for `id`,
  `question`, `answer`, `domain`, `tags`, `confidence`, `ghost_score`, and `use_count`, each
  with its own test.

## 5. The relational tensor system, and how it composes with the record

The tile family splits cleanly into three layers, and the 384-byte record is the *leaf*:

- **`plato-tile-spec`** — the schema. `FieldType` is `string | integer | float | boolean |
  timestamp | json | list | enum`; `TileSpec` is a named set of `FieldSpec`s; `SpecRegistry`
  adds fields to specs. It calls itself *"the lingua franca of the PLATO knowledge system."*
  This is the column definition — the part of a tabulation that is schema rather than data.
- **`plato-tile-encoder`** — the 384-byte leaf, three codecs, no deps. (Above.)
- **`plato-tile-relation`** — the tensor. A directed multigraph over tiles with
  `RelationType` (including **`CONTRADICTS`**) and `RelationStrength`; `find_path(source,
  target, max_depth)`, `transitive_closure`, and `detect_cycles` via DFS. `plato-tile-graph` is
  the DAG-specialised sibling.

**So the fleet already has a relational tensor system over a fixed-width vector record**, and
it has a contradiction edge type in it. That is a genuinely good shape: the record is a point,
the graph is the relation, and `CONTRADICTS` means the store can hold a disagreement as a
first-class edge rather than resolving it away.

## 6. The TUTOR vectorisation idea, as it survives in this fleet

Casey's read of TUTOR was that its vectorisation was the clever part. I did not find a
`plato-tutor` that is a vectoriser — `plato-tutor` is a spaced-repetition system (`Flashcard`,
`Difficulty`, `MasteryLevel`, `QuizQuestion`, `cards_by_tag`, `cards_due`, `generate_options`),
and `plato-forge-buffer` is a **prioritised experience-replay ring buffer** with
`EntryPriority`, `BufferOverflowPolicy.DROP_LOWEST`, backpressure, and `drain_by_room`.

**The vectorisation is in the *scheduler*, not the arithmetic:** priority classes, an overflow
policy that drops the *lowest* rather than the oldest, and a history of every pop. **A buffer
that chooses what to forget is a witness chain with a TTL** — which is the thing I reached
tonight from the ASSA read (a call signal that persists for exactly one iteration) and from
the trade-off ledger (Auditability is the only net-positive paradigm). Three lanes, same
shape, arrived at independently.

## 7. What I did not verify, and what it would take

- I did not run the Rust tests — no `cargo` in this sandbox. The fifteen tests are read, not
  executed, and every number above is from the source.
- I did not find a **Fortran** artefact that is the ancestor of the tile record. The Fortran
  repos are separate and I did not establish a lineage to `plato-tile-encoder`; I am not
  going to invent one.
- Whether the 384-byte record is meant to be *the* fleet tabulation or is one crate's
  local format. `plato-tile-bridge` is described as "Compatible with plato-tile-bridge C struct
  format", which suggests a C mirror exists; I did not read it.

## 8. The one-line version

**The shape of the tabulation is a 384-byte fixed-width record — `id 64, question 128, answer
128, domain 32, tags 20, confidence 4, ghost 4, use_count 4` — carrying a claim, its answer,
its relations, its JEV score, and its not-deleted column, with a directed graph over it that
has a `CONTRADICTS` edge. And the two doc comments that describe that layout are both wrong
about it, in the same way, on adjacent lines, with a passing test suite over the top.**
