# 🦀 quilt-pincher

> **A reflex engine built entirely from Quilt cells.** Pinch in, match a reflex, execute. <50ms, no LLM, zero marginal cost. Federates across cloud, workstation, and ESP32.

```
 ██████╗ ██╗   ██╗██╗     ████████╗      ██████╗ ██╗███╗   ██╗ ██████╗██╗  ██╗
██╔═══██╗██║   ██║██║     ╚══██╔══╝     ██╔═══██╗██║████╗  ██║██╔════╝██║  ██║
██║   ██║██║   ██║██║        ██║        ██║   ██║██║██╔██╗ ██║██║     ███████║
██║▄▄ ██║██║   ██║██║        ██║        ██║   ██║██║██║╚██╗██║██║     ██╔══██║
╚██████╔╝╚██████╔╝██║        ██║        ╚██████╔╝██║██║ ╚████║╚██████╗██║  ██║
 ╚══▀▀═╝  ╚═════╝ ╚═╝        ╚═╝         ╚═════╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝╚═╝  ╚═╝
                                          ╔══════╗
                                          ║ .nail║
                                          ╚══════╝
  reflex engine · vector store · LLM as compiler · three-tier compute
```

[![license](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](./LICENSE)
[![typescript](https://img.shields.io/badge/TypeScript-strict-blue.svg)](./tsconfig.json)
[![node](https://img.shields.io/badge/node-%3E%3D18-green.svg)](./package.json)
[![version](https://img.shields.io/badge/version-0.1.0-orange.svg)](./package.json)
[![platform](https://img.shields.io/badge/platform-cloud%20%7C%20workstation%20%7C%20esp32-blue)](./src/platforms)

---

## ✦ What is `quilt-pincher`?

A from-the-ground-up rewrite of [pincher](https://github.com/SuperInstance/pincher) where every layer of the reflex engine is a **Quilt cell**. The pinch is a `formula` cell, the match is a `program` cell, the vector store is a `vector_store` cell, the veto is a `listener` cell, the LLM compiler is an `ai` cell. The whole engine is a Quilt sheet.

Because the engine is composed of cells, it gets all the Quilt superpowers for free:
- **Federation** — the reflex database on your laptop can mirror the one on the cloud
- **Subscription** — clients subscribe to a specific reflex; they get notified when the database updates
- **Tensors** — reflexes have weight, gravity, distance; high-traffic reflexes are near the agent, cold reflexes are far
- **Audit** — the elves (quilt-elf) can audit which reflexes are stale, broken, or need recompilation
- **Persistence** — the reflex database is a content-addressed artifact in `FederatedArtifactStore`

## ✦ Three tiers, same engine

| Tier | Platform | Latency | LLM? | Storage |
|---|---|---|---|---|
| **Cloud** | Browser, Node, Worker | <50ms | Yes (for compile) | R2 / SQLite / Memory |
| **Workstation** | Node + native deps | <50ms | Yes (optional) | SQLite + sqlite-vec |
| **ESP32** | no_std Rust | <200ms | No (offline) | In-memory (limited) |

The same Quilt sheet runs on all three. The cells that need LLM compilation just no-op when no API key is configured.

## ✦ Architecture (as Quilt cells)

```
┌─────────────────────────────────────────────────────────────┐
│                       quilt-pincher                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  pinch (formula cell)                                 │  │
│  │  trigger + context → embedding                        │  │
│  └─────────────────┬──────────────────────────────────────┘  │
│                    ▼                                          │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  match (program cell)                                  │  │
│  │  vector_store.query(embedding) → top-K reflexes      │  │
│  └─────────────────┬──────────────────────────────────────┘  │
│                    ▼                                          │
│  ┌──────────────────┐  ┌────────────────┐  ┌──────────────┐ │
│  │ score ≥ 0.80     │  │ score 0.55-0.80 │  │ score < 0.55 │ │
│  │ execute directly │  │ confirm + run  │  │ compile new  │ │
│  │ (program cell)   │  │ (listener cell)│  │ (ai cell)    │ │
│  └──────────────────┘  └────────────────┘  └──────┬───────┘ │
│                                                   │         │
│                    ┌──────────────────────────────▼────┐    │
│                    │  veto (listener cell)               │    │
│                    │  sandbox + network + perms check    │    │
│                    └──────────────────┬────────────────┘    │
│                                       │                      │
│                    ┌──────────────────▼────────────────┐    │
│                    │  reflex store (vector_store cell)│    │
│                    │  + FederatedArtifactStore mirror  │    │
│                    └───────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## ✦ Install

```bash
npm install @quilt/pincher
```

## ✦ Quick start

```ts
import { QuiltEngine, parseSheet } from '@quilt/core';
import { PincherSheet } from '@quilt/pincher';

const sheet = PincherSheet({
  embedder: { model: '@cf/baai/bge-small-en-v1.5' },
  vectorStore: { backend: 'memory' },
  veto: { sandbox: 'wasm', network: 'local' },
  compiler: { provider: 'zai', model: 'glm-4.5' },  // optional
});

const engine = new QuiltEngine('my-agent');
engine.loadSheet(sheet);

const result = await engine.run('pinch', {
  trigger: 'list running containers',
  context: { host: 'prod-01' },
});
// → instant match from reflex DB, or LLM compile + store
```

## ✦ The .nail bundle

Every pincher engine is serializable as a `.nail` — a portable, content-addressed bundle containing:
- The reflex database (embeddings + actions)
- The veto rules
- The compile history
- The provenance of each reflex

You can ship a `.nail` to an ESP32 and the reflexes are immediately available offline.

## ✦ The Quilt ecosystem

`quilt-pincher` is one of 20 Quilt repos. It uses:

- `@quilt/core` — the cell runtime
- `@quilt/sdk` — `FederatedArtifactStore` for the reflex database
- `@quilt/ai` — the LLM compiler
- `@quilt/rag` — the vector store (memory / Vectorize / Pinecone / pgvector)
- `@quilt/elf` — the elves audit which reflexes are stale

`quilt-pincher` synergizes with the rest of the SuperInstance ecosystem at the protocol level:
- `pincher` (the cocapn fleet) — same architecture, Rust-native
- `claw` — Claw engine for cellular logic, can be a reflex target
- `cudaclaw` — GPU-resident cell agents
- `cellular-automata-agent` — pattern-matching reflexes

## ✦ License

Apache 2.0. See [LICENSE](./LICENSE).
