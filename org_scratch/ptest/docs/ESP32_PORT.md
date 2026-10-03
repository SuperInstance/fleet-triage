# ESP32 port — `quilt-pincher-no_std`

A `no_std` Rust port of `quilt-pincher` for ESP32 (and other embedded targets).

## What it includes

- `PincherEngine` — same algorithm, no_std-friendly
- `MemoryReflexStore` — static, fixed-size buffer (up to 256 reflexes)
- `HashEmbedder` — deterministic, no allocation
- `DefaultVeto` — same rules
- No `Compiler` — ESP32 is offline; reflexes are pre-loaded from a `.nail` bundle

## Cargo.toml

```toml
[package]
name = "quilt-pincher-esp32"
version = "0.1.0"
edition = "2021"

[dependencies]
heapless = "0.7"  # fixed-capacity Vec, no alloc
```

## Sample usage

```rust
#![no_std]
#![no_main]

use quilt_pincher_esp32::{PincherEngine, HashEmbedder, MemoryReflexStore, Reflex};

#[entry]
fn main() -> ! {
    let embedder = HashEmbedder::new(64);
    let mut store = MemoryReflexStore::<256>::new();  // up to 256 reflexes

    // Load a pre-compiled .nail bundle
    let bundle = include_bytes!("../reflexes.nail");
    for reflex in bundle.iter() {
        let embedding = embedder.embed(&reflex.intent);
        store.insert(Reflex { id: reflex.id, embedding, ..reflex.clone() });
    }

    let engine = PincherEngine::new(embedder, store);

    loop {
        // wait for pinch from network or button
        let trigger = read_trigger();
        let pinch = Pinch { trigger: &trigger, ..Default::default() };
        let result = engine.run(&pinch);
        // act on result
    }
}
```

## Memory budget

- HashEmbedder: 64 floats × 4 bytes = **256 bytes**
- MemoryReflexStore: 256 reflexes × (Reflex + 64-float embedding)
  - Reflex: ~128 bytes (id, intent, action, safety, etc.)
  - Embedding: 256 bytes
  - Per reflex: ~512 bytes
  - Total: **128 KB** for 256 reflexes

Fits comfortably on an ESP32 (520 KB SRAM).

## Building

```bash
cargo build --target xtensa-esp32-espidf --release
```

Or for the host (simulator):

```bash
cargo test
```

## The .nail bundle format

A flatbuffer-style binary format. The TypeScript `buildNail()` function emits
this format; the Rust `parse_nail()` function reads it.

```rust
pub struct NailBundle<'a> {
    pub version: &'a str,
    pub reflexes: &'a [Reflex<'a>],
    pub metadata: NailMetadata,
}
```

Reflexes are stored without embeddings (the ESP32 re-embeds on load to save
flash space).
